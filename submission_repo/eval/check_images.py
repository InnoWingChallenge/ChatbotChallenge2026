"""Small source-grounded acceptance set for the first reviewed-image ingestion.

lexical: local text + reviewed-image BM25 + facts, no API calls.
hybrid: actual filtered hybrid retrieval, embedding API (no LLM reranking).
answers: invoke the unchanged main.py in an isolated process, human grading.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from build.ingest_reviewed_images import OUTPUT, ROOT, read, sha, write

CASES = ROOT / "eval/image_smoke.json"


def normalize(value):
    return " ".join(value.casefold().split())


def check_evidence(chunks, case):
    hits = []
    for group in case["evidence_groups"]:
        hits.append(any(c["metadata"].get("record_path") == anchor["record_path"]
                        and normalize(anchor["quote"]) in normalize(c["text"])
                        for anchor in group for c in chunks))
    return {"hit": any(hits), "complete": all(hits),
            "group_recall": sum(hits) / len(hits), "groups": hits}


def validate(cases, records):
    seen = set()
    for case in cases:
        if case["id"] in seen or not case.get("expected_answer") or not case.get("evidence_groups"):
            raise ValueError("invalid acceptance question")
        seen.add(case["id"])
        if not check_evidence(records, case)["complete"]:
            raise ValueError(f"Gold evidence missing from prepared records: {case['id']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("lexical", "hybrid", "answers"), default="lexical")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--dataset", type=Path, default=CASES,
                        help="Question JSON; relative paths are resolved from the working directory")
    args = parser.parse_args()
    cases, records = read(args.dataset), read(OUTPUT / "records.json")
    if not cases:
        raise ValueError("question dataset is empty")
    validate(cases, records)
    if args.ids:
        if set(args.ids) - {c["id"] for c in cases}:
            raise ValueError("unknown question IDs")
        cases = [c for c in cases if c["id"] in args.ids]
    if args.output.exists():
        raise ValueError("choose a new output directory; reports are not overwritten")
    args.output.mkdir(parents=True)
    report = {"mode": args.mode, "dataset": str(args.dataset),
              "dataset_sha256": sha(args.dataset.read_bytes()),
              "records_sha256": sha((OUTPUT / "records.json").read_bytes()), "questions": []}
    for index, case in enumerate(cases, 1):
        print(f"[{index}/{len(cases)}] {case['id']}", file=sys.stderr, flush=True)
        row = {**case, "answer": None, "error": None}
        t0 = time.perf_counter()
        try:
            if args.mode == "answers":
                proc = subprocess.run([sys.executable, "main.py", case["question"]], cwd=ROOT,
                    capture_output=True, encoding="utf-8", errors="replace", timeout=30,
                    env=dict(os.environ, PYTHONIOENCODING="utf-8"))
                row["answer"] = proc.stdout.strip()
                row["output_lines"] = len(proc.stdout.splitlines())
                if proc.returncode or "[error]" in proc.stderr or row["output_lines"] != 1 or not row["answer"]:
                    row["error"] = "entrypoint_failure"
                row["grading"] = "manual_review_required"
            else:
                from bot.answer import _metadata_where, _retrieve_safe
                from bot.hybrid import hybrid_retrieve
                where = _metadata_where(case["question"])
                if args.mode == "lexical":
                    chunks = hybrid_retrieve(case["question"], [], k=20, where=where)
                    if not chunks and where:
                        chunks = hybrid_retrieve(case["question"], [], k=20)
                else:
                    chunks = _retrieve_safe(case["question"], k=20, where=where)
                row["retrieved"] = chunks
                row["evidence_at_k"] = {str(k): check_evidence(chunks[:k], case) for k in (1, 5, 20)}
        except Exception as exc:
            row["error"] = type(exc).__name__
        row["seconds"] = time.perf_counter() - t0
        report["questions"].append(row)
        write(args.output / "report.json", report)
    report["summary"] = {"questions": len(cases),
        "errors": sum(bool(r["error"]) for r in report["questions"]),
        "mean_seconds": sum(r["seconds"] for r in report["questions"]) / len(cases)}
    if args.mode != "answers":
        report["summary"]["complete_at_k"] = {str(k): sum(
            r.get("evidence_at_k", {}).get(str(k), {}).get("complete", False)
            for r in report["questions"]) / len(cases) for k in (1, 5, 20)}
    write(args.output / "report.json", report)
    lines = ["# First image batch acceptance results", "", "Evidence recall is not answer accuracy.", "",
             "```json", json.dumps(report["summary"], indent=2), "```"]
    for row in report["questions"]:
        lines.extend(["", f"## {row['id']}", "", row["question"], "",
                      "Expected: " + row["expected_answer"], "",
                      "Actual: " + (row["answer"] or "(retrieval only)"), "",
                      "Evidence: " + json.dumps(row.get("evidence_at_k", {})), "",
                      "Error: " + str(row["error"])])
    (args.output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    if report["summary"]["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
