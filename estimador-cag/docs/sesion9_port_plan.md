# Session 9 live — agreed incorporation plan

Bring Lidr `session_09_live` RAG estimation into `estimador-cag`. This is product, not a lab: a transcript becomes a grounded estimate, with a Streamlit wizard that walks the pipeline step by step and keeps a history. FastAPI is the only backend. Streamlit stays an HTTP client. Do not implement until the steps are executed in order. After each step, stop for review. Do not start the next step until told.

This file is the handoff. Closed plans (`pre_sesion9_plan.md`, `sesion8_port_plan.md`, …) are read-only except to reuse the import-rewrite rule.

Each step starts with a short human note (what this step is for), then copy-from / actions / stop.

## Handoff (start here in a new session)

| | Path / value |
|---|---|
| Ours | `/home/morales4dev/wsTakeoff/ai-engineering` branch `session-09/pre-work` @ `2d0bd6c`, app `estimador-cag/` |
| Reference | `/home/morales4dev/wsTakeoff/ai-engineering-lidr` `session_09_live` @ `cb83eb8`. **Not** `session_09` (docs-only pre-work). **Not** `session_10` (hybrid / rerank / FTS). **Not** `ai-engineering-lidr-temp`. |
| Copy-from | FastAPI tree under Lidr `estimator/`. Quarry is the working tree at `cb83eb8`. |
| Layout | Lidr `estimator/app/…`. Ours `estimador-cag/src/…`. |
| Already shipped | Pre-sesión 9: diagnóstico in `arquitectura-actual.md` (no product change). S08: `POST /search`, halfvec SELECT, HNSW operator indexes, `store/`. CAG `POST /api/v1/estimate` + Streamlit tabs New / Conversational / Recent / Chunking Lab / Ajustes. |
| Not in tree | `query_reformulator`, `context_assembler`, `estimator`, `search_filtered`, `/v1/*` RAG routes, `estimation_runs` table, Streamlit wizard tab, `slowapi`, `gpt-5` in `MODEL_COSTS`, `reasoning_effort` on the wrapper. |

Entry points **at plan start**:

- `src/generation/rag/retriever.py` — `SemanticRetriever.search` only. No `search_chunks`. No threshold. No metadata filters.
- `src/generation/rag/store/repository.py` — `search` halfvec k-NN. No `search_filtered`. `persist_document_with_chunks` always stamps `chunk_type=budget_component`.
- `src/generation/rag/schemas.py` — ingest/search types only. No `EstimationQuery` / `Estimate` / `RetrievedChunk`.
- `src/generation/rag/chunking/structural.py` — no `module` line.
- `src/main.py` — six routers. No request-id middleware. No limiter. CORS stays off.
- `src/services/llm_wrapper.py` — `complete_structured` / `complete_structured_chat`. **No** `complete()`. No `reasoning_effort`. `MODEL_COSTS` has no `gpt-5` / `gpt-5-mini`.
- `src/config.py` — no S09 fields. `LLM_TIMEOUT` default 30.
- `.env` / `.env.example` — `LLM_TIMEOUT=30`. No API keys for the new routers.
- `streamlit_app.py` — five tabs. No wizard.
- `alembic/versions/` — `0000` → `0001` → `0002_chunking_comparisons` → `0003_session8_pgvector`. **No `0004`.**
- `docs/evolution.md` — last event `pre_sesion_09`.
- `?? estimador-cag/src/alembic.ini` — leftover, out of this port. Do not touch.
- Git root `README.md` is dirty (pointer to the diagnóstico). Out of this port unless a step says otherwise.

## What Lidr actually is (git evidence, not the aula)

`session_09_live` HEAD is `cb83eb8`. Two commits after `origin/session_09` (`bd231b2`, already in our pre-work as material, not as product):

| Date | Commit | What |
|---|---|---|
| 2026-06-16 | `33a5e03` | FastAPI pipeline + `/v1/retrieval/search` + `/v1/estimate/from-transcript` + tests. No web UI. |
| 2026-06-19 | `cb83eb8` | Web wizard + per-stage HTTP + task corpus + `Estimate` as modules→tasks + `BudgetComponent.module`. |

`git diff --stat origin/session_09..origin/session_09_live` is 81 files, +8120/−14. About half is their web app. We do not copy that app. We copy the Python service and we rebuild the wizard in Streamlit.

Their web is only an HTTP client of the service. It stores each wizard run in **its own** database (`estimation_runs`). The AI service does not remember those runs. We have no second database: Streamlit does not persist. Same functionality lands in **our** Postgres, behind FastAPI, like Chunking Lab history.

