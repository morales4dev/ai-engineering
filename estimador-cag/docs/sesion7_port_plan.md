# Session 7 live — agreed incorporation plan

Bring Lidr `session_07_live` lab into `estimador-cag` without copying Rails, without `EstimationService`, and without rewriting the CAG we already shipped. FastAPI is the only backend. Streamlit is HTTP-only. Schema changes go through Alembic. Do not implement until the steps are executed in order. After each step, stop for review. Do not start the next step until told.

This file is the handoff. Closed plans (`pre-sesion7_plan.md`, `sesion6_port_plan.md`, …) are read-only except to reuse the import-rewrite rule and the `compare.py` sys.path trap.

## Handoff (start here in a new session)

| | Path / value |
|---|---|
| Ours | `/home/morales4dev/wsTakeoff/ai-engineering` branch `session_07_forense` @ `df31470`, app `estimador-cag/` |
| Reference | `/home/morales4dev/wsTakeoff/ai-engineering-lidr` (not `ai-engineering-lidr-temp` — same SHAs, no extra files) |
| Lab copy-from | Lidr `ee2e947` «session 07 code» — still `estimator/app/embedding_pipeline/` |
| Runtime-config copy-from | Lidr `b544ace` (`foundation/llm/runtime_config.py`, `api/config.py`). Land at `src/services/runtime_config.py` + `src/routers/config.py`. Do not copy their wrapper Router. |
| Persist spec | Lidr Rails table `chunking_comparisons` (`estimator-web/db/migrate/20260604150000_create_chunking_comparisons.rb`). **Not** in Lidr FastAPI. We put it in **our** Postgres via Alembic, like `estimations` / Recent. |
| Layout | Lidr `estimator/app/…`. Ours `estimador-cag/src/…`. |
| Already shipped | Pre-sesión 7: `src/embedding_pipeline/` (structural + embedder + `POST /embeddings/ingest`), `scripts/compare.py`, sample **15**, `tiktoken>=0.7.0`, scripts volume. CAG / sessions / ingest POST unchanged. |
| Not in tree | strategies, `base.py`, `comparison.py`, `/embeddings/compare`, `compare_chunkers.py`, `test_queries.json`, runtime config, `chunking_comparisons`, Streamlit lab / Ajustes tabs, `src/generation/` |

Entry points **at plan start**:

- `src/embedding_pipeline/` — `__init__`, `schemas`, `chunker`, `embedder`, `router` (ingest only), `SANITY_CHECK.md`
- `src/main.py` — routers: estimations + sessions + ingestion + embeddings (ingest)
- `src/dependencies.py` — `get_chunker`, `get_embedder`. No factories, no `ALL_STRATEGIES`
- `src/config.py` — no `PROPOSITIONAL_CHUNKER_MODEL` / `CONTEXTUAL_CHUNKER_MODEL` / `AVAILABLE_MODELS`
- `scripts/` — s06 demos + `compare.py`. No `compare_chunkers.py`
- `data/budgets_sample.json` — 15 rows, same schema as Lidr 001–015
- `streamlit_app.py` — tabs: New estimation / Conversational / Recent
- `alembic/` — `0000_estimations` + `0001_session6_initial`. No `chunking_comparisons`
- `src/services/llm_wrapper.py` — `primary_model` is an init field. No Router fallback (`.env.example` says so)
- `src/cache/semantic.py` — `bucket_for` is prompt_version + enums. **No model** in the bucket

## What Lidr actually is (git evidence, not the aula)

`session_07_live` HEAD is `b544ace`. Five commits after `session_07` (`ee1c3f5`, already ported):

| Date | Commit | What |
|---|---|---|
| 2026-05-27 | `ee2e947` | Lab. README title: «Comparativa de estrategias de chunking **(sesión en vivo)**». Still `embedding_pipeline/` |
| 2026-06-03 | `eb66136` / `fa85ae7` | Move to `generation/rag/` + `EstimationService` |
| 2026-06-04 | `0817036` | Rails Chunking Lab (HTTP client over `/embeddings/compare` + Rails table) |
| 2026-06-04 | `b544ace` | `GET/PUT /api/v1/config/models` + Rails Ajustes |

`session_08` is pgvector + `POST /search`. Out of this port.

`guides/session-7-live-guide.md` is not in the tree.

## Locked decisions

