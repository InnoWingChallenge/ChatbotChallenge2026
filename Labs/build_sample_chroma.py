"""Build sample_chroma/ from sample_corpus/.

Run this once and ship the folder it writes. Lab 1 opens it directly, so
teams must not have to build it themselves, or lab 1 becomes lab 2.

    python build_sample_chroma.py

Reads .env from the same folder as this script. Paths are resolved
relative to the script, so it works from any working directory.
"""
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(HERE / ".env")
except ImportError:
    pass

import chromadb
from openai import AzureOpenAI

KEY = os.environ.get("AZURE_OPENAI_KEY", "").strip()
if not KEY:
    sys.exit("Set AZURE_OPENAI_KEY in .env or the environment.")

API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
EMBED_BASE  = os.environ.get("AZURE_EMBED_BASE",
                             "https://api-iw.azure-api.net/sig-embedding")
DEPLOYMENT  = os.environ.get("EMBED_DEPLOYMENT", "text-embedding-3-small")
SIZE, OVERLAP = 800, 100

CORPUS = HERE / "sample_corpus"
OUT    = HERE / "sample_chroma"

# This gateway takes the full path as the endpoint, including the
# deployment, the operation and the api-version.
EMBED_URL = f"{EMBED_BASE}/openai/deployments/{DEPLOYMENT}/embeddings?api-version={API_VERSION}"

client = AzureOpenAI(azure_endpoint=EMBED_URL, api_key=KEY, api_version=API_VERSION)


def embed(texts, batch_size=256):
    texts = [t.replace("\n", " ") for t in texts]
    out = []
    for i in range(0, len(texts), batch_size):
        r = client.embeddings.create(model=DEPLOYMENT, input=texts[i:i + batch_size])
        out.extend(d.embedding for d in r.data)
    return out


def chunk(text, size=SIZE, overlap=OVERLAP):
    text = " ".join(text.split())
    step = size - overlap
    return [text[i:i + size] for i in range(0, len(text), step) if text[i:i + size].strip()]


files = sorted(CORPUS.glob("*.txt"))
if not files:
    sys.exit(f"No .txt files found in {CORPUS}\n"
             f"Expected sample_corpus/ next to this script.")
print(f"reading {len(files)} files from {CORPUS}")

texts, metas, ids = [], [], []
for f in files:
    # the filename prefix is the page type, which Level 4 filtering needs
    page_type = f.stem.split("-")[0]
    pieces = chunk(f.read_text(encoding="utf-8"))
    for i, piece in enumerate(pieces):
        ids.append(f"{f.stem}-{i}")
        texts.append(piece)
        metas.append({"url": f.name, "page_type": page_type,
                      "position": i, "kind": "text"})

if not texts:
    sys.exit("Files were found but produced no chunks. Are they empty?")
print(f"{len(texts)} chunks to embed")

# Start from nothing. An index left over from a different chromadb
# version raises KeyError: '_type' when the client tries to read its
# stored config, so removing the folder is safer than deleting the
# collection through the API.
if OUT.exists():
    shutil.rmtree(OUT)
    print(f"removed the previous {OUT.name}/")

try:
    store = chromadb.PersistentClient(path=str(OUT))
    col = store.create_collection("sample")
except KeyError as e:
    sys.exit(
        f"chromadb could not read its own config ({e}).\n"
        f"Delete {OUT} and any data/chroma folder, then run again.\n"
        f"If it persists, your chromadb version changed: pip install -U chromadb"
    )

for i in range(0, len(texts), 128):
    sl = slice(i, i + 128)
    col.add(ids=ids[sl], documents=texts[sl],
            embeddings=embed(texts[sl]), metadatas=metas[sl])
    print(f"  {min(i + 128, len(texts))}/{len(texts)}")

print(f"\n{col.count()} chunks in {OUT} (collection 'sample')")
if col.count() == 0:
    sys.exit("Nothing was written. Check the errors above.")
