"""Validate the curated, provenance-backed knowledge JSON files.

This command never imports ``dev_set.json`` or files under ``eval/``.  Facts
must be supported by source evidence, not copied from benchmark answers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.knowledge import ENTITIES_PATH, FACTS_PATH, GLOSSARY_PATH


FORBIDDEN_SOURCE_MARKERS = (
    "/aichallenge/",
    "/ai-chatbot-challenge-inno-trivia-duplicate-",
)


def _read_list(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a JSON list")
    return value


def _unique_ids(records: list[dict], field: str, label: str) -> set[str]:
    values = [str(record.get(field, "")).strip() for record in records]
    missing = [number for number, value in enumerate(values) if not value]
    if missing:
        raise ValueError(f"{label} records missing {field}: {missing}")
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise ValueError(f"duplicate {label} IDs: {duplicates}")
    return set(values)


def _validate_provenance(record: dict, label: str) -> None:
    provenance = record.get("provenance") or []
    if not provenance:
        raise ValueError(f"{label} has no provenance")
    for source in provenance:
        url = str(source.get("source_url", ""))
        evidence = str(source.get("evidence", "")).strip()
        if not url or not evidence:
            raise ValueError(f"{label} provenance needs source_url and evidence")
        if any(marker in url.casefold() for marker in FORBIDDEN_SOURCE_MARKERS):
            raise ValueError(f"{label} uses forbidden benchmark source: {url}")


def validate_knowledge() -> dict[str, int]:
    glossary = _read_list(GLOSSARY_PATH)
    entities = _read_list(ENTITIES_PATH)
    facts = _read_list(FACTS_PATH)
    entity_ids = _unique_ids(entities, "entity_id", "entity")
    _unique_ids(glossary, "term_id", "glossary")
    _unique_ids(facts, "fact_id", "fact")

    for entry in glossary:
        _validate_provenance(entry, f"glossary {entry['term_id']}")
        if not str(entry.get("canonical", "")).strip():
            raise ValueError(f"glossary {entry['term_id']} has no canonical term")

    for fact in facts:
        label = f"fact {fact['fact_id']}"
        _validate_provenance(fact, label)
        if fact.get("subject_id") not in entity_ids:
            raise ValueError(f"{label} has unknown subject_id {fact.get('subject_id')}")
        references = []
        if fact.get("object_id"):
            references.append(fact["object_id"])
        references.extend(fact.get("object_ids") or [])
        unknown = [value for value in references if value not in entity_ids]
        if unknown:
            raise ValueError(f"{label} has unknown object IDs: {unknown}")
        if not str(fact.get("statement", "")).strip():
            raise ValueError(f"{label} has no human-readable statement")
        confidence = float(fact.get("confidence", -1))
        if not 0 <= confidence <= 1:
            raise ValueError(f"{label} confidence must be between 0 and 1")

    return {
        "glossary_terms": len(glossary),
        "entities": len(entities),
        "facts": len(facts),
    }


def main() -> None:
    counts = validate_knowledge()
    print(
        "validated knowledge: "
        f"{counts['glossary_terms']} glossary terms, "
        f"{counts['entities']} entities, {counts['facts']} facts"
    )


if __name__ == "__main__":
    main()
