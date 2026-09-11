"""Vector store wrapper. GIVEN. You should not need to edit this file.

A thin layer over chromadb, kept deliberately small so you can see
through it. If you need something it does not do, edit it or bypass it.
"""
import os
import shutil
import tempfile
from pathlib import Path

import chromadb

from bot.llm import embed

DEFAULT_PATH = "data/chroma"
DEFAULT_NAME = "chatbot"


def _writable_copy(path: str) -> str:
    """Copy a Chroma index to a writable temp dir and return the new path.

    The grading machine extracts your submission read-only. Chroma writes a
    small journal next to its sqlite file just to open it -- even to read --
    so opening data/chroma in place there fails with "attempt to write a
    readonly database". Copying it somewhere writable first sidesteps that.
    Locally the index is already writable, so get_store only falls back to
    this when the in-place open actually fails.
    """
    dest = Path(tempfile.mkdtemp(prefix="chroma_")) / "chroma"
    shutil.copytree(path, dest)
    # copytree preserves the read-only bit from the source, so force writable.
    for root, dirs, files in os.walk(dest):
        for name in dirs:
            os.chmod(os.path.join(root, name), 0o777)
        for name in files:
            os.chmod(os.path.join(root, name), 0o666)
    os.chmod(dest, 0o777)
    return str(dest)


def get_store(path: str = DEFAULT_PATH, name: str = DEFAULT_NAME, reset: bool = False):
    """Open (or create) a persistent Chroma collection.

    reset=True deletes the folder first. Do this when the stored index
    was built by a different chromadb version: opening it otherwise
    raises KeyError: '_type', which is chromadb reading a config it does
    not recognise, not a bug in your data.

    On a read-only filesystem (the grading machine) opening the index in
    place fails because chroma cannot write its journal next to it. When
    that happens and the index already exists, get_store retries once from
    a writable temp copy, so the same code path works locally and on the
    grader.
    """
    if reset and Path(path).exists():
        shutil.rmtree(path)

    def _open(p: str):
        client = chromadb.PersistentClient(path=p)
        try:
            return client.get_or_create_collection(name)
        except KeyError as e:
            raise RuntimeError(
                f"chromadb could not read the index at {p} ({e}). It was likely "
                f"built by a different chromadb version. Delete that folder and "
                f"rebuild, or install the pinned version from requirements.txt."
            ) from None

    try:
        return _open(path)
    except RuntimeError:
        raise
    except Exception:
        # Likely a read-only filesystem (the grader): chroma cannot write
        # its journal beside the index. If the index exists, retry from a
        # writable copy; otherwise there is nothing to fall back to.
        if not Path(path).exists():
            raise
        return _open(_writable_copy(path))


def add_to_store(store, texts: list[str], metadatas: list[dict],
                  ids: list[str] = None, batch_size: int = 128) -> None:
    """Embed and insert. Batches both the embedding call and the write."""
    ids = ids or [f"c{i}" for i in range(len(texts))]
    for i in range(0, len(texts), batch_size):
        sl = slice(i, i + batch_size)
        store.add(
            ids=ids[sl], documents=texts[sl],
            embeddings=embed(texts[sl]), metadatas=metadatas[sl],
        )


def query(store, question: str, k: int = 5, where: dict = None) -> list[dict]:
    """Return the k nearest chunks as dicts with text, metadata, distance.

    Chroma returns squared L2 distance by default, so lower is closer.
    """
    r = store.query(query_embeddings=embed([question]), n_results=k, where=where or None)
    return [
        {"text": d, "metadata": m, "distance": dist}
        for d, m, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
    ]
