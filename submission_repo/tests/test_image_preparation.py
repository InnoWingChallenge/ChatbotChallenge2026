import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from build import prepare_image_batch as preparation
    from build.export_image_pilot import validate_description
except ModuleNotFoundError as exc:
    if exc.name != "PIL":
        raise
    preparation = None


@unittest.skipIf(preparation is None, "optional build/requirements-images.txt not installed")
class ImagePreparationTests(unittest.TestCase):
    def test_exact_duplicates_share_one_recovery_candidate(self):
        base = {"url": "https://innoacademy.engg.hku.hk/poster.jpg", "sha256": "same",
                "width": 800, "height": 800, "occurrences": []}
        manifest = {"a": {**base, "id": "a"}, "b": {**base, "id": "b", "width": 1600}}
        result = preparation.select_candidates(manifest, {}, 10)
        self.assertEqual([i["id"] for i in result], ["b"])

    def test_branding_external_and_tiny_images_are_deferred(self):
        base = {"width": 800, "height": 800, "occurrences": []}
        manifest = {"a": {**base, "id": "a", "url": "https://innoacademy.engg.hku.hk/logo.png"},
                    "b": {**base, "id": "b", "url": "https://example.org/poster.png"},
                    "c": {**base, "id": "c", "url": "https://innoacademy.engg.hku.hk/small.jpg", "width": 50}}
        self.assertEqual(preparation.select_candidates(manifest, {}, 10), [])

    def test_recovery_is_hash_verified_and_historical_manifest_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "raw.jpg").write_bytes(b"new-content")
            manifest = root / "manifest.json"
            preparation.save(manifest, {"x": {"id": "x", "url": "https://example.org/x.jpg", "sha256": "old-content-hash"},
                                        "y": {"id": "y", "url": "https://example.org/y.jpg"}})
            before = manifest.read_bytes()
            out = root / "preparation"
            preparation.save(out / "recovery.json", {key: {"status": "recovered", "local_path": "raw.jpg"} for key in ("x", "y")})
            with patch.multiple(preparation, ROOT=root, OUT=out, MANIFEST=manifest, REVIEWS=root / "reviews.json"):
                preparation.audit()
            inventory = preparation.read(out / "inventory.json")
            self.assertEqual(inventory["assets"][0]["file_state"], "hash_changed")
            self.assertEqual(inventory["assets"][1]["file_state"], "captured_without_prior_hash")
            self.assertEqual(manifest.read_bytes(), before)

    def test_path_cannot_escape_workspace(self):
        with self.assertRaises(ValueError):
            preparation.safe_path("../outside.jpg")

    def test_export_rejects_wrong_model_or_unviewed_output(self):
        record = {"model": "gpt-6-sol", "reasoning_effort": "low", "viewed": False,
                  "title": "test", "type": "poster", "location": "unknown",
                  "paragraphs": ["One.", "Two.", "Three."], "uncertainties": []}
        with self.assertRaises(ValueError):
            validate_description(record, "gpt-6-sol")
        record["viewed"] = True
        with self.assertRaises(ValueError):
            validate_description(record, "gpt-6-luna")
        validate_description(record, "gpt-6-sol")


if __name__ == "__main__":
    unittest.main()
