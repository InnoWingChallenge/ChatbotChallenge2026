# Innovation Academy website image descriptions

Target website: https://innoacademy.engg.hku.hk/ . This collection is separate from the local-photo records in `prompt/`.

The pipeline discovers public WordPress media and images referenced by site pages, preserves webpage context and original source URLs, downloads image bytes, deduplicates identical content and generates English paragraph descriptions using the five fields in Lab 4. Descriptions retain exact readable wording, visible counts, spatial relationships and identifying colours/materials. Missing location information is allowed. Quoted non-English source wording is preserved for exact retrieval, while explanatory prose is English.

`DESCRIPTION_PROMPT.txt` is the instruction sent to the vision model. Completed descriptions are written to `innoacademy/descriptions/<image_id>/prompt.md`; these are the knowledge documents intended for subsequent ingestion. `manifest.json`, `pages.json`, `failures.json` and `status.json` record sources and progress. Original image bytes and source-page captures are kept separately under `submission_repo/data/web_academy/`. A pending or failed image must not be represented as a completed visual description. Exact byte duplicates share one description while keeping all source occurrences.

Current description method: direct visual inspection by the assistant, as requested by the user. `innoacademy/manual_reviews.json` records completed reviews by original-image SHA-256, and `status.json` combines this registry with download progress. The optional gateway description command below is retained for future use but is not required for direct review. No gateway call is needed to save an assistant-authored description.

Run collection commands from the repository root:

```powershell
python submission_repo/build/web_image_collection.py discover
python submission_repo/build/web_image_collection.py download
python submission_repo/build/web_image_collection.py report
```

Directly inspected descriptions are saved with `submission_repo/build/save_web_manual.py`, using an explicit image batch and authored paragraph records. This writer verifies source hashes and preserves webpage context separately from visible evidence. It does not infer or generate visual facts. For a future accessible gateway, `python submission_repo/build/web_image_collection.py describe --limit 5` runs an optional trial and `describe` without the limit resumes the API batch.

The pipeline checkpoints each completed image and can resume. Existing local-photo prompts and Chroma data are not rebuilt by these commands. Page captions and surrounding text are stored as context, separately from the visible-image description. Website coverage is reported against discovered pages and public media; undiscoverable, inaccessible or subsequently uploaded images cannot be guaranteed. Check `status.json` for the actual number of completed descriptions before ingestion.