Lidr `estimator/README.md` has **no** Session 9 section. The contract lives in their `CLAUDE.md`. We do not have `CLAUDE.md`. Docs go in our `README.md` as a new section.

Their `CLAUDE.md` claims `REFORMULATION_MODEL` / `GENERATION_MODEL` are switchable from Ajustes. On this SHA, `MODEL_KEYS` does **not** include them. That arrives in `session_10`. Do not add them.

## Naming (locked)

- One saved wizard = **ejecución**. Not “pasada”, not “la clave”. In code / URLs / SQL keep Lidr’s English: `run`, `/v1/estimate/runs`, table `estimation_runs`. UI copy can say “estimación guiada” / “ejecución”.
- Auth is two **RAG API keys**, independent on purpose:
  - `ESTIMATE_API_KEY` — wizard ejecuciones + `POST /v1/estimate/from-transcript`
  - `RETRIEVAL_API_KEY` — `POST /v1/retrieval/search` only
- Header is still `X-API-Key` (what Lidr sends). Do **not** merge them into one `CUSTOM_API_KEY` / `CUSTOM_API_KEYS`: a client that may search must not be allowed to spend gpt-5 on generate. In this plan, never write “the key” without naming which variable.
- Rate limit buckets by the value of `X-API-Key` (same as Lidr), not by IP.

## Why slowapi (locked)

`slowapi` is the library Lidr uses to **rate-limit** the RAG HTTP paths. It is not auth (that is `ESTIMATE_API_KEY` / `RETRIEVAL_API_KEY`). It caps how often a given `X-API-Key` may call an expensive route: Lidr’s numbers are retrieval 120/min, one-shot estimate 10/min, generate-like 15/min. Identity is the API key, not the IP (so two laptops on the same Wi‑Fi do not share a bucket, and rotating IP does not dodge it). Over the limit → 429 + `Retry-After`. Point: a Streamlit loop or a leaked demo key must not be able to fire gpt-5 without a brake. Copy Lidr’s `rate_limiting.py`. Do not invent different numbers unless we reopen this.

## Why gpt-5 (locked, cost accepted)

Lidr’s default: reformulate with `gpt-5-mini`, generate the grounded estimate with `gpt-5` + `reasoning_effort=high`. Generation has to read `<source>` blocks, cite ids, split work into modules/tasks, and say `insufficient` instead of inventing numbers. That is why it is a bigger model than CAG’s `gpt-4o-mini`. `MODEL_COSTS` rows exist so the wrapper can price the call (otherwise cost shows as 0). They do not force spend; they are accounting. Defaults stay Lidr’s. To spend less later, change `.env` (`GENERATION_MODEL`, `GENERATION_REASONING_EFFORT`) — out of this port unless we reopen it. `GENERATION_MAX_TOKENS=64000` is a cap, not a target.

## Locked decisions

- Quarry = Lidr `session_09_live` @ `cb83eb8` working tree. Copy a file only when we need that piece.
- CAG path stays. `POST /api/v1/estimate` and the New / Conversational / Recent tabs are untouched. RAG is a **second** path with its own `Estimate` (engineer-days, modules→tasks), not a rewrite of `EstimationResult`.
- Do not implement `budget_assembler` from our diagnóstico. Lidr sends retrieved chunks straight into `<source>` XML. That is what we copy.
- Do not copy their web app. Streamlit gets a **new tab** with the same wizard: paste/upload transcript → reformulate → retrieve (filters) → assemble → generate → human-edit the table → history of ejecuciones.
- **No duplicated HTTP.** Lidr exposes amnesiac `POST /v1/estimate/stages/*` because their web remembers. Ours remembers in FastAPI. Do not mount `/v1/estimate/stages/*`. Streamlit (and curl) talk only to the ejecución URLs (`/v1/estimate/runs…`) below.
- **Layers (this is the design; a closed chat must still implement this, not a fat router).** Four layers, top to bottom. Do not collapse 2 and 3 into the router.
  1. **Streamlit** — HTTP client. No Postgres, no pipeline calls, no orchestration.
  2. **Routers** — transport only, same grain as `routers/search.py` / `embeddings.py`. Validate, auth, rate limit, call a service, map errors to HTTP. No SQL. No `reformulate_query` / `search_chunks` / `generate_estimate` imports in `rag_runs.py`.
  3. **Facade** — `src/services/rag_runs.py` (name locked). This is our stand-in for their web: `create_run`, `reformulate`, `retrieve`, `assemble`, `generate`, `verify`, `get`, `list`. Each mutating method calls the amnesiac functions (layer 4), writes `estimation_runs`, and `clear_downstream` when an earlier step is re-run. Persistence failure on a mutating call is **503**, not fail-open (unlike Chunking Lab history: losing a paid generate is not acceptable).
  4. **Amnesiac pipeline** — `generation/rag/query_reformulator.py`, `search_chunks`, `context_assembler`, `prompt_builder`, `validation`, `estimator.generate_estimate` / `estimate_from_transcript`. These do not know what an ejecución is and do not touch `estimation_runs`. Unit-test them without HTTP.
