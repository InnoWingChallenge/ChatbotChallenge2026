"""Hybrid text retrieval: SQLite BM25 plus dense candidates and rule reranking."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from bot.knowledge import expand_query, retrieve_knowledge
from bot.image_evidence import retrieve_images


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FTS_PATH = PROJECT_ROOT / "data" / "text_search.sqlite"
RRF_K = 60

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does",
    "for", "from", "how", "in", "is", "it", "of", "on", "or", "that", "the",
    "their", "there", "this", "to", "was", "were", "what", "when", "where",
    "which", "who", "with",
}


def _terms(question: str) -> list[str]:
    tokens = re.findall(r"[^\W_]+(?:['’][^\W_]+)?", question.casefold())
    output = []
    for token in tokens:
        if token not in STOPWORDS and (len(token) > 1 or token.isdigit()):
            if token not in output:
                output.append(token)
    for start, short_end in re.findall(
        r"(?<!\d)(20\d{2})\s*[-/]\s*(\d{2})(?!\d)", question
    ):
        expanded = str(int(start) // 100 * 100 + int(short_end))
        if short_end in output:
            output.remove(short_end)
        if expanded not in output:
            output.append(expanded)
    return output


def _match_expression(question: str) -> str:
    return " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in _terms(question))


def _metadata_from_row(row: sqlite3.Row) -> dict:
    metadata = {
        "chunk_id": row["chunk_id"],
        "document_id": row["document_id"],
        "position": int(row["position"]),
        "title": row["title"],
        "section": row["section"],
        "url": row["url"],
        "page_type": row["page_type"],
        "status": row["status"],
        "kind": "text",
    }
    if str(row["year"] or "").isdigit():
        metadata["year"] = int(row["year"])
    return metadata


def _where_matches(metadata: dict, where: dict | None) -> bool:
    if not where:
        return True
    if "$and" in where:
        return all(_where_matches(metadata, item) for item in where["$and"])
    if "$or" in where:
        return any(_where_matches(metadata, item) for item in where["$or"])
    for key, expected in where.items():
        actual = metadata.get(key)
        if isinstance(expected, dict) and "$eq" in expected:
            expected = expected["$eq"]
        if actual != expected:
            return False
    return True


def bm25_retrieve(question: str, k: int = 30, where: dict | None = None,
                  path: Path = DEFAULT_FTS_PATH) -> list[dict]:
    """Return local FTS5 candidates. Missing indexes degrade to dense-only."""
    expression = _match_expression(question)
    if not expression or not path.exists():
        return []
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT chunk_id, document_id, position, title, section, text, url,
                   page_type, year, status,
                   bm25(chunks, 0.0, 0.0, 0.0, 5.0, 3.0, 1.0,
                                0.0, 0.0, 0.0, 0.0) AS lexical_score
            FROM chunks
            WHERE chunks MATCH ?
            ORDER BY lexical_score
            LIMIT ?
            """,
            (expression, max(k * 3, k)),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        connection.close()

    results = []
    for row in rows:
        metadata = _metadata_from_row(row)
        if _where_matches(metadata, where):
            results.append({
                "text": row["text"],
                "metadata": metadata,
                "bm25_score": float(row["lexical_score"]),
            })
            if len(results) >= k:
                break
    return results


def _candidate_key(candidate: dict) -> str:
    metadata = candidate.get("metadata", {})
    if metadata.get("chunk_id"):
        return str(metadata["chunk_id"])
    value = "\n".join([
        str(metadata.get("url", "")), str(metadata.get("position", "")),
        candidate.get("text", ""),
    ])
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _question_years(question: str) -> set[int]:
    years = {int(year) for year in re.findall(r"(?<!\d)(20\d{2})(?!\d)", question)}
    for start, short_end in re.findall(r"(?<!\d)(20\d{2})\s*[-/]\s*(\d{2})(?!\d)", question):
        start_year = int(start)
        end_year = start_year // 100 * 100 + int(short_end)
        years.update({start_year, end_year})
    return years


