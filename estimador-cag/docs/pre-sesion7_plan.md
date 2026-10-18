# Pre-sesión 7 — plan de import

Copy Lidr `session_07` (`ee1c3f5` «exercise session 07 solved») into `estimador-cag` on `session-07/pre-exercise`. Do not implement from the enunciado sketch. Do not rewrite the CAG, Streamlit, or the Session 6 ingestion POST. Do not implement until this plan is executed in order.

This file is the handoff. Closed plans (`sesion6_port_plan.md`, `pre_sesion6_plan.md`, …) are read-only except to reuse the import-rewrite rule.

## Handoff (start here)

| | Path / value |
|---|---|
| Ours | `/home/morales4dev/wsTakeoff/ai-engineering` branch `session-07/pre-exercise` @ `92b486d`, app `estimador-cag/` |
| Reference | `/home/morales4dev/wsTakeoff/ai-engineering-lidr` branch `session_07` @ `ee1c3f5` (parent `aa1fcf4` = `session_06_completed`) |
| Layout | Lidr `estimator/app/…`. Ours `estimador-cag/src/…`. |
| Service name | Both Compose services are `estimator`. The enunciado says `servicio_ia`. That name is in neither repo. README/commands use `estimator`. |
| Already shipped | Session 6 ingest port. `EMBEDDING_MODEL=text-embedding-3-small` already in `src/config.py` and `.env.example` (semantic cache, Session 4). `openai>=1.0` already in `pyproject.toml`. `get_openai_client()` already in `src/dependencies.py`. |
| Not in tree | `src/embedding_pipeline/`, `data/budgets_sample.json`, `scripts/compare.py`, `tiktoken` as a **direct** dep. |

Entry points **at plan start** (this port replaces the last two):

- `src/main.py` — routers: estimations + sessions + ingestion. No embeddings.
- `src/dependencies.py` — no `get_chunker` / `get_embedder`.
- `scripts/` — s06 host demos only. No `compare.py` in git.
- `docker-compose.yml` — volumes: `./src:/app`, alembic, data. **No** `./scripts`.
- `pyproject.toml` — `openai>=1.0`, no `tiktoken`.
- `README.md` — Ingestion at the end. No Sesión 7 section.

## What Lidr actually changed (git evidence)

`git diff --stat aa1fcf4..ee1c3f5` is 15 files, +1136/−8. No tests. No Streamlit. No persistence. No new settings in `config.py`.

| Lidr path | Role | Action |
|---|---|---|
| `estimator/app/embedding_pipeline/{__init__,schemas,chunker,embedder,router}.py` | New module | Copy → `estimador-cag/src/embedding_pipeline/`, rewrite imports |
| `estimator/app/embedding_pipeline/SANITY_CHECK.md` | Three-pair writeup | Copy **structure + commentary idea**. **Re-run** the three pairs; do not paste Lidr’s numbers as ours |
| `estimator/scripts/compare.py` | CLI cosine | Copy → `estimador-cag/scripts/compare.py`, rewrite imports **and** `sys.path` (see trap below) |
| `estimator/data/budgets_sample.json` | 15 budgets, schema of the exercise | Copy as-is → `estimador-cag/data/budgets_sample.json` |
| `estimator/app/main.py` | `include_router(embeddings_router)` | Patch ours; do not copy the file |
| `estimator/app/dependencies.py` | `get_chunker`, `get_embedder` | Patch ours; do not copy the file |
| `estimator/pyproject.toml` | `tiktoken>=0.7.0` | Same line in ours (`openai` already present) |
| `estimator/docker-compose.yml` | `./scripts:/app/scripts` | Same volume in ours. **Locked:** s06 host-only is for s06 demos; s07 needs the mount (Lidr + `docker exec`). |
| `estimator/README.md` | «Sesión 7 — Pipeline de embeddings» | Port the section; adapt paths and service name |
| `estimator/uv.lock` | lockfile bump | **Do not copy.** `uv lock` / `uv sync` after pyproject |
| `estimator/data/catalog/catalog.yaml` | comment «Proyecto 2» → «Proyecto» | **Do not copy.** Unrelated to embeddings. Ours still says «Proyecto 2» |