- **Store** (locked file): `src/services/estimation_runs.py`. Same grain as `services/comparisons.py`: insert / get / list(20) / update JSON columns / `clear_downstream`. Talks to Postgres only. Does **not** call the LLM or the retriever. The facade imports this module; do not hide the SQL as private helpers inside `rag_runs.py`.
- Keep two other HTTP paths that are not the wizard:
  - `POST /v1/retrieval/search` — threshold + filters, no run id, no row. Same job as Lidr’s retrieval router.
  - `POST /v1/estimate/from-transcript` — one shot, Redis idempotency, **does not** write `estimation_runs` (Lidr’s one-shot does not either).
- Persist ejecuciones in our Postgres (`estimation_runs`), Alembic `0004`. FastAPI is the only process that talks to the DB. Streamlit only consumes HTTP.
- `POST /search` stays as-is (Chunking Lab / S08). New retrieval does not replace it.
- CORS stays off. Streamlit is Python, not a browser.
- Wrapper: add `reasoning_effort` + `gpt-5` / `gpt-5-mini` rows in `MODEL_COSTS` (see “Why gpt-5”). **Do not resurrect `complete()`.** Reformulation fallback uses `complete_structured` with a one-field model (or `EstimationQuery(function=…)` from a tiny schema). Adapt Lidr’s fallback tests.
- Ajustes: adding those two models to `MODEL_COSTS` makes them appear in the available list. Do **not** add `REFORMULATION_MODEL` / `GENERATION_MODEL` to `MODEL_KEYS`.
- `LLM_TIMEOUT`: Settings default stays 30 (Lidr’s `config.py` does). `.env.example` becomes 600. Human updates the real `.env` and recreates `estimator`. Without that, gpt-5 dies at 30s.
- Tests **do** enter (product). Flat under `tests/`, like ours, not Lidr’s `tests/api/` + `tests/generation/rag/` folders. Rewrite Lidr’s stage-router tests against `/v1/estimate/runs…`. Patch `test_embeddings_ingest_persist.py` for `chunk_type`.
- Task corpus: copy `data/task_corpus.json` + `scripts/build_task_corpus.py`. Agent does not `--ingest` (OpenAI). Guide only, like S08 synthetics.
- README: **new section** after Live Session 08. Lidr has no README S09; write ours from the locked HTTP + wizard behaviour. Do not fold into the diagnóstico.
- `docs/evolution.md`: **last step only**. Event `session_09_forense`. Do not rewrite `pre_sesion_09` / S08 rows.
- Import rewrite: drop `app.`. Do not write `from src.…`.
- Do not copy `uv.lock` wholesale, Lidr compose, their web app, `ARCHITECTURE.md`, `guides/`, `session_10`, Lidr `arquitectura-actual.md`.
- Do not `docker compose down -v`. Do not `alembic init`. Do not touch `?? src/alembic.ini`.
- Agent does not fire OpenAI for ingest of the task corpus. Does not invent estimates.

## Import rewrite (every copied `.py`)

| Lidr `session_09_live` | Ours |
|---|---|
| `from app.config import get_settings` | `from config import get_settings` |
| `from app.dependencies import …` | `from dependencies import …` |
| `from app.generation.rag.…` | `from generation.rag.…` |
| `from app.foundation.llm.wrapper import …` | `from services.llm_wrapper import …` |
| `from app.foundation.persistence.database import …` | `from persistence.database import …` |
| `from app.api.security import …` | `from routers.security import …` |
| `from app.api.rate_limiting import …` | `from routers.rate_limiting import …` |
| `from app.api.deps import get_request_id` | `from routers.deps import get_request_id` |
| `from app.api.routers.estimate import …` | do not copy that router as-is (see run URLs) |

sys.path on copied scripts (same trap as `compare_chunkers.py` / `scripts/s08/`):

```python
ROOT = Path(__file__).resolve().parent.parent.parent  # estimador-cag/ on host, /app in the container
for candidate in (ROOT / "src", ROOT):
    if (candidate / "config.py").exists():
        sys.path.insert(0, str(candidate))
        break
```

