# Session 6 live — agreed incorporation plan

Bring Lidr `session_06_live` (`aa1fcf4`) into `estimador-cag` without copying Rails, without a Streamlit tab, and without rewriting the CAG we already shipped. FastAPI is the only backend. Schema changes go through Alembic (including the `estimations` table). Ingestion is proven with curl. Scripts run on the host. Do not implement until the steps are executed in order. After each step, stop for review. Do not start the next step until told.

This file is the handoff. A later session should need only this plan plus the two repos. Do not reopen closed decisions.

## Handoff (start here in a new session)

| | Path / value |
|---|---|
| Ours | `/home/morales4dev/wsTakeoff/ai-engineering` branch `session_06_forense`, app `estimador-cag/` |
| Reference | `/home/morales4dev/wsTakeoff/ai-engineering-lidr` `origin/session_06_live` @ `aa1fcf4` |
| Already shipped | CAG through stress: one-shot, sessions, attachments, compression, tier, ACB, golden evals, `TurnObservation`, `evals/stress/`. Postgres table `estimations` via `create_all` in `history.py`. |
| Closed plans (read-only) | `pre_pre_sesion_06_evals.md`, `pre_sesion6_plan.md`, `sesion5_port_plan.md` |
| Lidr copy-from | listed per step. Layout is `estimator/app/…`; ours is `estimador-cag/src/…`. |

Entry points today (ours):

- `src/main.py` — lifespan calls `init_db()`; routers: estimations + sessions. No ingestion.
- `src/services/history.py` — `Base` + `EstimationRow` + `create_all` in `init_db` / persist / list / get. `get_engine()` returns `None` if `DATABASE_URL` is unset. Fail-open writes.
- `src/config.py` — `DATABASE_URL: str | None = None`. No catalog / PII settings.
- `src/utils.py` — `get_absolute_path()` is the `src/` directory. `.env` is `parent / ".env"`.
- `pyproject.toml` — `pythonpath = ["src", "."]`. Tests import `from main import app`, `from schemas.…`.
- `tests/conftest.py` — `from main import app`. That import must work without Postgres.
- `docker-compose.yml` — `postgres:16-alpine` on `5432`, user/db `postgres`/`estimator`. Bind-mount `./src:/app`. Command is uvicorn only.
- `Dockerfile` — `COPY src/ /app/`.
- `streamlit_app.py` — New / Conversational / Recent. Do not touch.

Lidr `session_06_live` does not change estimate, sessions, cache, guardrails, or Streamlit. It adds ingestion.

## Import rewrite (every copied file)

| Lidr | Ours |
|---|---|
| `from app.ingestion.catalog import load_catalog` | `from ingestion.catalog import load_catalog` |
| `from app.persistence.database import get_session` | `from persistence.database import get_session` |
| `from app.main import app` | `from main import app` |
| `from app.dependencies import get_catalog` | `from dependencies import get_catalog` |
| `python -m app.ingestion.architecture` | `python -m ingestion.architecture` |

Drop the `app.` prefix. Do not write `from src.…`. `pytest` already has `src` on `pythonpath`. Host scripts add `src` themselves.

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

Alembic is a CLI (`upgrade head`). `env.py` reads `get_settings().DATABASE_URL`. Compose sets it. Host `.env` already has it. If the URL is missing, `upgrade` fails.

---

## Summary

| # | Title | OK |
|---|-------|----|
| 1 | Alembic (`0000_estimations` + `0001_session6_initial`) + `pgvector` image + seed | [ ] |
| 2 | Catalog YAML (load, inspect, boot log) | [ ] |
| 3 | Filesystem loader + JSON/TXT parsers | [ ] |
| 4 | Orchestrator + `POST /runs` + `GET /jobs` | [ ] |
| 5 | Cleaning library + demo (not on the POST) | [ ] |
| 6 | PII library + demo (not on the POST) | [ ] |
| 7 | Teaching CLIs + README Ingestion (curl) | [ ] |

## Incorporation order (not runtime)

1. Infra — Postgres image, Alembic, seed, lazy `persistence/database.py`. No HTTP.
2. Catalog — YAML is code. Boot logs it. Dep: `pyyaml`.
3. Parse — disk → `Document`s.
4. HTTP — catalog + loader + parser + job row. Does not call steps 5–7.
5. Cleaning — library + host demo.
6. PII — library + host demo. Uses `pseudonym_mappings` from step 1.
7. CLIs + README.

Why this order: the POST needs tables, catalog and parsers. Cleaning and PII are not part of that path. README waits until curl can hit the API.

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

The catalog **is** on the POST. `loader.py` / `inspect.py` do not get this block. Their `__main__` may say they are a CLI.

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
- `alembic/env.py`: `from config import get_settings`, `from persistence.models import Base`. Insert `src` on `sys.path` so `uv run alembic` from `estimador-cag/` resolves them. Compose already has `PYTHONPATH=/app`.
- Host: `cd estimador-cag && PYTHONPATH=src:. uv run alembic upgrade head`.
- Compose: image `pgvector/pgvector:pg16`. Service `postgres`, host **5432**, user/password/db `postgres` / `postgres` / `estimator`. No `CREATE EXTENSION vector` (Session 7).
- Compose command: `alembic upgrade head && uvicorn …`. Volumes: `./src:/app`, `./alembic`, `./alembic.ini`, `./data`.
- Dockerfile: `COPY data/`, `COPY alembic/`, `COPY alembic.ini`.
- Dep: `alembic>=1.13`.
- Settings (boot without keys / without DB):

  | Name | Default (host) |
  |---|---|
  | `CATALOG_PATH` | `get_absolute_path().parent / "data/catalog/catalog.yaml"` |
  | `INGESTION_DATA_ROOT` | `get_absolute_path().parent / "data/seed"` |
  | `PRESIDIO_SPACY_MODEL` | `es_core_news_md` |
  | `PSEUDONYM_FAKER_LOCALE` | `es_ES` |
  | `PSEUDONYM_HASH_SALT` | `change-me-in-prod` |

  `DATABASE_URL` stays optional. Credentials and port stay as they are.
