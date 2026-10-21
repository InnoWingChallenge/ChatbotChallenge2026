"""Describe useful crawl images once, then add their text to Chroma.

Run after ``build/index.py``. Descriptions are checkpointed locally so an
interrupted or rate-limited run can safely be resumed without paying for
successful images again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.llm import describe_image
from bot.store import add_to_store, get_store


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
IMAGES_PATH = DATA_DIR / "processed" / "image_queue.json"
DOCUMENTS_PATH = DATA_DIR / "processed" / "documents.json"
CACHE_PATH = DATA_DIR / "descriptions.json"
FAILURES_PATH = DATA_DIR / "description_failures.json"
CHECKPOINT_EVERY = 10
MAX_IMAGE_BYTES = 20 * 1024 * 1024
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

DESCRIPTION_PROMPT = """Describe this image as retrieval evidence for questions
about HKU's Tam Wing Fan Innovation Wing and Innovation Academy.

Be literal and exhaustive. Transcribe every legible word, heading, label, date,
number, team name, material, room name, and sign exactly. Describe equipment,
people, objects, colours, and their spatial relationships. Count repeated
objects when possible and state the count. For posters, preserve the event
title, date, time, venue, deadlines, and award results. For rooms and diagrams,
describe layout, labels, and what is written on walls. Distinguish visible
evidence from uncertain interpretation; never invent unreadable text. Return
plain text only, with concise sentences suitable for semantic search.
"""


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "InnoWingChallengeImageBuilder/1.0"})
    return session


def _load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _suffix_for(src: str, content_type: str) -> str:
    suffix = Path(urlparse(src).path).suffix.lower()
    if suffix in SUPPORTED_SUFFIXES:
        return suffix
    guessed = mimetypes.guess_extension(content_type.partition(";")[0].strip()) or ""
    return ".jpg" if guessed == ".jpe" else guessed.lower()


def _download_image(session: requests.Session, src: str) -> Path:
    response = session.get(src, timeout=(10, 60), stream=True)
    response.raise_for_status()
    suffix = _suffix_for(src, response.headers.get("Content-Type", ""))
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported image format: {suffix or 'unknown'}")

    handle = tempfile.NamedTemporaryFile(prefix="innowing_", suffix=suffix, delete=False)
    path = Path(handle.name)
    total = 0
    try:
        with handle:
            for block in response.iter_content(64 * 1024):
                if not block:
                    continue
                total += len(block)
                if total > MAX_IMAGE_BYTES:
                    raise ValueError(f"image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB")
                handle.write(block)
        if total == 0:
            raise ValueError("empty image response")
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        response.close()


def describe_all(images: list[dict], limit: int | None = None) -> dict[str, str]:
    """Describe uncached images and checkpoint progress every few successes."""
    cache = _load_json(CACHE_PATH, {})
    if not isinstance(cache, dict):
        raise ValueError(f"expected a JSON object in {CACHE_PATH}")
    failures = _load_json(FAILURES_PATH, {})
    if not isinstance(failures, dict):
        failures = {}

    pending = [image for image in images if image.get("src") not in cache]
    if limit is not None:
        pending = pending[:max(0, limit)]
    session = _session()
    successes = 0

    try:
        for number, image in enumerate(pending, 1):
            src = image.get("src", "")
            if not src:
                continue
            local_path: Path | None = None
            try:
                local_path = _download_image(session, src)
                description = describe_image(str(local_path), DESCRIPTION_PROMPT).strip()
                if not description:
                    raise ValueError("vision model returned an empty description")
                cache[src] = description
                failures.pop(src, None)
                successes += 1
                if successes % CHECKPOINT_EVERY == 0:
                    _write_json_atomic(CACHE_PATH, cache)
                    _write_json_atomic(FAILURES_PATH, failures)
                if number % 25 == 0:
                    print(f"described {number}/{len(pending)} pending images")
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                failures[src] = {
                    "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                    "last_attempt_at": datetime.now(timezone.utc).isoformat(),
                }
                if getattr(exc, "status_code", None) in {401, 403}:
                    raise RuntimeError(
                        "vision gateway rejected the request. For 403, connect to "
                        "the HKU VPN; for 401, check AZURE_OPENAI_KEY in .env."
                    ) from exc
                print(f"failed: {src[:90]} ({failures[src]['error']})", file=sys.stderr)
            finally:
                if local_path is not None:
                    local_path.unlink(missing_ok=True)
    finally:
        _write_json_atomic(CACHE_PATH, cache)
        _write_json_atomic(FAILURES_PATH, failures)

    print(f"{len(cache)} descriptions cached; {successes} added in this run")
    return cache


def _image_chunk(image: dict, description: str, document: dict | None) -> str:
    parts = []
    if document:
        parts.extend([
            f"Page title: {document.get('title', '')}",
            f"Page URL: {document.get('url', '')}",
        ])
    parts.extend([
        f"Image URL: {image.get('src', '')}",
        f"Alt text: {image.get('alt', '')}" if image.get("alt") else "",
        f"Caption: {image.get('caption', '')}" if image.get("caption") else "",
        f"Visible content: {description}",
    ])
    return "\n".join(part for part in parts if part)


def index_descriptions(descriptions: dict[str, str], images: list[dict],
                       documents: list[dict]) -> int:
    """Replace image chunks while preserving the text chunks in Chroma."""
    documents_by_id = {document["id"]: document for document in documents}
    texts: list[str] = []
    metas: list[dict] = []
    ids: list[str] = []

    for image in images:
        src = image.get("src", "")
        description = descriptions.get(src, "").strip()
        if not description:
            continue
        document_ids = image.get("document_ids") or [""]
        for document_id in document_ids:
            document = documents_by_id.get(document_id)
            meta = {
                "url": document.get("url", src) if document else src,
                "title": document.get("title", "") if document else "",
                "image": src,
                "kind": "image",
                "evidence_pipeline": "legacy_web_images",
                "document_id": document_id,
            }
            if document and document.get("year") is not None:
                meta["year"] = int(document["year"])
            if document and document.get("page_type"):
                meta["page_type"] = str(document["page_type"])
            texts.append(_image_chunk(image, description, document))
            metas.append(meta)
            digest = hashlib.sha256(f"{src}\n{document_id}".encode("utf-8")).hexdigest()[:24]
            ids.append(f"img_{digest}")

    if not texts:
        print("no cached image descriptions to index; existing image chunks were preserved")
        return 0

    store = get_store(reset=False)
    # This legacy builder owns img_* records, not reviewed local/web evidence.
    existing = store.get(where={"kind": "image"}, include=["metadatas"])
    owned = [identifier for identifier, meta in zip(existing["ids"], existing["metadatas"])
             if identifier.startswith("img_")
             and (meta or {}).get("evidence_pipeline") != "reviewed_images_v1"]
    for start in range(0, len(owned), 128):
        store.delete(ids=owned[start:start + 128])
    add_to_store(store, texts, metas, ids=ids)
    print(f"indexed {len(texts)} image description chunks")
    return len(texts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--describe-only", action="store_true",
                      help="cache descriptions without updating Chroma")
    mode.add_argument("--index-only", action="store_true",
                      help="index descriptions already present in the cache")
    parser.add_argument("--limit", type=int,
                        help="describe at most this many uncached images (for a trial run)")
    args = parser.parse_args()

    if not IMAGES_PATH.exists() or not DOCUMENTS_PATH.exists():
        raise SystemExit("Missing processed data. Run python build/clean.py first.")
    images = _load_json(IMAGES_PATH, [])
    documents = _load_json(DOCUMENTS_PATH, [])
    if not isinstance(images, list) or not isinstance(documents, list):
        raise SystemExit("Processed image and document files must contain JSON lists.")

    if args.index_only and not CACHE_PATH.exists():
        raise SystemExit("Missing data/descriptions.json. Run image description first.")
    descriptions = _load_json(CACHE_PATH, {}) if args.index_only else describe_all(images, args.limit)
    if not isinstance(descriptions, dict):
        raise SystemExit("data/descriptions.json must contain a JSON object.")
    if not args.describe_only:
        index_descriptions(descriptions, images, documents)


if __name__ == "__main__":
    main()
