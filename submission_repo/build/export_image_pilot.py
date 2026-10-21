"""Export model-authored pilot drafts, keeping them outside production ingestion."""
from datetime import datetime, timezone
import json

from build.prepare_image_batch import ROOT, OUT, MANIFEST, read, save, digest, safe_path


def validate_description(record, expected_model):
    if record.get("model") != expected_model or record.get("reasoning_effort") != "low":
        raise ValueError("description model provenance mismatch")
    if record.get("viewed") is not True:
        raise ValueError("image not marked inspected")
    if not isinstance(record.get("paragraphs"), list) or len(record["paragraphs"]) < 3:
        raise ValueError("insufficient description paragraphs")
    if not all(isinstance(p, str) and p.strip() for p in record["paragraphs"]):
        raise ValueError("empty description paragraph")
    for field in ("title", "type", "location"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError("missing " + field)
    if not isinstance(record.get("uncertainties"), list):
        raise ValueError("missing uncertainty list")


def main():
    manifest = read(MANIFEST)
    date = datetime.now(timezone.utc).isoformat()
    planned = []
    for label, model in (("sol", "gpt-6-sol"), ("luna", "gpt-6-luna")):
        batch = read(OUT / (label + "_batch.json"))
        descriptions = read(OUT / (label + "_descriptions.json"))
        if set(descriptions) != {i["id"] for i in batch}:
            raise ValueError("batch/description ID mismatch: " + label)
        for item in batch:
            record = descriptions[item["id"]]
            validate_description(record, model)
            if digest(safe_path(item["local_path"])) != item["sha256"]:
                raise ValueError("raw image changed: " + item["id"])
            if item.get("content_changed"):
                raise ValueError("historically changed image must be separately reviewed")
            planned.append((item, record))
    registry = {}
    for item, record in planned:
        target = ROOT / "prompt_from_web/innoacademy/pilot_descriptions" / item["id"] / "prompt.md"
        lines = ["# " + record["title"], "Status: model-described pilot draft; not ingested.",
                 "Model: " + record["model"] + "; reasoning effort: low.",
                 "Description exported at: " + date + "; capture date: unknown.",
                 "Image ID: " + item["id"], "Image source: " + item["url"],
                 "Raw image: " + item["local_path"], "SHA-256: " + item["sha256"],
                 "## Visible image description", *record["paragraphs"],
                 "## Uncertainty and coverage limitations", *(record["uncertainties"] or ["No additional limitations recorded by the describing model; this is not a guarantee of complete OCR."]),
                 "## Webpage context (not visual evidence)"]
        occurrences = []
        for source in manifest.values():
            if source.get("sha256") == item["sha256"] or source["id"] == item["id"]:
                for occurrence in source.get("occurrences", []):
                    if occurrence not in occurrences:
                        occurrences.append(occurrence)
        for occurrence in occurrences:
            lines.append("Source page: " + occurrence.get("source_page", ""))
            for key, label in (("page_title", "Page title"), ("alt", "Alt text"), ("caption", "Caption"), ("nearby_text", "Surrounding text")):
                if occurrence.get(key):
                    lines.append(label + ": " + occurrence[key])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n\n".join(lines) + "\n", encoding="utf-8")
        registry[item["id"]] = {"status": "model_described_pending_full_review", "model": record["model"],
            "reasoning_effort": "low", "description_path": target.relative_to(ROOT).as_posix(),
            "sha256": item["sha256"], "local_path": item["local_path"], "url": item["url"],
            "retrieved_at": item["retrieved_at"], "exported_at": date, "capture_date": "unknown",
            "type": record["type"], "location": record["location"], "uncertainties": record["uncertainties"]}
    save(OUT / "pilot_reviews.json", registry)
    print(json.dumps({"exported": len(registry), "production_manual_reviews_modified": False, "indexed": False}))


if __name__ == "__main__":
    main()