`build_task_corpus.py` lives in `scripts/s09/` → one extra `.parent` versus a file flat under `scripts/` (same as s08). Ingest URL stays `POST /embeddings/ingest` on `ESTIMATOR_BASE_URL` / compose service. `.env` path in messages: `estimador-cag/.env`.

## HTTP we will have (locked)

Header `X-API-Key`. Compare with `secrets.compare_digest`. Missing/wrong `ESTIMATE_API_KEY` or `RETRIEVAL_API_KEY` (whichever that path requires) → 401. Rate limit per API-key value (slowapi), 429 + `Retry-After`.

| Method | Path | RAG API key | Memory | What |
|---|---|---|---|---|
| POST | `/v1/retrieval/search` | `RETRIEVAL_API_KEY` | none | Embed `query_text`, `search_chunks` (k, threshold, filters). Soft-fail = 200 + `low_confidence`. |
| POST | `/v1/estimate/from-transcript` | `ESTIMATE_API_KEY` | Redis idempotency only | Full pipeline. Citation retry + coherence. **No** `estimation_runs` row. |
| POST | `/v1/estimate/runs` | `ESTIMATE_API_KEY` | row | Create ejecución from `{transcript}`, reformulate, persist, return it. |
| POST | `/v1/estimate/runs/{id}/reformulate` | `ESTIMATE_API_KEY` | row | Re-run step 1, clear later steps. |
| POST | `/v1/estimate/runs/{id}/retrieve` | `ESTIMATE_API_KEY` | row | Filters in body (or defaults from the brief). Persist retrieval. Clear later steps. |
| POST | `/v1/estimate/runs/{id}/assemble` | `ESTIMATE_API_KEY` | row | Token budget, `<source>` block, persist. Clear later steps. |
| POST | `/v1/estimate/runs/{id}/generate` | `ESTIMATE_API_KEY` | row | Generate **without** Lidr’s one-shot auto-retry (wizard shows fabricated ids / coherence, like their stage generate). Persist. |
| PATCH | `/v1/estimate/runs/{id}/verify` | `ESTIMATE_API_KEY` | row | Human-edited modules/tasks. Recompute total on the server. Keep the model output untouched. |
| GET | `/v1/estimate/runs` | `ESTIMATE_API_KEY` | read | Last 20 ejecuciones, newest first. |
| GET | `/v1/estimate/runs/{id}` | `ESTIMATE_API_KEY` | read | One ejecución. 404 if missing. |

Do **not** add `POST /v1/estimate/stages/*`.

Existing: `POST /search`, `POST /api/v1/estimate`, sessions, embeddings, config — unchanged contracts.

`X-Request-ID` middleware on the app (echo header; `log_stage` uses it). New if missing, reuse if present.

## Lidr path → action