## Session 6 seed is the wrong schema

Do not feed `data/seed/budgets/*.json` to `POST /embeddings/ingest`.

Ours (`BUDGET-2024-0001.json`): `client_name`, `currency`, `total_amount`, `signed_at`, `phases[]`. No `client_metadata`, no `components`, no `project_summary`.

Lidr sample (`BUD-2024-001`): `client_metadata.{name,sector,country}`, `project_summary`, `main_technology`, `year`, `total_estimated_hours`, `components[]` with `component_id` / `tech_stack` / `complexity`.

`Budget` in Lidr `schemas.py` will 422 the seed. The enunciado allows «tu propio dataset de la Sesión 06» only if it matches that schema. Ours does not. Use the sample.

`Sector = Literal["finance", "ecommerce", "healthcare", "industrial"]` in Lidr schemas matches the 15 sample rows (4/4/4/3). Keep the Literal. Do not widen it for the seed.

## Import rewrite (every copied `.py`)

Same rule as Session 6. Drop the `app.` prefix. Do not write `from src.…`.

| Lidr | Ours |
|---|---|
| `from app.embedding_pipeline.schemas import …` | `from embedding_pipeline.schemas import …` |
| `from app.embedding_pipeline.chunker import JSONStructuralChunker` | `from embedding_pipeline.chunker import JSONStructuralChunker` |
| `from app.embedding_pipeline.embedder import OpenAIEmbedder` | `from embedding_pipeline.embedder import OpenAIEmbedder` |
| `from app.embedding_pipeline.router import router as embeddings_router` | `from embedding_pipeline.router import router as embeddings_router` |
| `from app.dependencies import get_chunker, get_embedder` | `from dependencies import get_chunker, get_embedder` |
| `from app.config import get_settings` | `from config import get_settings` |

`pytest` `pythonpath = ["src", "."]`. Host scripts that run outside pytest must put `src` on `sys.path` themselves — **except** `compare.py` also has to run inside the container (see trap).

## `compare.py` sys.path trap (do not copy Lidr blindly)

Lidr layout is the same on host and in Docker: package is `app/` under the project root. Their script does `sys.path.insert(0, ROOT)` and `from app.…`. Both work.

Ours is not:

| | Host (`cd estimador-cag`) | Container (`WORKDIR /app`, volume `./src:/app`) |
|---|---|---|
| `config.py` lives at | `src/config.py` | `/app/config.py` |
| `PYTHONPATH` | unset for `uv run python scripts/…` (pytest pythonpath does not apply) | Dockerfile sets `PYTHONPATH=/app` |
| s06 demos | insert `ROOT / "src"`; host-only | never run in the container |

If `compare.py` only inserts `ROOT / "src"`, Docker looks for `/app/src/config.py` and misses. If it only inserts `ROOT`, the host looks for `estimador-cag/config.py` and misses.

**Locked:** option 1 — the script inserts `src` on `sys.path` (same as s06 demos). Not `PYTHONPATH` by hand. Not installing the project.

Required adaptation (not in Lidr):

```python
ROOT = Path(__file__).resolve().parent.parent  # estimador-cag/ on host, /app in the container
for candidate in (ROOT / "src", ROOT):
    if (candidate / "config.py").exists():
        sys.path.insert(0, str(candidate))
        break
```

Docstring commands:

```bash
# host
cd estimador-cag
uv run python scripts/compare.py --text-a "..." --text-b "..."

# container (after the scripts volume)
docker compose exec estimator python scripts/compare.py --text-a "..." --text-b "..."
```

Not `servicio_ia`. Not Lidr’s `from estimator/` wording.

## Scripts volume vs Session 6 rule

**Locked (yes):** add `./scripts:/app/scripts`. s06 said scripts stay on the host; s07 is a different exercise. Lidr mounts it so `docker compose exec estimator python scripts/compare.py` works, and we need the same command.

