# Session 6 live — agreed incorporation plan

Bring Lidr `session_06_live` (`aa1fcf4`) into `estimador-cag` without copying Rails, without a Streamlit tab, and without rewriting the CAG we already shipped. FastAPI is the only backend. Schema changes go through Alembic (including the `estimations` table). Ingestion is proven with curl. Scripts run on the host. Do not implement until the steps are executed in order. After each step, stop for review. Do not start the next step until told.

This file is the handoff. A later session should need only this plan plus the two repos. Do not reopen closed decisions.

## Handoff (start here in a new session)

**Next work is step 4 only.** Step 3 is done. Do not redo HTTP, catalog, parsers, Alembic, the image, or `create_all`. Do not reopen the Q&A below. Stop after step 4 and wait.

| | Path / value |
|---|---|
| Ours | `/home/morales4dev/wsTakeoff/ai-engineering` branch `session_06_forense` @ `61d2659`, app `estimador-cag/` |
| Reference | `/home/morales4dev/wsTakeoff/ai-engineering-lidr` `origin/session_06_live` @ `aa1fcf4` |
| Already shipped | CAG through stress: one-shot, sessions, attachments, compression, tier, ACB, golden evals, `TurnObservation`, `evals/stress/`. **Step 1:** Alembic `0000_estimations` + `0001_session6_initial`, image `pgvector/pgvector:pg16`, seed+catalog on disk, lazy `persistence.database`. **Step 2:** `src/ingestion/` catalog + documents + loaders + parsers (json/txt). `get_catalog` / `get_filesystem_loader` / `get_parser_registry`. Lifespan logs `catalog_loaded` / `catalog_load_failed` (no crash). `pyyaml>=6.0`. **Step 3:** `ingest_source` + `POST /api/v1/ingestion/runs` + `GET /jobs/{job_id}`. No `SessionLocal`; BackgroundTask uses `_open_background_session` (lazy engine). No cleaning / PII on the POST. |
| Closed plans (read-only) | `pre_pre_sesion_06_evals.md`, `pre_sesion6_plan.md`, `sesion5_port_plan.md` |
| Lidr copy-from | listed per step. Layout is `estimator/app/…`; ours is `estimador-cag/src/…`. |

Entry points **after step 3** (ours):

- `src/main.py` — routers: estimations + sessions + ingestion.
- `src/ingestion/orchestrator.py` — `ingest_source`; no cleaning / PII imports. Documents stay in memory.
- `src/routers/ingestion.py` — POST 202 / 404 unknown / 400 not-include; GET 200 / 404. BackgroundTask opens `_open_background_session` (not `SessionLocal`). No URL → request `get_session` → 503.
- `src/schemas/ingestion.py` — run request/response + job view.
- `tests/test_ingestion_endpoint.py` — `smoke`. In-memory jobs; patches `JobsRepository` + `_open_background_session`.
- Everything else under “after step 2” still holds.

Entry points **after step 2** (step 3 added the router; keep as freeze, do not restore):

- `src/main.py` — lifespan: catalog try/except, then `application_started`, then `init_db()`. Routers: estimations + sessions. Still no ingestion HTTP.
- `src/dependencies.py` — `get_catalog`, `get_filesystem_loader`, `get_parser_registry` (`lru_cache`).
- `src/ingestion/` — package docstring only in `__init__.py` (names cleaning / PII / orchestrator; does not import them). `catalog/` + `documents/` + `loaders/` + `parsers/`. `default_registry()` is json + txt.
- `data/catalog/catalog.yaml` — comments say `ingestion.…`, not `app.ingestion`. Loaded at boot; decisions unchanged.
- `tests/test_catalog_loader.py`, `test_parsers_json.py`, `test_parsers_txt.py` — `unit`.
- `pyproject.toml` — `pyyaml>=6.0`.
- Everything else under “after step 1” still holds.

Entry points **after step 1** (step 2 only changed `main.py` + catalog comments; keep as freeze, do not restore):