| Lidr path | Role | Action |
|---|---|---|
| `app/generation/rag/schemas.py` (S09 types only) | `EstimationQuery`, `Estimate` modules→tasks, HTTP models | **Patch ours.** Keep S08 ingest/search types and our `IngestResponse.stats`. Add S09 types from HEAD (`WorkModule` / `TaskItem`, not the older flat breakdown). |
| `app/generation/rag/errors.py` | `RagError` hierarchy | Copy → `src/generation/rag/errors.py`. Rewrite imports. |
| `app/generation/rag/query_reformulator.py` | transcript → brief + search text | Copy. Fallback: `complete_structured`, not `complete()`. |
| `app/generation/rag/retriever.py` (`search_chunks` only) | filtered k-NN | **Patch ours.** Keep `SemanticRetriever.search`. Add `search_chunks`. |
| `app/generation/rag/store/repository.py` (`search_filtered` + `chunk_type` arg) | SQL | **Patch ours.** Do not copy the file. Keep halfvec `search`. |
| `app/generation/rag/context_assembler.py` | `<source>` XML + token budget | Copy |
| `app/generation/rag/prompt_builder.py` | grounding prompts | Copy |
| `app/generation/rag/validation.py` | citations + coherence | Copy |
| `app/generation/rag/estimator.py` | one-shot orchestrator | Copy. Used by `/from-transcript` only. |
| `app/generation/rag/idempotency.py` | Redis / dict | Copy |
| `app/generation/rag/observability.py` | `log_stage` | Copy |
| `app/generation/rag/chunking/structural.py` | optional `module` | **Patch ours.** |
| `app/generation/rag/ingest_service.py` + `api/embeddings.py` | `chunk_type` through | **Patch ours.** Keep `stats`. |
| `app/api/security.py` | `ESTIMATE_API_KEY` / `RETRIEVAL_API_KEY` | Copy → `src/routers/security.py` |
| `app/api/rate_limiting.py` | slowapi | Copy → `src/routers/rate_limiting.py` |
| `app/api/deps.py` | request id | Copy → `src/routers/deps.py` |
| `app/api/routers/retrieval.py` | `/v1/retrieval/search` | Copy → `src/routers/retrieval.py` |
| `app/api/routers/estimate.py` | `/from-transcript` | Copy → `src/routers/rag_estimate.py` (prefix stays `/v1/estimate`) |
| `app/api/routers/estimate_stages.py` | amnesiac HTTP stages | **Do not copy as a router.** Its *function calls* are the recipe for the facade (`services/rag_runs.py`), not for `routers/rag_runs.py`. |
| (new) `src/services/estimation_runs.py` | Postgres CRUD for ejecuciones | **Write.** Like `comparisons.py`. No LLM. |
| (new) `src/services/rag_runs.py` | wizard facade | **Write.** Calls the same functions Lidr’s stages router called; writes via `estimation_runs.py`. |
| (new) `src/routers/rag_runs.py` | wizard HTTP | **Write.** Thin: Depends + call facade + HTTP errors. No pipeline imports. |
| `app/config.py` S09 fields | models, k, threshold, RAG API keys | **Patch ours.** |
| `app/dependencies.py` S09 factories | encoder, idempotency | **Patch ours.** |
| `app/foundation/llm/wrapper.py` hunk | `reasoning_effort` + prices | **Patch ours.** No `complete()`. |
| `app/main.py` hunk | limiter, request id, include routers | **Patch ours.** Do not turn CORS on. |
| `pyproject.toml` `slowapi` | dep | **Patch ours.** `uv lock` on our tree, do not copy Lidr lock. |
| `.env.example` S09 block + `LLM_TIMEOUT=600` | env | **Patch ours.** Human then edits `.env`. |
| `data/task_corpus.json` | 12 synthetic projects | Copy → `estimador-cag/data/task_corpus.json` |
| `scripts/build_task_corpus.py` | generate / ingest | Copy → `scripts/s09/`. Trap + rewrite. |
| tests listed below | contract | Copy/adapt under `tests/` |
| `estimator-web/**` | their wizard | **Do not copy.** Rebuild in `streamlit_app.py`. |
| `uv.lock` / compose wholesale / CORS on | — | **Do not copy** |

`psql` / compose names stay ours (`postgres`, `-U postgres`, db `estimator`).

---

## Step 1 — Plumbing (config, wrapper, slowapi)

The new path needs settings, gpt-5 on the price table, `reasoning_effort` on structured calls, and slowapi installed. No HTTP yet.

Copy-from: Lidr `config.py` S09 fields, wrapper hunk, `pyproject.toml` slowapi line, `.env.example` S09 block.

- `pyproject.toml`: add `slowapi>=0.1.9`. Run `uv lock` in `estimador-cag/`.
- `config.py`: add Lidr’s S09 settings (`REFORMULATION_MODEL`, `GENERATION_MODEL`, `GENERATION_REASONING_EFFORT`, `GENERATION_MAX_TOKENS`, `RETRIEVAL_TOP_K`, `RETRIEVAL_DISTANCE_THRESHOLD`, `MAX_CONTEXT_TOKENS`, `IDEMPOTENCY_TTL`, `RETRIEVAL_API_KEY`, `ESTIMATE_API_KEY`). Defaults as Lidr HEAD (`gpt-5-mini` / `gpt-5` / `high` / `64000` / `10` / `0.6` / `16384` / `86400` / both API keys `None`). Do not add those two model names to `runtime_config.MODEL_KEYS`.
- `llm_wrapper.py`: `gpt-5` and `gpt-5-mini` rows in `MODEL_COSTS` (Lidr numbers; see “Why gpt-5”). `reasoning_effort: str | None = None` on `complete_structured` **and** `complete_structured_chat`; pass through to Instructor when set. Do not add `complete()`.
- `.env.example`: `LLM_TIMEOUT=600` + the S09 block (demo `ESTIMATE_API_KEY` / `RETRIEVAL_API_KEY` like Lidr). Comment: Streamlit sends `ESTIMATE_API_KEY` as `X-API-Key`. Do not print the real `.env`. Tell the human to copy the block into `.env` and recreate `estimator` before any live gpt-5 call.

No routers. No Streamlit. No Alembic.

**Acceptance:** `rg reasoning_effort src/services/llm_wrapper.py` hits both structured methods. `rg slowapi pyproject.toml` hits. Settings import. Existing pytest still green.

**Stop.** Tick. Wait.

