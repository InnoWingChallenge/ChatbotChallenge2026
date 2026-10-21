"""Small regression tests for extraction and cleaned-data integrity."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build.clean import clean_images, clean_pages, validate_outputs  # noqa: E402
from build.scrape import extract  # noqa: E402


class ScrapeExtractionTests(unittest.TestCase):
    def test_extracts_sections_dates_and_image_dimensions(self) -> None:
        html = """
        <html><head>
          <link rel="canonical" href="https://example.com/page/">
          <script type="application/ld+json">
            {"datePublished": "2026-02-27"}
          </script>
        </head><body><main>
          <h1>Example</h1><h2>Details</h2>
          <p>First fact</p><p>Second fact</p>
          <img src="/poster.jpg" width="640" height="480" alt="Poster">
        </main></body></html>
        """
        page = extract(html, "https://example.com/page/")
        self.assertEqual(page["published_at"], "2026-02-27")
        self.assertEqual(page["sections"][0]["heading"], "Details")
        self.assertEqual(page["images"][0]["width"], 640)


class CleaningTests(unittest.TestCase):
    def test_exact_duplicates_and_image_occurrences_are_collapsed(self) -> None:
        pages = [
            {
                "url": "https://example.com/a/", "site": "example.com",
                "title": "A", "text": "Same sufficiently long body " * 10,
                "sections": [], "images": [], "categories": [],
            },
            {
                "url": "https://example.com/b/", "site": "example.com",
                "title": "B", "text": "Same sufficiently long body " * 10,
                "sections": [], "images": [], "categories": [],
            },
        ]
        documents, rejected, mapping = clean_pages(pages)
        raw_images = [
            {"src": "https://example.com/x.jpg", "page": page["url"], "position": 0}
            for page in pages
        ]
        images, _ = clean_images(raw_images, mapping, documents)
        validate_outputs(documents, images)
        self.assertEqual(len(documents), 1)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["occurrence_count"], 2)

    def test_generated_dataset_has_valid_references_when_present(self) -> None:
        documents_path = ROOT / "data" / "processed" / "documents.json"
        images_path = ROOT / "data" / "processed" / "images.json"
        if not documents_path.exists() or not images_path.exists():
            self.skipTest("processed dataset has not been built")
        documents = json.loads(documents_path.read_text(encoding="utf-8"))
        images = json.loads(images_path.read_text(encoding="utf-8"))
        validate_outputs(documents, images)
        self.assertTrue(all(document["sections"] for document in documents))


if __name__ == "__main__":
    unittest.main()
