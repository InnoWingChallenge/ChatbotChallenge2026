# InnoWing Chatbot Challenge 2026

## Mission

Build a retrieval-augmented chatbot about HKU's Tam Wing Fan Innovation Wing. The Codabench benchmark asks one question at each of five levels:

1. general knowledge;
2. exact text retrieval from an Innovation Academy page;
3. visual retrieval from an image;
4. aggregation or comparison across facts;
5. physical-world knowledge gathered inside the Innovation Wing.

The score is the mean of the five AI-judged answers. Prefer short, direct answers containing every requested fact.

Challenge page: <https://innoacademy.engg.hku.hk/aichallenge/>

## Source of truth

- `submission_repo/` is the deliverable. Run and package the bot from this directory.
- `submission_repo/main.py`, `bot/llm.py`, and `bot/store.py` are provided interfaces. Preserve `main.py` unless the challenge rules change.
- Implement answer behaviour in `submission_repo/bot/answer.py` and ingestion in `submission_repo/build/`.
- `submission_repo/dev_set.json` is a practice set, not evidence about the private benchmark questions.
- `Labs/` and `Slides/` are learning material. Do not package them with the submission.
- `deprecated/` is historical reference only.

When new websites, photographs, or on-site notes are supplied, preserve their provenance. Record at least the source URL or physical location, retrieval/observation date, content type, and a stable local identifier. Keep raw captures separate from derived chunks and image descriptions so the database can be rebuilt without recrawling.

## Build pipeline

Run commands from `submission_repo/` using Python 3.9 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python check_setup.py
python build/scrape.py
python build/clean.py
python build/index.py
python build/images.py --describe-only
python build/images.py --index-only
```

The expected generated artifacts live under `submission_repo/data/`, including scraped page/image records, cached image descriptions, and the Chroma index. Image understanding belongs at ingestion time; answering must use cached descriptions and finish within 30 seconds per question.
`build/index.py` resets the Chroma collection, including existing image chunks;
after every text-index rebuild, rerun `python build/images.py --index-only`.

### API access

The HKU Azure gateway is network-restricted. A `403 Forbidden` from chat,
embedding, or vision calls normally means the machine is outside the HKU
network: connect to the HKU VPN, then rerun `python check_setup.py`. Preserve
the configured gateway routes while diagnosing a 403. Treat `401 Unauthorized`
as a key or `.env` problem instead. Agents may run offline tests without the
VPN, but the user must run live API checks and ingestion after connecting.

Before changing retrieval, inspect retrieved chunks separately from generated answers. Store metadata needed for filtering and aggregation, including `url`, `title`, `kind`, page type, year when available, and chunk position. Batch embedding calls and keep image descriptions rich enough to capture visible text, counts, colours, spatial relationships, equipment, and signs.

## Verification

From `submission_repo/`, verify in this order:

```powershell
python check_setup.py
python main.py "What is 3D printing also known as?"
python main.py "question one" "question two"
```

Completion requires one stdout line per question, answers in input order, no unhandled exception, and an average runtime below 30 seconds per question. Put diagnostics on stderr so stdout remains grader-safe. Test text, visual, aggregate, and physical-world retrieval after every index rebuild.

## Submission

Create one `.zip` whose root contains `main.py`, `bot/`, `build/`, required dependencies/configuration, and the built `data/` artifacts. Inspect the archive before uploading: `main.py` must be at the archive root, and local environments, secrets, logs, Labs, Slides, and Git metadata must be absent.

Never commit `.env`, API keys, or other credentials. Use Git for each coherent change: inspect `git status`, stage only intended files, and commit with a focused message. Preserve unrelated local modifications and generated data unless the current task explicitly owns them.