Do not `COPY scripts/` into the image. s06 demos stay host-first; they just become visible inside the container as a side effect of the mount. Do not document `docker exec` for the s06 demos.

Compose volume list after the patch:

```yaml
volumes:
  - ./src:/app
  - ./alembic:/app/alembic
  - ./alembic.ini:/app/alembic.ini
  - ./data:/app/data
  - ./scripts:/app/scripts
```

`./src:/app` still hides image files under `/app`. `scripts` must be mounted on top, same as `data` / `alembic`.

## tiktoken

`openai>=1.0` is already a direct dep. `tiktoken` is already in `uv.lock` as a **transitive** package (openai / litellm). It is **not** in `[project] dependencies` (the specifier list around `uv.lock` line 1114 has no `tiktoken`).

Lidr added `"tiktoken>=0.7.0"` as a direct dep with the comment «openai already above». Do the same. Then `uv lock` so the lockfile records the specifier. Rebuild the image (`docker compose build estimator`) because the image venv is `/opt/venv` from the builder stage.

Do not add numpy / scikit-learn. Lidr cosine is `math` + `zip`. Copy that.

## What Lidr added beyond the enunciado (copy anyway)

The enunciado is a sketch. Lidr is the reference. Copy these extras; they are small and already match our DI / logging habits:

- `IngestStats` as a Pydantic model. The enunciado said `stats` is «un dict». The JSON shape is the same four keys: `total_budgets`, `total_chunks`, `total_tokens`, `estimated_cost_usd`.
- `get_chunker` / `get_embedder` in `dependencies.py` with `@lru_cache`. Router uses `Depends`. Enunciado did not mention DI; we already wire everything this way.
- `get_embedder()` returns `None` without `OPENAI_API_KEY`; router maps that to 500 `"Embedding service is not available."` Generic 500 on any other embedder exception, detail in logs. Matches the enunciado 500 contract.
- `PRICE_PER_MILLION_TOKENS_USD = 0.02`, `BATCH_SIZE = 100`, `_RETRY_BACKOFF_SECONDS = (1, 2, 4)`, `EMBEDDING_DIM = 1536` (comment only; they do not pass `dimensions=` to the API).
- Router prefix lives on the router (`APIRouter(prefix="/embeddings")`), then `app.include_router(embeddings_router)` with no extra prefix. Full path `POST /embeddings/ingest`. Do not also pass `prefix="/embeddings"` in `include_router` or the path doubles.

Do **not** invent: other chunkers, Matryoshka `dimensions=`, pgvector, retrieval, Streamlit tab, tests.

## `config.py`

No new fields. `OPENAI_API_KEY` and `EMBEDDING_MODEL` already exist. Lidr `session_07` did not touch `config.py`. Do not add an embeddings-specific setting.

Ours still boots without a key (`llm_configured` on `/health`). Lidr `get_settings` raises if both keys are missing. `get_embedder` already handles `None` client. Leave our boot-without-key behaviour.

## SANITY_CHECK.md

**Locked:** we re-run. Do not paste Lidr’s numbers (0.5957 / 0.1920 / 0.5407, dated 2026-05-27). Cost is ~53 tokens / ~$0.000001.

Lidr’s run is only a reference for “what ‘interesting’ looks like”, not a key:

| Pair | Lidr cosine | Enunciado expectation |
|---|---|---|
| A near | **0.5957** | high (> 0.6) — **they missed the threshold** |
| B unrelated | **0.1920** | low (< 0.4) — pass |
| C generic | **0.5407** | none — they note C ≈ A |

Target path: `src/embedding_pipeline/SANITY_CHECK.md`.

