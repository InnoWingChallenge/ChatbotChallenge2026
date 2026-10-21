"""Offline contract tests for indexing, image ingestion, and retrieval."""

from __future__ import annotations

import sys
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot import answer, hybrid  # noqa: E402
from build import images, index  # noqa: E402


class TextIndexTests(unittest.TestCase):
    def test_clean_metadata_and_stable_ids_are_indexed(self) -> None:
        document = {
            "id": "doc_123",
            "url": "https://example.com/workshop/",
            "site": "example.com",
            "title": "Workshop",
            "text": "Fallback text",
            "sections": [{"heading": "Details", "text": "Date: 1 January 2025"}],
            "year": 2025,
            "academic_year": "2024/25",
            "page_type": "event",
        }
        with patch.object(index, "get_store", return_value=object()), patch.object(
            index, "add_to_store"
        ) as add, patch.object(index, "build_fts_index"):
            index.build_index([document])

        texts, metadata = add.call_args.args[1:3]
        ids = add.call_args.kwargs["ids"]
        self.assertEqual(
            texts,
            [
                "Page title: Workshop\nPage type: event\nYear: 2025\n"
                "Section: Details\nDate: 1 January 2025"
            ],
        )
        self.assertEqual(metadata[0]["year"], 2025)
        self.assertEqual(metadata[0]["page_type"], "event")
        self.assertEqual(ids, ["txt_doc_123_0"])

    def test_noise_pages_are_excluded_but_short_physical_pages_remain(self) -> None:
        photo = {
            "url": "https://example.com/photo/", "title": "Photo gallery",
            "text": "Pitch New Tech Ideas 2025 Photo gallery", "status": "review_short",
        }
        physical = {
            "url": "https://example.com/sign/", "title": "Innovation Wing Signage",
            "text": "Words visible on the wall", "status": "review_short",
        }
        challenge = {
            "url": "https://example.com/aichallenge/", "title": "Challenge",
            "text": "Benchmark questions and answers", "status": "ready",
        }
        self.assertFalse(index.is_indexable(photo))
        self.assertTrue(index.is_indexable(physical))
        self.assertFalse(index.is_indexable(challenge))

    def test_sqlite_bm25_finds_exact_deadline_terms(self) -> None:
        records = [
            {
                "id": "txt_funding_0",
                "text": "Page title: Funding Scheme\nDeadline: February 27 2026",
                "metadata": {
                    "document_id": "funding", "position": 0,
                    "title": "Funding Scheme", "section": "Deadline",
                    "url": "https://example.com/funding/", "page_type": "funding",
                    "year": "", "status": "ready",
                },
            },
            {
                "id": "txt_gallery_0",
                "text": "Page title: Photo gallery\nPitch New Tech Ideas 2025",
                "metadata": {
                    "document_id": "gallery", "position": 0,
                    "title": "Photo gallery", "section": "",
                    "url": "https://example.com/gallery/", "page_type": "competition",
                    "year": 2025, "status": "review_short",
                },
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "text.sqlite"
            index.build_fts_index(records, path)
            results = hybrid.bm25_retrieve("funding deadline 2026", path=path)
        self.assertEqual(results[0]["metadata"]["document_id"], "funding")

    def test_rule_rerank_demotes_empty_photo_gallery(self) -> None:
        photo = {
            "text": "Photo gallery Pitch New Tech Ideas 2025",
            "metadata": {
                "chunk_id": "photo", "document_id": "photo", "position": 0,
                "title": "Photo gallery", "page_type": "competition",
                "status": "review_short", "year": 2025,
            },
            "distance": 0.3,
        }
        winner = {
            "text": "Pitch New Tech Ideas 2025 winners: SmartSocks and Gingtrolley",
            "metadata": {
                "chunk_id": "winner", "document_id": "pitch", "position": 4,
                "title": "Pitching 2025", "page_type": "competition",
                "status": "ready", "year": 2025,
            },
            "distance": 0.5,
        }
        ranked = hybrid.hybrid_rank(
            "What were the winning teams in Pitch New Tech Ideas in 2025?",
            [photo, winner], [], k=2,
        )
        self.assertEqual(ranked[0]["metadata"]["chunk_id"], "winner")

    def test_rule_rerank_prefers_matching_academic_year_deadline(self) -> None:
        correct = {
            "text": "Applicants should submit materials by February 27 2026 (Friday).",
            "metadata": {
                "chunk_id": "current", "document_id": "scheme", "position": 8,
                "title": "Funding Scheme", "page_type": "funding", "status": "ready",
            },
            "distance": 0.95,
        }
        stale = {
            "text": "Second Round 2022-2023. Application Period: February 2023.",
            "metadata": {
                "chunk_id": "stale", "document_id": "scheme", "position": 6,
                "title": "Funding Scheme", "page_type": "funding", "status": "ready",
            },
            "distance": 0.94,
        }
        tba = {
            "text": "Funding application deadline: TBA.",
            "metadata": {
                "chunk_id": "tba", "document_id": "other", "position": 1,
                "title": "Available Fundings", "page_type": "funding", "status": "ready",
            },
            "distance": 0.93,
        }
        ranked = hybrid.hybrid_rank(
            "When was the second round funding deadline in 2025-26?",
            [tba, stale, correct], [], k=3,
        )
        self.assertEqual(ranked[0]["metadata"]["chunk_id"], "current")


class ImageIndexTests(unittest.TestCase):
    def test_descriptions_keep_document_metadata(self) -> None:
        image = {
            "src": "https://example.com/poster.jpg",
            "alt": "Workshop poster",
            "caption": "Robotics",
            "document_ids": ["doc_123"],
        }
        document = {
            "id": "doc_123", "url": "https://example.com/workshop/",
            "title": "Workshop", "year": 2025, "page_type": "event",
        }
        store = Mock()
        store.get.return_value = {"ids": ["img_old", "revimg_keep"],
                                  "metadatas": [{}, {"evidence_pipeline": "reviewed_images_v1"}]}
        with patch.object(images, "get_store", return_value=store), patch.object(
            images, "add_to_store"
        ) as add:
            count = images.index_descriptions(
                {image["src"]: "Visible date: 1 January 2025."}, [image], [document]
            )

        self.assertEqual(count, 1)
        store.delete.assert_called_once_with(ids=["img_old"])
        texts, metadata = add.call_args.args[1:3]
        self.assertIn("Visible date", texts[0])
        self.assertEqual(metadata[0]["kind"], "image")
        self.assertEqual(metadata[0]["year"], 2025)
        self.assertTrue(add.call_args.kwargs["ids"][0].startswith("img_"))

    def test_prompt_requests_ocr_counts_and_spatial_evidence(self) -> None:
        prompt = images.DESCRIPTION_PROMPT.casefold()
        for term in ("transcribe", "count", "spatial", "wall"):
            self.assertIn(term, prompt)
        self.assertNotIn("todo", prompt)


class AnswerTests(unittest.TestCase):
    def test_multiline_answer_is_one_line(self) -> None:
        with patch.object(answer, "_retrieve_and_rerank", return_value=[]), patch.object(
            answer, "chat", return_value="  Studio A: IW-LG05\r\nStudio B: IW-LG06\u2028Done\t "
        ):
            result = answer.rag_answer("List the studio identifiers.")
        self.assertEqual(result, "Studio A: IW-LG05 Studio B: IW-LG06 Done")

    def test_entrypoint_batch_preserves_line_count_and_order(self) -> None:
        import main as entrypoint
        output = io.StringIO()
        with patch.object(answer, "_retrieve_and_rerank", return_value=[]), patch.object(
            answer, "chat", side_effect=["A: IW-LG05\nB: IW-LG06", "\r\nGreen\n"]
        ), patch.object(sys, "argv", ["main.py", "List studio identifiers.", "Cord colour?"]), \
                contextlib.redirect_stdout(output):
            entrypoint.main()
        self.assertEqual(output.getvalue().splitlines(), ["A: IW-LG05 B: IW-LG06", "Green"])

    def test_visual_year_filter_uses_chroma_types_and_and_operator(self) -> None:
        self.assertEqual(
            answer._metadata_where("What is shown in the 2025 picture?"),
            {"$and": [{"kind": "image"}, {"year": 2025}]},
        )

    def test_text_year_does_not_hide_undated_living_pages(self) -> None:
        self.assertIsNone(
            answer._metadata_where("What was the funding deadline in 2025-26?")
        )

    def test_empty_filtered_retrieval_falls_back(self) -> None:
        fallback = [{"text": "answer", "metadata": {}, "distance": 0.1}]
        with patch.object(answer, "retrieve", side_effect=[[], fallback]) as retrieve:
            result = answer._retrieve_safe("question", where={"kind": "image"})
        self.assertEqual(result, fallback)
        self.assertEqual(retrieve.call_count, 2)

    def test_number_questions_no_longer_request_fifty_chunks(self) -> None:
        evidence = [{"text": "Verified aggregate: 7", "metadata": {}}]
        with patch.object(answer, "_retrieve_safe", return_value=evidence) as retrieve, patch.object(
            answer, "rerank_candidates", return_value=evidence
        ), patch.object(answer, "chat", return_value="7"):
            result = answer.rag_answer("How many 3D printers are there in total?")
        self.assertEqual(result, "7")
        self.assertEqual(retrieve.call_args.kwargs["k"], answer.CONFIG["candidate_k"])

    def test_plain_and_does_not_trigger_subquestion_llm(self) -> None:
        self.assertFalse(answer._needs_split("HKU, Engineering, and what?"))


if __name__ == "__main__":
    unittest.main()