def _rule_adjustment(question: str, candidate: dict) -> float:
    q = question.casefold()
    metadata = candidate.get("metadata", {})
    title = str(metadata.get("title", "")).casefold()
    text = candidate.get("text", "").casefold()
    page_type = str(metadata.get("page_type", "")).casefold()
    score = 0.0
    # An explicit image filename is an evidence selector, not a generic noun.
    source_ids = json.loads(metadata.get("source_ids_json", "[]"))
    named_images = re.findall(r"[\w/.-]+\.(?:jpg|jpeg|png|heic|webp)\b", q)
    if any(str(source).casefold().endswith(name) for source in source_ids for name in named_images):
        score += 0.12

    query_terms = set(_terms(question))
    title_terms = set(_terms(title))
    score += min(0.018, 0.003 * len(query_terms & title_terms))

    years = _question_years(question)
    candidate_year = metadata.get("year")
    if candidate_year is not None and years:
        score += 0.018 if int(candidate_year) in years else -0.012
    text_years = {int(year) for year in re.findall(r"(?<!\d)(20\d{2})(?!\d)", text)}
    if years and text_years:
        score += 0.014 if years & text_years else -0.018

    if "fund" in q and page_type == "funding":
        score += 0.020
    elif "fund" in q and page_type in {"competition", "event"}:
        score -= 0.018
    if "second round" in q and "second round" in text:
        score += 0.014
    if "interim" not in q and "interim report" in text:
        score -= 0.030
    if any(word in q for word in ("pitch", "winner", "winning", "award")):
        if page_type in {"competition", "project"}:
            score += 0.012
        if any(word in text for word in ("winner", "winning", "award")):
            score += 0.016
    if any(word in q for word in ("deadline", "when", "date")):
        if any(word in text for word in ("deadline", "date", "by ")):
            score += 0.014
        if years and "tba" in text:
            score -= 0.025
    if any(word in q for word in ("printer", "equipment", "facility")):
        if page_type == "facility":
            score += 0.012
    if "workshop" in q and page_type == "event":
        score += 0.010

    if title in {"photo gallery", "gallery"}:
        score -= 0.060
    if metadata.get("status") == "review_short":
        score -= 0.035
    if len(candidate.get("text", "")) < 140:
        score -= 0.020
    return score


def hybrid_rank(question: str, dense: list[dict], lexical: list[dict],
                k: int, knowledge: list[dict] | None = None,
                image_lexical: list[dict] | None = None) -> list[dict]:
    """Fuse ranks, apply transparent rules, and cap repeated documents."""
    candidates: dict[str, dict] = {}
    sources = (
        ("dense", dense, 1.0),
        ("bm25", lexical, 1.15),
        ("image_bm25", image_lexical or [], 1.15),
        ("knowledge", knowledge or [], 1.35),
    )
    for source, values, weight in sources:
        for rank, value in enumerate(values, 1):
            key = _candidate_key(value)
            if key not in candidates:
                candidates[key] = {
                    "text": value.get("text", ""),
                    "metadata": dict(value.get("metadata", {})),
                    "distance": value.get("distance"),
                    "retrieval_sources": [],
                    "hybrid_score": 0.0,
                }
            record = candidates[key]
            record["hybrid_score"] += weight / (RRF_K + rank)
            record["retrieval_sources"].append(source)
            if source == "dense" and value.get("distance") is not None:
                record["distance"] = value["distance"]
            if source == "knowledge":
                # A provenance-backed fact is more precise than an ordinary
                # semantic mention. Its local score still gates this boost, so
                # a fact matching only one generic word cannot dominate.
                knowledge_score = max(0.0, float(value.get("knowledge_score", 0.0)))
                record["hybrid_score"] += min(0.080, 0.040 * knowledge_score)

    for record in candidates.values():
        record["hybrid_score"] += _rule_adjustment(question, record)

    ranked = sorted(
        candidates.values(),
        key=lambda item: (
            -item["hybrid_score"],
            item["distance"] if item.get("distance") is not None else float("inf"),
        ),
    )
    selected: list[dict] = []
    per_document: dict[str, int] = {}
    seen_text: set[str] = set()
    max_per_document = 3 if k > 10 else 2
    for item in ranked:
        document_id = str(item["metadata"].get("document_id", ""))
        fingerprint = re.sub(r"\W+", "", item["text"].casefold())
        if fingerprint in seen_text:
            continue
        if document_id and per_document.get(document_id, 0) >= max_per_document:
            continue
        seen_text.add(fingerprint)
        if document_id:
            per_document[document_id] = per_document.get(document_id, 0) + 1
        selected.append(item)
        if len(selected) >= k:
            break
    return selected


def hybrid_retrieve(question: str, dense: list[dict], k: int = 5,
                    where: dict | None = None,
                    path: Path = DEFAULT_FTS_PATH) -> list[dict]:
    expanded = expand_query(question)
    lexical = bm25_retrieve(expanded, k=max(30, k * 3), where=where, path=path)
    image_lexical = retrieve_images(expanded, k=max(30, k * 3), where=where)
    knowledge = retrieve_knowledge(question, k=max(10, k))
    if where:
        knowledge = [
            item for item in knowledge
            if _where_matches(item.get("metadata", {}), where)
        ]
    return hybrid_rank(question, dense, lexical, k=k, knowledge=knowledge,
                       image_lexical=image_lexical)
