"""Clean and structure the raw InnoWing crawl without overwriting it.

Inputs are ``data/pages.json`` and ``data/images.json``. Outputs are written to
``data/processed`` so that every transformation can be reviewed and rebuilt
before embedding or indexing.

Run from the submission repository with::

    python build/clean.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "processed"
SCHEMA_VERSION = 1

MOJIBAKE = {
    "\ufffdC": "\u2013",
    "\ufffd\ufffds": "'s",
    "\u951f\u7dba": "\u2013",
    "\u00e2\u20ac\u201c": "\u2013",
    "\u00e2\u20ac\u201d": "\u2014",
    "\u00e2\u20ac\u2122": "'",
    "\u00c2\u00a0": " ",
}
BOILERPLATE_LINES = {
    "skip to content",
    "read more",
    "learn more",
    "share this:",
    "loading...",
}
IMAGE_NOISE_WORDS = {
    "facebook", "instagram", "linkedin", "youtube", "twitter", "wechat",
    "whatsapp", "icon", "favicon", "logo", "avatar", "spinner", "loader",
    "placeholder", "transparent", "pixel", "cropped-site-icon",
}


def read_json(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, list):
        raise ValueError(f"expected a JSON list: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def normalise_inline(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    for broken, replacement in MOJIBAKE.items():
        text = text.replace(broken, replacement)
    text = text.replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def normalise_text(value: object) -> str:
    lines: list[str] = []
    previous = ""
    for raw in str(value or "").splitlines():
        line = normalise_inline(raw)
        if not line or line.casefold() in BOILERPLATE_LINES or line == previous:
            continue
        lines.append(line)
        previous = line
    return "\n".join(lines)


def canonical_image_url(value: str) -> str:
    parsed = urlparse(normalise_inline(value))
    if parsed.scheme not in {"http", "https"}:
        return ""
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", "", ""))


def infer_page_type(page: dict) -> str:
    metadata = " ".join([
        page.get("url", ""), page.get("title", ""),
        " ".join(page.get("categories", [])),
    ]).casefold()
    opening = page.get("text", "")[:1000].casefold()
    path = urlparse(page.get("url", "")).path.casefold()
    if re.search(r"/(?:20\d{6})[_-]", path):
        return "event"
    if "treasure hunt" in metadata:
        return "facility"
    if any(marker in opening for marker in (
        "project supervisor:", "project information", "project descriptions",
        "team information\nproject leader:",
    )):
        return "project"
    rules = [
        ("funding", ("funding", "seed fund", "financial support")),
        ("facility", ("facility", "equipment", "makerspace", "maker space",
                      "brainstorming room", "co-working", "coworking", "venue",
                      "3d printer", "laser cutter", "laser cutting")),
        ("competition", ("competition", "pitching", "hackathon", "robomaster")),
        ("event", ("event", "workshop", "seminar", "showcase", "innoshow",
                   "inno show", "study tour", "ceremony", "exhibition")),
        ("course", ("course", "training", "tutorial", "arduino basic")),
        ("news", ("news", "announcement", "newsletter")),
        ("people", ("people", "team member", "staff", "advisor")),
        ("policy", ("policy", "guideline", "safety", "regulation", "booking rule")),
        ("about", ("about", "contact", "mission", "overview", "home")),
        ("project", ("project", "prototype", "fyp", "capstone", "team")),
    ]
    for page_type, markers in rules:
        if any(marker in metadata for marker in markers):
            return page_type
    return "other"


def infer_year(page: dict) -> tuple[int | None, str]:
    primary = " ".join([
        page.get("published_at", ""), page.get("url", ""), page.get("title", ""),
    ])
    def academic_years(value: str) -> list[tuple[int, int]]:
        output = []
        for match in re.finditer(r"\b(20\d{2})\s*[/\u2013-]\s*(\d{2,4})\b", value):
            start = int(match.group(1))
            end_raw = match.group(2)
            end = int(end_raw) if len(end_raw) == 4 else (start // 100 * 100 + int(end_raw))
            if 2010 <= start <= 2035 and start <= end <= start + 2:
                output.append((start, end))
        return output

    academic = academic_years(primary)
    if academic:
        start, end = academic[0]
        return start, f"{start}/{str(end)[-2:]}"
    dated_slug = re.search(r"(?<!\d)(20\d{2})\d{4}(?!\d)", primary)
    if dated_slug:
        return int(dated_slug.group(1)), ""
    primary_years = [int(x) for x in re.findall(
        r"(?<!\d)(20(?:1\d|2\d|3[0-5]))(?!\d)", primary
    )]
    if primary_years:
        return primary_years[0], ""
    if "/workshop/" in urlparse(page.get("url", "")).path.casefold():
        opening_years = [int(x) for x in re.findall(
            r"(?<!\d)(20(?:1\d|2\d|3[0-5]))(?!\d)", page.get("text", "")[:800]
        )]
        if opening_years:
            return opening_years[0], ""
    return None, ""


def clean_sections(page: dict, text: str) -> list[dict]:
    sections: list[dict] = []
    for index, raw in enumerate(page.get("sections") or []):
        section_text = normalise_text(raw.get("text", ""))
        heading = normalise_inline(raw.get("heading", ""))
        if not section_text:
            continue
        sections.append({
            "position": index,
            "heading": heading,
            "level": int(raw.get("level") or 0),
            "text": section_text,
        })
    if not sections and text:
        sections.append({"position": 0, "heading": "", "level": 0, "text": text})
    return sections


def page_quality(page: dict) -> tuple[int, int, int, int]:
    return (
        bool(page.get("published_at")) + bool(page.get("modified_at")),
        len(page.get("sections") or []),
        len(page.get("images") or []),
        len(page.get("text", "")),
    )


def clean_pages(raw_pages: list[dict]) -> tuple[list[dict], list[dict], dict[str, str]]:
    candidates: list[dict] = []
    rejected: list[dict] = []
    for raw in raw_pages:
        url = normalise_inline(raw.get("url", ""))
        text = normalise_text(raw.get("text", ""))
        title = normalise_inline(raw.get("title", ""))
        if not url or not text:
            rejected.append({"url": url, "title": title, "reason": "missing_url_or_text"})
            continue
        page = dict(raw)
        page.update({"url": url, "title": title, "text": text})
        page["sections"] = clean_sections(raw, text)
        candidates.append(page)

    groups: dict[str, list[dict]] = defaultdict(list)
    for page in candidates:
        fingerprint = hashlib.sha256(page["text"].casefold().encode("utf-8")).hexdigest()
        groups[fingerprint].append(page)

    documents: list[dict] = []
    page_to_document: dict[str, str] = {}
    for fingerprint, group in groups.items():
        primary = max(group, key=page_quality)
        duplicate_urls = sorted(p["url"] for p in group if p["url"] != primary["url"])
        categories = sorted({normalise_inline(c) for p in group for c in p.get("categories", []) if c})
        year, academic_year = infer_year(primary)
        document_id = stable_id("doc", primary["url"])
        status = "ready"
        if len(primary["text"]) < 200:
            status = "review_short"
        elif "\ufffd" in primary["text"]:
            status = "review_encoding"
        document = {
            "id": document_id,
            "url": primary["url"],
            "site": normalise_inline(primary.get("site")) or urlparse(primary["url"]).netloc,
            "title": primary["title"],
            "text": primary["text"],
            "sections": primary["sections"],
            "content_type": normalise_inline(primary.get("content_type")) or "page",
            "page_type": infer_page_type(primary),
            "year": year,
            "academic_year": academic_year,
            "categories": categories,
            "published_at": normalise_inline(primary.get("published_at")),
            "modified_at": normalise_inline(primary.get("modified_at")),
            "retrieved_at": normalise_inline(primary.get("retrieved_at")),
            "raw_id": normalise_inline(primary.get("raw_id")),
            "content_sha256": fingerprint,
            "duplicate_urls": duplicate_urls,
            "image_ids": [],
            "status": status,
        }
        documents.append(document)
        for page in group:
            page_to_document[page["url"]] = document_id
        for duplicate in duplicate_urls:
            rejected.append({
                "url": duplicate,
                "title": next((p["title"] for p in group if p["url"] == duplicate), ""),
                "reason": "exact_duplicate",
                "kept_as": primary["url"],
            })

    documents.sort(key=lambda item: (item["site"], item["page_type"], item["title"].casefold(), item["url"]))
    rejected.sort(key=lambda item: (item["reason"], item["url"]))
    return documents, rejected, page_to_document


def image_noise_reason(image: dict, occurrence_count: int) -> str:
    searchable = " ".join([
        image.get("src", ""), image.get("alt", ""), image.get("caption", ""),
        image.get("title", ""),
    ]).casefold()
    width = image.get("width")
    height = image.get("height")
    if isinstance(width, int) and isinstance(height, int) and width <= 32 and height <= 32:
        return "tiny_image"
    if any(word in searchable for word in IMAGE_NOISE_WORDS):
        return "site_chrome_or_social"
    if occurrence_count >= 25 and not (image.get("alt") or image.get("caption")):
        return "repeated_unlabelled_asset"
    return ""


def clean_images(raw_images: list[dict], page_to_document: dict[str, str],
                 documents: list[dict]) -> tuple[list[dict], list[dict]]:
    by_url: dict[str, list[dict]] = defaultdict(list)
    for raw in raw_images:
        src = canonical_image_url(raw.get("src", ""))
        page = normalise_inline(raw.get("page", ""))
        if src and page in page_to_document:
            item = dict(raw)
            item.update({
                "src": src,
                "page": page,
                "alt": normalise_inline(raw.get("alt")),
                "caption": normalise_inline(raw.get("caption")),
                "title": normalise_inline(raw.get("title")),
            })
            by_url[src].append(item)

    images: list[dict] = []
    document_images: dict[str, list[str]] = defaultdict(list)
    for src, occurrences in by_url.items():
        best = max(occurrences, key=lambda item: (
            bool(item.get("caption")), bool(item.get("alt")), bool(item.get("title")),
            (item.get("width") or 0) * (item.get("height") or 0),
        ))
        document_ids = sorted({page_to_document[item["page"]] for item in occurrences})
        image_id = stable_id("img", src)
        reason = image_noise_reason(best, len(occurrences))
        record = {
            "id": image_id,
            "src": src,
            "alt": best.get("alt", ""),
            "caption": best.get("caption", ""),
            "title": best.get("title", ""),
            "width": best.get("width"),
            "height": best.get("height"),
            "document_ids": document_ids,
            "source_pages": sorted({item["page"] for item in occurrences}),
            "occurrence_count": len(occurrences),
            "is_noise": bool(reason),
            "noise_reason": reason,
            "description": "",
            "description_status": "pending" if not reason else "skipped_noise",
        }
        images.append(record)
        if not reason:
            for document_id in document_ids:
                document_images[document_id].append(image_id)

    for document in documents:
        document["image_ids"] = sorted(document_images.get(document["id"], []))
    images.sort(key=lambda item: (item["is_noise"], -len(item["caption"]), -len(item["alt"]), item["src"]))
    queue = [image for image in images if not image["is_noise"]]
    return images, queue


def validate_outputs(documents: list[dict], images: list[dict]) -> None:
    """Fail before writing if relationships or stable identifiers are broken."""
    document_ids = [document["id"] for document in documents]
    image_ids = [image["id"] for image in images]
    if len(document_ids) != len(set(document_ids)):
        raise ValueError("duplicate document ids after cleaning")
    if len(image_ids) != len(set(image_ids)):
        raise ValueError("duplicate image ids after cleaning")
    known_documents = set(document_ids)
    known_images = set(image_ids)
    for document in documents:
        unknown = set(document["image_ids"]) - known_images
        if unknown:
            raise ValueError(f"unknown image references in {document['id']}: {sorted(unknown)}")
    for image in images:
        unknown = set(image["document_ids"]) - known_documents
        if unknown:
            raise ValueError(f"unknown document references in {image['id']}: {sorted(unknown)}")


def report_markdown(report: dict) -> str:
    lines = [
        "# Cleaned crawl report",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Counts",
        "",
        f"- Raw pages: {report['counts']['raw_pages']}",
        f"- Clean documents: {report['counts']['documents']}",
        f"- Exact duplicate pages removed: {report['counts']['duplicate_pages']}",
        f"- Documents requiring review: {report['counts']['review_documents']}",
        f"- Review records including duplicates/rejections: {report['counts']['review_records']}",
        f"- Raw image occurrences: {report['counts']['raw_image_occurrences']}",
        f"- Unique images: {report['counts']['unique_images']}",
        f"- Images queued for description: {report['counts']['image_queue']}",
        f"- Images marked as noise: {report['counts']['noise_images']}",
        "",
        "## Document types",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in report["page_types"].items())
    lines.extend(["", "## Sites", ""])
    lines.extend(f"- {key}: {value}" for key, value in report["sites"].items())
    lines.extend(["", "## Metadata completeness", ""])
    lines.extend(f"- {key}: {value}" for key, value in report["metadata_completeness"].items())
    lines.extend([
        "",
        "## Files to inspect",
        "",
        "- `documents.json`: canonical clean text and metadata.",
        "- `images.json`: one record per unique image, including noise decisions.",
        "- `image_queue.json`: images worth describing before indexing.",
        "- `review_pages.json`: short, encoding-damaged, rejected, and duplicate pages.",
        "- `manifest.json`: source hashes and schema version for reproducibility.",
        "",
    ])
    return "\n".join(lines)


def schema_markdown() -> str:
    return """# Processed data schema

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
"""


def build(pages_path: Path, images_path: Path, output_dir: Path) -> dict:
    raw_pages = read_json(pages_path)
    raw_images = read_json(images_path)
    documents, rejected, page_to_document = clean_pages(raw_pages)
    images, image_queue = clean_images(raw_images, page_to_document, documents)
    validate_outputs(documents, images)
    review_documents = [
        {"url": d["url"], "title": d["title"], "reason": d["status"]}
        for d in documents if d["status"] != "ready"
    ]
    review_pages = sorted(rejected + review_documents, key=lambda item: (item["reason"], item["url"]))
    generated_at = datetime.now(timezone.utc).isoformat()
    counts = {
        "raw_pages": len(raw_pages),
        "documents": len(documents),
        "duplicate_pages": sum(item["reason"] == "exact_duplicate" for item in rejected),
        "review_documents": len(review_documents),
        "review_records": len(review_pages),
        "raw_image_occurrences": len(raw_images),
        "unique_images": len(images),
        "image_queue": len(image_queue),
        "noise_images": sum(image["is_noise"] for image in images),
    }
    report = {
        "generated_at": generated_at,
        "schema_version": SCHEMA_VERSION,
        "counts": counts,
        "page_types": dict(sorted(Counter(d["page_type"] for d in documents).items())),
        "sites": dict(sorted(Counter(d["site"] for d in documents).items())),
        "statuses": dict(sorted(Counter(d["status"] for d in documents).items())),
        "metadata_completeness": {
            "documents_with_multiple_sections": sum(len(d["sections"]) > 1 for d in documents),
            "documents_with_year": sum(d["year"] is not None for d in documents),
            "documents_with_source_date": sum(bool(d["published_at"] or d["modified_at"]) for d in documents),
            "documents_with_kept_images": sum(bool(d["image_ids"]) for d in documents),
        },
        "image_noise_reasons": dict(sorted(Counter(
            image["noise_reason"] or "kept" for image in images
        ).items())),
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "inputs": {
            "pages": {"path": pages_path.name, "sha256": file_sha256(pages_path)},
            "images": {"path": images_path.name, "sha256": file_sha256(images_path)},
        },
        "outputs": ["documents.json", "images.json", "image_queue.json", "review_pages.json", "report.json", "SCHEMA.md"],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "documents.json", documents)
    write_json(output_dir / "images.json", images)
    write_json(output_dir / "image_queue.json", image_queue)
    write_json(output_dir / "review_pages.json", review_pages)
    write_json(output_dir / "report.json", report)
    write_json(output_dir / "manifest.json", manifest)
    (output_dir / "REPORT.md").write_text(report_markdown(report), encoding="utf-8")
    (output_dir / "SCHEMA.md").write_text(schema_markdown(), encoding="utf-8")
    print(
        f"wrote {len(documents)} documents and {len(images)} unique images "
        f"({len(image_queue)} queued) to {output_dir}"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=Path, default=DATA_DIR / "pages.json")
    parser.add_argument("--images", type=Path, default=DATA_DIR / "images.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    build(args.pages.resolve(), args.images.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
