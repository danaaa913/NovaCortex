# NovaCortex — Architecture

NovaCortex is a layered Telegram bot: a thin transport layer, an agent that
owns the request lifecycle, a hybrid answer pipeline (facts → cache → RAG →
web → LLM), and static knowledge/RAG subpackages. Everything is wired in
`src/novacortex/` and configured from one place (`config.py`).

## 1. Module map

| Module | Responsibility |
|---|---|
| `config.py` | CWD-relative paths (`data/`, `cache/`, `chroma_ultra/`, DB, log), verbatim constants (`RAG_CONFIDENCE_THRESHOLD`, `OFFICIAL_PDFS`, …), secret loading from env/`.env`, `missing_secrets()` / `require_secrets()` |
| `llm.py` | `_LazyLLMClient` — Groq via the OpenAI SDK (`base_url=api.groq.com`), built on **first attribute access** so imports never fail without secrets. `llm_client` (+ legacy alias `grok_client`) |
| `logging_setup.py` | Idempotent `configure_logging()` → `logs/novacortex.log` (override: `NOVACORTEX_LOG_FILE`); called from `main()` and the compatibility shim only |
| `bot/handlers.py` | Telegram transport: `/start`, `/clear`, `/privacy`, confirmed `/delete_my_data`, `/cancel`, long-message splitting and free-text handling; the heavy agent is initialized during application startup |
| `agent.py` | `YarmoukAgent.ask()` — loads embeddings + Chroma, builds retriever/cache/scope-detector/pipeline, sanitises the response (strips CJK/invisible chars), formats it, logs to SQLite; returns `{response, source, confidence, response_time_ms, docs_retrieved}` |
| `pipeline.py` | `EnhancedHybridPipeline.process_question()` — the routing brain: safety checks, facts routing, semantic cache lookup, RAG, web search, LLM fallback, confidence scoring |
| `intents.py` | `semantic_parser`, `facts_router`, `expand_colloquial_terms` — colloquial Arabic → canonical intent before routing |
| `safety.py` | `SmartOutOfScopeDetector` — out-of-scope, prompt injection, false premises, comparison refusal |
| `cache.py` | `SemanticResponseCache` — SQLite question→answer cache with cosine similarity, `SIMILARITY_THRESHOLD = 0.88`, `_is_incompatible_cache()` guard and volatile/entity-specific question exclusion |
| `quality.py` | Evidence scoring for RAG/web results plus dependency-free transport/cache helpers |
| `input_rules.py` | Dependency-free prompt-injection and false-premise gating rules |
| `memory.py` | Per-user message history + rolling summaries (SQLite, `DB_PATH`) |
| `db.py` | Schema and CRUD: users, questions, daily stats (`init_db`, `save_user`, `log_question`, …) |
| `text.py` | `ArabicProcessor`: normalise (إأآا→ا, ى→ي, ة→ه), tokenise with NLTK Arabic stopwords + Snowball stemming, language detection with a 0.6 Arabic-dominance threshold |
| `formatting.py` | Source-aware response decoration, `NO_RESULT_MESSAGE_AR/EN` |
| `knowledge/*` | Pure data: `facts` (bilingual verified facts), `faculty` (deans/colloquial terms), `careers`, `keywords`, `localization` |
| `rag/indexing.py` | `load_data_from_json()` — MD5 change detection, garbled-PDF text repair (`_fix_reversed_arabic`, `_is_garbled_content`), ExternalPlans title mapping and non-destructive chunking → Chroma. Heavy langchain imports are **lazy inside this function** |
| `rag/retriever.py` | `ImprovedHybridRetriever` — Chroma similarity + BM25 fusion (reciprocal-rank fusion), priority-1 boosting |
| `rag/reranking.py`, `rag/generation.py` | LLM re-ranking and grounded answer synthesis with citations |
| `rag/web_search.py` | Serper fallback with Arabic/English query shaping; reads HTML/PDF evidence from verified `yu.edu.jo` hosts and falls back to snippets |
| `rag/pdf.py` | `PDFExtractor.fetch_and_extract` — `pdfplumber` imported lazily inside the method |
| `__main__.py` | `python -m novacortex` → `bot.handlers.main()` |

The root `NovaCortexbot.py` is a **compatibility shim**: it re-exports the
public names of the package so old commands (`python NovaCortexbot.py`,
`from NovaCortexbot import …`) keep working.

## 2. Request flow