- Lab first in `src/embedding_pipeline/` (like `ee2e947`). **Last step** moves only that lab to `src/generation/rag/`. No `EstimationService`. No CAG move (`services/`, `cache/`, one-shot estimate stay).
- No Rails / `estimator-web` as a repo. Lab UI + Ajustes → Streamlit tabs. Existing tab labels stay (`New estimation` / `Conversational` / `Recent`). Add `Chunking Lab` (4th) and `Ajustes` (5th). Do not rename the first three.
- Runtime config FastAPI **and** Streamlit Ajustes in this port. Store module is `src/services/runtime_config.py` (not `src/runtime_config.py`, not `foundation/`).
- Compare history: table `chunking_comparisons`, same columns as Lidr Rails, Alembic, FastAPI list/show/save. Streamlit HTTP only. Same grain as Recent: list is the table, show is reopen.
- `response_payload` (JSONB) is the full FastAPI `CompareResponse` (`stats_per_strategy` + `queries_per_strategy`). That is **stats** (per-strategy n / min / p50 / p95 / max / orphans / obese / cost / seconds), **cost bars** (same costs), and **playground** (per-query top-k: `chunk_id`, cosine, `text_preview`). Playground is empty when the run had no queries. Reopen = `GET /embeddings/comparisons/{id}` reads that column and Streamlit paints it. No second `POST /compare`.
- List vs show (Rails index + our Recent): `GET /embeddings/comparisons` last 20, newest first, **no** `response_payload` in the JSON. List item fields: `id`, `created_at`, `strategies`, `queries`, `top_k`, `corpus_label`, `corpus_count`, `duration_ms`, `cost_total_usd`. `cost_total_usd` is derived server-side from the stored payload (Rails `cost_total_usd` / `total_ingestion_cost_usd`); it is not its own column. `GET /embeddings/comparisons/{id}` returns those fields plus the full `CompareResponse` (200 / 404 / 503). No third `/metrics` endpoint. Sidebar stays service settings (`PRIMARY_MODEL`, URLs, TTL) — not comparison detail.
- Corpus of `/embeddings/compare` is the operator’s. FastAPI never reads `budgets_sample.json` (nor any other sample) for compare. Budgets arrive in the request body. No `GET /embeddings/corpus`. Streamlit: `st.file_uploader` plus an optional shortcut that reads `data/budgets_sample.json` from the Streamlit process cwd. Do not embed the array in `streamlit_app.py`. Do not copy Lidr Rails `BudgetCorpus` (bundled JSON in the client).
- `corpus_label` persisted = the operator file name (uploader) or `budgets_sample.json` (shortcut). Optional field on the compare request; omitted (curl/CLI) defaults to `budgets_sample`. `corpus_count` = `len(budgets)`.
- Sample file in the repo: copy Lidr live JSON (15 identical + `BUD-2024-016` + `BUD-2024-017`). Schema unchanged. Fixture for CLI/curl/shortcut, not a server store.
- `ee2e947` collaterals (ingestion, anchors, guardrails, `estimation.py`, s06 scripts, …) are **formatter wrap only**. Do not port. Do not reformat S5/S6.
- Import rewrite: drop `app.`. Do not write `from src.…`. Same as S6 / pre-s7.
- No Lidr test suite. Do not add pytest for this port unless a step breaks an existing test.
- Do not edit `docs/evolution.md` unless asked.
- Do not copy `uv.lock`. `uv lock` / `uv sync` after `pyproject.toml`. Compose is how we run (`pyproject.toml` is not bind-mounted). Step 1 ends with `docker compose up --build`. Do not `down -v`.
- Do not copy Lidr `Settings.validate_at_least_one_api_key`. We still boot without keys.
- Do not copy Lidr LiteLLM Router / auto-fallback. Our wrapper stays direct. No `FALLBACK_MODEL` field (not in Settings, `.env`, `MODEL_KEYS`, or Ajustes).
- Persist compare after a 200, fail-open (log + still return the body), same grain as `persist_estimation`. Streamlit still paints the live result.
- `POST /embeddings/ingest` stays in-memory. No pgvector. No `POST /search`.
- Scripts volume already mounted (pre-s7). Keep it.

## Import rewrite (every copied `.py`)

Until step 9 the package is still `embedding_pipeline`.