- `src/main.py` — lifespan calls `init_db()`; routers: estimations + sessions. Still no ingestion HTTP.
- `src/services/history.py` — no `Base`, no `EstimationRow` class, no `create_all`. Imports `EstimationRow` from `persistence.models`. Own `get_engine()` (not merged). Fail-open writes. `init_db`: no URL → `history_disabled`; URL set → `schema_via_alembic`.
- `src/persistence/models.py` — one `Base`: `EstimationRow` + `IngestionJobRow` + `PseudonymMappingRow`.
- `src/persistence/database.py` — lazy `get_engine()` (`None` if no URL). `get_session()` is FastAPI `Depends`; 503 `"database is unavailable"` if unset. No eager `SessionLocal`.
- `src/persistence/repositories/` — Lidr `jobs.py` / `mappings.py`, our imports.
- `src/config.py` — `DATABASE_URL: str | None = None` plus the five Session 6 settings (host Path defaults). None of the five in the machine `.env`.
- `alembic/` — `0000_estimations` then `0001_session6_initial`. `env.py` inserts `src` on `sys.path` if that dir exists; raises if `DATABASE_URL` is missing.
- `docker-compose.yml` — `pgvector/pgvector:pg16`, host **5432**, user/db `postgres`/`estimator`. Command: `alembic upgrade head && uvicorn`. Volumes: `./src:/app`, `./alembic`, `./alembic.ini`, `./data`. Compose env: `CATALOG_PATH` + `INGESTION_DATA_ROOT` under `/app/data/…`. Healthcheck `start_period: 30s`.
- `Dockerfile` — `COPY src/`, `data/`, `alembic/`, `alembic.ini`.
- `data/catalog/catalog.yaml` + `data/seed/` — copied from Lidr, not loaded yet.
- `tests/test_persistence_database.py` — `unit`. Import-safe; 503 without URL (settings monkeypatched).
- `streamlit_app.py` — New / Conversational / Recent. Do not touch.
- Compose bind-mount collision: an empty `src/alembic.ini` can reappear while the stack is up. Do not commit it.

Entry points **at plan start** (step 1 replaced these; keep as freeze, do not restore):

- `src/main.py` — lifespan calls `init_db()`; routers: estimations + sessions. No ingestion. *(was)*
- `src/services/history.py` — `Base` + `EstimationRow` + `create_all` in `init_db` / persist / list / get. `get_engine()` returns `None` if `DATABASE_URL` is unset. Fail-open writes. *(was)*
- `src/config.py` — `DATABASE_URL: str | None = None`. No catalog / PII settings. *(was)*
- `src/utils.py` — `get_absolute_path()` is the `src/` directory. `.env` is `parent / ".env"`. *(still true)*
- `pyproject.toml` — `pythonpath = ["src", "."]`. Tests import `from main import app`, `from schemas.…`. *(still true; step 1 also added `alembic>=1.13`)*
- `tests/conftest.py` — `from main import app`. That import must work without Postgres. *(still true)*
- `docker-compose.yml` — `postgres:16-alpine` on `5432`, user/db `postgres`/`estimator`. Bind-mount `./src:/app`. Command is uvicorn only. *(was)*
- `Dockerfile` — `COPY src/ /app/`. *(was)*
- `streamlit_app.py` — New / Conversational / Recent. Do not touch. *(still true)*

Lidr `session_06_live` adds ingestion. It does not change cache, guardrails, or Streamlit. `estimation.py` / `sessions.py` vs `session_05_live` only grew `TurnObservation` (already in our CAG). See step 1 Q&A. Do not re-port those files.

## Import rewrite (every copied file)

| Lidr | Ours |
|---|---|
| `from app.ingestion.catalog import load_catalog` | `from ingestion.catalog import load_catalog` |
| `from app.persistence.database import get_session` | `from persistence.database import get_session` |
| `from app.main import app` | `from main import app` |
| `from app.dependencies import get_catalog` | `from dependencies import get_catalog` |
| `python -m app.ingestion.architecture` | `python -m ingestion.architecture` |

Drop the `app.` prefix. Do not write `from src.…`. `pytest` already has `src` on `pythonpath`. Host scripts add `src` themselves. Same rewrite for comments in `data/catalog/catalog.yaml` that still say `app.ingestion`.

## Scripts

Architecture, preflight and demos run on the host:

```python
ROOT = Path(__file__).resolve().parent.parent  # estimador-cag/
sys.path.insert(0, str(ROOT / "src"))
```

Docstrings and README: host commands only. Do not put `scripts/` in the image or in Compose volumes. `es_core_news_md` is installed on the host.

## Engine

`src/persistence/database.py` follows `history.get_engine()`: importing the module does not call `create_engine`. `get_session` as a FastAPI `Depends` raises `HTTPException(503, detail="database is unavailable")` when `DATABASE_URL` is unset. Tests override `get_session`.

Leave `history.get_engine()` in place. History writes stay fail-open. Ingest does not return 202 without a database.

Alembic is a CLI (`upgrade head`). `env.py` reads `get_settings().DATABASE_URL`. Compose sets it. Host `.env` already has it. If the URL is missing, `env.py` raises explicitly — do not pass `None` to `set_main_option`.

