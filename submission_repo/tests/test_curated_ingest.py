import unittest
from unittest.mock import Mock

from build.ingest_curated_images import additive_upsert, PIPELINE


def row(ident):
    return {"id": ident, "text": ident, "metadata": {"evidence_pipeline": PIPELINE}}


class CuratedIngestTests(unittest.TestCase):
    def store(self, extra=False):
        store = Mock()
        store.peek.return_value = {"embeddings": [[1.0, 0.0]]}
        records = {"old": row("old")}
        if extra:
            records["unexpected"] = row("unexpected")

        def get(**kwargs):
            ids = kwargs.get("ids", list(records))
            selected = [records[i] for i in ids if i in records]
            return {"ids": [r["id"] for r in selected],
                    "documents": [r["text"] for r in selected],
                    "metadatas": [r["metadata"] for r in selected]}

        def upsert(**kwargs):
            for i, text, meta in zip(kwargs["ids"], kwargs["documents"], kwargs["metadatas"]):
                records[i] = {"id": i, "text": text, "metadata": meta}
        store.get.side_effect = get
        store.upsert.side_effect = upsert
        return store, records

    def test_additive_and_idempotent_without_delete_or_old_reembedding(self):
        store, records = self.store()
        original = dict(records["old"])
        for _ in range(2):
            additive_upsert([row("new")], [row("old"), row("new")], [[0.0, 1.0]], store)
        self.assertEqual(records["old"], original)
        self.assertEqual(set(records), {"old", "new"})
        store.delete.assert_not_called()
        for call in store.upsert.call_args_list:
            self.assertEqual(call.kwargs["ids"], ["new"])

    def test_changed_baseline_and_dimension_fail_before_upsert(self):
        for extra, vector in ((True, [0.0, 1.0]), (False, [1.0]), (False, [float("nan"), 1.0])):
            with self.subTest(extra=extra, vector=vector):
                store, _ = self.store(extra)
                with self.assertRaises(ValueError):
                    additive_upsert([row("new")], [row("old"), row("new")], [vector], store)
                store.upsert.assert_not_called()

    def test_changed_chroma_document_is_not_overwritten(self):
        store, records = self.store()
        records["old"]["text"] = "Changed outside this release"
        with self.assertRaises(ValueError):
            additive_upsert([row("new")], [row("old"), row("new")], [[0.0, 1.0]], store)
        store.upsert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