```
Telegram update
  └─ bot/handlers.handle_message
       └─ YarmoukAgent.ask(question, user_id)
            ├─ db.get_user / update_user_activity          (profile, study level)
            ├─ text.detect_language(question)              (ar / en)
            ├─ pipeline.process_question(...)
            │    ├─ safety: out-of-scope / injection / false premise
            │    ├─ intents: expand_colloquial_terms → facts_router
            │    ├─ knowledge/facts: deterministic answer (source="verified_facts")
            │    ├─ cache: semantic hit?                (source="cache")
            │    ├─ rag:  retriever (Chroma ⊕ BM25) → rerank → evidence gate → generate (source="rag")
            │    ├─ web:  serper search → evidence score → synthesize + source links (source="web")
            │    └─ llm:  direct Groq fallback          (source="llm")
            ├─ agent._sanitize_response                  (CJK / bidi cleanup)
            ├─ formatting.format                         (source-aware decoration)
            └─ db.log_question                           (analytics for dashboard.py)
```

Every answer carries a `source` and `confidence`; the dashboard
(`scripts/dashboard.py`) aggregates these fields from `novacortex_v12.db`.

## 3. Knowledge-base indexing flow

```
data/yarmouk_data.json ── MD5 (cache/data_hash.txt) ── unchanged? skip
        │ changed
        ├─ garbled-PDF repair: _is_garbled_content → _fix_reversed_arabic
        ├─ title fixes: EXTERNAL_PLANS_TITLE_MAP
        ├─ structure-aware chunking without destructive first/last truncation
        └─ HuggingFaceEmbeddings("intfloat/multilingual-e5-large-instruct")
             → chroma_ultra/ vector store
```

`main()` calls `load_data_from_json()` at startup, so deleting `chroma_ultra/`
or editing the JSON triggers a rebuild on the next run.

## 4. Design decisions

- **Lazy LLM client** (`llm.py`) — the OpenAI/Groq client is constructed on
  first use, so `import novacortex` (and the test suite) works in environments
  where secrets or network are unavailable.
- **Lazy heavy imports** — `pdfplumber` (inside `PDFExtractor`) and the
  langchain trio (inside `load_data_from_json()`) are imported at call time.
  Importing the package therefore never requires the full RAG stack.
- **Secrets at the edge** — `config.py` reads empty defaults from the
  environment; `require_secrets()` is invoked from `main()`, not at import
  time, and reports exactly which keys are missing.
- **Single configuration point** — paths and thresholds live in `config.py`;
  environment overrides (`NOVACORTEX_*`) are honoured there. Scripts mirror
  this by anchoring to the repository root via `Path(__file__).parents[1]`.
- **Idempotent logging** — `configure_logging()` can be called from both the
  shim and `main()` without duplicating handlers.
- **CWD-relative runtime paths** — `data/`, `cache/`, `chroma_ultra/`,
  `novacortex_v12.db` and `logs/` resolve from the working directory; run the
  bot from the project root (or set the `NOVACORTEX_*` overrides).

## 5. Data & artefacts

| Path | Tracked? | Notes |
|---|---|---|
| `data/yarmouk_data.json` | yes | the knowledge base (JSON list, `priority` field boosts retrieval) |
| `novacortex_v12.db` | no | users/questions/stats; also read by `scripts/dashboard.py` |
| `cache/` | no | BM25 index cache + `data_hash.txt` change marker |
| `chroma_ultra/` | no | Chroma vector store (auto-rebuilt) |
| `*.pkl` (root) | no | large BM25 corpora (`bm25_docs.pkl` ≈ 4.5 GB) — unused by the current code |
| `logs/novacortex.log` | no | current log; `logs/archive/` holds historical logs |
| `dashboard_output/` | no | generated HTML/markdown analytics |

## 6. Testing strategy

- **Static**: every module must parse (checked on multiple Python versions),
  all `from novacortex.x import y` targets must exist, and the import graph
  must stay acyclic.
- **Unit** (`tests/test_unit_*.py`): Arabic text helpers and the static
  knowledge/config invariants — no network, no DB, no model downloads.
- **Data integrity** (`tests/test_data_integrity.py`): JSON validity, garbled
  text, title fixes, priority coverage (non-fatal, warns like the original),
  plus regression markers (e.g. `SIMILARITY_THRESHOLD = 0.88`) asserted
  against the package sources. Runnable with or without pytest.
- **Integration** (`tests/test_bot_internal.py`): full agent round-trips,
  gated behind `NOVACORTEX_RUN_INTEGRATION=1` because it needs a working
  environment, network and the embedding model.

## 7. Legacy

`legacy/` contains orphaned pre-refactor files (`config.py`, `constants.py`,
`database.py`, `AA.txt`) that were never imported by the bot. They are kept
for reference only and are not on the import path.