---

## Summary

| # | Title | OK |
|---|-------|----|
| 1 | Alembic (`0000_estimations` + `0001_session6_initial`) + `pgvector` image + seed | [x] |
| 2 | Catalog YAML + filesystem loader + JSON/TXT parsers | [x] |
| 3 | Orchestrator + `POST /runs` + `GET /jobs` | [x] |
| 4 | Cleaning library + demo (not on the POST) | [ ] |
| 5 | PII library + demo (not on the POST) | [ ] |
| 6 | Teaching CLIs + README Ingestion (curl) | [ ] |

## Incorporation order (not runtime)

1. Infra — Postgres image, Alembic, seed, lazy `persistence/database.py`. No HTTP.
2. Catalog + parse — YAML is code; boot logs it; disk → `Document`s. One package (`src/ingestion/`), one new dep (`pyyaml`). No HTTP.
3. HTTP — catalog + loader + parser + job row. Does not call steps 4–6.
4. Cleaning — library + host demo.
5. PII — library + host demo. Uses `pseudonym_mappings` from step 1.
6. CLIs + README.

Why this order: the POST needs tables, catalog and parsers. Catalog and parsers share one dep and live in one package; they are not two feature slices. Cleaning and PII pull pandas / Presidio and are not on that path. README waits until curl can hit the API.

Runtime of `POST /api/v1/ingestion/runs`:

source in catalog? → `decision == include`? → insert job `pending` → 202 → BackgroundTask: load files → parse → count docs → job `completed` / `failed`.

Not in that path: pandas/pandera, Presidio, architecture CLI, preflight.

---

## Four-line block

`POST /api/v1/ingestion/runs` does not call cleaning or PII. Those packages run only via the host demos. Architecture and preflight are host CLIs.

Put this English block on these files only:

- `src/ingestion/cleaning/__init__.py`
- `src/ingestion/pii/__init__.py`
- `src/ingestion/architecture.py`
- `scripts/preflight_s06.py`
- `scripts/demo_cleaning_s06.py`
- `scripts/demo_pii_s06.py`

Inner files (`policy.py`, `analyzer.py`, …) keep Lidr’s docstring (what the file does).

```
NOT ON THE HTTP PATH.

What:        <one sentence>
What for:    <one sentence>
Why not wired: POST /api/v1/ingestion/runs only does catalog → load → parse → job row.
When useful: <the exact host command>
```

The catalog **is** on the POST. `loader.py` / `inspect.py` do not get this block. Their `__main__` may say they are a CLI. `documents/` / `loaders/` / `parsers/` are on the POST; no block.

---

## Step 1 — Alembic + image + seed

Lidr copy-from: `estimator/alembic.ini`, `estimator/alembic/{env.py,script.py.mako}`, `estimator/alembic/versions/0001_session6_initial.py`, `estimator/app/persistence/{__init__,database,models}.py`, `estimator/app/persistence/repositories/{__init__,jobs,mappings}.py`, `estimator/data/catalog/catalog.yaml`, `estimator/data/seed/**`, `estimator/.env.example` (Session 6 block).

| Rev | What |
|---|---|
| `0000_estimations` | `CREATE TABLE estimations` matching `EstimationRow` |
| `0001_session6_initial` | Lidr’s filename and `revision`. `down_revision = "0000_estimations"` |

`0000` columns (`src/services/history.py`):

| Column | Type |
|---|---|
| `id` | `Integer` PK |
| `description` | `Text` not null |
| `project_type` | `String` not null |
| `detail_level` | `String` not null |
| `output_format` | `String` not null |
| `response_payload` | `JSONB` not null |
| `prompt_version` | `String` nullable |
| `cached` | `Boolean` not null, default false |
| `created_at` | `DateTime(timezone=True)` not null, `server_default=now()` |
| `updated_at` | `DateTime(timezone=True)` not null, `server_default=now()` |

`EstimationRow.updated_at` uses SQLAlchemy `onupdate=func.now()`. The migration does not add a Postgres trigger.