| Lidr `ee2e947` | Ours (steps 1–8) |
|---|---|
| `from app.embedding_pipeline.base import …` | `from embedding_pipeline.base import …` |
| `from app.embedding_pipeline.chunker import …` | `from embedding_pipeline.chunker import …` |
| `from app.embedding_pipeline.comparison import …` | `from embedding_pipeline.comparison import …` |
| `from app.embedding_pipeline.strategies.…` | `from embedding_pipeline.strategies.…` |
| `from app.embedding_pipeline.embedder import …` | `from embedding_pipeline.embedder import …` |
| `from app.embedding_pipeline.schemas import …` | `from embedding_pipeline.schemas import …` |
| `from app.dependencies import …` | `from dependencies import …` |
| `from app.config import get_settings` | `from config import get_settings` |

`compare_chunkers.py` has the same host-vs-Docker `sys.path` trap as `compare.py` (pre-sesion7, option 1: insert `src`, dual-path for the container flatten). Do not copy Lidr `sys.path.insert(0, ROOT)` + `from app.…`.

## Lidr path → action

### Lab (`ee2e947`)

| Lidr path | Role | Action |
|---|---|---|
| `embedding_pipeline/base.py` | `Chunker` ABC + `count_tokens` + `emit_chunking_done` | Copy → `src/embedding_pipeline/base.py` |
| `embedding_pipeline/similarity.py` | cosine, stdlib | Copy |
| `embedding_pipeline/comparison.py` | `ChunkingComparator`, `CompareRequest` / `CompareResponse` | Copy |
| `embedding_pipeline/strategies/*` | 7 strategies (+ structural stays in `chunker.py`) | Copy package |
| `embedding_pipeline/chunker.py` | now a `Chunker`; exports `render_component_text` / `serialize_budget` | **Replace** ours |
| `embedding_pipeline/embedder.py` | optional `dimensions` (Matryoshka / `--models`) | Patch ours |
| `embedding_pipeline/router.py` | add `POST /compare` | Patch ours; do not copy the file |
| `embedding_pipeline/schemas.py` | Budget / Chunk / ingest | **Keep ours.** Compare schemas live in `comparison.py` |
| `embedding_pipeline/__init__.py` | module docstring | Patch; do not wipe `SANITY_CHECK.md` |
| `embedding_pipeline/COMPARISON_REPORT.md` | Lidr numbers | **Do not copy.** Optional regenerate later |
| `embedding_pipeline/SANITY_CHECK.md` | pre-s7 student numbers | **Do not overwrite** |
| `scripts/compare_chunkers.py` | demo CLI | Copy + sys.path trap |
| `data/budgets_sample.json` | 17 rows | Copy over ours (001–015 identical) |
| `data/test_queries.json` | 6 canned queries | Copy |
| `dependencies.py` | factories + `ALL_STRATEGIES` + `build_chunkers` | Patch ours |
| `config.py` | two chunker model fields | Patch ours |
| `pyproject.toml` | langchain* + nltk | Same lines in ours |
| `README.md` | «sesión en vivo» block | Port the section; adapt paths |
| `uv.lock` | lock bump | Do not copy |

`ee2e947` factories use `@lru_cache` and `get_settings()` for the paid chunkers. Copy that in step 3. Step 8 drops `@lru_cache` on propositional / contextual and reads `runtime_config.effective(…)`, like Lidr HEAD.

### Persist (our design, Rails columns)

| Rails column | Our column |
|---|---|
| `strategies` jsonb not null default `[]` | same |
| `queries` jsonb not null default `[]` | same |
| `top_k` integer not null default 3 | same |
| `corpus_label` string not null default `budgets_sample` | same default; written value is the operator label (see locked) |
| `corpus_count` integer not null default 0 | same |
| `response_payload` jsonb not null default `{}` | full `CompareResponse` (show only; not in the list JSON) |
| `duration_ms` integer null | wall clock of the FastAPI compare |
| `created_at` / `updated_at` | timestamptz, server default now |

Table name: `chunking_comparisons`. Index on `created_at`. One `Base` in `src/persistence/models.py`. Alembic `0002_chunking_comparisons`, revises `0001_session6_initial`.

### Runtime config (`b544ace`)