**Stop protocol (after step 5):** the agent does steps 1–5 (tree + CLI + README + image rebuild), then **stops**. The agent does **not** run the live ingest, does **not** run `compare.py` on the three pairs, and does **not** write the three numbers. Steps 6 and 7 are student-run; the agent only guides (commands, expected shape, how to read failures). After the student pastes ingest stats (step 6) and the three `Cosine similarity` lines + a 3–5 line comment (step 7), the agent lands `SANITY_CHECK.md` from **those** numbers if asked, and finishes anything still open (usually nothing).

## README

Append a «Sesión 7 — Pipeline de embeddings» section after Ingestion (end of file), modelled on Lidr lines 207–262. Adapt:

- module path `src/embedding_pipeline/`
- sample `data/budgets_sample.json` is a **JSON array**; body is `{"budgets": [...]}`
- curl/httpie against `http://localhost:8000/embeddings/ingest`
- `docker compose exec estimator` (not `servicio_ia`)
- host: `uv run python scripts/compare.py` from `estimador-cag/`
- link to `src/embedding_pipeline/SANITY_CHECK.md`
- one line: vectors are in-memory; pgvector is Session 8

Lidr quotes «15 presupuestos → 52 chunks → ~4.1k tokens → coste estimado ~$0.00008». Do not copy that sentence until the student has run ingest (step 6) and pasted the stats (or drop the numbers and keep the wrap-array warning).

Do not rewrite the CAG intro («needs no extra infrastructure (embeddings, vector stores)»). That sentence is historically true for CAG. The new section covers the new pipeline.

## Out of scope (do not touch)

- `streamlit_app.py`, Rails, `src/routers/estimations.py`, `src/routers/sessions.py`, `src/routers/ingestion.py`
- `src/ingestion/**`, `data/seed/**`, `data/catalog/catalog.yaml`
- persistence / Alembic / pgvector `CREATE EXTENSION`
- recursive / semantic / hierarchical chunking, contextual retrieval, LLM-enriched chunks
- model bake-off, recall@k, NDCG
- numpy, scikit-learn
- tests (Lidr added none; enunciado defers them)

## Work, in order

### Step 1 — `tiktoken` + rebuild

- Add `"tiktoken>=0.7.0"` to `estimador-cag/pyproject.toml` (comment: Session 7; openai already above).
- `cd estimador-cag && uv lock && uv sync`
- `docker compose build estimator`

**Acceptance:** `uv run python -c "import tiktoken; tiktoken.encoding_for_model('text-embedding-3-small')"` works on the host. Image rebuild finished.

### Step 2 — copy the module, rewrite imports

Copy five files from Lidr `estimator/app/embedding_pipeline/` → `estimador-cag/src/embedding_pipeline/`. Apply the import table. Leave logic, constants, log event names, chunk text format, `chunk_id` `{budget_id}::{component_id}` untouched.

Do not copy `SANITY_CHECK.md` yet (step 7).

### Step 3 — wire FastAPI

`src/main.py`:

```python
from embedding_pipeline.router import router as embeddings_router
# ...
app.include_router(embeddings_router)
```

Keep the existing three includes. Do not copy Lidr CORS (ours is off on purpose).

`src/dependencies.py`: add the two factories from Lidr, with our imports:

```python
from embedding_pipeline.chunker import JSONStructuralChunker
from embedding_pipeline.embedder import OpenAIEmbedder
```

`get_embedder` reuses `get_openai_client()` and `settings.EMBEDDING_MODEL`. Same `None` + log `embedder_disabled` as Lidr.

**Acceptance:** with the stack up, `GET /docs` lists `POST /embeddings/ingest`. A bogus body 422s. No OpenAI call yet.

### Step 4 — sample + `compare.py` + scripts volume

- Copy `estimator/data/budgets_sample.json` → `estimador-cag/data/budgets_sample.json` unchanged.
- Copy `estimator/scripts/compare.py` → `estimador-cag/scripts/compare.py` with import rewrite + sys.path trap above. Cosine stays stdlib. There is no file there now (`scripts/` is only the three s06 demos).
- Add `./scripts:/app/scripts` to `docker-compose.yml`.

**Acceptance:** `python scripts/compare.py --help` works on the host (`uv run`) and via `docker compose exec estimator` after recreate.