- One `DeclarativeBase` in `src/persistence/models.py`. `EstimationRow` lives there. `history.py` imports `Base` / `EstimationRow`. Alembic `target_metadata` is that metadata. Import `EstimationRow` so Alembic sees it.
- `src/persistence/database.py` — lazy engine. Same `DATABASE_URL` as history.
- Repos: Lidr `jobs.py` / `mappings.py`, our imports.
- `init_db()`: no URL → log `history_disabled`; URL set → log `schema_via_alembic`. No `create_all`. No migrate. Remove every `Base.metadata.create_all(...)` from `history.py`. Estimate persist stays fail-open.
- `alembic.ini`: same layout as Lidr. Placeholder `sqlalchemy.url` = `postgresql+psycopg://postgres:postgres@localhost:5432/estimator`. Live URL comes from Settings in `env.py`.
- `alembic/env.py`: `from config import get_settings`, `from persistence.models import Base`. Insert `src` on `sys.path` so `uv run alembic` from `estimador-cag/` resolves them. Compose already has `PYTHONPATH=/app`. Missing `DATABASE_URL` → raise; do not pass `None` to `set_main_option`.
- Host: `cd estimador-cag && PYTHONPATH=src:. uv run alembic upgrade head`.
- Compose: image `pgvector/pgvector:pg16`. Service `postgres`, host **5432**, user/password/db `postgres` / `postgres` / `estimator`. No `CREATE EXTENSION vector` (Session 7).
- Compose command: `alembic upgrade head && uvicorn …`.
- Volumes (host → container). `./src:/app` hides anything `COPY`’d into `/app`, so the other three must be mounted on top:
  - `./src:/app`
  - `./alembic:/app/alembic`
  - `./alembic.ini:/app/alembic.ini`
  - `./data:/app/data`
- Dockerfile: `COPY src/`, `COPY data/`, `COPY alembic/`, `COPY alembic.ini`. Image is self-contained; Compose bind-mounts win at runtime (same pattern as `src/` today).
- Compose `environment` (container only; same pattern as `REDIS_URL` / `DATABASE_URL`):
  - `CATALOG_PATH=/app/data/catalog/catalog.yaml`
  - `INGESTION_DATA_ROOT=/app/data/seed`
  Host uvicorn does not read this block. It uses the Settings defaults below.
- Dep: `alembic>=1.13`.
- Settings (boot without keys / without DB). Host defaults use `get_absolute_path().parent` (`estimador-cag/`). Compose overrides the two paths. None of the five go in the machine `.env`.

  | Name | Default (host) |
  |---|---|
  | `CATALOG_PATH` | `get_absolute_path().parent / "data/catalog/catalog.yaml"` |
  | `INGESTION_DATA_ROOT` | `get_absolute_path().parent / "data/seed"` |
  | `PRESIDIO_SPACY_MODEL` | `es_core_news_md` |
  | `PSEUDONYM_FAKER_LOCALE` | `es_ES` |
  | `PSEUDONYM_HASH_SALT` | `change-me-in-prod` |

  `DATABASE_URL` stays optional. Credentials and port stay as they are.
- Copy `data/catalog/catalog.yaml` and `data/seed/` from Lidr.
- `.env.example`: Session 6 block, `localhost:5432`, our user/db. List the five names with their host defaults. Comment on each: not required in local `.env` — Settings defaults cover the host; Compose sets the two paths. Do not add them to the machine `.env`.

The current `postgres_data` volume has `estimations` and no `alembic_version`, and uses `postgres:16-alpine`. Before the first `upgrade` on the new image: `docker compose down -v` (wipes Recent-tab rows).

Out of this step: catalog loader, parsers, router, spaCy download.

Acceptance: `down -v` + compose up. `\dt` shows `estimations`, `ingestion_jobs`, `pseudonym_mappings`, `alembic_version` (head = `0001_session6_initial`). No `vector` extension. No `create_all` in `history.py`. `persistence.database` is import-safe without a URL.

**Done.** Measured on compose after `down -v`: four tables, head `0001_session6_initial`, no `vector`, boot log `schema_via_alembic`, `/health` 200, `tests/test_persistence_database.py` green. Commit `7186193`. Volume wipe was once; do not `down -v` again unless told.

### Step 1 — Q&A (do not reopen)

Recorded so a later session does not re-litigate this. Not a new design pass.

**Before implement (readiness + two doubts)**

Plan vs trees: matched. No `alembic/` / `ingestion/` / `persistence/` yet. `history.py` had `create_all` in four places. Lidr `aa1fcf4` has every copy-from file. `ingest_source` does not import cleaning or PII. Catalog decisions: `presupuestos_json` include, `transcripciones_txt` review, `rate_card_xlsx` exclude. `PROYECTO_2` → RAG is in Lidr’s `test_architecture.py`.

Plan wording that is imprecise — do not “fix” Lidr or re-port CAG:

- «Lidr does not change estimate / sessions»: vs `session_05_live`, `estimation.py` and `sessions.py` *did* change (`82fd1d9`, `TurnObservation`). That is already in our CAG. Cache / guardrails / Streamlit: no diff. Do not copy those two files.
- Lidr `database.py` is **not** lazy (`SessionLocal = sessionmaker(bind=create_engine_from_settings())` at import). We did not copy that. Lidr’s ingest smoke also patches `SessionLocal`; our step-3 test must patch the lazy factory / `get_session`, not an eager `SessionLocal`.
- Lidr `DATABASE_URL` is a required `str` with default `estimator@localhost:5433`. Ours stays optional. `env.py` must raise if unset (Lidr never passes `None`).
- Lidr `0001` has `down_revision = None`. Ours is `"0000_estimations"`.
- Lidr image does not `COPY` alembic/data (they mount `./app:/app/app`, so those paths are not hidden). Ours `./src:/app` hides them → the extra Compose mounts are required.
- Lidr `CATALOG_PATH` is cwd-relative. Inside our container `get_absolute_path().parent` is `/`, not `/app`. Compose must set the two paths.
- Lidr scripts insert `ROOT` for package `app`. Ours insert `ROOT / "src"`. Drop Lidr’s `docker compose exec … python scripts/…` lines (scripts are host-only).
- Four-line POST block is ours, not in Lidr.

Unverified at that review (later closed by doing step 1): volume `\dt` before wipe; machine `.env` (example has `DATABASE_URL`; the five Session 6 names were not added); spaCy on host; whether `unstructured[all-docs]` builds on slim (step 6).

Doubts asked and answered:

1. Compose healthcheck `start_period` is 10s; Lidr uses 30s with `alembic && uvicorn`. **Use 30s.**
2. Lazy engine, what to name it. **Lazy.** Symbols: `persistence.database.get_engine()` and `get_session()` (Depends → 503). No eager `SessionLocal`. Leave `history.get_engine()` in place.

**After implement (same session; architecture, not new work)**

Q: `pgvector/pgvector:pg16` still has Postgres?  
A: Yes. PostgreSQL 16 with the pgvector **binary compiled in**. We did not `CREATE EXTENSION vector`. Same reason as Lidr: avoid recreating the volume in session 7. Not Alpine.

Q: What is `\dt`? What did it prove?  
A: psql *describe tables*. It proved Alembic created `estimations`, `ingestion_jobs`, `pseudonym_mappings`, `alembic_version`. It does not prove the API, jobs, or data. `vector` was a separate `pg_extension` query (empty).

Q: What is `script.py.mako`?  
A: Alembic’s template for `alembic revision`. `0000`/`0001` were written by hand. Compose `upgrade head` does not execute the mako.

Q: What does `.mako` stand for?  
A: **Mako**, a Python templating engine. Not “migration”.

Q: Settings/`.env` mixes estimator and ingest. Two envs?  
A: The smell is real (`Settings` is a session 2–6 drawer). Two `.env` files do not isolate anything: one FastAPI process, one `os.environ`. `DATABASE_URL` is already shared (`estimations` and ingest tables). Cosmetic unless we split **processes**. Not this port.

Q: Why “they share a process”? Is `src/producto` vs `src/ingesta` easy?  
A: Folders ≠ process. One uvicorn PID, `BackgroundTask` on that worker. A folder split is a rename. Two products = two apps, who owns Alembic, a worker for 202, session-7 glue. **Buried.** Ingestion-as-router is the grain for this course.

Q: Same Postgres for two unrelated things — two schemas?  
A: Same server, two uses, no FKs. All tables are `public`. Two schemas are possible and still one URL / one Alembic. Not worth it. Two databases would be real isolation on **one engine**; two engines is over-resource.

Q: One PG engine, two DBs, two Alembic, two products, almost two repos?  
A: One server + two databases = cheap isolation, fine as a picture. Two **products** is a different bill: ingest today is catalog → parse → job row, not a product. Session 7 RAG joins what we would split. Monorepo with two apps later if ingest becomes a pipeline. Almost-two-repos for a course is theatre. Drawn, not built.

Q: `services/` mixes ingest and estimator — a mess?  
A: `services/` is estimator-only (`history`, conversational, LLM, cache, ACB…). Lidr puts ingest in `app/ingestion/`. The mix is `persistence/models.py` (three rows, one `Base`) and `config` / `dependencies`. Do not reshuffle `services/`. Step 2 adds `src/ingestion/` as a package, like Lidr.

Q: `history.py`?  
A: Estimator persist for the Recent tab. Fail-open. The **model** moved to `persistence.models`; the **access** stayed here; two `get_engine()` on purpose (closed: do not merge). Not ingest. A later cleanup could be `persistence/repositories/estimations.py`. Not this port.