| Lidr path | Action |
|---|---|
| `foundation/llm/runtime_config.py` | Copy → `src/services/runtime_config.py`. Rewrite imports |
| `api/config.py` | Copy → `src/routers/config.py`. Prefix `/api/v1/config` |
| `config.py` `AVAILABLE_MODELS` | Add the same four-model list Lidr has |
| wrapper `primary_model` property | Patch **our** wrapper: resolve `effective("PRIMARY_MODEL")` per call. Do not add their Router |
| `generation/cag/semantic.py` bucket + model | Patch **our** `src/cache/semantic.py` `bucket_for` / `lookup` / `store` to take the model, and the callers in `src/services/llm_service.py` |
| Rails Ajustes | Do not copy. Streamlit tab over GET/PUT |

Redis hash key stays `estimator:runtime_config`. `MODEL_KEYS` same seven. `EMBEDDING_MODEL` read-only in the payload.

### Out (do not copy)

- `estimator-web/` (all of it)
- `EstimationService` / `domain/` / `foundation/` / `generation/cag|agentic|conversation`
- Lidr tests (`test_runtime_config.py`, `test_config_endpoint.py`, …)
- `ee2e947` wrap-only diffs (ingestion, anchors, guardrails, s06 scripts, …)
- Rails `BudgetCorpus` / JSON baked into the client
- S08 `store/`, `retriever.py`, `ingest_service.py`, `api/search.py`, alembic `0002_session8_pgvector`

---

## Step 1 — Deps, settings, sample 17

Copy-from: `ee2e947` `pyproject.toml` (the four live lines only), `config.py` (the two Session 7 live fields), `data/budgets_sample.json`, `data/test_queries.json`.

- `pyproject.toml`: `langchain-text-splitters>=0.3.0`, `langchain-experimental>=0.3.0`, `langchain-openai>=0.2.0`, `nltk>=3.9`. `anthropic` and `tiktoken` already present.
- `uv lock` && `uv sync`. Then `docker compose up --build` (do not `down -v`).
- `config.py` + `.env.example` comments (defaults only; do not put the two names in the machine `.env`):
  - `PROPOSITIONAL_CHUNKER_MODEL: str = "gpt-4o-mini"`
  - `CONTEXTUAL_CHUNKER_MODEL: str = "claude-sonnet-4-5"`
- Replace `data/budgets_sample.json` with Lidr’s 17. Do not touch `data/seed/`.
- Add `data/test_queries.json` as-is.

Do not wire strategies yet. Existing `/embeddings/ingest` must still work (structural chunker unchanged until step 2).

**Stop.** Tick the summary. Wait.

## Step 2 — Lab package inside `embedding_pipeline/`

Copy-from: `ee2e947` files in the table above (base, similarity, comparison, strategies, chunker replace, embedder patch, `__init__` docstring).

- `SANITY_CHECK.md` stays ours.
- Do not add `COMPARISON_REPORT.md` from Lidr.
- `schemas.py` stays ours. If `ee2e947` `chunker.py` / strategies import something we do not have, add **that symbol only** — do not replace the ingest schemas.

`JSONStructuralChunker` must remain a `Chunker` so ingest and compare share it. `POST /embeddings/ingest` still uses `get_chunker()`.

**Stop.** Tick. Wait.

## Step 3 — Wire `/embeddings/compare`

Copy-from: `ee2e947` `dependencies.py` factories / `CHUNKER_FACTORIES` / `ALL_STRATEGIES` / `build_chunkers`; `router.py` `compare` handler.

- Patch `dependencies.py`. Do not copy the file. Add `get_anthropic_client()` (we have none). `None` without `ANTHROPIC_API_KEY`, same grain as `get_openai_client()`.
- Paid factories in this step: `@lru_cache` + `get_settings()` (live-day). Runtime override is step 8.
- Patch `router.py`: `POST /compare`. Body carries `budgets` (Lidr contract). The handler does not open `data/budgets_sample.json`. 400 unknown strategy; 500 missing key / embedder down / compare error. Generic client message; detail in logs. Same as ingest.
- `main.py` already includes `embeddings_router`. Do not copy Lidr `main.py`.

**Stop.** Tick. Wait. Agent does not run a paid compare. Guide-only curl is fine if asked.

## Step 4 — `compare_chunkers.py`

Copy-from: `ee2e947` `scripts/compare_chunkers.py`.

- Rewrite imports + **option 1 sys.path** (pre-sesion7 trap). Host: insert `src`. Container: flattened `/app`.
- Reads `data/budgets_sample.json` + `data/test_queries.json`.
- Do not generate `COMPARISON_REPORT.md` in this step.

