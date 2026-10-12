# NovaCortex

Bilingual (Arabic/English) Telegram assistant for **Yarmouk University** — answers
admissions, faculties, fees, study-plan and campus questions using a hybrid of
verified facts, a RAG vector index over the scraped university knowledge base,
web search and an LLM fallback, with guardrails, semantic caching and per-user
conversation memory.

The implementation used to live in a single ~4,200-line `NovaCortexbot.py`.
It is now a normal Python package under `src/novacortex/`; the original file
remains only as a thin compatibility shim.

## Features

- **Verified facts first** — deterministic answers for curated questions
  (founding date, deans, admissions, careers, …) with 100% confidence.
- **Hybrid RAG** — Chroma vector store + BM25 with reciprocal-rank fusion,
  cross-encoder-style reranking, priority boosting and per-document chunk caps.
- **Web-search fallback** — Serper (Google) search when the index is not enough.
- **Guardrails** — out-of-scope detection, prompt-injection blocking,
  false-premise correction and comparison-request refusal.
- **Semantic cache** — SQLite-backed cosine cache with a tunable similarity
  threshold (0.88). Time-sensitive, person-specific and numeric questions are
  excluded so a similar old question cannot reuse a stale answer.
- **Memory** — per-user conversation history with rolling summaries.
- **Bilingual NLP** — Arabic normalisation/tokenisation/stemming (NLTK
  Snowball) and language detection with an Arabic-dominance threshold.
- **Auto-reindex** — MD5 of `data/yarmouk_data.json` is cached; the vector
  store rebuilds itself when the knowledge base changes without dropping the
  middle sections of long source documents.

## Requirements

- Python **3.10+** (the pinned dependency stack requires it; the source itself
  is written to stay import-compatible with older interpreters).
- A working virtual environment with the dependencies from `requirements.txt`
  (or `pip install -e .`).

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
pip install -e .              # optional: installs the `novacortex` command
```

## Configuration

Secrets are read from the environment, optionally via a git-ignored `.env`
file in the project root:

```bash
cp .env.example .env          # then fill in your keys
```

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | yes | Groq LLM (OpenAI-compatible endpoint) |
| `TELEGRAM_TOKEN` | yes | Telegram bot token (@BotFather) |
| `SERPER_API_KEY` | yes | Serper.dev web search (RAG fallback) |
| `GEMINI_API_KEY` | no | used only by legacy/auxiliary tooling |
| `NOVACORTEX_DATA_DIR` | no | knowledge-base directory (default `data/`) |
| `NOVACORTEX_DB_PATH` | no | SQLite database (default `novacortex_v12.db`) |
| `NOVACORTEX_LOG_FILE` | no | log file (default `logs/novacortex.log`) |

The bot refuses to start when a required secret is missing (`require_secrets`).

> **Security note:** all keys that ever lived in this repository were moved
> out of source control. Rotate any key that was previously committed, and
> keep `.env` out of git (`.gitignore` already excludes it).

## Running

Run from the project root (paths such as `data/`, `cache/`, `chroma_ultra/`
and the SQLite database are CWD-relative):

```bash
python -m novacortex          # preferred
python NovaCortexbot.py       # legacy shim (same entry point)
novacortex                    # if installed with `pip install -e .`
```

Bot commands: `/start` (registration conversation), `/clear` (wipe memory),
`/privacy` (show stored-data information), `/delete_my_data CONFIRM` (delete
the profile, question log and memory), `/cancel` (abort conversation), then
ask anything in the free-text handler.

## Project layout

```
NovaCortes/
├── NovaCortexbot.py        # thin compatibility shim (imports from the package)
├── pyproject.toml          # package metadata, entry point, pytest config
├── requirements.txt
├── .env / .env.example     # secrets (git-ignored) / template
├── src/novacortex/         # the actual implementation
│   ├── config.py           # paths, constants, secrets, require_secrets()
│   ├── llm.py              # lazy Groq/OpenAI-compatible client
│   ├── logging_setup.py    # configure_logging() -> logs/novacortex.log
│   ├── bot/handlers.py     # Telegram handlers + main()
│   ├── agent.py            # YarmoukAgent.ask() orchestrator
│   ├── pipeline.py         # EnhancedHybridPipeline (routing/answering)
│   ├── intents.py          # semantic parser, facts router, colloquial terms
│   ├── safety.py           # out-of-scope / injection / false-premise guards
│   ├── cache.py            # semantic answer cache (SQLite, threshold 0.88)
│   ├── memory.py           # per-user history + summaries
│   ├── db.py               # users/questions/stats schema
│   ├── text.py             # ArabicProcessor (normalise/tokenise/detect)
│   ├── formatting.py       # response formatting + no-result messages
│   ├── knowledge/          # static data: facts, faculty, careers, keywords
│   └── rag/                # indexing, chroma retrieval, web search,
│                           # reranking, answer generation, PDF extraction
├── data/                   # knowledge base JSON (yarmouk_data.json, …)
├── tests/                  # pytest suite (data integrity + unit + gated E2E)
├── scripts/                # scrapers, data cleaners, dashboard, generators
├── docs/architecture.md    # module map and request-flow documentation
├── legacy/                 # orphaned pre-refactor files (not imported)
└── logs/                   # novacortex.log + archive/ of historical logs
```

Runtime artefacts that stay **out of git** (see `.gitignore`): `cache/`,
`chroma_ultra/`, `*.pkl` (BM25 corpora), `*.db`, `*.log`, `dashboard_output/`,
`synthetic_questions.json`.

## Tests

```bash
python -m pytest                    # from the project root
python tests/test_data_integrity.py # standalone, no pytest needed
```

- `tests/test_data_integrity.py` — knowledge-base integrity (JSON validity,
  garbled-text detection, title fixes, priority coverage) plus syntax and
  regression-marker checks over the whole package.
- `tests/test_unit_text.py` — Arabic normalisation / language detection.
- `tests/test_unit_knowledge.py` — static knowledge + config sanity.
- `tests/golden_questions.json` + `scripts/evaluate_answers.py` — content-level
  evaluation of sources, required facts, forbidden claims and abstention.
- `tests/test_bot_internal.py` — end-to-end agent test, **skipped unless**
  `NOVACORTEX_RUN_INTEGRATION=1` (needs a working environment + network).

## Scripts

All scripts are run from the project root (`python scripts/<name>.py`) and
anchor their data paths to the repository root:

| Script | Purpose |
|---|---|
| `yu_scraper.py` | full YU site scraper → `data/yarmouk_data_new.json` |
| `update_facts_db.py` | incremental facts/scraper merge |
| `yarmouk_missing_scraper.py` | targeted PDF/plan backfill (`--input/--only`) |
| `clean_data.py` / `safe_data_cleaner.py` | noise removal pipeline |
| `Generate synthetic questions.py` | LLM-generated training questions |
| `dashboard.py` | Plotly/HTML analytics dashboard → `dashboard_output/` |

## Documentation

See [`docs/architecture.md`](docs/architecture.md) for the module map, the
request flow through the pipeline, and notes on the lazy-import design.