Q: `EstimationRow` — estimations or ingest?  
A: **Estimations.** One-shot `/estimate` row for Recent. It **lives** in `persistence/models.py` next to ingest tables because one `Base` / one Alembic, not because it is ingest.

Q: So the messy drawer is `persistence/`?  
A: Yes. `persistence/` is Postgres (Base, Alembic, lazy engine, job/mapping repos), not the ingest package and not the estimate package. Ingest will be `src/ingestion/`. Estimate stays `services/` + `routers/estimations.py`. `history.py` is the Recent facade.

Q: “The three rows share `models.py` because we share engine and migration chain, not domain”?  
A: Plumbing. Alembic sees one `Base.metadata`. No FKs. A join between `estimations` and `ingestion_jobs` means nothing. Same disk, same `upgrade head`. If we had two databases, each would have its own `models.py`.

Q: Package inside-out: `ingesta/persistence`, `estimation/routers`, `common/`?  
A: Package-by-domain (modular monolith), not two services. Cleaner if this grows. `common/` would still hold `Base` / Alembic / `DATABASE_URL` while there is one DB — the drawer changes name. Two true persistences = two Alembic = the two-DB design again. **Not mid-port.** Lidr is already a hybrid: ingest is a feature package; CAG is layered. Step 2’s `src/ingestion/` is that hybrid, not the glove.

## Step 2 — Catalog + parse

Lidr copy-from: `estimator/app/ingestion/__init__.py`, `estimator/app/ingestion/catalog/{models,loader,inspect,__init__}.py`, `estimator/app/ingestion/documents/`, `estimator/app/ingestion/loaders/`, `estimator/app/ingestion/parsers/`, `estimator/tests/test_catalog_loader.py`, `estimator/tests/test_parsers_{json,txt}.py`.

- Import rewrite.
- Dep: `pyyaml` (`import yaml` in `catalog/loader.py`). Parsers and the filesystem loader add no further deps (stdlib + pydantic already in the project).
- `src/ingestion/__init__.py` is Lidr’s package docstring (no imports). Rewrite `app.` paths. It names cleaning / PII / orchestrator; those packages are not copied here and this file does not import them (Lidr’s doesn’t either).
- Same catalog validators: snake_case names, `include` / `review` / `exclude`, `decision_reason` required when not `include`.
- `dependencies.get_catalog()` — `lru_cache`.
- Lifespan: log `catalog_loaded` (version, totals, included) or `catalog_load_failed`. Do not crash boot.
- Keep the two catalog CLIs. No four-line POST block on them.
- `FileSystemLoader` resolves `CatalogSource.location` under `INGESTION_DATA_ROOT`.
- `default_registry()` registers json + txt only.
- `dependencies.get_filesystem_loader`, `get_parser_registry`.
- Tests: `tests/test_catalog_loader.py`, `tests/test_parsers_json.py`, `tests/test_parsers_txt.py`. All `"""unit: in-process objects only. No HTTP."""`

Catalog decisions: `presupuestos_json` include, `transcripciones_txt` review, `rate_card_xlsx` exclude.

Out of this step: HTTP, cleaning, PII, orchestrator.

**Done.** `uv run pytest tests/test_catalog_loader.py tests/test_parsers_json.py tests/test_parsers_txt.py tests/test_persistence_database.py tests/test_conversational_client.py` — 15 passed. No HTTP.

### Step 2 — Q&A (do not reopen)

1. `src/ingestion/__init__.py` — copy Lidr’s (docstring, no imports). Rewrite `app.` paths. It names cleaning / PII / orchestrator; those packages are not in this step and this file does not import them.
2. `data/catalog/catalog.yaml` comments — align: `app.ingestion` → `ingestion` (same rewrite as Python).
3. After this step (and every later step): tick the summary checkbox, point the handoff at the next step, stop. Do not start the next step until told.

## Step 3 — Orchestrator + HTTP

Lidr copy-from: `estimator/app/ingestion/orchestrator.py`, `estimator/app/routers/ingestion.py`, `estimator/app/schemas/ingestion.py`, `estimator/tests/test_ingestion_endpoint.py`.

- Import rewrite. Smoke monkeypatch: `routers.ingestion.JobsRepository`.
- `ingest_source(...)`: unknown / not-include → `IngestionRejected`; job pending → running → completed / failed; returns `list[Document]` in memory; does not persist documents; does not import cleaning or PII.
- Router `/api/v1/ingestion`:
  - `POST /runs` `{ "source_name" }` → 202 `{ job_id, source_name, status }` (`pending`). BackgroundTask opens its own Session.
  - Unknown → 404 `{ reason: unknown_source, source_name }`.
  - Not include → 400 `{ reason: source_not_included, decision, decision_reason }`.
  - `GET /jobs/{job_id}` → 200 or 404 `"job not found"`.
