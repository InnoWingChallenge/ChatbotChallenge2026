"""Local lexical retrieval for reviewed image evidence; no model calls."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "data/image_search.sqlite"
PIPELINE = "reviewed_images_v1"


def retrieve_images(question: str, k: int = 30, where: dict | None = None,
                    path: Path = INDEX_PATH) -> list[dict]:
    # Lazy import avoids a circular import with the hybrid ranker.
    from bot.hybrid import _match_expression, _where_matches
    expression = _match_expression(question)
    if not path.exists() or not expression or k <= 0:
        return []
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        results = []
        rows = connection.execute(
            "SELECT text, metadata, bm25(evidence,0,4,2,1,0) FROM evidence "
            "WHERE evidence MATCH ? ORDER BY bm25(evidence,0,4,2,1,0), chunk_id", (expression,))
        # Filter before the result limit so undated/other-kind records cannot
        # crowd out qualifying hits. This first collection is small and local.
        for text, metadata, score in rows:
            meta = json.loads(metadata)
            if _where_matches(meta, where):
                results.append({"text": text, "metadata": meta, "bm25_score": score})
                if len(results) == k:
                    break
        return results
    finally:
        connection.close()
