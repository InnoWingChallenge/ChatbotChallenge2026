# Deprecated

These files are from the old, monolithic prototype and are **no longer used**.
They have been kept here for reference only. The current, authoritative
submission scaffold lives in [`../submission_repo/`](../submission_repo/)
(`main.py` + `bot/` + `build/`), as documented in
[`../Labs/Notebook_Guide.md`](../Labs/Notebook_Guide.md).

Do not build against anything in this folder.

| File | Why deprecated |
|---|---|
| `main.py` | Old monolithic entry point (`generate_rag_answers`). Superseded by `submission_repo/main.py` + `bot/answer.py`. |
| `chroma_db/` | Prebuilt index read only by the old `main.py`. The submission repo builds its own index under `data/chroma`; the labs ship `sample_chroma/`. |
| `describe_image.py` | Standalone vision helper. Superseded by `submission_repo/bot/llm.py` (`describe_image`). |
| `data.json` | Scraped corpus consumed only by `check_chunks.py`. |
| `check_chunks.py` | One-off chunking debug script (depends on `langchain_text_splitters`, which was never in `requirements.txt`). |
| `questions.json` | Sample question list, unreferenced. |
| `testing.py` | Standalone gateway smoke-test, unreferenced. |
