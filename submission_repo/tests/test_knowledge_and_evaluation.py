"""Offline tests for the knowledge layer and evidence-level evaluation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot import knowledge, rerank  # noqa: E402
from build.knowledge import validate_knowledge  # noqa: E402
from eval.evaluate_retrieval import is_relevant, recall_at  # noqa: E402


class KnowledgeTests(unittest.TestCase):
    def test_curated_knowledge_is_valid_and_provenance_backed(self) -> None:
        counts = validate_knowledge()
        self.assertGreaterEqual(counts["facts"], 4)
        self.assertGreaterEqual(counts["entities"], 7)

    def test_glossary_expands_3d_printing_query(self) -> None:
        expanded = knowledge.expand_query("What is 3D printing also known as?")
        self.assertIn("additive manufacturing", expanded.casefold())

    def test_exact_fact_is_retrievable_without_an_api(self) -> None:
        results = knowledge.retrieve_knowledge(
            "When was the second round Funding Scheme deadline in 2025-26?"
        )
        self.assertEqual(
            results[0]["metadata"]["fact_id"],
            "fact_funding_2025_26_second_round_deadline",
        )


class EvaluationTests(unittest.TestCase):
    def test_fact_id_counts_as_relevant(self) -> None:
        annotation = {
            "fact_ids": ["fact_correct"],
            "relevant_chunk_ids": [],
            "evidence_patterns": [],
            "relevant_sources": [],
        }
        candidates = [
            {"text": "noise", "metadata": {"fact_id": "fact_wrong"}},
            {"text": "evidence", "metadata": {"fact_id": "fact_correct"}},
        ]
        self.assertEqual(recall_at(candidates, annotation, 1), 0)
        self.assertEqual(recall_at(candidates, annotation, 5), 1)

    def test_correct_page_wrong_chunk_is_not_automatically_relevant(self) -> None:
        annotation = {
            "fact_ids": [],
            "relevant_chunk_ids": [],
            "evidence_patterns": ["winner: smart socks"],
            "relevant_sources": ["https://example.com/pitching/"],
        }
        candidate = {
            "text": "This page explains contest eligibility.",
            "metadata": {"url": "https://example.com/pitching/"},
        }
        self.assertFalse(is_relevant(candidate, annotation))


class RerankerTests(unittest.TestCase):
    def test_llm_can_reorder_candidates_by_id(self) -> None:
        candidates = [
            {"text": "2024 winner", "metadata": {"chunk_id": "old"}},
            {"text": "2025 winner", "metadata": {"chunk_id": "current"}},
        ]
        response = '{"evidence_sufficient": true, "selected": [' \
                   '{"id": "current", "score": 0.99}]}'
        with patch.object(rerank, "chat", return_value=response):
            result = rerank.rerank_candidates("Who won in 2025?", candidates, k=1)
        self.assertEqual(result[0]["metadata"]["chunk_id"], "current")

    def test_invalid_llm_output_falls_back_to_existing_order(self) -> None:
        candidates = [
            {"text": "first", "metadata": {"chunk_id": "one"}},
            {"text": "second", "metadata": {"chunk_id": "two"}},
        ]
        with patch.object(rerank, "chat", return_value="not json"):
            result = rerank.rerank_candidates("question", candidates, k=1)
        self.assertEqual(result, candidates[:1])


if __name__ == "__main__":
    unittest.main()
