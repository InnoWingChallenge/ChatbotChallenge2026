import unittest
import tempfile
import contextlib
import io
from pathlib import Path
from unittest.mock import patch
from build import export_curated_images as exporter
from build.export_curated_images import selected_evidence


class CuratedExportTests(unittest.TestCase):
    def test_preserves_exact_source_wording_and_field(self):
        result = selected_evidence(
            {"facts": [0], "spatial": [], "ocr": [1]},
            {"visual_facts": ["A cabinet."], "spatial_relations": [],
             "visible_text": ["other", "Metal Laser"]})
        self.assertEqual(result, [
            {"field": "visual_facts", "index": 0, "text": "A cabinet."},
            {"field": "visible_text", "index": 1, "text": "Metal Laser"}])

    def test_rejects_invalid_or_duplicate_references(self):
        source = {"visual_facts": ["A cabinet."], "spatial_relations": [], "visible_text": []}
        for indices in ([-1], [1], [True], [0, 0]):
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                selected_evidence({"facts": indices, "spatial": [], "ocr": []}, source)

    def test_export_preserves_baseline_and_rejects_changed_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dest = root / "curation"
            save = exporter.batch.save
            baseline_path = root / "submission_repo/data/image_evidence/records.json"
            baseline = [{"id": "old-record", "text": "Existing evidence", "metadata": {}}]
            save(baseline_path, baseline)
            save(baseline_path.parent / "sources.json", {"assets": {"old-source": {}}})
            save(dest / "baseline_records.json", baseline)
            inputs = []
            for n in range(3):
                raw = root / f"{n}.jpg"
                raw.write_bytes(b"photo" + bytes([n]))
                desc = {"visual_facts": [f"Equipment observation {n}."],
                        "visible_text": [], "spatial_relations": [], "uncertainties": [],
                        "model": "gpt-5-mini", "prompt_version": "equipment-space-api-v3"}
                path = root / f"{n}.json"
                save(path, desc)
                ident = str(n)
                inputs.append({"id": ident, "description": desc,
                    "description_path": path.name, "description_sha256": exporter.checksum(path),
                    "task": {"id": ident, "sha256": exporter.checksum(raw),
                             "local_path": raw.name, "category": "equipment_facility",
                             "url": "https://example.org/" + ident, "context": []}})
                save(dest / f"packet-{n}.json", [{"id": ident}])
                save(dest / f"decisions-{n}.json", [{
                    "id": ident, "disposition": "keep", "facts": [0], "spatial": [], "ocr": [],
                    "reason": "Relevant equipment observation.", "conflicts": [], "duplicate_of": []}])
            save(dest / "inputs.json", inputs)
            save(dest / "inventory.json", {"missing_description_ids": ["missing"],
                 "comparison_corpora": [{"path": baseline_path.relative_to(root).as_posix(),
                                         "sha256": exporter.checksum(baseline_path)}]})
            save(dest / "review_run.json", {"model": "gpt-6-luna", "reasoning_effort": "low",
                 "inputs": {name: exporter.checksum(dest / name)
                            for name in ["inputs.json", "baseline_records.json"]}})
            with patch.object(exporter, "DEST", dest), patch.object(exporter.batch, "ROOT", root):
                with contextlib.redirect_stdout(io.StringIO()):
                    exporter.main()
                rows = exporter.batch.read(dest / "release/merged_records.json")
                self.assertEqual(len(rows), 4)
                self.assertEqual(rows[0]["id"], "old-record")
                self.assertFalse(rows[1]["metadata"]["visual_reverified"])
                self.assertEqual(exporter.batch.read(baseline_path), baseline)
                (root / "0.jpg").write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "Image changed"):
                    exporter.main()


if __name__ == "__main__":
    unittest.main()
