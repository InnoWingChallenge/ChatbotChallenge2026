import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock

from bot.image_evidence import PIPELINE, retrieve_images
from build.ingest_reviewed_images import (
    OUTPUT, build_bm25, index_chroma, local_sections, make_record, read,
)


def record(identifier, kind="image"):
    value = make_record("prompt/test/prompt.md", "Laboratory", "Sign",
                        "A green laboratory sign.", ["image_source/test.jpg"],
                        kind, "physical_photo", "visual_description", "", "2026-10-13")
    value["id"] = identifier
    value["metadata"]["chunk_id"] = identifier
    return value


class ReviewedImageTests(unittest.TestCase):
    def test_sources_do_not_leak_across_headings(self):
        text = "# Room\n\nUnsourced claim.\n\n## Sign\n\nSources: [photo](a.jpg)\n\nGreen sign.\n\n## Other\n\nAnother unsourced claim."
        self.assertEqual(list(local_sections(text)), [("Sign", ["a.jpg"], "Green sign.")])

    def test_review_date_is_not_evidence_year(self):
        value = record("a")
        self.assertNotIn("year", value["metadata"])
        self.assertEqual(value["metadata"]["capture_date"], "unknown")

    def test_lexical_filters_before_limit_and_preserves_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "images.sqlite"
            build_bm25([record("a", "text"), record("z")], path)
            hits = retrieve_images("laboratory", k=1, where={"kind": "image"}, path=path)
            self.assertEqual(hits[0]["metadata"]["chunk_id"], "z")
            self.assertEqual(hits[0]["metadata"]["source_ids_json"], '["image_source/test.jpg"]')

    def test_invalid_vectors_cannot_mutate_store(self):
        store = Mock()
        with self.assertRaises(ValueError):
            index_chroma([record("a")], store, [[float("nan")]])
        store.upsert.assert_not_called()
        store.delete.assert_not_called()

    def test_failed_upsert_never_deletes_old_evidence(self):
        store = Mock()
        store.upsert.side_effect = RuntimeError("write failed")
        with self.assertRaises(RuntimeError):
            index_chroma([record("a")], store, [[1.0, 0.0]])
        store.delete.assert_not_called()

    def test_real_chroma_idempotency_and_owner_isolation_offline(self):
        import chromadb
        from chromadb.config import Settings
        client = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
        name = "image-test-" + uuid.uuid4().hex
        store = client.create_collection(name, embedding_function=None)
        try:
            store.add(ids=["text", "img_legacy", "stale"], documents=["text", "legacy", "stale"],
                      embeddings=[[1., 0.]] * 3,
                      metadatas=[{"kind": "text"}, {"kind": "image"}, {"evidence_pipeline": PIPELINE}])
            for _ in range(2):
                self.assertEqual(index_chroma([record("revimg_current")], store, [[0., 1.]]), 1)
            self.assertEqual(set(store.get()["ids"]), {"text", "img_legacy", "revimg_current"})
        finally:
            client.delete_collection(name)

    def test_prepared_evidence_keeps_web_context_separate(self):
        records = read(OUTPUT / "records.json")
        self.assertEqual(len(records), len({r["id"] for r in records}))
        context = [r for r in records if r["metadata"]["evidence_type"] == "web_context"]
        self.assertTrue(context)
        for value in context:
            self.assertEqual(value["metadata"]["kind"], "text")
            self.assertIn("not visible image evidence", value["text"])
        for value in records:
            if value["metadata"].get("curation_version") == "image-text-curation-v1":
                self.assertEqual(value["metadata"]["status"], "text_curated_not_visual_verified")
                self.assertIs(value["metadata"]["visual_reverified"], False)
                self.assertEqual(value["metadata"]["evidence_type"], "visual_description")
                self.assertTrue(value["metadata"]["description_sha256"])
            else:
                self.assertEqual(value["metadata"]["status"], "assistant_reviewed")
            self.assertTrue(value["metadata"]["source_ids_json"])


if __name__ == "__main__":
    unittest.main()
