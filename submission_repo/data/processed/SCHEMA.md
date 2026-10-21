# Processed data schema

This directory is derived from `../pages.json` and `../images.json`. Rebuild it
with `python build/clean.py`; do not edit generated records by hand.

## documents.json

One canonical record per exact body-text fingerprint. Important fields:

- `id`: stable identifier derived from the canonical URL.
- `url`, `site`, `raw_id`, `retrieved_at`: source provenance.
- `title`, `text`, `sections`: normalized content; each section preserves its
  heading, level, order, and text.
- `page_type`, `year`, `academic_year`, `categories`: retrieval filters inferred
  conservatively from page metadata and recognizable page templates.
- `duplicate_urls`: mirrored pages with the same normalized body.
- `image_ids`: non-noise images connected to this document.
- `status`: `ready`, `review_short`, or `review_encoding`.

## images.json and image_queue.json

`images.json` contains one record per unique source URL and keeps all source-page
occurrences. Noise is labelled rather than deleted. `image_queue.json` is the
non-noise subset intended for later cached image description; its `description`
field is deliberately empty at this stage.

## review_pages.json

Records that need human attention, including short pages, rejected empty pages,
and exact duplicates. A duplicate points to the retained canonical URL in
`kept_as`.

## Reproducibility

`manifest.json` records the schema version and SHA-256 hashes of both input
files. `report.json` and `REPORT.md` summarize quality and completeness. The
compressed raw HTML cache is local under `../raw_pages/` and is intentionally
excluded from Git and the final Codabench archive.
