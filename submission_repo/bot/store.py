"""Vector store wrapper. GIVEN. You should not need to edit this file.

A thin layer over chromadb, kept deliberately small so you can see
through it. If you need something it does not do, edit it or bypass it.
"""
from pathlib import Path

import chromadb

from bot.llm import embed

DEFAULT_PATH = "data/chroma"
DEFAULT_NAME = "chatbot"

# One PersistentClient per path, cached for the life of the process.
# chromadb caches internal state per path, so deleting the folder and
# opening a fresh PersistentClient while an earlier one is still alive
# in this process corrupts the connection: the next call fails with
# "attempt to write a readonly database" or "database is locked". This
# only bites if get_store(reset=True) runs more than once in one Python
# process, e.g. build/index.py and bot/answer.py both imported into the
# same interactive session, so it will not show up in a normal
# `python build/index.py` run, only in a notebook or a test harness.
_stores: dict = {}


def get_store(path: str = DEFAULT_PATH, name: str = DEFAULT_NAME, reset: bool = False):
    """Open (or create) a persistent Chroma collection.

    reset=True deletes and recreates the collection, not the directory,
    so it is safe to call more than once in the same process.
    """
    if path not in _stores:
        # First time this path is opened in this process. Safe to wipe a
        # stale, wrong-chromadb-version index here, since no client for
        # this path exists yet.
        if reset and Path(path).exists():
            import shutil
            shutil.rmtree(path)
        try:
            _stores[path] = chromadb.PersistentClient(path=path)
        except KeyError as e:
            raise RuntimeError(
                f"chromadb could not read the index at {path} ({e}). It was likely "
                f"built by a different chromadb version. Delete that folder and "
                f"rebuild, or install the pinned version from requirements.txt."
            ) from None

    client = _stores[path]
    if reset:
        try:
            client.delete_collection(name)
        except Exception:
            pass
    return client.get_or_create_collection(name)


def add_to_store(store, texts: list[str], metadatas: list[dict],
                  ids: list[str] = None, batch_size: int = 128) -> None:
    """Embed and insert. Batches both the embedding call and the write."""
    ids = ids or [f"c{i}" for i in range(len(texts))]
    for i in range(0, len(texts), batch_size):
        sl = slice(i, i + batch_size)
        store.add(
            ids=ids[sl], documents=texts[sl],
            embeddings=embed(texts[sl]), metadatas=metadatas[sl],
        )


def query(store, question: str, k: int = 5, where: dict = None) -> list[dict]:
    """Return the k nearest chunks as dicts with text, metadata, distance.

    Chroma returns squared L2 distance by default, so lower is closer.
    """
    r = store.query(query_embeddings=embed([question]), n_results=k, where=where or None)
    return [
        {"text": d, "metadata": m, "distance": dist}
        for d, m, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
    ]