## Step 2 — Pipeline modules (no HTTP)

This is the transcript → brief → search → XML context → grounded `Estimate` machinery. Still no URLs.

Copy-from: Lidr files in the table (schemas patch, errors, reformulator, `search_chunks`, `search_filtered`, assembler, prompt_builder, validation, estimator, idempotency, observability, structural `module`, ingest `chunk_type`).

- Patch `schemas.py`: append S09 types from Lidr HEAD. Keep S08 types. `IngestRequest.chunk_type` default `budget_component`. Do not drop `IngestStats` / `stats` on our ingest response.
- `BudgetComponent.module: str | None = None`.
- `query_reformulator.py`: fallback via `complete_structured`, not `complete()`. If structured extraction fails, one-field rewrite still becomes `EstimationQuery(function=…)`.
- `repository.py`: add `chunk_type=` to persist (default `BUDGET_COMPONENT`). Add `search_filtered` as Lidr (JSONB `client_sector` / `year`, `chunk_type` column, distance threshold, `candidates_evaluated`). Keep existing `search`.
- `retriever.py`: add `search_chunks`. Keep `SemanticRetriever`.
- `ingest_service.py` + embeddings router: pass `chunk_type` through. Keep `stats`.
- `structural.py`: `Module:` line + `module` in metadata when present.
- `dependencies.py`: `get_idempotency_store`, `get_token_encoder` (tiktoken `cl100k_base`), same grain as Lidr.

Unit tests this step (import rewrite, flat `tests/`):

- `test_query_reformulator.py` (fallback must not call `complete`)
- `test_context_assembler.py`
- `test_retriever.py` (`search_chunks` / filtered store — fake the store)
- `test_estimator.py`
- `test_validation.py`
- `test_structural_chunker.py` (module line)
- patch `test_embeddings_ingest_persist.py` (`chunk_type` default + custom)

Do not add HTTP tests yet. Do not run OpenAI.

**Acceptance:** pytest of the files above green. `POST /search` contract unchanged. No new routes in `main.py`.

**Stop.** Tick. Wait.

## Step 3 — `estimation_runs` table + facade (no HTTP)

Wizard history needs a row per run, and a service that *uses* that row. Same grain as Chunking Lab for the table; the facade is new (their web was that facade). No HTTP yet.

Copy-from: Lidr web migration **shape** (columns), not Ruby. Recipe for the facade methods: the function calls inside Lidr `estimate_stages.py` (not the FastAPI decorator layer). Our table pattern: `0002_chunking_comparisons.py` + `ChunkingComparisonRow`.

Table `estimation_runs`:

- `id`, `transcript` (text, not null)
- `status` (string, default `started`)
- `current_step` (string, default `transcript`)
- `reformulation` / `retrieval` / `augmentation` / `generation` / `adjusted_breakdown` JSONB, default `{}`
- `idempotency_key` nullable string
- `duration_ms` nullable int
- `created_at` / `updated_at` timestamptz
- index on `created_at`

- Alembic `0004_session9_estimation_runs.py`, `down_revision = "0003_session8_pgvector"`.
- ORM on `persistence.models.Base` (same as comparisons, not the vector `store.models`).
- Register the new class in `alembic/env.py` imports.
- Store (CRUD): `src/services/estimation_runs.py` (locked). insert / get / list(20) / update JSON columns / `clear_downstream` (null later JSON so a re-run never leaves a stale estimate). List/get raise if Postgres is down (router will map 503). Do not inline this into `rag_runs.py`.
- Facade `src/services/rag_runs.py` (locked name). Methods matching the run URLs: create (insert + reformulate), reformulate, retrieve, assemble, generate, verify, get, list. This module **is** allowed to import `reformulate_query`, `compose_search_text`, `search_chunks`, `truncate_to_token_budget`, `build_context_block`, `generate_estimate`, `validate_citations`, `check_coherence`. Generate here follows Lidr’s **stage** generate (no auto-retry; return fabricated ids / coherence on the run payload). `estimate_from_transcript` stays on the one-shot path only. Persist after each successful step; if persist fails → error the caller (503 at HTTP), do not fail-open.
- Recreate `estimator` **without** `-v` so compose runs `alembic upgrade head`.

**Acceptance:** `\dt` shows `estimation_runs`. `alembic_version` is `0004_session9_estimation_runs`. `documents` / `chunks` / `chunking_comparisons` still there. Facade exists and is callable from tests without FastAPI. No new routes in `main.py`.

**Stop.** Tick. Wait.

## Step 4 — HTTP (retrieval, one-shot, ejecuciones) + security

