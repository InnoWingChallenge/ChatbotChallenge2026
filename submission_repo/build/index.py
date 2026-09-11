"""Indexer. STUB. Workshop 1 block 4.

Chunk the scraped text and write it to the store. Run this file
directly, after build/scrape.py, to (re)build data/chroma.

Store metadata now. Level 4 questions need to filter by year and page
type, and adding a field later means rebuilding everything.
"""
import json
from pathlib import Path

from bot.store import add_to_store, get_store

CHUNK_SIZE, OVERLAP = 800, 100


def chunk(text: str, size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[str]:
    """Fixed-size chunks with overlap.

    Overlap exists because a fact split across a boundary is lost: a
    date at char 998 and its event name at char 1002 land in different
    chunks and neither answers the question.

    TODO try a better strategy once this works: split on headings
    TODO first, fall back to characters last, and prepend the section
    TODO heading to each chunk.
    """
    text = " ".join(text.split())
    step = size - overlap
    return [text[i:i + size] for i in range(0, len(text), step) if text[i:i + size].strip()]


def build_index(pages: list[dict], reset: bool = True):
    texts, metas = [], []
    for page in pages:
        for i, piece in enumerate(chunk(page["text"])):
            texts.append(piece)
            metas.append({
                "url":      page["url"],
                "title":    page.get("title", ""),
                "position": i,
                "kind":     "text",
                # TODO add "year" and "page_type" here. Level 4 needs them.
            })
    store = get_store(reset=reset)
    add_to_store(store, texts, metas)
    print(f"indexed {len(texts)} chunks")
    return store


if __name__ == "__main__":
    pages = json.loads(Path("data/pages.json").read_text())
    build_index(pages)
