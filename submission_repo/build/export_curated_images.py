"""Validate Luna text-review decisions and export an offline, additive evidence bundle."""
import json
from collections import Counter
from datetime import datetime, timezone

from build import describe_priority_images as batch
from build.ingest_reviewed_images import make_record, sha
from build.prepare_image_curation import DEST, checksum

CURATOR = "gpt-6-luna"
VERSION = "image-text-curation-v1"


def selected_evidence(decision, description):
    selected = []
    for field, original in (("facts", "visual_facts"), ("spatial", "spatial_relations"),
                            ("ocr", "visible_text")):
        indices = decision.get(field)
        if not isinstance(indices, list) or len(indices) != len(set(indices)):
            raise ValueError("Missing or repeated indices: " + field)
        values = description[original]
        for index in indices:
            if type(index) is not int or index < 0 or index >= len(values):
                raise ValueError("Invalid evidence index")
            selected.append({"field": original, "index": index, "text": values[index]})
    return selected


def main():
    run = batch.read(DEST / "review_run.json")
    if run["model"] != CURATOR or run["reasoning_effort"] != "low":
        raise ValueError("Unexpected reviewer provenance")
    for name, digest in run["inputs"].items():
        if checksum(DEST / name) != digest:
            raise ValueError("Frozen review input changed: " + name)
    inputs = batch.read(DEST / "inputs.json")
    inventory = batch.read(DEST / "inventory.json")
    by_id = {x["id"]: x for x in inputs}
    decisions = []
    for number in range(3):
        packet = batch.read(DEST / f"packet-{number}.json")
        reviewed = batch.read(DEST / f"decisions-{number}.json")
        if reviewed is None or len(reviewed) != len(packet):
            raise ValueError("Incomplete reviewer batch " + str(number))
        if {x["id"] for x in reviewed} != {x["id"] for x in packet}:
            raise ValueError("Reviewer assignment mismatch")
        decisions.extend(reviewed)
    if len(decisions) != len(by_id) or len({d["id"] for d in decisions}) != len(decisions):
        raise ValueError("Decision coverage mismatch")
    for reference in inventory["comparison_corpora"]:
        if checksum(batch.ROOT / reference["path"]) != reference["sha256"]:
            raise ValueError("Comparison corpus changed; prepare a new review snapshot")
    baseline = batch.read(DEST / "baseline_records.json")
    if baseline != batch.read(batch.ROOT / "submission_repo/data/image_evidence/records.json"):
        raise ValueError("Frozen baseline differs from current evidence")
    baseline_sources_path = batch.ROOT / "submission_repo/data/image_evidence/sources.json"
    baseline_sources = batch.read(baseline_sources_path)
    if not baseline_sources or not isinstance(baseline_sources.get("assets"), dict):
        raise ValueError("Missing existing source registry")
    baseline_ids = {x["id"] for x in baseline}
    now = datetime.now(timezone.utc).isoformat()
    records, sources, audit, pending = [], {}, [], []
    exact_bodies = {}
    for decision in decisions:
        item = by_id[decision["id"]]
        task, desc = item["task"], item["description"]
        if checksum(batch.ROOT / item["description_path"]) != item["description_sha256"]:
            raise ValueError("Description changed: " + item["id"])
        if checksum(batch.ROOT / task["local_path"]) != task["sha256"]:
            raise ValueError("Image changed: " + item["id"])
        if decision["disposition"] not in ("keep", "hold", "exclude", "duplicate"):
            raise ValueError("Unknown disposition")
        if not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
            raise ValueError("Decision lacks explanation")
        for key in ("conflicts", "duplicate_of"):
            if not isinstance(decision.get(key), list) or not all(isinstance(v, str) for v in decision[key]):
                raise ValueError("Invalid decision " + key)
        if not set(decision["duplicate_of"]) <= baseline_ids:
            raise ValueError("Unknown baseline reference")
        if decision["disposition"] == "duplicate" and not decision["duplicate_of"]:
            raise ValueError("Duplicate decision lacks target")
        evidence = selected_evidence(decision, desc)
        if decision["disposition"] == "keep" and (not evidence or decision["conflicts"]):
            raise ValueError("Kept record empty or unresolved conflict")
        if decision["disposition"] != "keep" and evidence:
            raise ValueError("Non-kept record has selected evidence")
        entry = dict(decision, selected_evidence=evidence, curator_model=CURATOR,
                     curator_reasoning_effort="low", curation_version=VERSION,
                     description_model=desc["model"],
                     description_path=item["description_path"],
                     description_sha256=item["description_sha256"],
                     image_sha256=task["sha256"], visual_reverified=False)
        audit.append(entry)
        if decision["disposition"] == "hold" or decision["conflicts"]:
            pending.append(entry)
        if decision["disposition"] != "keep":
            continue
        body = " ".join(e["text"] for e in evidence if e["field"] != "visible_text")
        ocr = [e["text"] for e in evidence if e["field"] == "visible_text"]
        if ocr:
            body += " Reported visible text: " + "; ".join(ocr) + "."
        body = body.strip()
        if body in exact_bodies:
            entry["export_disposition"] = "exact_duplicate"
            entry["same_text_as"] = exact_bodies[body]
            continue
        exact_bodies[body] = item["id"]
        source = "webimg_" + task["sha256"][:24]
        sources[source] = {
            "source_id": source, "source_type": "web_image",
            "raw_available_at_prepare": True, "capture_date": None,
            "review_date": now[:10],
            "image_id": item["id"], "sha256": task["sha256"],
            "raw_path": task["local_path"], "url": task["url"],
            "description_path": item["description_path"],
            "description_sha256": item["description_sha256"],
            "description_model": desc["model"], "description_prompt_version": desc["prompt_version"],
            "context": task["context"], "uncertainties": desc["uncertainties"],
            "curator_model": CURATOR, "curator_reasoning_effort": "low",
            "selected_evidence": evidence, "visual_reverified": False,
        }
        # Do not reuse an unchecked model-generated title as an asserted device identity.
        title = "Equipment and facilities" if task["category"] == "equipment_facility" else "Space and layout"
        record = make_record(item["description_path"], title, "Selected visual observations",
            "Model-described observations of this image; location and current facility inventory "
            "are not established by these observations. " + body,
            [source], "image", "web_image", "visual_description", task["url"], now[:10],
            status="text_curated_not_visual_verified", location="unknown",
            description_model=desc["model"], description_prompt_version=desc["prompt_version"],
            curator_model=CURATOR, curator_reasoning_effort="low", curation_version=VERSION,
            image_sha256=task["sha256"], description_sha256=item["description_sha256"],
            visual_reverified=False,
            source_pages_json=json.dumps(sorted({c.get("source_page", "") for c in task["context"]})),
            uncertainties_json=json.dumps(desc["uncertainties"], ensure_ascii=False))
        records.append(record)
        entry["export_disposition"] = "exported"
        entry["record_id"] = record["id"]
    if not records or len({r["id"] for r in records}) != len(records):
        raise ValueError("Empty or duplicate output")
    # This bundle is additive; never feed it alone to the old replacement-style index function.
    merged = {r["id"]: r for r in baseline}
    merged.update({r["id"]: r for r in records})
    for pos, record in enumerate(merged.values()):
        record["metadata"]["position"] = pos
    combined_sources = dict(baseline_sources)
    combined_sources["assets"] = dict(baseline_sources["assets"])
    combined_sources["assets"].update(sources)
    for record in records:
        if not set(json.loads(record["metadata"]["source_ids_json"])) <= set(combined_sources["assets"]):
            raise ValueError("Dangling source reference")
    out = DEST / "release"
    for name, value in (("records.json", records), ("sources.json", {"assets": sources}),
                        ("decisions.json", audit), ("needs_review.json", pending),
                        ("merged_records.json", list(merged.values())),
                        ("merged_sources.json", combined_sources)):
        batch.save(out / name, value)
    report = {"created_at": now, "curator_model": CURATOR, "reasoning_effort": "low",
              "curation_version": VERSION, "input_descriptions": len(inputs),
              "missing_descriptions": len(inventory["missing_description_ids"]),
              "decisions": dict(Counter(d["disposition"] for d in decisions)),
              "exported_records": len(records), "baseline_records": len(baseline),
              "merged_records": len(merged), "needs_review": len(pending),
              "description_models": dict(Counter(x["description"]["model"] for x in inputs)),
              "visual_reverified": False, "database_modified": False,
              "input_hashes": run["inputs"],
              "baseline_sources_sha256": checksum(baseline_sources_path),
              "review_decision_hashes": {
                  f"decisions-{i}.json": checksum(DEST / f"decisions-{i}.json") for i in range(3)},
              "validation": "coverage, indices, source hashes, baseline references, output IDs",
              "files": {p.name: checksum(p) for p in sorted(out.glob("*.json")) if p.name != "report.json"}}
    batch.save(out / "report.json", report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
