"""Freeze source-bound inputs for model curation; no model calls or database writes."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from build import describe_priority_images as batch

DEST = batch.DEST.parent / "curation"


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    pages = {}
    references = []
    for relative in ("submission_repo/data/pages.json",
                     "prompt_from_web/innoacademy/pages.json"):
        path = batch.ROOT / relative
        data = batch.read(path)
        references.append({"path": relative, "sha256": checksum(path)})
        for page in data.values() if isinstance(data, dict) else data:
            url = page.get("url", "").rstrip("/")
            if url:
                pages.setdefault(url, []).append({
                    "corpus_path": relative, "url": page["url"],
                    "title": page.get("title", ""), "text": page.get("text", ""),
                })
    baseline = batch.ROOT / "submission_repo/data/image_evidence/records.json"
    references.append({"path": baseline.relative_to(batch.ROOT).as_posix(),
                       "sha256": checksum(baseline)})
    # Frozen comparison corpus, not a declaration that old model descriptions are correct.
    batch.save(DEST / "baseline_records.json", batch.read(baseline))
    ready, missing, invalid = [], [], []
    for task in batch.read(batch.DEST / "tasks.json"):
        path = batch.DEST / "descriptions" / (task["id"] + ".json")
        if not path.exists():
            missing.append(task["id"])
            continue
        try:
            record = batch.read(path)
            batch.validate(record, task)
            raw = (batch.ROOT / task["local_path"]).resolve()
            raw.relative_to(batch.ROOT.resolve())
            if checksum(raw) != task["sha256"]:
                raise ValueError("Raw image hash changed")
            exact_pages = []
            seen = set()
            for context in task["context"]:
                for page in pages.get(context.get("source_page", "").rstrip("/"), []):
                    key = (page["corpus_path"], page["url"])
                    if key not in seen:
                        exact_pages.append(page)
                        seen.add(key)
            ready.append({
                "id": task["id"], "task": task, "description": record,
                "description_path": path.relative_to(batch.ROOT).as_posix(),
                "description_sha256": checksum(path),
                "exact_source_pages": exact_pages,
                "review_state": "pending_model_curation",
            })
        except (ValueError, OSError, TypeError, KeyError) as exc:
            invalid.append({"id": task["id"], "error": str(exc)})
    batch.save(DEST / "inputs.json", ready)
    batch.save(DEST / "inventory.json", {
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "requested_curator": "gpt-6-luna",
        "curator_reasoning_effort": "low",
        "curator_resolution": "user_confirmed",
        "completed_descriptions": len(ready),
        "description_models": dict(Counter(x["description"]["model"] for x in ready)),
        "categories": dict(Counter(x["task"]["category"] for x in ready)),
        "with_exact_page_text": sum(bool(x["exact_source_pages"]) for x in ready),
        "missing_description_ids": missing, "invalid": invalid,
        "comparison_corpora": references,
        "curation_performed": False, "database_modified": False,
    })
    print(json.dumps({"prepared": len(ready), "missing": len(missing),
                      "invalid": len(invalid),
                      "with_exact_page_text": sum(bool(x["exact_source_pages"]) for x in ready),
                      "curation_performed": False, "database_modified": False}))


if __name__ == "__main__":
    main()