**Stop.** Tick. Wait.

## Step 5 — README live section

Port Lidr `ee2e947` README block «Comparativa de estrategias de chunking (sesión en vivo)» into ours. Paths = ours. Service name `estimator`. Keep the existing ingest / `compare.py` / `SANITY_CHECK` text. Late chunking = concept only. S08 persist/search = out of scope.

**Stop.** Tick. Wait.

## Step 6 — Persist comparisons (Alembic + HTTP)

No Lidr FastAPI file to copy. Columns from the Rails migration. Grain from `history.py` + `routers/estimations.py`.

- `ChunkingComparisonRow` on the existing `Base` in `src/persistence/models.py`.
- Alembic `0002_chunking_comparisons` revises `0001_session6_initial`. Hand-written, like `0000` / `0001`. `alembic upgrade head` (Compose already runs it on boot).
- Repository or small module next to history (do not merge into `history.py`). Own lazy engine via `persistence.database.get_engine()` if that is what jobs use; do **not** invent a second engine if one lazy getter already exists. Do not merge with `history.get_engine()` if they are still separate (S6 lock).
- `POST /embeddings/compare`: time the call; on success persist (`corpus_label` from the request or default `budgets_sample`, `corpus_count=len(budgets)`); fail-open. Response body stays `CompareResponse` (Lidr contract). Persistence is a side effect, not a new response field. Optional `corpus_label` on the request is ours; Lidr’s compare body has no such field.
- `GET /embeddings/comparisons` — last 20, newest first. List item: `id`, `created_at`, `strategies`, `queries`, `top_k`, `corpus_label`, `corpus_count`, `duration_ms`, `cost_total_usd` (derived from payload; not a column). No `response_payload` in this JSON.
- `GET /embeddings/comparisons/{id}` — same list fields plus the stored `CompareResponse` (stats + playground). 200 / 404 / 503 if DB down. This is reopen.

Do not persist `/embeddings/ingest`.

**Stop.** Tick. Wait. Do not `down -v`.

## Step 7 — Streamlit Chunking Lab tab

No Lidr Streamlit. Visible lab = Rails Chunking Lab (checkboxes, stats, cost bars, playground, history), over **our** HTTP. Corpus handling is not Rails `BudgetCorpus`.

Fourth tab, label `Chunking Lab`, next to the unchanged `New estimation` / `Conversational` / `Recent`. HTTP only. No SQL.

- Form: 8 strategy checkboxes (same names, free vs `$` vs `$ · lento`, key badges). Defaults = Lidr `Rag::Strategy.defaults` (structural, fixed_size, recursive).
- Query chips: the six strings from `data/test_queries.json`, hardcoded in the tab (they are the canned demo queries, not the corpus).
- `top_k` 1–10.
- Corpus: `st.file_uploader` (JSON array, Budget schema). Optional shortcut button that reads `data/budgets_sample.json` from the Streamlit cwd (`estimador-cag/`) when that file exists. Parse in the UI; POST `{budgets, queries, strategies, top_k, corpus_label}` to `/embeddings/compare`. `corpus_label` = uploaded file name, or `budgets_sample.json` for the shortcut. Do not embed the array in `streamlit_app.py`. Do not add `GET /embeddings/corpus`. Timeout **600 s** (Rails `COMPARE_TIMEOUT_SECONDS`). Estimate timeout stays 120 s.
- Paint stats (n, min/p50/p95/max, orphans, obese, cost, seconds), cost bars, playground if queries were sent.
- History table from `GET /embeddings/comparisons` (list fields above). Reopen paints stats / cost bars / playground from `GET …/{id}`. No second compare.

**Stop.** Tick. Wait.

## Step 8 — Runtime config + Ajustes tab

Copy-from: `b544ace` store + endpoint. Patch our wrapper / call sites / semantic bucket / paid chunker factories.

