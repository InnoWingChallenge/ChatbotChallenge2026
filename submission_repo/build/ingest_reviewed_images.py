"""Prepare reviewed photo prose, build BM25 offline, then index cached embeddings.

From submission_repo:
  python -m build.ingest_reviewed_images prepare
  python -m build.ingest_reviewed_images bm25
  python -m build.ingest_reviewed_images index  # user: after HKU VPN/check_setup

Never reads test answers. No vision calls, no database reset. Managed records
use a separate namespace; source text and legacy images are preserved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from bot.image_evidence import INDEX_PATH, PIPELINE

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUTPUT = ROOT / "data/image_evidence"


def sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def paragraphs(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def local_sections(text: str):
    """Yield only source-linked body paragraphs, not README/introductions."""
    heading, sources = "", []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if block.startswith("#"):
            heading = block.lstrip("# ")
            sources = []
        elif block.startswith("Sources:"):
            sources = re.findall(r"\[[^\]]+\]\(([^)]+)\)", block)
            if not sources:
                raise ValueError("Sources paragraph has no parseable image links")
        elif block and sources:
            yield heading, sources, re.sub(r"\s+", " ", block)


def make_record(record_path: str, title: str, section: str, body: str,
                source_ids: list[str], kind: str, source_type: str,
                evidence_type: str, url: str, review_date: str, **extra) -> dict:
    if len(body) > 8000:
        raise ValueError(f"Oversized paragraph requires reviewed splitting: {record_path}")
    identifier = "revimg_" + sha(json.dumps([record_path, section, body, sorted(source_ids)],
                                           ensure_ascii=False))[:24]
    # Subtopics form the retrieval diversity unit, not an entire large room record.
    document_id = "imgtopic_" + sha(record_path + "\n" + section)[:20]
    metadata = {"chunk_id": identifier, "document_id": document_id, "kind": kind,
                "title": title, "section": section, "url": url, "record_path": record_path,
                "source_type": source_type, "evidence_type": evidence_type,
                "source_ids_json": json.dumps(sorted(source_ids), ensure_ascii=False),
                "evidence_pipeline": PIPELINE, "review_date": review_date,
                "capture_date": "unknown", "status": "assistant_reviewed",
                "page_type": "facility" if source_type == "physical_photo" else "image_record",
                **extra}
    # These are years mentioned in the evidence, never capture/upload/review years.
    years = sorted(set(int(y) for y in re.findall(r"\b20\d{2}\b", body)))
    metadata["content_years_json"] = json.dumps(years)
    if len(years) == 1:
        metadata["year"] = years[0]
    label = "Webpage context (not visible image evidence)" if evidence_type == "web_context" else "Image-derived evidence"
    text = f"Title: {title}\nSection: {section}\n{label}:\n{body}"
    return {"id": identifier, "text": text, "body": body, "metadata": metadata,
            "content_sha256": sha(text)}


def prepare(repo: Path = REPO) -> tuple[list[dict], dict]:
    records, assets, known_hashes = [], {}, {}
    imported = read(repo / "image_source/import_manifest_20261013.json")
    for item in imported["files"]:
        known_hashes["image_source/" + item["relative_path"]] = item["sha256"]
    for name in ("pictures_hzx_manifest.json", "image_hzq_manifest.json"):
        for item in read(repo / "prompt" / name)["images"]:
            known_hashes[item["source_id"]] = item["sha256"]

    local_files = sorted((repo / "prompt").rglob("prompt.md"))
    for path in local_files:
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ")
        relative = path.relative_to(repo).as_posix()
        for section, links, body in local_sections(text):
            sources = []
            for link in links:
                source = (path.parent / link).resolve()
                source_id = source.relative_to(repo.resolve()).as_posix()
                if source_id not in assets:
                    checksum = sha(source.read_bytes())
                    if checksum != known_hashes.get(source_id):
                        raise ValueError(f"Missing provenance or changed source image: {source_id}")
                    assets[source_id] = {"source_id": source_id, "sha256": checksum,
                        "content_type": "image/heic" if source.suffix.lower() == ".heic" else "image/jpeg",
                        "source_type": "physical_photo", "raw_available_at_prepare": True,
                        "review_date": "2026-10-13", "capture_date": None}
                sources.append(source_id)
            records.append(make_record(relative, title, section, body, sources,
                "image", "physical_photo", "visual_description", sources[0], "2026-10-13",
                location=title, description_sha256=sha(text)))

    web = repo / "prompt_from_web/innoacademy"
    manifest, reviews = read(web / "manifest.json"), read(web / "manual_reviews.json")
    for checksum, review in sorted(reviews.items()):
        if review.get("status") != "completed":
            continue
        item = manifest[review["image_id"]]
        if item.get("sha256") != checksum:
            raise ValueError("Web review no longer matches source manifest")
        path = repo / review["description_path"]
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ")
        marker = "## Visible image description"
        if marker not in text or "## Webpage context (not visual evidence)" not in text:
            raise ValueError(f"Missing visual/context boundary: {path}")
        visible, context = text.split(marker, 1)[1].split("## Webpage context (not visual evidence)", 1)
        source_id = "webimg_" + checksum[:24]
        raw = repo / item["local_path"]
        if raw.exists() and sha(raw.read_bytes()) != checksum:
            raise ValueError(f"Web image bytes changed: {raw}")
        variants = [v for v in manifest.values() if v.get("sha256") == checksum]
        occurrences = [o for v in variants for o in v.get("occurrences", [])]
        assets[source_id] = {"source_id": source_id, "sha256": checksum, "url": item["url"],
            "raw_path": item["local_path"], "raw_available_at_prepare": raw.exists(),
            "content_type": item["content_type"], "source_type": "web_image",
            "retrieved_at": item.get("retrieved_at", "unknown"), "capture_date": None,
            "review_date": review["reviewed_at"][:10], "review_method": review["review_method"],
            "description_path": review["description_path"], "description_sha256": sha(text),
            "source_pages": sorted({o["source_page"] for o in occurrences if o.get("source_page")})}
        for body in paragraphs(visible):
            records.append(make_record(review["description_path"], title, "Visible image description",
                body, [source_id], "image", "web_image", "visual_description", item["url"],
                review["reviewed_at"][:10], image_type=review.get("type", "unknown"),
                location=review.get("location", "unknown"), description_sha256=sha(text)))
        # Generic branding repeated across hundreds of pages is not event evidence.
        # Preserve all occurrences in the registry, not in vector/BM25 content.
        if review.get("type") == "branding":
            continue
        seen = set()
        for occurrence in occurrences:
            page = occurrence.get("source_page", "")
            for key in ("caption", "alt", "nearby_text"):
                body = re.sub(r"\s+", " ", occurrence.get(key, "")).strip()
                if len(body) < 20 or body.casefold() == title.casefold() or body.casefold() in seen:
                    continue
                seen.add(body.casefold())
                # Context remains explicitly text, never falsely labelled visible OCR.
                records.append(make_record(review["description_path"], title, "Associated webpage wording",
                    body, [source_id], "text", "web_image", "web_context", page,
                    review["reviewed_at"][:10], context_field=key, image_url=item["url"],
                    retrieved_at=occurrence.get("retrieved_at", "unknown")))
    from build.describe_priority_images import evidence as priority_evidence
    additional, additional_assets = priority_evidence(repo)
    records.extend(additional)
    assets.update(additional_assets)
    unique = {}
    for record in records:
        unique.setdefault(record["id"], record)
    result = list(unique.values())
    for position, record in enumerate(result):
        record["metadata"]["position"] = position
    if not result or not assets:
        raise ValueError("No reviewed records; refusing empty replacement")
    return result, {"schema_version": 1, "pipeline": PIPELINE, "assets": assets,
                    "local_documents": len(local_files), "web_reviewed_images": len(reviews),
                    "priority_described_images": len(additional_assets)}


def build_bm25(records: list[dict], path: Path = INDEX_PATH):
    if not records:
        raise ValueError("refusing empty BM25 replacement")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".sqlite.tmp")
    temp.unlink(missing_ok=True)
    connection = sqlite3.connect(temp)
    try:
        connection.execute("CREATE VIRTUAL TABLE evidence USING fts5(chunk_id UNINDEXED, "
            "title, section, text, metadata UNINDEXED, tokenize='porter unicode61 remove_diacritics 2')")
        connection.executemany("INSERT INTO evidence VALUES(?,?,?,?,?)", [
            (r["id"], r["metadata"]["title"], r["metadata"]["section"], r["text"],
             json.dumps(r["metadata"], ensure_ascii=False)) for r in records])
        connection.commit()
    finally:
        connection.close()
    temp.replace(path)


def index_chroma(records, store, vectors):
    """Upsert before stale cleanup. Retry is safe; never delete another owner."""
    if not records or len(records) != len(vectors):
        raise ValueError("records/embeddings missing or misaligned")
    dimensions = {len(v) for v in vectors}
    if len(dimensions) != 1 or 0 in dimensions or any(not math.isfinite(x) for v in vectors for x in v):
        raise ValueError("invalid embedding vectors")
    for start in range(0, len(records), 64):
        batch = records[start:start + 64]
        store.upsert(ids=[r["id"] for r in batch], documents=[r["text"] for r in batch],
                     metadatas=[r["metadata"] for r in batch], embeddings=vectors[start:start + 64])
    desired = {r["id"] for r in records}
    existing = store.get(where={"evidence_pipeline": PIPELINE}, include=["metadatas"])
    stale = [identifier for identifier in existing["ids"] if identifier not in desired]
    for start in range(0, len(stale), 128):
        store.delete(ids=stale[start:start + 128])
    actual = set(store.get(where={"evidence_pipeline": PIPELINE}, include=["metadatas"])["ids"])
    if actual != desired:
        raise RuntimeError("managed Chroma records do not match prepared evidence")
    return len(actual)


def cached_vectors(records, cache: Path, cached_only: bool = False):
    from bot.llm import embed, EMBED_DEPLOYMENT, EMBED_URL
    config = EMBED_DEPLOYMENT + "\n" + EMBED_URL
    keys = [sha(config + "\n" + r["text"]) for r in records]
    vectors, pending = {}, {}
    for key, record in zip(keys, records):
        path = cache / (key + ".json")
        if path.exists():
            entry = read(path)
            if entry["key"] != key:
                raise ValueError("embedding cache key mismatch")
            vectors[key] = entry["embedding"]
        else:
            pending[key] = record["text"]
    if pending and cached_only:
        raise ValueError(f"{len(pending)} uncached embeddings; user must run index after connecting HKU VPN")
    items = list(pending.items())
    for start in range(0, len(items), 64):
        batch = items[start:start + 64]
        embedded = embed([text for _, text in batch], batch_size=64)
        if len(embedded) != len(batch):
            raise RuntimeError("embedding endpoint returned wrong result count")
        for (key, _), vector in zip(batch, embedded):
            write(cache / (key + ".json"), {"key": key, "model": EMBED_DEPLOYMENT, "embedding": vector})
            vectors[key] = vector
    return [vectors[key] for key in keys]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "bm25", "index"))
    parser.add_argument("--cached-only", action="store_true")
    args = parser.parse_args()
    if args.stage == "prepare":
        records, assets = prepare()
        write(OUTPUT / "records.json", records)
        write(OUTPUT / "sources.json", assets)
        print(json.dumps({"chunks": len(records), "source_images": len(assets["assets"]),
                          "local_documents": assets["local_documents"],
                          "web_images": assets["web_reviewed_images"]}))
        return
    records = read(OUTPUT / "records.json")
    if args.stage == "bm25":
        build_bm25(records)
        print(f"Indexed {len(records)} reviewed image/context chunks in {INDEX_PATH}")
        return
    if not (ROOT / "data/chroma/chroma.sqlite3").exists():
        raise ValueError("Build the text collection first; refusing an image-only database")
    # Complete embedding first, so a gateway failure cannot change Chroma.
    vectors = cached_vectors(records, OUTPUT / "embeddings", args.cached_only)
    from bot.store import get_store
    count = index_chroma(records, get_store(), vectors)
    build_bm25(records)
    write(OUTPUT / "indexed.json", {"indexed_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": PIPELINE, "records_sha256": sha((OUTPUT / "records.json").read_bytes()),
        "chroma_records": count, "bm25_records": len(records)})
    print(f"Indexed {count} Chroma records and {len(records)} BM25 records; existing text preserved")


if __name__ == "__main__":
    main()