This is the surface Streamlit (and curl) will call. Limiter + the two RAG API keys + request id. Routers stay thin.

Copy-from: Lidr `security.py`, `rate_limiting.py`, `deps.py`, `retrieval.py`, `estimate.py` (from-transcript), `main.py` hunk.

- `routers/rag_estimate.py`: one-shot `/from-transcript` → `estimate_from_transcript` (Lidr). Does not go through the facade. Does not write `estimation_runs`.
- `routers/retrieval.py`: Lidr retrieval router. Does not write `estimation_runs`.
- `routers/rag_runs.py`: **thin.** Each handler: auth + limiter + `Depends` + one facade method + 404/502/503 mapping. **Forbidden in this file:** `from generation.rag.query_reformulator`, `search_chunks`, `context_assembler`, `estimator`, `validation`. If you need those, you are in the wrong layer — go back to `services/rag_runs.py`.
- `main.py`: `app.state.limiter`, 429 handler, request-id middleware, include retrieval / from-transcript / runs. CORS stays commented off.
- Rate limits: copy Lidr numbers (retrieval 120/min, from-transcript 10/min). Runs: same order of magnitude as the matching Lidr stage (reformulate 30, retrieve/assemble 60, generate 15). List/show 60.
- Tests: `test_security.py`, `test_rate_limiting.py`, `test_idempotency.py`, HTTP tests for retrieval + from-transcript + ejecuciones (adapt Lidr `test_estimate_stages.py` to `/v1/estimate/runs…`; do not assert `/stages/`). Fake LLM / embedder at the facade or pipeline boundary, like Lidr.

**Acceptance:** `GET /docs` shows the new paths. `POST /search` and `POST /api/v1/estimate` still documented as before. Hitting a new path without `X-API-Key` is 401. `rg "reformulate_query|search_chunks|generate_estimate" src/routers/rag_runs.py` is empty. Existing pytest still green.

**Stop.** Tick. Wait.

## Step 5 — Streamlit wizard tab

Same product as their wizard, in our client. No Ruby. No second database.

Copy-from: behaviour of their wizard screens (new / step reformulation / retrieval / augmentation / generation / verification / index), not their templates.

- New tab after Chunking Lab, before Ajustes. Name: `RAG Wizard`.
- Existing five tabs: do not change behaviour.
- Streamlit sends `X-API-Key: settings.ESTIMATE_API_KEY` and uses `ESTIMATOR_API_BASE_URL`. Timeouts: generation/from-transcript **600s** (same as Chunking Lab compare), not the 30s default.
- Screens, in order:
  1. Paste transcript or upload `.txt`. Start → `POST /v1/estimate/runs`.
  2. Show brief + search text. Button to re-run reformulate. Continue.
  3. Filters: `top_k`, threshold, sector checkboxes (`finance` / `ecommerce` / `healthcare` / `industrial`), year min/max. Run / re-run retrieve. Show hits + distances. If `low_confidence`, say so and do not pretend there is evidence.
  4. Assemble: show how many chunks were kept/dropped and the `<source>` block (collapsible is fine).
  5. Generate: spinner while waiting. Show modules/tasks/days, citations, assumptions, confidence. If fabricated ids or incoherent, show that warning (the point of the wizard generate).
  6. Human table: edit days, add/remove tasks and modules, totals recomputed. Save → `PATCH …/verify`. Keep the model version visible next to the human one.
  7. History: list ejecuciones, reopen one (GET). New ejecución link.
- Re-running an early step must not leave a stale later step on screen (API already clears; UI must follow the payload).
- Do not call `/v1/estimate/stages/*`. Do not call `/from-transcript` from this tab (one-shot is API-only unless a later step says otherwise).

**Acceptance:** with stack up, `ESTIMATE_API_KEY` in `.env`, a short transcript walks all steps and reappears in history after a Streamlit rerun. New / Conversational / Recent / Chunking Lab / Ajustes still work.

**Stop.** Tick. Wait.

## Step 6 — Task corpus + README (student ingest)

The 17 historical budgets are coarse (one chunk per component). Lidr added 12 synthetic projects broken into module→task so the generator can cite task-sized pieces. Optional. Tagged `document_type=historical_task_breakdown` / `chunk_type=historical_task`. Wipe: `DELETE FROM documents WHERE document_type = 'historical_task_breakdown';`

Copy-from: Lidr `data/task_corpus.json`, `scripts/build_task_corpus.py`.