- `RuntimeModelConfig` + `MODEL_KEYS` + hash `estimator:runtime_config`. Reads fail-open to `.env` defaults. Writes raise → 503.
- `AVAILABLE_MODELS` on Settings: `gpt-4o-mini`, `gpt-4o`, `claude-haiku-4-5-20251001`, `claude-sonnet-4-5` (Lidr list).
- `GET/PUT /api/v1/config/models` — same snapshot shape. PUT partial; `null` = reset; all-or-nothing validate; 422 unknown / not-in-catalog; 400 missing provider key; 503 Redis write down. `EMBEDDING_MODEL` in the GET, not writable.
- `include_router` in `main.py`.
- Wrapper: `primary_model` resolved per call from the store. Do not rebuild a Router. Do not add auto-fallback.
- `acb.py` / `conversational.py`: `CRITIC_MODEL` / `METADATA_EXTRACTOR_MODEL` / `COMPRESSION_MODEL` via `effective()`, not `get_settings()` alone.
- `get_propositional_chunker` / `get_contextual_retrieval_chunker`: drop `@lru_cache`; `effective()` for the model.
- Semantic cache: `bucket_for` / `lookup` / `store` take the **effective** primary model so a switch cannot serve another model’s hit (Lidr `b544ace` bugfix). Patch `src/cache/semantic.py` **and** the callers in `src/services/llm_service.py` (today `lookup(request, version)` / `store(request, result, version)`).
- Streamlit fifth tab, label `Ajustes`: table of knobs + default/override + save. Read-only embeddings row. HTTP GET/PUT only. Optional caption of the effective primary (Rails navbar badge) — nice, not required if the tab already shows it. Do not rename the first three tabs.

**Stop.** Tick. Wait.

## Step 9 — LAST. Move lab to `src/generation/rag/`

No CAG rewrite. No `EstimationService`. No `foundation/` / `domain/` / `api/` package.

| After step 8 | After step 9 |
|---|---|
| `src/embedding_pipeline/base.py` | `src/generation/rag/chunking/base.py` |
| `src/embedding_pipeline/chunker.py` | `src/generation/rag/chunking/structural.py` |
| `src/embedding_pipeline/strategies/*` | `src/generation/rag/chunking/strategies/*` |
| `src/embedding_pipeline/embedder.py` | `src/generation/rag/embedding/embedder.py` |
| `src/embedding_pipeline/{similarity,comparison}.py` | `src/generation/rag/analysis/*` |
| `src/embedding_pipeline/schemas.py` | `src/generation/rag/schemas.py` |
| `src/embedding_pipeline/router.py` | `src/routers/embeddings.py` (we already have `src/routers/`) |
| `src/embedding_pipeline/SANITY_CHECK.md` | `src/generation/rag/SANITY_CHECK.md` |

Delete the empty `src/embedding_pipeline/` package after the move. Patch every import (`dependencies`, `main`, scripts, tests that import the old path). `compare.py` / `compare_chunkers.py` sys.path trap unchanged (`src` on the path); only the `from …` lines change.

Do **not** move `services/`, `cache/`, `guardrails/`, `sessions/`, `prompts/`, `ingestion/`.

README paths in the Sesión 7 section.

**Stop.** Port complete after this step is ticked.

---

## Summary

| # | Title | OK |
|---|---|---|
| 1 | Deps + two settings + sample 17 + `test_queries.json` | [x] |
| 2 | Lab package in `embedding_pipeline/` (keep SANITY_CHECK) | [x] |
| 3 | Wire `POST /embeddings/compare` | [x] |
| 4 | `compare_chunkers.py` (sys.path trap) | [x] |
| 5 | README live section | [x] |
| 6 | Alembic `0002` + persist/list/show comparisons | [x] |
| 7 | Streamlit Chunking Lab tab | [x] |
| 8 | Runtime config FastAPI + Ajustes tab | [x] |
| 9 | Move lab → `src/generation/rag/` (no EstimationService, no CAG) | [ ] |

Next work is **step 1 only**.

## Out of this port

- Rails / `estimator-web` as code.
- `EstimationService` and Lidr layered CAG.
- pgvector, `POST /search`, ingest persist, S08 alembic.
- Lidr tests.
- Reformatting S5/S6 wrap-only files.
- `COMPARISON_REPORT.md` numbers from Lidr.
- Overwriting `SANITY_CHECK.md`.
- `guides/` (not in the tree).
- `docker compose down -v`.
- Streamlit SQL.
- FastAPI reading `data/budgets_sample.json` (or any sample path) on compare.
- `GET /embeddings/corpus`.
- JSON array embedded in `streamlit_app.py` or any client package.
- Auto-fallback Router.
- Settings that refuse to boot without API keys.