- `main.py` includes the router.
- Test: `test_ingestion_endpoint.py` (in-memory jobs, stub `get_session`, tmp catalog). `"""smoke: TestClient. No provider. No Postgres."""`
- No `DATABASE_URL` on a real request: 503.

Out of this step: README, cleaning, PII, Streamlit.

**Done.** `uv run pytest tests/test_ingestion_endpoint.py` plus catalog/parser/persistence/conversational — 21 passed. BackgroundTask patched via `_open_background_session`, not `SessionLocal`.

## Step 4 — Cleaning (not on the POST)

Lidr copy-from: `estimator/app/ingestion/cleaning/**`, `estimator/scripts/demo_cleaning_s06.py`, `estimator/tests/test_cleaning_budgets.py`, `estimator/tests/test_validation_policy.py`.

- Import rewrite. Demo: `ROOT / "src"` on `sys.path`. Host usage in the docstring.
- Do not call cleaning from `ingest_source` or the router.
- Four-line block on `cleaning/__init__.py` and `scripts/demo_cleaning_s06.py`.
- Deps: `pandas`, `pandera`.
- Tests: `unit`.

## Step 5 — PII (not on the POST)

Lidr copy-from: `estimator/app/ingestion/pii/**`, `estimator/scripts/demo_pii_s06.py`, `estimator/tests/test_pii_{recognizers,pseudonymizer}.py`, `build_pseudonymizer` in Lidr `dependencies.py`.

- Import rewrite. Demo: `ROOT / "src"` on path. Host usage in the docstring.
- Do not call PII from `ingest_source` or the router.
- Four-line block on `pii/__init__.py` and `scripts/demo_pii_s06.py`.
- `PostgresMappingStore` uses `pseudonym_mappings`. Demos and tests use `InMemoryMappingStore`.
- Deps: `presidio-analyzer`, `presidio-anonymizer`, `spacy`, `faker`.
- Tests stub the analyzer. No spaCy model required for pytest. `unit`.

## Step 6 — Teaching CLIs + README Ingestion

Lidr copy-from: `estimator/app/ingestion/architecture.py`, `estimator/scripts/preflight_s06.py`, `estimator/tests/test_architecture.py`.

- Import rewrite. Preflight: `ROOT / "src"` on path. Host usage in the docstring.
- `python -m ingestion.architecture` — `PROYECTO_2` → RAG. Four-line block on the module.
- `scripts/preflight_s06.py` — four-line block. Checks: spaCy model, `unstructured.partition.auto`, package versions (including `alembic`), catalog, seed, `/health`, tables `ingestion_jobs` / `pseudonym_mappings` / `alembic_version`.
- Deps: `unstructured[all-docs]`, `openpyxl`.
- Host: `uv run python -m spacy download es_core_news_md`. Not in the image.
- `test_architecture.py` — `unit`.
- README: **Ingestion** section after Logs / CAG stress. Curl + host scripts. One sentence: the POST does not clean or pseudonymize.

```bash
cd estimador-cag
docker compose down -v   # empty volume before the first Alembic upgrade
docker compose up --build -d
curl -sf http://localhost:8000/health
```

```bash
curl -sS -X POST http://localhost:8000/api/v1/ingestion/runs \
  -H 'Content-Type: application/json' \
  -d '{"source_name":"presupuestos_json"}'

curl -sS http://localhost:8000/api/v1/ingestion/jobs/<job_id>
```

```bash
curl -sS -X POST http://localhost:8000/api/v1/ingestion/runs \
  -H 'Content-Type: application/json' \
  -d '{"source_name":"transcripciones_txt"}'

curl -sS -X POST http://localhost:8000/api/v1/ingestion/runs \
  -H 'Content-Type: application/json' \
  -d '{"source_name":"rate_card_xlsx"}'

curl -sS -X POST http://localhost:8000/api/v1/ingestion/runs \
  -H 'Content-Type: application/json' \
  -d '{"source_name":"no_existe"}'
```

```bash
cd estimador-cag
PYTHONPATH=src:. uv run alembic upgrade head
uv run python -m spacy download es_core_news_md
PYTHONPATH=src:. uv run python -m ingestion.catalog.inspect data/seed
PYTHONPATH=src:. uv run python -m ingestion.catalog.loader data/catalog/catalog.yaml
PYTHONPATH=src:. uv run python -m ingestion.architecture
PYTHONPATH=src:. uv run python scripts/preflight_s06.py
PYTHONPATH=src:. uv run python scripts/demo_cleaning_s06.py
PYTHONPATH=src:. uv run python scripts/demo_pii_s06.py
```

