"""Build matching dense and BM25 indexes from the cleaned text corpus.

Run after ``build/clean.py``. Both indexes use the same stable chunk IDs:
Chroma provides semantic retrieval, while SQLite FTS5 provides exact-term
BM25 retrieval for names, dates, acronyms, and model numbers.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.store import add_to_store, get_store


CHUNK_SIZE = 800
OVERLAP = 100
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_PATH = PROJECT_ROOT / "data" / "processed" / "documents.json"
FTS_PATH = PROJECT_ROOT / "data" / "text_search.sqlite"

# Benchmark instructions and empty WordPress/gallery shells are retrieval
# distractors rather than evidence. Short Treasure Hunt and physical-space
# records remain indexable because they may contain unique facts.
EXCLUDED_URL_MARKERS = (
    "/aichallenge/",
    "/ai-chatbot-challenge-inno-trivia-duplicate-",
)
EXCLUDED_TITLES = {"hello world!"}
GENERIC_SHORT_TITLES = {"photo gallery"}

BOUNDARY_RE = re.compile(
    r"^(?:"
    r"important dates?|application and review|application and cover period|"
    r"general application guidelines?|first round(?:\b|:)|second round(?:\b|:)|"
    r"winners?|awards?(?:\s*&\s*prizes)?|finalists?|the best presenter|"
    r"about the activity|briefing session|eligibility|"
    r"team information|project information|project descriptions?|"
    r"equipment|facilit(?:y|ies)|location|description|mission|"
    r"applicants should arrange|the scheme will be overseen|periodic reviews|"
    r"students are required to submit"
    r")[^\n]{0,100}$",
    flags=re.IGNORECASE,
)


def is_indexable(page: dict) -> bool:
    """Return whether a cleaned document contains useful retrieval evidence."""
    url = str(page.get("url", "")).casefold()
    title = " ".join(str(page.get("title", "")).split()).casefold()
    text = str(page.get("text", "")).strip()
    if not text or any(marker in url for marker in EXCLUDED_URL_MARKERS):
        return False
    if title in EXCLUDED_TITLES or title.startswith("elementor #"):
        return False
    if title in GENERIC_SHORT_TITLES and len(text) < 300:
        return False
    return True


def _prefix(title: str = "", heading: str = "", page_type: str = "",
            year: int | None = None) -> str:
    lines = []
    if title:
        lines.append(f"Page title: {' '.join(title.split())}")
    if page_type:
        lines.append(f"Page type: {page_type}")
    if year is not None:
        lines.append(f"Year: {year}")
    if heading and heading.casefold() != title.casefold():
        lines.append(f"Section: {' '.join(heading.split())}")
    return "\n".join(lines) + ("\n" if lines else "")


def _logical_blocks(text: str) -> list[str]:
    """Keep lists/table-like fields together and split at semantic labels."""
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        if current and BOUNDARY_RE.match(line):
            blocks.append("\n".join(current))
            current = []
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _word_windows(text: str, size: int, overlap: int) -> list[str]:
    """Split an oversized logical block without cutting through words."""
    words = text.split()
    windows: list[str] = []
    start = 0
    while start < len(words):
        end = start
        length = 0
        while end < len(words):
            added = len(words[end]) + (1 if end > start else 0)
            if end > start and length + added > size:
                break
            length += added
            end += 1
        if end == start:
            end += 1
        windows.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        kept = 0
        next_start = end
        while next_start > start and kept < overlap:
            next_start -= 1
            kept += len(words[next_start]) + 1
        # A very short window can itself be smaller than the requested
        # overlap. In that case retaining it would revisit the same start
        # forever, so advance to the next unseen word.
        start = next_start if start < next_start < end else end
    return windows


def chunk(text: str, size: int = CHUNK_SIZE, overlap: int = OVERLAP,
          heading: str = "", title: str = "", page_type: str = "",
          year: int | None = None) -> list[str]:
    """Make structure-aware chunks with source context embedded in each one."""
    prefix = _prefix(title=title, heading=heading, page_type=page_type, year=year)
    body_size = size - len(prefix)
    if body_size <= overlap or overlap < 0:
        raise ValueError("chunk size must exceed prefix length and overlap")

    output: list[str] = []
    for block in _logical_blocks(text):
        for window in _word_windows(block, body_size, overlap):
            output.append(prefix + window)
    return output


def prepare_chunks(pages: list[dict]) -> tuple[list[dict], int]:
    """Return the single chunk representation shared by both indexes."""
    records: list[dict] = []
    excluded = 0
    for page in pages:
        if not is_indexable(page):
            excluded += 1
            continue
        sections = page.get("sections") or []
        section_text = "\n".join(str(section.get("text", "")) for section in sections)
        coverage = len(section_text) / max(1, len(str(page.get("text", ""))))
        # Elementor often renders important visual headings as plain divs. If
        # semantic sections miss too much (or collapse to one unnamed block),
        # use the complete cleaned page text so labels such as Winners and
        # Application and review remain available to the logical splitter.
        if coverage < 0.9 or (len(sections) == 1 and not sections[0].get("heading")):
            sections = [{"heading": "", "text": page["text"]}]
        position = 0
        for section in sections:
            pieces = chunk(
                section.get("text", ""),
                heading=section.get("heading", ""),
                title=page.get("title", ""),
                page_type=page.get("page_type", ""),
                year=page.get("year"),
            )
            for piece in pieces:
                document_id = str(page.get("id", ""))
                chunk_id = f"txt_{document_id or len(records)}_{position}"
                metadata = {
                    "chunk_id": chunk_id,
                    "url": page["url"],
                    "title": page.get("title", ""),
                    "position": position,
                    "kind": "text",
                    "document_id": document_id,
                    "site": page.get("site", ""),
                    "status": page.get("status", "ready"),
                }
                if section.get("heading"):
                    metadata["section"] = str(section["heading"])
                if page.get("year") is not None:
                    metadata["year"] = int(page["year"])
                if page.get("academic_year"):
                    metadata["academic_year"] = str(page["academic_year"])
                if page.get("page_type"):
                    metadata["page_type"] = str(page["page_type"])
                records.append({"id": chunk_id, "text": piece, "metadata": metadata})
                position += 1
    return records, excluded


def build_fts_index(records: list[dict], path: Path = FTS_PATH) -> None:
    """Atomically replace the local SQLite FTS5/BM25 index."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    try:
        connection.execute(
            """
            CREATE VIRTUAL TABLE chunks USING fts5(
                chunk_id UNINDEXED,
                document_id UNINDEXED,
                position UNINDEXED,
                title,
                section,
                text,
                url UNINDEXED,
                page_type UNINDEXED,
                year UNINDEXED,
                status UNINDEXED,
                tokenize='porter unicode61 remove_diacritics 2'
            )
            """
        )
        rows = []
        for record in records:
            meta = record["metadata"]
            rows.append((
                record["id"], meta.get("document_id", ""), meta.get("position", 0),
                meta.get("title", ""), meta.get("section", ""), record["text"],
                meta.get("url", ""), meta.get("page_type", ""), meta.get("year", ""),
                meta.get("status", "ready"),
            ))
        connection.executemany(
            "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
        )
        connection.commit()
    except sqlite3.OperationalError as exc:
        raise RuntimeError(
            "SQLite FTS5 is unavailable in this Python build; use the project .venv."
        ) from exc
    finally:
        connection.close()
    temporary.replace(path)


def build_index(pages: list[dict], reset: bool = True):
    if not pages:
        raise ValueError("No pages to index; refusing to reset the existing index")
    records, excluded = prepare_chunks(pages)
    if not records:
        raise ValueError("No indexable text remained after quality filtering")

    build_fts_index(records)
    store = get_store(reset=reset)
    add_to_store(
        store,
        [record["text"] for record in records],
        [record["metadata"] for record in records],
        ids=[record["id"] for record in records],
    )
    print(
        f"indexed {len(records)} text chunks; excluded {excluded} noise documents; "
        f"wrote BM25 index to {FTS_PATH}"
    )
    return store


def main() -> None:
    if not DOCUMENTS_PATH.exists():
        raise SystemExit(
            "Missing data/processed/documents.json. Run python build/clean.py first."
        )
    pages = json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))
    if not pages:
        raise SystemExit(
            "data/processed/documents.json contains no documents; "
            "refusing to reset the existing index."
        )
    build_index(pages)


if __name__ == "__main__":
    main()
