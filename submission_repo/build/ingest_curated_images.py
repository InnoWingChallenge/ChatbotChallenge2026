"""Offline plan or cached, additive embedding/indexing of the curated image release."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil

from build.ingest_reviewed_images import (
    ROOT, REPO, OUTPUT, INDEX_PATH, PIPELINE, read, write, sha, cached_vectors, build_bm25,
)

RELEASE = REPO / "prompt_from_web/innoacademy/preparation/curation/release"


@contextmanager
def lock():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "curated_ingest.lock").open("a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def validate_rows(rows):
    if not rows or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Empty or duplicate records")
    for row in rows:
        if sha(row["text"]) != row["content_sha256"]:
            raise ValueError("Record content hash mismatch")
        if row["metadata"]["evidence_pipeline"] != PIPELINE:
            raise ValueError("Unexpected evidence owner")


def load_release():
    report = read(RELEASE / "report.json")
    for name in ("records.json", "sources.json", "merged_records.json", "merged_sources.json"):
        if sha((RELEASE / name).read_bytes()) != report["files"][name]:
            raise ValueError("Release file changed: " + name)
    added, merged = read(RELEASE / "records.json"), read(RELEASE / "merged_records.json")
    validate_rows(added)
    validate_rows(merged)
    target = {r["id"]: r for r in merged}
    for row in added:
        if target.get(row["id"]) != row:
            raise ValueError("New record differs from merged release")
    current = read(OUTPUT / "records.json")
    validate_rows(current)
    for row in current:
        other = target.get(row["id"])
        if not other or row["text"] != other["text"]:
            raise ValueError("Current evidence changed since release; rebuild merge first")
        a, b = dict(row["metadata"]), dict(other["metadata"])
        a.pop("position", None)
        b.pop("position", None)
        if a != b:
            raise ValueError("Existing record metadata changed since release")
    sources = read(RELEASE / "merged_sources.json")
    current_sources = read(OUTPUT / "sources.json")
    for key, asset in current_sources["assets"].items():
        if sources["assets"].get(key) != asset:
            raise ValueError("Existing source registry changed since release")
    for asset in read(RELEASE / "sources.json")["assets"].values():
        for field, digest in (("raw_path", "sha256"), ("description_path", "description_sha256")):
            path = (REPO / asset[field]).resolve()
            path.relative_to(REPO.resolve())
            if sha(path.read_bytes()) != asset[digest]:
                raise ValueError("Curated source changed: " + asset[field])
    for row in merged:
        if not set(json.loads(row["metadata"]["source_ids_json"])) <= set(sources["assets"]):
            raise ValueError("Missing source registry entry")
    return added, merged, sources


def additive_upsert(added, merged, vectors, store):
    """No deletes or reset: retry safely completes any partial batch."""
    if len(vectors) != len(added) or not vectors:
        raise ValueError("Embedding count mismatch")
    dimensions = {len(v) for v in vectors}
    if len(dimensions) != 1 or 0 in dimensions or any(not math.isfinite(v) for a in vectors for v in a):
        raise ValueError("Invalid embedding vectors")
    peek = store.peek(limit=1)
    old = peek.get("embeddings")
    if old is not None and len(old) and len(old[0]) != len(vectors[0]):
        raise ValueError("Embedding dimension differs from existing collection; use its original model")
    expected = {r["id"] for r in merged}
    new_ids = {r["id"] for r in added}
    existing = store.get(where={"evidence_pipeline": PIPELINE}, include=["metadatas", "documents"])
    old_ids = set(existing["ids"])
    if old_ids - expected or (expected - new_ids) - old_ids:
        raise ValueError("Chroma baseline differs from release; reconcile existing evidence first")
    target = {r["id"]: r for r in merged}
    for ident, document in zip(existing["ids"], existing["documents"]):
        if document != target[ident]["text"]:
            raise ValueError("Existing Chroma content changed: " + ident)
    # Check collisions even when another pipeline owns the same ID.
    collision = store.get(ids=list(new_ids), include=["metadatas"])
    if any(m.get("evidence_pipeline") != PIPELINE for m in collision["metadatas"]):
        raise ValueError("New ID is owned by another pipeline")
    for start in range(0, len(added), 32):
        chunk = added[start:start + 32]
        store.upsert(ids=[r["id"] for r in chunk], documents=[r["text"] for r in chunk],
                     metadatas=[r["metadata"] for r in chunk], embeddings=vectors[start:start + 32])
    actual = store.get(where={"evidence_pipeline": PIPELINE}, include=["metadatas"])
    if set(actual["ids"]) != expected:
        raise RuntimeError("Post-index coverage mismatch; rerun to resume")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["plan", "index"])
    parser.add_argument("--batch-size", type=int, default=16, choices=range(1, 65), metavar="1..64")
    parser.add_argument("--cached-only", action="store_true")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from bot.llm import EMBED_DEPLOYMENT, EMBED_URL
    with lock():
        added, merged, sources = load_release()
        config = EMBED_DEPLOYMENT + "\n" + EMBED_URL
        cache = OUTPUT / "embeddings"
        missing = sum(not (cache / (sha(config + "\n" + r["text"]) + ".json")).exists() for r in added)
        print(json.dumps({"new_chunks": len(added), "merged_image_chunks": len(merged),
                          "embedding_deployment": EMBED_DEPLOYMENT, "uncached": missing,
                          "stage": args.stage}), flush=True)
        if args.stage == "plan":
            return
        if not (ROOT / "data/chroma/chroma.sqlite3").exists():
            raise ValueError("Existing Chroma database required")
        receipt = OUTPUT / "curated_indexed.json"
        if receipt.exists() and read(receipt)["embedding_config_sha256"] != sha(config):
            raise ValueError("Embedding config changed since previous curated index")
        pending = OUTPUT / "curated_pending.json"
        if pending.exists() and read(pending)["embedding_config_sha256"] != sha(config):
            raise ValueError("Embedding config changed during interrupted indexing")
        vectors = []
        for start in range(0, len(added), args.batch_size):
            chunk = added[start:start + args.batch_size]
            print(f"Embedding/cache {start + 1}-{start + len(chunk)}/{len(added)}", flush=True)
            vectors.extend(cached_vectors(chunk, cache, args.cached_only))
        # A failed API batch above cannot touch Chroma or active retrieval files.
        staged_bm25 = OUTPUT / "curated_staged.sqlite"
        build_bm25(merged, staged_bm25)
        from bot.store import get_store
        store = get_store(path=str(ROOT / "data/chroma"))
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = OUTPUT / "curated_backups" / stamp
        backup.mkdir(parents=True)
        for path in (OUTPUT / "records.json", OUTPUT / "sources.json", INDEX_PATH, receipt):
            if path.exists():
                shutil.copy2(path, backup / path.name)
        write(OUTPUT / "curated_pending.json", {"started_at": stamp,
              "release_sha256": sha((RELEASE / "report.json").read_bytes()),
              "embedding_config_sha256": sha(config),
              "backup": str(backup), "state": "upserting"})
        additive_upsert(added, merged, vectors, store)
        write(OUTPUT / "records.json", merged)
        write(OUTPUT / "sources.json", sources)
        staged_bm25.replace(INDEX_PATH)
        write(receipt, {"completed_at": stamp, "new_chunks": len(added),
              "merged_image_chunks": len(merged), "embedding_deployment": EMBED_DEPLOYMENT,
              "embedding_config_sha256": sha(config),
              "release_sha256": sha((RELEASE / "report.json").read_bytes()),
              "records_sha256": sha((OUTPUT / "records.json").read_bytes()),
              "backup": str(backup), "status": "complete"})
        (OUTPUT / "curated_pending.json").unlink(missing_ok=True)
        print("Complete: Chroma and image BM25 updated; existing text preserved.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Interrupted. Rerun the same command; saved embeddings will be reused.")
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        if status:
            raise SystemExit(f"API HTTP {status}. Check VPN, quota and .env; rerun to resume.")
        if isinstance(exc, (ValueError, RuntimeError)):
            raise SystemExit(str(exc))
        raise
