"""Measure evidence Recall@K without treating final answers as evidence.

Examples (run from ``submission_repo``):

    python eval/evaluate_retrieval.py --retriever bm25
    python eval/evaluate_retrieval.py --retriever hybrid --rerank

BM25 and knowledge modes are local. Hybrid and reranking use the configured
embedding/chat endpoints and therefore require the HKU VPN in this project.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.hybrid import bm25_retrieve
from bot.knowledge import expand_query, retrieve_knowledge


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANNOTATIONS = PROJECT_ROOT / "eval" / "dev_annotations.json"
EVALUATED_STATUSES = {"answerable"}


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def is_relevant(candidate: dict, annotation: dict) -> bool:
    """Return whether a retrieved record matches annotated gold evidence."""
    metadata = candidate.get("metadata") or {}
    fact_ids = {str(value) for value in annotation.get("fact_ids") or []}
    chunk_ids = {str(value) for value in annotation.get("relevant_chunk_ids") or []}
    candidate_fact = str(metadata.get("fact_id", ""))
    candidate_chunk = str(metadata.get("chunk_id", ""))
    if candidate_fact and candidate_fact in fact_ids:
        return True
    if candidate_chunk and candidate_chunk in chunk_ids:
        return True

    text = _normalized(str(candidate.get("text", "")))
    patterns = [_normalized(str(value)) for value in annotation.get("evidence_patterns") or []]
    if any(pattern and pattern in text for pattern in patterns):
        return True

    # A source URL alone is only sufficient when the annotation has no more
    # precise fact, chunk, or text marker. This prevents an unrelated chunk on
    # the correct long page from being counted as a hit.
    if not fact_ids and not chunk_ids and not patterns:
        sources = {str(value) for value in annotation.get("relevant_sources") or []}
        return str(metadata.get("url", "")) in sources
    return False


def recall_at(candidates: list[dict], annotation: dict, k: int) -> int:
    return int(any(is_relevant(item, annotation) for item in candidates[:k]))


def _retrieve(question: str, retriever: str, k: int) -> list[dict]:
    if retriever == "bm25":
        return bm25_retrieve(expand_query(question), k=k)
    if retriever == "knowledge":
        return retrieve_knowledge(question, k=k)
    if retriever == "hybrid":
        from bot.answer import retrieve
        return retrieve(question, k=k)
    raise ValueError(f"unknown retriever: {retriever}")


def evaluate(annotations: list[dict], retriever: str, ks: list[int],
             use_reranker: bool = False) -> dict:
    largest = max(ks)
    rows = []
    totals = {k: 0 for k in ks}
    evaluated = 0

    for annotation in annotations:
        status = str(annotation.get("status", ""))
        row = {
            "id": annotation.get("id"),
            "status": status,
            "question": annotation.get("question"),
        }
        if status not in EVALUATED_STATUSES:
            row["recall"] = None
            row["note"] = "excluded from recall denominator until evidence is available"
            rows.append(row)
            continue

        candidates = _retrieve(str(annotation["question"]), retriever, largest)
        if use_reranker:
            from bot.rerank import rerank_candidates
            candidates = rerank_candidates(
                str(annotation["question"]), candidates, k=largest
            )
        result = {str(k): recall_at(candidates, annotation, k) for k in ks}
        row["recall"] = result
        row["retrieved"] = len(candidates)
        rows.append(row)
        evaluated += 1
        for k in ks:
            totals[k] += result[str(k)]

    summary = {
        f"recall@{k}": (totals[k] / evaluated if evaluated else None)
        for k in ks
    }
    summary["evaluated_questions"] = evaluated
    summary["source_gap_or_partial"] = len(annotations) - evaluated
    return {"retriever": retriever, "reranked": use_reranker,
            "summary": summary, "questions": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--retriever", choices=("bm25", "knowledge", "hybrid"),
                        default="hybrid")
    parser.add_argument("--k", type=int, nargs="+", default=[1, 5, 10])
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--output", type=Path,
                        help="optional path for the complete JSON report")
    args = parser.parse_args()
    annotations = json.loads(args.annotations.read_text(encoding="utf-8"))
    report = evaluate(annotations, args.retriever, sorted(set(args.k)), args.rerank)

    for row in report["questions"]:
        if row.get("recall") is None:
            print(f"{row['id']}: {row['status']} (not scored)")
        else:
            scores = " ".join(f"R@{k}={v}" for k, v in row["recall"].items())
            print(f"{row['id']}: {scores}")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