(`alembic upgrade head` on the host is for uvicorn-on-the-host. Compose already runs it.)

---

## Settings (Session 6)

| Name | Default (host) | Container | Step |
|---|---|---|---|
| `CATALOG_PATH` | `get_absolute_path().parent / "data/catalog/catalog.yaml"` | Compose `environment`: `/app/data/catalog/catalog.yaml` | 1 / used in 2 |
| `INGESTION_DATA_ROOT` | `get_absolute_path().parent / "data/seed"` | Compose `environment`: `/app/data/seed` | 1 / used in 2 |
| `PRESIDIO_SPACY_MODEL` | `es_core_news_md` | Settings default | 1 / used in 5 |
| `PSEUDONYM_FAKER_LOCALE` | `es_ES` | Settings default | 1 / used in 5 |
| `PSEUDONYM_HASH_SALT` | `change-me-in-prod` | Settings default | 1 / used in 5 |

`DATABASE_URL` already exists. It stays optional.

None of the five belong in the local `.env`. `.env.example` lists them with that comment so `cp .env.example .env` does not look like they must be filled in.

---

## Closed decisions

- FastAPI only. No Rails. No `EstimationService`. No Streamlit change. Curl for ingest.
- Feature steps. Stop after each step. Then update this file (summary checkbox + handoff “Next work is step N only”) and wait. Do not start the next step until told.
- Imports: drop `app.`. Do not add `src.`.
- Scripts and `es_core_news_md`: host. `sys.path` includes `ROOT / "src"`.
- Engine: lazy. Alembic: CLI. `env.py` raises if `DATABASE_URL` is missing.
- Image `COPY` + Compose bind-mount for `src`, `alembic`, `alembic.ini`, `data`. Container paths: `/app`, `/app/alembic`, `/app/alembic.ini`, `/app/data`.
- Catalog/seed paths: Settings default on the host; Compose `environment` in the container. The five Session 6 settings stay out of the local `.env`.
- Four-line block: the six files listed above. Catalog is on the POST. `documents/` / `loaders/` / `parsers/` are on the POST.
- Cleaning, PII, architecture, preflight, demos ship and stay off the POST.
- Ingestion tests ship (`unit` / `smoke`). Older product tests do not.
- One Postgres. Alembic: `0000_estimations` + `0001_session6_initial`. Image `pgvector/pgvector:pg16`. No `CREATE EXTENSION vector`. Port `5432`, user/db `postgres`/`estimator`. Wipe `postgres_data` once before first upgrade.
- Preflight packages include `spacy`, `unstructured[all-docs]`, `openpyxl`, `alembic`.
- `pyyaml` in step 2. Catalog + parse are one step: same dep, one package, no HTTP.
- CAG / estimate / sessions / stress unchanged. History writes fail-open.
- README Ingestion in step 6. No `evolution.md`.
- Compose healthcheck `start_period: 30s` (step 1 Q&A).
- Ingest engine: lazy `get_engine` / `get_session`. No eager `SessionLocal`. Do not merge with `history.get_engine()`.
- One process, one `Settings`, one Postgres, one Alembic, tables in `public`. Not two envs, not two schemas, not two products, not `src/producto` vs `src/ingesta`, not inverted-glove packaging.
- `persistence/` is the shared Postgres drawer. `EstimationRow` is estimations. Ingest code goes in `src/ingestion/`.
- Do not re-port Lidr `estimation.py` / `sessions.py` (`TurnObservation` already shipped).
- Do not commit a Compose-leaked `src/alembic.ini`.
- `postgres_data` was wiped once for the first Alembic upgrade. Do not `down -v` again unless told.

## Out of this port

- Rails / `estimator-web`.
- A second Postgres or Lidr’s `estimator@5433` credentials.
- Streamlit Ingestion tab.
- Persisting parsed `Document`s.
- Wiring cleaning or PII into `ingest_source`.
- XLSX/DOCX/PDF parsers.
- `es_core_news_md` in the Docker image.
- A stamp helper for an existing `estimations` table.
- Merging `history.get_engine()` into `persistence.database`.
- Forcing `DATABASE_URL` at Settings boot.
- Changing `/api/v1/estimate` or conversational routes.
- Older product tests.
- Session 7+ (RAG, indexing, `CREATE EXTENSION vector`, wiring PII into ingest).
