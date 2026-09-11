# Chatbot Challenge 2026: Notebook Guide

Five notebooks. These are lab exercises for the two workshops, not your
submission.

## What you submit

Your bot is the `.py` package in your forked repository:

```
main.py              given, frozen, the entry point
bot/
  answer.py          you write this: rag_answer, rag_answer_batch
  llm.py             given: the gateway client
  store.py           given: the vector store wrapper
build/
  scrape.py          you write this: crawl and extract
  index.py           you write this: chunk and index
  images.py          you write this: describe and index images
check_setup.py       given: run this before Workshop 1
```

Edit `bot/answer.py` and the files under `build/` directly. Run your bot
with `python main.py "question"` from a terminal, the same command the
grader uses.

## The lab notebooks

| Notebook | Workshop | Block | Time |
|---|---|---|---|
| `lab1_inspecting_retrieval.ipynb` | 1 | 3 | 15 min |
| `lab2_test_and_iterate.ipynb` | 1 | 5 | 25 min |
| `lab3_diagnosing_image_failures.ipynb` | 2 | 2 | 25 min |
| `lab4_description_prompt.ipynb` | 2 | 3 | 20 min |
| `lab5_query_decomposition.ipynb` | 2 | 4 | 20 min |

Each notebook is self-contained. The setup and helper cells are repeated
in full, so you can open any one of them on its own and run it top to
bottom without importing anything from the others.

## Setup

```
pip install -r requirements.txt
jupyter lab
```

## Your API key and the gateway

The first cell of every notebook asks for your key with `getpass`, so it
is not echoed to the screen and never written to disk. It lives in
memory until the kernel stops.

The gateway is **Azure OpenAI**, which differs from the plain OpenAI API
in three ways that matter:

- **You address a deployment, not a model.** `model="text-embedding-3-small"`
  is the name someone gave the deployment when it was created. It may not
  match the model name at all.
- **Every call needs an `api-version`.** It is pinned in the setup cell.
- **This gateway routes by capability**, so chat, vision and embeddings
  sit at different URLs. The setup cell builds three separate clients
  for this reason: `chat_client`, `vision_client`, `embed_client`.

The setup cell already has the real values, so there is nothing to fill
in. For reference:

| | |
|---|---|
| Chat endpoint | `https://api-iw.azure-api.net/sig-shared-jpeast-increased` |
| Embedding endpoint | `https://api-iw.azure-api.net/sig-embedding` |
| API version | `2025-01-01-preview` |
| Chat deployment | `gpt-4o-mini` |
| Vision deployment | `gpt-5-mini` |
| Embedding deployment | `text-embedding-3-small` |

Chat and vision are separate deployments. `describe_image` uses the
vision one; everything else uses chat.

This gateway wants the **full path** as the endpoint: deployment,
operation and api-version included, which is why one client only ever
talks to one deployment:

```
chat    .../sig-shared-jpeast-increased/deployments/gpt-4o-mini/chat/completions?api-version=...
vision  .../sig-shared-jpeast-increased/deployments/gpt-5-mini/chat/completions?api-version=...
embed   .../sig-embedding/openai/deployments/text-embedding-3-small/embeddings?api-version=...
```

Notice the chat route has no `/openai` segment and the embedding route
does. That is correct. Do not make them match.

**Do not commit a notebook with a key visible in its output.** If you
do, the key is rotated and your submission breaks. Clear outputs before
pushing:

```
jupyter nbconvert --clear-output --inplace *.ipynb
```

## The labs chain together

Each lab reads what the previous one left on disk. Run them in order.

| Notebook | Needs | Leaves behind |
|---|---|---|
| 1 | `sample_chroma/`, `dev_set.json` | your two retrieval numbers |
| 2 | `sample_corpus/`, `dev_set.json` | `data/chroma`, `experiment_log.csv` |
| 3 | `data/chroma` | `data/images.json` |
| 4 | `data/images.json`, `images/` | `data/descriptions.json`, image chunks in `data/chroma` |
| 5 | `data/chroma` with image descriptions | a working decomposition function |

Everything after lab 2 opens the same Chroma collection: `data/chroma`,
collection name `workshop`. **Run lab 2 before Workshop 2**, or labs 3,
4 and 5 will have nothing to read.

If you miss a session, the notebook still runs. Lab 3 rebuilds the image
inventory itself, and labs 4 and 5 will tell you plainly which file is
missing.

## Provided in the workshop folder

- `dev_set.json` — 15 questions with answers, three per level
- `sample_corpus/` — small text corpus for labs 1 and 2
- `sample_chroma/` — the sample corpus already indexed, for lab 1
- `images/` — five Inno Wing photographs, for labs 3 and 4

## The labs and your submission are separate

The labs run entirely on the sample corpus, in their own `data/chroma`
folder. Your submission runs on the real Inno Wing sites, in its own
`data/chroma` folder, inside your forked repository. Nothing is shared
between the two, and nothing needs to be copied from one to the other.

The labs teach you the technique. You then apply that technique for
real when you write `build/scrape.py`, `build/index.py`,
`build/images.py` and `bot/answer.py` in your own repository.

A reasonable order:

1. Before Workshop 1: nothing
2. Workshop 1: labs 1 and 2, on the sample corpus
3. Between the workshops: write `build/scrape.py` and `build/index.py`
   in your repository, against the real sites
4. Workshop 2: labs 3, 4 and 5, on the sample corpus
5. Between Workshop 2 and 21 October: write `build/images.py` and
   `bot/answer.py` in your repository

## If chromadb raises KeyError: '_type'

An index on disk was written by a different version of chromadb than the
one installed. The stored config is missing a field the new version
expects, and it fails while opening the collection.

Delete the index and rebuild:

```
rm -rf data/chroma sample_chroma      # Windows: rmdir /s data\chroma
```

`sample_chroma/` comes from your organiser, so ask for a rebuild rather
than rebuilding it yourself. `data/chroma` you rebuild by re-running
`build/index.py`.

`requirements.txt` pins chromadb for this reason. Installing an
unpinned version is the usual cause.
