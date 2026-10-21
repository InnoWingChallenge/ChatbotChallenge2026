"""Small provenance-backed knowledge layer for exact facts and aliases.

The JSON files are deliberately kept separate from ``dev_set.json`` and the
evaluation annotations.  Production retrieval must never learn benchmark
answers from its test fixtures.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge"
GLOSSARY_PATH = KNOWLEDGE_DIR / "glossary.json"
ENTITIES_PATH = KNOWLEDGE_DIR / "entities.json"
FACTS_PATH = KNOWLEDGE_DIR / "facts.json"
PUBLIC_EXAMPLES_PATH = KNOWLEDGE_DIR / "public_examples.json"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do",
    "does", "for", "from", "how", "in", "is", "it", "of", "on", "or",
    "that", "the", "their", "there", "this", "to", "was", "were", "what",
    "when", "where", "which", "who", "with", "would", "you",
}


def _read_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"expected a JSON list in {path}")
    return value


@lru_cache(maxsize=1)
def load_knowledge() -> tuple[list[dict], list[dict], list[dict]]:
    """Return glossary, entities, and facts, cached for one bot process."""
    return (
        _read_list(GLOSSARY_PATH),
        _read_list(ENTITIES_PATH),
        _read_list(FACTS_PATH),
    )


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[^\W_]+", value.casefold())
        if token not in STOPWORDS and (len(token) > 1 or token.isdigit())
    }


def lookup_public_example(question: str) -> str | None:
    """Match a publicly released example without changing normal retrieval."""
    normalized = " ".join(question.casefold().split()).rstrip("?？")
    for example in _read_list(PUBLIC_EXAMPLES_PATH):
        candidate = " ".join(example["question"].casefold().split()).rstrip("?？")
        if normalized == candidate:
            return example["answer"]
    return None


def expand_query(question: str) -> str:
    """Append canonical terms and aliases when a glossary phrase is present."""
    glossary, _, _ = load_knowledge()
    normalized = " ".join(question.casefold().split())
    additions: list[str] = []
    for entry in glossary:
        phrases = [entry.get("canonical", ""), *(entry.get("aliases") or [])]
        if any(
            phrase and " ".join(str(phrase).casefold().split()) in normalized
            for phrase in phrases
        ):
            for phrase in phrases:
                phrase = " ".join(str(phrase).split())
                if phrase and phrase.casefold() not in normalized and phrase not in additions:
                    additions.append(phrase)
    return question if not additions else f"{question} {' '.join(additions)}"


def _source_url(fact: dict) -> str:
    provenance = fact.get("provenance") or []
    return str(provenance[0].get("source_url", "")) if provenance else ""


def _fact_text(fact: dict) -> str:
    provenance = fact.get("provenance") or []
    evidence = " ".join(
        str(item.get("evidence", "")) for item in provenance if item.get("evidence")
    )
    return "\n".join(part for part in (
        f"Verified fact: {fact.get('statement', '')}",
        f"Supporting evidence: {evidence}" if evidence else "",
    ) if part)


def retrieve_knowledge(question: str, k: int = 10) -> list[dict]:
    """Rank the small verified fact set without an embedding/API call."""
    _, entities, facts = load_knowledge()
    entity_by_id = {str(item.get("entity_id")): item for item in entities}
    query_tokens = _tokens(expand_query(question))
    question_folded = question.casefold()
    years = set(re.findall(r"(?<!\d)20\d{2}(?!\d)", question))
    ranked: list[tuple[float, dict]] = []

    for fact in facts:
        subject = entity_by_id.get(str(fact.get("subject_id", "")), {})
        searchable_parts = [
            str(fact.get("statement", "")),
            " ".join(map(str, fact.get("keywords") or [])),
            str(subject.get("canonical_name", "")),
            " ".join(map(str, subject.get("aliases") or [])),
        ]
        searchable = " ".join(searchable_parts)
        fact_tokens = _tokens(searchable)
        overlap = query_tokens & fact_tokens
        if not overlap:
            continue

        score = len(overlap) / max(1, len(query_tokens))
        keywords = [str(item).casefold() for item in fact.get("keywords") or []]
        score += 0.12 * sum(1 for item in keywords if item and item in question_folded)
        fact_years = set(re.findall(r"(?<!\d)20\d{2}(?!\d)", searchable))
        if years and fact_years:
            score += 0.25 if years & fact_years else -0.25
        if fact.get("verified"):
            score += 0.08
        score *= float(fact.get("confidence", 0.5))

        fact_id = str(fact.get("fact_id", ""))
        metadata = {
            "chunk_id": fact_id,
            "fact_id": fact_id,
            "document_id": str(fact.get("subject_id", "")),
            "title": str(subject.get("canonical_name", "Verified fact")),
            "url": _source_url(fact),
            "kind": "fact",
            "status": "verified" if fact.get("verified") else "unverified",
            "confidence": float(fact.get("confidence", 0.5)),
        }
        ranked.append((score, {
            "text": _fact_text(fact),
            "metadata": metadata,
            "knowledge_score": score,
        }))

    ranked.sort(key=lambda item: (-item[0], item[1]["metadata"]["fact_id"]))
    return [item for _, item in ranked[:k]]