- Copy `data/catalog/catalog.yaml` and `data/seed/` from Lidr.
- `.env.example`: Session 6 block, `localhost:5432`, our user/db.

The current `postgres_data` volume has `estimations` and no `alembic_version`, and uses `postgres:16-alpine`. Before the first `upgrade` on the new image: `docker compose down -v` (wipes Recent-tab rows).

Out of this step: catalog loader, parsers, router, spaCy download.

Acceptance: `down -v` + compose up. `\dt` shows `estimations`, `ingestion_jobs`, `pseudonym_mappings`, `alembic_version` (head = `0001_session6_initial`). No `vector` extension. No `create_all` in `history.py`. `persistence.database` is import-safe without a URL.

## Step 2 — Catalog

Lidr copy-from: `estimator/app/ingestion/catalog/{models,loader,inspect,__init__}.py`, `estimator/tests/test_catalog_loader.py`.

- Import rewrite.
- Dep: `pyyaml` (`import yaml` in `loader.py`).
- Same validators: snake_case names, `include` / `review` / `exclude`, `decision_reason` required when not `include`.
- `dependencies.get_catalog()` — `lru_cache`.
- Lifespan: log `catalog_loaded` (version, totals, included) or `catalog_load_failed`. Do not crash boot.
- Keep the two CLIs. No four-line POST block on them.
- Test: `tests/test_catalog_loader.py`. `"""unit: in-process objects only. No HTTP."""`

Catalog decisions: `presupuestos_json` include, `transcripciones_txt` review, `rate_card_xlsx` exclude.

Out of this step: parsers, HTTP.

## Step 3 — Loader + parsers

Lidr copy-from: `estimator/app/ingestion/documents/`, `loaders/`, `parsers/`, `estimator/tests/test_parsers_{json,txt}.py`.

- Import rewrite.
- `FileSystemLoader` resolves `CatalogSource.location` under `INGESTION_DATA_ROOT`.
- `default_registry()` registers json + txt only.
- `dependencies.get_filesystem_loader`, `get_parser_registry`.
- Tests: `unit`.

Out of this step: HTTP, cleaning, PII.

## Step 4 — Orchestrator + HTTP

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

## Step 5 — Cleaning (not on the POST)

Lidr copy-from: `estimator/app/ingestion/cleaning/**`, `estimator/scripts/demo_cleaning_s06.py`, `estimator/tests/test_cleaning_budgets.py`, `estimator/tests/test_validation_policy.py`.

- Import rewrite. Demo: `ROOT / "src"` on `sys.path`. Host usage in the docstring.
- Do not call cleaning from `ingest_source` or the router.
- Four-line block on `cleaning/__init__.py` and `scripts/demo_cleaning_s06.py`.
- Deps: `pandas`, `pandera`.
- Tests: `unit`.

## Step 6 — PII (not on the POST)

Lidr copy-from: `estimator/app/ingestion/pii/**`, `estimator/scripts/demo_pii_s06.py`, `estimator/tests/test_pii_{recognizers,pseudonymizer}.py`, `build_pseudonymizer` in Lidr `dependencies.py`.

- Import rewrite. Demo: `ROOT / "src"` on path. Host usage in the docstring.
- Do not call PII from `ingest_source` or the router.
- Four-line block on `pii/__init__.py` and `scripts/demo_pii_s06.py`.
- `PostgresMappingStore` uses `pseudonym_mappings`. Demos and tests use `InMemoryMappingStore`.
- Deps: `presidio-analyzer`, `presidio-anonymizer`, `spacy`, `faker`.
- Tests stub the analyzer. No spaCy model required for pytest. `unit`.

## Step 7 — Teaching CLIs + README Ingestion

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

| Name | Default | Step |
|---|---|---|
| `CATALOG_PATH` | `<repo>/data/catalog/catalog.yaml` | 1 / used in 2 |
| `INGESTION_DATA_ROOT` | `<repo>/data/seed` | 1 / used in 3 |
| `PRESIDIO_SPACY_MODEL` | `es_core_news_md` | 1 / used in 6 |
| `PSEUDONYM_FAKER_LOCALE` | `es_ES` | 1 / used in 6 |
| `PSEUDONYM_HASH_SALT` | `change-me-in-prod` | 1 / used in 6 |

`DATABASE_URL` already exists. It stays optional.

---

## Closed decisions

- FastAPI only. No Rails. No `EstimationService`. No Streamlit change. Curl for ingest.
- Feature steps. Stop after each step.
- Imports: drop `app.`. Do not add `src.`.
- Scripts and `es_core_news_md`: host. `sys.path` includes `ROOT / "src"`.
- Engine: lazy. Alembic: CLI.
- Four-line block: the six files listed above. Catalog is on the POST.
- Cleaning, PII, architecture, preflight, demos ship and stay off the POST.
- Ingestion tests ship (`unit` / `smoke`). Older product tests do not.
- One Postgres. Alembic: `0000_estimations` + `0001_session6_initial`. Image `pgvector/pgvector:pg16`. No `CREATE EXTENSION vector`. Port `5432`, user/db `postgres`/`estimator`. Wipe `postgres_data` once before first upgrade.
- Preflight packages include `spacy`, `unstructured[all-docs]`, `openpyxl`, `alembic`.
- `pyyaml` in step 2.
- CAG / estimate / sessions / stress unchanged. History writes fail-open.
- README Ingestion in step 7. No `evolution.md`.

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