- Copy json to `estimador-cag/data/task_corpus.json`.
- Copy script to `scripts/s09/build_task_corpus.py`. Trap + import rewrite. Compose/host URLs like other scripts. Do not run `--ingest`.
- Known `chunk_type` strings live together as constants (not an enum; the column stays open): `BUDGET_COMPONENT`, `HISTORICAL_TASK`, `SYNTHETIC`. Reuse them from store / ingest / the s09 script / s08 synthetic insert. Values stay snake_case (`"budget_component"`, …).
- README: new section after «Live Session 08», title «Live Session 09 — RAG estimation». What each new URL is for, wizard tab, `ESTIMATE_API_KEY` / `RETRIEVAL_API_KEY`, timeout 600, task-corpus how-to, wipe SQL. Standalone. Do not rewrite the diagnóstico or Live Session 08. (`evolution.md` is step 7, not here.)

**Guide (human, paid embeddings).** Agent does not run `--ingest`. In this step the agent walks the human through the commands, checks the counts after, and stops if anything looks wrong.

```bash
# from estimador-cag/, stack up, OPENAI_API_KEY in .env
docker compose run --rm estimator python scripts/s09/build_task_corpus.py --ingest
```

Host alternative: `uv run python scripts/s09/build_task_corpus.py --ingest` with `ESTIMATOR_BASE_URL=http://localhost:8000`.

After ingest, check (expect 12 documents of this type; each has many `historical_task` chunks):

```bash
docker compose exec -T postgres psql -U postgres -d estimator -c \
  "SELECT document_type, count(*) FROM documents GROUP BY 1 ORDER BY 1;"
```

Wipe:

```sql
DELETE FROM documents WHERE document_type = 'historical_task_breakdown';
```

**Acceptance:** files on disk. README section present. Corpus in DB only if the human ingested; if they did, the count query matches.

**Stop.** Tick. Wait.

## Step 7 — LAST. `docs/evolution.md`

Diary already has `pre_sesion_09`. This step only adds the live we just adopted.

- Event name `session_09_forense` in the list.
- Rows, same grain, `[x]`:
  - RAG pipeline: reformulator (structured brief + fallback) → filtered retrieval (threshold + sector/year/type) → `<source>` assembler → grounded `Estimate` (modules→tasks, engineer-days)
  - HTTP: `POST /v1/retrieval/search`, `POST /v1/estimate/from-transcript` (idempotent), ejecuciones under `/v1/estimate/runs` (persist in Postgres)
  - Security: `ESTIMATE_API_KEY` / `RETRIEVAL_API_KEY`, rate limit per API key, `X-Request-ID`
  - Streamlit tab RAG Wizard (stepper + human verify + history)
  - Optional task corpus (`historical_task_breakdown`)
- Intro line: extend to `session_09_forense`.
- Do **not** edit `pre_sesion_09` or S08 rows. Do not mark the diagnóstico as withdrawn.

**Stop.** Port complete after this step is ticked.

---

## Summary

| # | Title | OK |
|---|---|---|
| 1 | Config, wrapper (`reasoning_effort` + gpt-5 prices), slowapi, `.env.example` | [x] |
| 2 | Pipeline modules + unit tests (no HTTP) | [x] |
| 3 | Alembic `0004` + store + facade `services/rag_runs.py` | [x] |
| 4 | HTTP: RAG API keys, limiter, retrieval, one-shot, thin ejecución router | [x] |
| 5 | Streamlit RAG Wizard tab | [x] |
| 6 | Task corpus files + README section (human ingest) | [x] |
| 7 | `evolution.md` event `session_09_forense` only | [x] |

Port complete.

## Out of this port

- Their web app / copying Rails / a Streamlit-owned database / a second backend “just for the facade”.
- `POST /v1/estimate/stages/*`.
- A fat `routers/rag_runs.py` that imports pipeline functions or talks SQL. Orchestration belongs in `services/rag_runs.py`.
- `budget_assembler` from the diagnóstico.
- Wiring RAG chunks into CAG `POST /api/v1/estimate` / `EstimationResult`.
- `session_10` (hybrid, FTS, rerank, Ajustes keys for reformulation/generation).
- Resurrecting `LLMWrapper.complete()`.
- Turning CORS on.
- Alembic for vector indexes (still operator SQL from S08).
- `docker compose down -v`. Changing compose user/pass/image/port.
- Copying Lidr `uv.lock` / compose wholesale / `CLAUDE.md` / `guides/` / their solved `arquitectura-actual.md`.
- Editing `docs/evolution.md` before step 7, or rewriting pre-s9 / S08 rows.
- Agent-run task-corpus ingest or invented estimates.
- `?? src/alembic.ini`.
- Changing New / Conversational / Recent / Chunking Lab / Ajustes behaviour.
