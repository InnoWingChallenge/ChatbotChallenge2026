import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from build import bulk_web_images as bulk
except ModuleNotFoundError as exc:
    if exc.name != "PIL":
        raise
    bulk = None


@unittest.skipIf(bulk is None, "optional image dependencies not installed")
class BulkImageTests(unittest.TestCase):
    def test_plan_skips_valid_cache_and_defers_permanent_errors(self):
        manifest = {name: {"id": name, "url": "https://innoacademy.engg.hku.hk/" + name + ".jpg"}
                    for name in ("cached", "missing", "broken", "transient", "notfound")}
        state = {"cached": {"status": "recovered", "sha256": "valid", "local_path": "a.jpg"},
                 "broken": {"status": "recovered", "sha256": "bad", "local_path": "b.jpg"},
                 "transient": {"status": "failed", "error_type": "ConnectionError"},
                 "notfound": {"status": "failed", "http_status": 404}}
        with tempfile.TemporaryDirectory() as directory, patch.object(bulk, "BULK", Path(directory)), \
                patch.object(bulk, "cached", side_effect=lambda e: e.get("sha256") == "valid"), \
                patch.object(bulk, "session") as network:
            selected = bulk.plan(manifest, state)
            self.assertEqual({v["id"] for v in selected}, {"missing", "broken", "transient"})
            network.assert_not_called()
            selected_all = bulk.plan(manifest, state, retry_all=True)
            self.assertIn("notfound", {v["id"] for v in selected_all})

    def test_dry_run_never_contacts_site(self):
        with patch.object(bulk, "read", return_value={}), patch.object(bulk, "load_state", return_value={}), \
                patch.object(bulk, "plan", return_value=[{"id": "pending"}]), patch.object(bulk, "session") as network:
            bulk.download(1, dry_run=True)
        network.assert_not_called()

    def test_cached_requires_matching_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.jpg"
            path.write_bytes(b"original")
            entry = {"status": "recovered", "local_path": "image.jpg", "sha256": bulk.digest(path)}
            with patch.object(bulk, "safe_path", return_value=path):
                self.assertTrue(bulk.cached(entry))
                path.write_bytes(b"changed")
                self.assertFalse(bulk.cached(entry))
                path.unlink()
                self.assertFalse(bulk.cached(entry))

    def test_hamming_index_matches_exhaustive_candidates(self):
        rng = random.Random(42)
        values = [rng.getrandbits(64) for _ in range(20)]
        values += [values[0] ^ sum(1 << i for i in rng.sample(range(64), distance)) for distance in range(1, 11)]
        assets = [{"id": str(i), "sha256": str(i), "dhash": f"{v:016x}",
                   "width": 100, "height": 100, "source_type": "physical_photo" if i == 0 else "web_image"}
                  for i, v in enumerate(values)]
        expected = {(str(i), str(j)) for i in range(len(values)) for j in range(i+1, len(values))
                    if bin(values[i] ^ values[j]).count("1") <= 8}
        actual = bulk.near_pairs(assets)
        self.assertEqual({(p["a"], p["b"]) for p in actual}, expected)
        self.assertTrue(any(p["cross_source"] for p in actual))
        self.assertTrue(all(p["decision"] == "review_candidate_not_deleted" for p in actual))

    def test_exact_hash_and_incompatible_aspect_are_not_near_pairs(self):
        base = {"dhash": "0000000000000000", "width": 100, "height": 100, "source_type": "web_image"}
        assets = [{**base, "id": "a", "sha256": "same"}, {**base, "id": "b", "sha256": "same"},
                  {**base, "id": "c", "sha256": "other", "height": 400}]
        self.assertEqual(bulk.near_pairs(assets), [])

    def test_invalid_image_is_not_decoded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong.jpg"
            path.write_text("not image data", encoding="utf-8")
            with self.assertRaises(Exception):
                bulk.signature(path)

    def test_similarity_chain_is_only_a_review_group(self):
        assets = [{"id": name, "width": size, "height": size, "source_type": "web_image"}
                  for name, size in (("a", 10), ("b", 20), ("c", 30))]
        groups = bulk.candidate_groups(assets, [{"a": "a", "b": "b"}, {"a": "b", "b": "c"}])
        self.assertEqual(groups[0]["members"], ["a", "b", "c"])
        self.assertEqual(groups[0]["candidate_representative"], "c")
        self.assertIn("not identity", groups[0]["decision"])


if __name__ == "__main__":
    unittest.main()