### Step 5 — README

Port the Sesión 7 section. Commands use our paths and `estimator`.

### Step 6 — STOP. Student runs the live ingest

Agent stops here. Do not `curl` / httpie the ingest. Do not start `docker compose up` to fire the POST. Guide only.

**Guide (from `estimador-cag/`, stack up, `.env` with `OPENAI_API_KEY`):**

```bash
curl -s -X POST http://localhost:8000/embeddings/ingest \
  -H 'Content-Type: application/json' \
  -d "{\"budgets\": $(cat data/budgets_sample.json)}"
```

Expect 200, `stats.total_budgets == 15`, `chunks[].embedding` length 1536, `estimated_cost_usd` from `total_tokens / 1e6 * 0.02`. 500 if the key is missing (generic message; reason in logs).

The sample has 52 `"component_id"` keys and the chunker is one-chunk-per-component, so `total_chunks == 52` is determined by the file. Tokens and cost are not: count those from the response, do not pre-write Lidr’s ~4.1k / ~$0.00008.

Student pastes `stats` (and a short note if it 500s). Then step 7.

### Step 7 — STOP. Student runs the three pairs

Agent still does not execute `compare.py`. Do not fill `SANITY_CHECK.md` with invented or Lidr numbers.

**Guide (host, from `estimador-cag/`, `.env` with `OPENAI_API_KEY`):**

```bash
uv run python scripts/compare.py \
  --text-a "OAuth 2.0 authentication backend with JWT tokens for fintech mobile app" \
  --text-b "Authorization service using JSON Web Tokens for a banking application"

uv run python scripts/compare.py \
  --text-a "OAuth 2.0 authentication backend with JWT tokens for fintech mobile app" \
  --text-b "Database migration from MySQL to PostgreSQL with zero downtime"

uv run python scripts/compare.py \
  --text-a "Backend services" \
  --text-b "API development"
```

Optional same three via `docker compose exec estimator python scripts/compare.py …` after the scripts volume.

**How to read the numbers** (cosine is −1..1; for these embeddings expect ~0..1):

- A — same idea, different words. Enunciado says “high (> 0.6)”. Lidr got 0.5957. Below 0.6 is not a broken pipeline; write it down.
- B — different topics. Expect clearly under 0.4. If B ≥ A, something is wrong (wrong model, empty vectors, bug in cosine).
- C — two vague phrases. No target. Interesting if C sits close to A: short generic text has little signal. That is why the chunker prepends project/sector/tech.

Student pastes the three `Cosine similarity: …` lines and a 3–5 line comment. Then land `SANITY_CHECK.md` from **those** numbers. After that, finish leftover implementation if any (usually nothing).

## Summary

| # | Title | OK |
|---|-------|----|
| 1 | `tiktoken>=0.7.0` + lock + image rebuild | [x] |
| 2 | Copy `embedding_pipeline/` (minus SANITY_CHECK), import rewrite | [x] |
| 3 | Wire `main.py` + `get_chunker` / `get_embedder` | [x] |
| 4 | Sample JSON + `compare.py` (option 1 sys.path) + scripts volume | [x] |
| 5 | README Sesión 7 | [x] |
| 6 | STOP — student runs live ingest; agent guides only | [x] |
| 7 | STOP — student runs three pairs → `SANITY_CHECK.md` | [x] |

## Locked (was open questions)

1. **SANITY_CHECK** — re-run. Student executes; agent stops and guides. Cost ~$0.000001. Not Lidr’s file.
2. **Scripts volume** — yes, `./scripts:/app/scripts`. s07 ≠ s06. No `COPY` into the image.
3. **Plan path** — `estimador-cag/docs/pre-sesion7_plan.md`.
4. **`compare.py` sys.path** — option 1 (insert `src`, dual-path for Docker flatten).
5. **Live ingest (step 6)** — student executes; agent guides only. Same stop protocol as step 7. Agent does 1–5, then stops.
