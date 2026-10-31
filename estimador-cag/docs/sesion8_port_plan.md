# Session 8 live — agreed incorporation plan

Bring Lidr `session_08_live` lab into `estimador-cag` without copying Rails, without Alembic for the vector indexes, and without inventing UI. FastAPI is the only backend. Streamlit is untouched. Schema stays on `0003_session8_pgvector` (no vector index in migrations). Do not implement until the steps are executed in order. After each step, stop for review. Do not start the next step until told.

This file is the handoff. Closed plans (`pre-sesion8_plan.md`, `sesion7_port_plan.md`, …) are read-only except to reuse the import-rewrite rule and the `compare_chunkers.py` sys.path trap.

Each step starts with a short human note (what this step is for), then the usual copy-from / actions / stop.

## Handoff (start here in a new session)

| | Path / value |
|---|---|
| Ours | `/home/morales4dev/wsTakeoff/ai-engineering` branch `session_08_forense` @ `4e7b8ca`, app `estimador-cag/` |
| Reference | `/home/morales4dev/wsTakeoff/ai-engineering-lidr` `session_08_live` @ `211602d`. **Not** `sesion_08_forense` on Lidr (that tip is session 16). **Not** `ai-engineering-lidr-temp` (`session_07_live`). |
| Lab copy-from | Lidr `6e5e354` (scripts + `sql_s08/01..05` + compose tuning + README section) + `a5e1abc` (`99_revert_live_session.sql`) |
| Search copy-from | Lidr `211602d` (`repository.py` halfvec cast). Apply in **step 5**, after the lab files, not before. |
| Layout | Lidr `estimator/app/…`. Ours `estimador-cag/src/…`. |
| Already shipped | Pre-sesión 8: `store/` + `POST /search` + Alembic `0003` (no vector index) + `query_examples.py` + `README-session-08.md`. Compose already `pgvector/pgvector:pg16`, user/pass `postgres`/`postgres`, service `postgres`, host `5432`, scripts volume. `session_07_forense` and `pre_sesion_08` already have rows in `docs/evolution.md`. |
| Not in tree | `scripts/*_s08.py`, `scripts/s08_common.py`, `scripts/sql_s08/`, compose `shm_size` / `-c` flags, README «Live Session 08», halfvec in `ChunkStore.search`. |

Entry points **at plan start**:

- `src/generation/rag/store/repository.py` — `search` uses `ChunkRow.embedding.cosine_distance` (full vector). No `HALFVEC`.
- `src/generation/rag/store/models.py` — `EMBEDDING_DIMENSIONS = 1536` already there.
- `src/persistence/database.py` — lazy `get_async_session_factory()` → `None` if `DATABASE_URL` unset.
- `src/dependencies.py` — `get_embedder()` → `None` without `OPENAI_API_KEY`.
- `docker-compose.yml` — service `postgres`, no `shm_size`, no `command:` flags. `./scripts:/app/scripts` already mounted.
- `scripts/` — `query_examples.py` (`QUERIES` is the benchmark source of truth), `compare.py`, `compare_chunkers.py` (sys.path trap), s06 demos. No `*_s08.py`.
- `alembic/versions/` — `0000` → `0001` → `0002_chunking_comparisons` → `0003_session8_pgvector`. **No `0004`.**
- `README.md` — «Sesión 8» says `/search` is sequential scan / no vector index in the schema.
- `docs/evolution.md` — last event `pre_sesion_08`. Do not edit s7 / pre-s8 rows.
- `streamlit_app.py` — do not touch.
- `?? estimador-cag/src/alembic.ini` — leftover, out of this port. Do not touch.

## What Lidr actually is (git evidence, not the aula)

`session_08_live` HEAD is `211602d`. Four commits after `origin/session_08` (`837dcbe`, already ported as pre-s8):

| Date | Commit | What |
|---|---|---|
| 2026-06-04 | `6e5e354` | Lab. Scripts `*_s08.py` + `s08_common.py`, `scripts/sql_s08/01..05`, compose shm/tuning, README «Live Session 08» |
| 2026-06-04 | `ca9651d` | Merge `session_08` into `session_08_live` (no unique files) |
| 2026-06-11 | `a5e1abc` | `scripts/sql_s08/99_revert_live_session.sql` |
| 2026-06-12 | `211602d` | `ChunkStore.search` → `cast(embedding, HALFVEC(1536)).cosine_distance`. **After** the live day. |

`git diff --stat origin/session_08..origin/session_08_live` is 15 files, +1276/−6. No Rails. No new tests. No new Alembic. No new HTTP endpoint. No Streamlit. No metadata filters. No hybrid search. The pre-s8 plan listed filters/hybrid as live material; they are **not** in this diff.

`guides/session-8-live-guide.md` is gitignored (`guides/`). Not in the tree. Not a source.

`211602d` was applied the day after the lab. Lidr `compare_indexes_s08.py` still says `ChunkStore.search` is the **vector** path. After `211602d` that is false: `search` is the halfvec path. We copy the script as Lidr live-day, then in step 5 we patch the vector path so the comparison still compares two indexes. See step 5.

## Locked decisions

- Quarry = Lidr `session_08_live` @ `211602d` working tree. Copy a file only when we need that piece.
- `211602d` **enters**, in step 5 (after lab files). `/search` then uses the halfvec expression so it can hit `chunks_embedding_halfvec_idx`.
- Compose **is** edited this time: `shm_size: 1gb` + the five `-c` flags, on **our** service `postgres`. No user/pass/image/port/service-name change. Recreate `postgres` **without** `-v`.
- Indexes = SQL in caliente, like Lidr. **No Alembic `0004`.** `0003` stays «no vector index».
- Comments on every `sql_s08/*.sql` and every `*_s08.py`: brief + sharp, **what the index/script is for and how it acts**, not a CREATE tutorial. Keep Lidr’s pedagogical blocks; adapt compose service/user/paths; drop leftover «repository.py no se editó» after step 5.
- README: **new section** after «Sesión 8», title like Lidr: «Live Session 08 — Indexación vectorial y operación». One line per script/SQL of *para qué*. Adapt `psql` to `postgres` / `-U postgres` / `scripts/sql_s08/…`. Do not fold this into the pre-s8 section. Do not call it only «Creating indexes».
- Entregable Lia: **entra**, student-run (step 6). Agent does not invent latencies or recall. File: `docs/sesion8_ef_search.md`.
- No new pytest. If an existing test goes red, fix that test only.
- No Streamlit tab. No Rails. No UI we do not see in the delta.
- `docs/evolution.md`: **last step only**. Add event `session_08_forense`. Do not rewrite `session_07_forense` / `pre_sesion_08` rows. The pre-s8 `/search` row («sin índice vectorial») stays: that is the **schema**. The live adds operator-created indexes + the halfvec SELECT.
- Import rewrite: drop `app.`. Do not write `from src.…`. `app.foundation.persistence` → `persistence`.
- sys.path: same trap as `compare_chunkers.py` (option 1: insert `src` on host, flattened `/app` in the container). Do not copy Lidr `sys.path.insert(0, ROOT)` + `from app.…`.
- `s08_common.py` adds `require_async_session_factory()` (ours). Lidr always has an engine; our factory returns `None`. Same grain as `require_embedder()`.
- Do not copy `uv.lock`, Lidr `docker-compose.yml` wholesale, `ARCHITECTURE.md`, `output_examples.txt`, Lidr tests, `guides/`.
- Do not edit `Dockerfile` (scripts are bind-mounted). Do not `alembic init`. Do not `docker compose down -v`.
- Agent does not `CREATE INDEX`, does not insert 30k synthetics, does not run the sweep, does not fire OpenAI. Guide only.
- Do not edit `README-session-08.md` (schema answers stay).
- Do not edit `query_examples.py` except if a copied import needs `QUERIES` — it already exports them.

## Import rewrite (every copied `.py`)

| Lidr `session_08_live` | Ours |
|---|---|
| `from app.dependencies import get_embedder` | `from dependencies import get_embedder` |
| `from app.generation.rag.embedding.embedder import …` | `from generation.rag.embedding.embedder import …` |
| `from app.generation.rag.store.repository import ChunkStore` | `from generation.rag.store.repository import ChunkStore` |
| `from app.generation.rag.store.models import …` | `from generation.rag.store.models import …` |
| `from app.generation.rag.schemas import Chunk` | `from generation.rag.schemas import Chunk` |
| `from app.foundation.persistence.database import get_async_session_factory` | `from persistence.database import get_async_session_factory` |
| `from query_examples import QUERIES` | same (sibling under `scripts/`) |

sys.path on every `*_s08.py` that imports project packages (same trap as `compare_chunkers.py`, one extra `.parent` because the lab lives in `scripts/s08/`):

```python
ROOT = Path(__file__).resolve().parent.parent.parent  # estimador-cag/ on host, /app in the container
for candidate in (ROOT / "src", ROOT):
    if (candidate / "config.py").exists():
        sys.path.insert(0, str(candidate))
        break
```

Python lab lives in `scripts/s08/` (not flat under `scripts/`). `s08_common.py` inserts `scripts/` (`parent.parent`) so `query_examples` still resolves. Callers set the project path **before** importing `s08_common`.

`require_embedder()` message: `estimador-cag/.env` (not `estimator/.env`). Recreate command stays `docker compose up -d --force-recreate estimator`.

## Lidr path → action

| Lidr path | Role | Action |
|---|---|---|
| `estimator/docker-compose.yml` (shm + 5 `-c` only) | HNSW build tuning | **Patch** ours. Do not copy the file. Service name stays `postgres`. |
| `scripts/s08_common.py` | Shared helpers + `QUERIES` | Copy → `scripts/s08/s08_common.py`. Rewrite imports. Add `require_async_session_factory()`. |
| `scripts/measure_baseline_s08.py` | SQL latency of `/search`’s SELECT | Copy → `scripts/s08/`. Trap + rewrite |
| `scripts/sweep_ef_search_s08.py` | `ef_search` vs recall | Copy → `scripts/s08/`. Trap + rewrite |
| `scripts/compare_indexes_s08.py` | vector vs halfvec, no drop | Copy → `scripts/s08/`. Trap + rewrite. **Step 5 patches** the vector path. |
| `scripts/report_index_sizes_s08.py` | sizes / `idx_scan` | Copy → `scripts/s08/`. Trap + rewrite |
| `scripts/insert_synthetic_chunks_s08.py` | real embeddings, `count` | Copy → `scripts/s08/`. Trap + rewrite |
| `scripts/sql_s08/01_create_hnsw.sql` | HNSW on `embedding` (`<=>`) | Copy. Adapt `psql` lines. Lead comment = what this index does. |
| `scripts/sql_s08/02_test_antipatron.sql` | `<=>` vs `<->`, silent seq scan | Copy. Adapt `psql` lines. |
| `scripts/sql_s08/03_create_halfvec.sql` | HNSW on `(embedding::halfvec(1536))` | Copy. Adapt `psql` lines. Lead comment = what this index does. |
| `scripts/sql_s08/04_monitoring_queries.sql` | `pg_stat_user_indexes` | Copy. Adapt `psql` lines. |
| `scripts/sql_s08/05_maintenance_cycle.sql` | ANALYZE / VACUUM / REINDEX | Copy. Adapt `psql` lines. |
| `scripts/sql_s08/99_revert_live_session.sql` | drop vector indexes, keep 30k | Copy. Adapt `psql` lines. Step 5 updates the «repository.py» sentence. `ALTER DATABASE estimator` stays (our db name is `estimator`). |
| `estimator/README.md` live section | scripts + SQL tables + Lia | Port section; adapt paths. |
| `app/generation/rag/store/repository.py` | halfvec SELECT | **Patch ours** (step 5). Do not copy the file. |
| `uv.lock` / Lidr compose wholesale / tests / Rails | — | **Do not copy** |

`psql` adaptation (every SQL header and the README):

```bash
# from estimador-cag/
docker compose exec -T postgres psql -U postgres -d estimator \
  < scripts/sql_s08/01_create_hnsw.sql
docker compose exec postgres psql -U postgres -d estimator
```

Not `estimator-postgres`. Not `-U estimator`. Not `estimator/scripts/…`.

---

## Step 1 — Compose tuning

Postgres needs more shared memory and a bigger maintenance budget to build HNSW indexes. This step only changes those knobs; it does not touch credentials, the image, or the data volume.

Copy-from: Lidr `6e5e354` `estimator/docker-compose.yml` hunk (comments + `shm_size` + `command:`).

On **our** `postgres` service, add the same block Lidr put on `estimator-postgres`:

- `shm_size: 1gb`
- `command:` `postgres` with `-c shared_buffers=512MB`, `-c effective_cache_size=1536MB`, `-c work_mem=64MB`, `-c maintenance_work_mem=512MB`, `-c max_parallel_maintenance_workers=2`
- Keep Lidr’s comment (conservative dev values; production scales with RAM).

Do not change `POSTGRES_USER` / `PASSWORD` / `DB`, host port `5432`, image, volume name, healthcheck user (`postgres`). Do not copy Lidr’s `5433` / `estimator` / `estimator-postgres`.

Recreate so the flags apply: `docker compose up -d --force-recreate postgres` (do **not** `-v`). Then `docker compose up -d` if the API was waiting on health.

**Acceptance:** `docker compose exec postgres psql -U postgres -d estimator -c "SHOW shared_buffers;"` prints `512MB`. Volume `postgres_data` still has `documents` / `chunks`. `0003` still applied. No new Alembic file.

**Stop.** Tick. Wait.

## Step 2 — SQL lab (`scripts/sql_s08/`)

These files are the operator’s tools: they create the two vector indexes, show the silent operator mismatch, monitor usage, run maintenance, and undo the lab. They are not migrations; Alembic will not recreate these indexes.

Copy-from: Lidr `scripts/sql_s08/01..05` + `99_revert_live_session.sql`.

- Create `scripts/sql_s08/`. Copy all six files.
- Rewrite every `docker compose exec … estimator-postgres … -U estimator` header to our `postgres` / `-U postgres` / path `scripts/sql_s08/…` (see table above).
- Keep the SQL itself (`CREATE INDEX` names, `m=16`, `ef_construction=128`, `vector_cosine_ops`, `halfvec_cosine_ops`, revert `keep_synthetic=30000`, `ALTER DATABASE estimator RESET hnsw.ef_search`).
- Lead / nearby comments: **what it is for**, brief + sharp. Do not turn them into a CREATE tutorial.

Purpose to keep visible (Lidr already says this; do not dilute):

| File | What it is for |
|---|---|
| `01_create_hnsw.sql` | Index `chunks_embedding_idx`: HNSW over the full `embedding` column so `ORDER BY embedding <=> …` can Index Scan instead of seq scan. Operator class **must** be cosine (`<=>`). |
| `02_test_antipatron.sql` | Proof that `<->` (L2) against a cosine index is a silent seq scan. No error. Defense = `EXPLAIN ANALYZE` + `idx_scan`. |
| `03_create_halfvec.sql` | Index `chunks_embedding_halfvec_idx`: same HNSW idea on `(embedding::halfvec(1536))`. Column stays `vector(1536)`. ~half the size. **Only** queries that order by that same cast use it. |
| `04_monitoring_queries.sql` | Production habit: `idx_scan` / size / last use. `idx_scan = 0` after semantic traffic ≈ operator/class mismatch. |
| `05_maintenance_cycle.sql` | After corpus growth: ANALYZE (planner stats), VACUUM (dead tuples), REINDEX CONCURRENTLY (rebuild without blocking reads). |
| `99_revert_live_session.sql` | Back to pre-flight DB: drop both vector indexes, drop the extra ~100 synthetics, reset `ef_search` and `pg_stat`. Keeps the 30k pre-flight synthetics. Does **not** revert application code. |

Do not run these files in this step.

**Acceptance:** six files on disk. Headers use `postgres` / `-U postgres`. No Alembic change. `0003` still says no vector index.

**Stop.** Tick. Wait.

## Step 3 — Python lab scripts

The Python scripts measure the SQL that `/search` runs, sweep `ef_search`, compare the two indexes, report sizes, and fatten the corpus with real embeddings. They talk to our async session and embedder; they do not go through HTTP (except `query_examples.py`, which we do not rewrite).

Copy-from: Lidr `s08_common.py` + `measure_baseline_s08.py` + `sweep_ef_search_s08.py` + `compare_indexes_s08.py` + `report_index_sizes_s08.py` + `insert_synthetic_chunks_s08.py`.

- Copy into `scripts/s08/` (package). Import rewrite + sys.path trap (table above).
- `s08_common.py`: keep `QUERIES` from `query_examples.py`. Add `require_async_session_factory()`: if `get_async_session_factory()` is `None`, print a short error and `SystemExit(1)`. Call it from every script that today does `session_factory = get_async_session_factory()` / `async with session_factory()`.
- Docstrings: keep Lidr’s purpose (baseline = SQL time only; sweep = recall vs latency; compare = two expressions, nothing dropped; report = read-only; insert = real embeddings, not random). Usage lines: `docker compose run --rm estimator python scripts/s08/…`.
- `compare_indexes_s08.py` in **this** step: copy as Lidr live-day (`via_vector_index` → `store.search`, `via_halfvec_index` → `halfvec_statement`). Step 5 patches it. Do not “fix” it early.
- Do not add `rich` / `tabulate`. Tables stay `format_table`.

Do not run the scripts (they need OpenAI + a live corpus).

**Acceptance:** `python -c` on the host is not required. Files import-rewrite cleanly (no `app.` / no `foundation.persistence`). Trap present. `query_examples.py` untouched. Existing tests still collect.

**Stop.** Tick. Wait.

## Step 4 — README live section

The README keeps the pre-s8 contract as-is and adds a new section for the operator lab: which script to run, which SQL creates which index, and how to talk to our Postgres container.

Copy-from: Lidr README «Live Session 08 — Indexación vectorial y operación».

- Insert **after** our «Sesión 8 — Vector persistence and semantic search» (same place Lidr put it: after the pre-exercise block).
- Title stays that. Not «Creating indexes» alone (halfvec, antipattern, monitoring, revert, Lia).
- Tables: one row per script / SQL with the *para qué* from step 2–3 (not CREATE syntax). Python scripts: `scripts/s08/<script>`.
- `psql` examples: our commands (`postgres`, `-U postgres`, path `scripts/sql_s08/…`).
- Tuning sentence: our service is `postgres`, not `estimator-postgres`.
- Keep Lidr’s canonical `pg_stat_user_indexes` query.
- Entregable Lia: point at `docs/sesion8_ef_search.md` (lands in step 6).
- In the existing Sesión 8 `/search` bullet («No vector index: sequential scan»), add one pointer: indexes are created by the operator (next section); Alembic `0003` still has none. Do not rewrite the rest of that section. Our README has no «Fuera de scope» line (Lidr’s pre-s8 section does). Do not invent one. The new Live section is the live material.
- Do not rewrite `README-session-08.md`.

**Acceptance:** new section is in `README.md`. Commands work if you type them from `estimador-cag/`. Pre-s8 contract text still true of the schema.

**Stop.** Tick. Wait.

## Step 5 — Halfvec in `ChunkStore.search` (`211602d`) + compare patch

Until now `/search` ordered by the full `embedding` column, so only the vector HNSW could serve it. This step switches that SELECT to the halfvec cast — the same expression `03_create_halfvec.sql` indexed — and fixes the compare script, which Lidr left assuming the old SELECT.

Copy-from: Lidr `211602d` hunk in `repository.py`.

Patch **our** `src/generation/rag/store/repository.py` (do not copy the file):

- `from pgvector.sqlalchemy import HALFVEC` and `cast` from sqlalchemy.
- Import `EMBEDDING_DIMENSIONS` from `generation.rag.store.models` (already in that file).
- `search`: comment out (or delete) `ChunkRow.embedding.cosine_distance(...)`; use `cast(ChunkRow.embedding, HALFVEC(EMBEDDING_DIMENSIONS)).cosine_distance(query_vector)`.
- **Docstring:** Lidr left «sequential scan» stale. Rewrite it: this is the halfvec expression so Postgres can use `chunks_embedding_halfvec_idx` when that index exists; without it, seq scan + cast. No new HTTP fields.

Patch `scripts/s08/compare_indexes_s08.py` (Lidr HEAD is inconsistent after `211602d`):

- `via_vector_index`: **do not** call `store.search`. Order by `ChunkRow.embedding.cosine_distance(vector)` (the expression `chunks_embedding_idx` was built on).
- `via_halfvec_index`: `store.search(...)` (now the `/search` SELECT) **or** keep `halfvec_statement` — they are the same expression. Prefer `store.search` so the script says “this side is `/search`”.
- Update the module docstring: vector path = column `<=>`; halfvec path = `/search` / cast. EXPLAIN checks stay as Lidr wrote them.

Patch `99_revert_live_session.sql` “Qué NO toca”: drop «repository.py no se editó». Say: revert drops DB indexes only; the halfvec SELECT in `repository.py` stays (code).

`measure_baseline_s08.py` / `sweep_ef_search_s08.py` keep calling `store.search`. After this step that **is** the `/search` SELECT (halfvec). Do not add a second code path.

HTTP contract unchanged. No new test. No Alembic.

**Acceptance:** `GET /docs` still shows the same `POST /search` body. `rg HALFVEC src/generation/rag/store/repository.py` hits the cast. `rg "via_vector_index" -A8 scripts/s08/compare_indexes_s08.py` does not call `store.search`. Existing pytest still green (`test_search_endpoint` fakes the retriever; it does not see this SQL).

**Stop.** Tick. Wait.

## Step 6 — Student run + entregable Lia

The sweep table and the `ef_search` choice have to come from *this* stack, not from Lidr’s README numbers. Same grain as `output_examples.txt`: you run it; we only land the file.

Agent does not create indexes, does not insert synthetics, does not run `sweep_ef_search_s08.py`, does not start compose just to fire OpenAI. Guide only.

**Guide (from `estimador-cag/`, stack up, `.env` with `OPENAI_API_KEY`, corpus already ingested — `query_examples.py` is enough for a thin corpus; 30k synthetics only if you want a measurable gap):**

```bash
# optional fatten (paid embeddings):
docker compose run --rm estimator python scripts/s08/insert_synthetic_chunks_s08.py 30000

# indexes (psql, our names):
docker compose exec -T postgres psql -U postgres -d estimator < scripts/sql_s08/01_create_hnsw.sql
docker compose exec -T postgres psql -U postgres -d estimator < scripts/sql_s08/03_create_halfvec.sql

docker compose run --rm estimator python scripts/s08/sweep_ef_search_s08.py
```

Land `docs/sesion8_ef_search.md` from **that** run:

- the sweep table (`ef_search`, latency, recall, ★)
- the value adopted and why (recall gained vs latency paid vs the other rows)
- ours, not Lidr’s 0.80→1.00 / ★ at 80

Do not paste Lidr’s live-session timings into this file.

**Stop.** Tick. Wait. Port complete after step 7.

## Step 7 — LAST. `docs/evolution.md`

The diary already has `session_07_forense` and `pre_sesion_08`. This step only adds the live we just adopted. No backfill.

- Add event name `session_08_forense` to the list (port live: HNSW/halfvec operator indexes, compose tuning, halfvec SELECT, lab scripts).
- Add rows, same grain as the other live events, `[x]`:
  - Compose `postgres`: `shm_size` + maintenance flags for HNSW builds
  - Operator SQL: `chunks_embedding_idx` (vector HNSW) + `chunks_embedding_halfvec_idx` (expression halfvec). Not Alembic
  - Lab scripts `s08/*_s08.py` / `sql_s08/` (baseline, sweep, compare, report, synthetics, revert)
  - `ChunkStore.search` / `POST /search` orders by the halfvec cast so it can use `chunks_embedding_halfvec_idx`
- Intro line that still says «`pre-session-08` incluida»: extend to `session_08_forense`.
- Do **not** edit `session_07_forense` or `pre_sesion_08` rows. Do not mark pre-s8 `/search` as withdrawn.

**Stop.** Port complete after this step is ticked.

---

## Summary

| # | Title | OK |
|---|---|---|
| 1 | Compose shm + five `-c` flags on `postgres`; recreate without `-v` | [x] |
| 2 | `scripts/sql_s08/` (01–05 + 99), comments = purpose, `psql` names ours | [x] |
| 3 | `s08_common` + five `*_s08.py` (trap, rewrite, `require_async_session_factory`) | [x] |
| 4 | README «Live Session 08» section + pointer from Sesión 8 | [x] |
| 5 | `211602d` halfvec in `search` + compare_indexes vector-path patch + revert comment | [x] |
| 6 | Student run → `docs/sesion8_ef_search.md` | [x] |
| 7 | `evolution.md` event `session_08_forense` only | [ ] |

Next work is **step 1 only**.

## Out of this port

- Rails / `estimator-web` / Streamlit changes.
- Alembic `0004` or any vector index in migrations.
- `docker compose down -v`. Changing compose user/pass/image/port.
- New pytest.
- Inventing UI, filters, hybrid search, IVFFlat.
- Copying Lidr `uv.lock` / `ARCHITECTURE.md` / compose wholesale / tests / `guides/`.
- Editing `README-session-08.md` or `query_examples.py` (except `QUERIES` already exported).
- Editing `docs/evolution.md` before step 7, or rewriting s7 / pre-s8 rows.
- Agent-run `CREATE INDEX`, 30k insert, sweep, or invented distances.
- `?? src/alembic.ini`.
- CAG / `/embeddings/compare` / `chunking_comparisons` / S06 ingestion rewrites.

---

## Step 6. Plan — runbook (humano)

Python en el host, desde `estimador-cag/`: `uv run python scripts/s08/<script>.py`.  
SQL `01`–`05` en pgAdmin (`localhost:5432`, `postgres` / `postgres` / `estimator`).  
`99` no es pgAdmin (`\if` / `\set`): `psql` local o `docker compose exec postgres psql …`.  
`05`: sentencias sueltas, sin transacción envolvente (`VACUUM` / `REINDEX CONCURRENTLY`).  
`s08_common.py` no se ejecuta. Postgres arriba. `OPENAI_API_KEY` en `.env`. No `docker compose down -v`.

Tras el paso 5, `/search` (y por tanto `measure_baseline` y `sweep`) ordenan por el **cast halfvec**. El índice de `01` (columna `embedding`) **no** sirve a esas dos. Si corres el baseline justo después de `01` y no baja el tiempo: no está roto; esa query no usa ese índice. El de `03` sí.

Mínimo para Lia: 0 → 1 → 5 → 8. El resto es el laboratorio (ver el truco, comparar tamaños, mantenimiento).

### 0. Foto inicial

`uv run python scripts/s08/report_index_sizes_s08.py`

- **Por qué:** ver el “antes”: btree/GIN, cero HNSW.
- **Notarás:** ~60 chunks si aún no has engordado. Ningún `hnsw`.
- **Check:** `SELECT count(*) FROM chunks;` y la query canónica de `pg_stat_user_indexes` (README).

### 1. Engordar — `insert_synthetic_chunks_s08.py 30000`

- **Por qué primero:** con 60 filas el seq scan es sub-ms. No hay nada que medir. Esto cuesta embeddings (~0,03 $).
- **Notarás:** progreso `500/30000…`, minutos. Al final, tokens y coste.
- **Check:** `SELECT count(*) FROM chunks;` ≈ 30060. `chunk_type = 'synthetic'` ≈ 30000.

### 2. Baseline sin índice — `measure_baseline_s08.py`

- **Por qué:** cronómetro del SQL de `/search` *antes* de indexar. Embebe una vez; mide solo el `SELECT`.
- **Notarás:** `mean_ms` que se puede leer (no sub-ms). Al final, un literal pgvector (por si lo pegas en `02`).
- **Check:** la tabla que imprime. Guárdala: es el “antes”.

### 3. Índice vector — `01_create_hnsw.sql` (pgAdmin)

- **Por qué:** HNSW sobre la columna `embedding` (`<=>` cosine). Lo usan el antipatrón y el lado vector del compare. **No** lo usa `/search`.
- **Notarás:** el `CREATE INDEX` tarda (30k). El SELECT del final lista el índice nuevo y su tamaño.
- **Check:** `report_index_sizes_s08.py` → `chunks_embedding_idx`, tipo `hnsw`.

### 4. Baseline otra vez — `measure_baseline_s08.py`

- **Por qué / qué no notarás:** `/search` sigue en seq scan + cast. Los `mean_ms` **no tienen por qué bajar**. Si no bajan, sigue al 5.

### 5. Índice halfvec — `03_create_halfvec.sql` (pgAdmin)

- **Por qué:** el mismo HNSW sobre `(embedding::halfvec(1536))`. Es el que **sí** puede usar `/search`. ~mitad de tamaño. Obligatorio para Lia.
- **Notarás:** segundo `CREATE INDEX` (también tarda). El SELECT compara tamaños.
- **Check:** `report_index_sizes_s08.py` → `chunks_embedding_halfvec_idx`, más pequeño que el de `01`. `EXPLAIN` del propio archivo: `Index Scan using chunks_embedding_halfvec_idx`.

### 6. Baseline con índice que sí pega — `measure_baseline_s08.py`

- **Por qué:** ahora el `SELECT` de `/search` puede hacer Index Scan.
- **Notarás:** `mean_ms` claramente por debajo del paso 2. Eso es el hueco.
- **Check:** compara las dos tablas (paso 2 vs este).

### 7. Antipatrón — `02_test_antipatron.sql` (pgAdmin)

- **Por qué:** hace falta `01`. `<=>` usa el índice; `<->` (L2) no. Sin error.
- **Notarás:** primer `EXPLAIN`: Index Scan. Segundo: Seq Scan + Sort. Tiempos distintos, cero aviso.
- **Check:** `idx_scan` de `chunks_embedding_idx` sube solo con el caso `<=>`.

### 8. Barrido — `sweep_ef_search_s08.py`  ← entregable Lia

- **Por qué:** necesita el índice de `03`. Barre `ef_search` 10…200 contra un seq scan forzado (verdad exacta). Marca ★.
- **Notarás:** tabla `ef_search / avg_latency_ms / avg_recall / recommendation`. Recall sube y se aplana; la latencia sigue creciendo.
- **Check:** hay una fila ★. Esa tabla + “por qué esa y no la de al lado” es `docs/sesion8_ef_search.md`. Números vuestros, no los de Lidr.

### 9. Compare — `compare_indexes_s08.py`

- **Por qué:** hacen falta `01` y `03`. Misma query, dos expresiones. No dropea nada.
- **Notarás:** overlap 5/5 (o casi). Halfvec no cambia el ranking en este corpus; el índice es más chico.
- **Check:** las dos líneas `Plan check — … uses: chunks_embedding_*`. Si dice `seq scan`, el índice no está o la expresión no pega.

### 10. Monitor — `04_monitoring_queries.sql` (pgAdmin)

- **Por qué:** hábito. `idx_scan` / tamaño / último uso.
- **Notarás:** el halfvec tiene scans (pasos 6 y 8). El vector, los del 7 y 9. `idx_scan = 0` tras tráfico semántico ≈ operador/clase cruzados.
- **Check:** la query canónica del README.

### 11. (Opcional) +100 sintéticos — `insert_synthetic_chunks_s08.py`  (default 100)

- **Por qué:** el `05` simula “ha crecido el corpus”. Encima de 30k, +100 casi no se siente en latencia.
- **Notarás:** `100/100`. Count += 100.
- **Check:** `SELECT count(*) FROM chunks WHERE chunk_type = 'synthetic';`

### 12. (Opcional) Mantenimiento — `05_maintenance_cycle.sql` (pgAdmin, sin transacción)

- **Por qué:** ANALYZE / VACUUM / `REINDEX CONCURRENTLY` del halfvec. Hace falta `03`.
- **Notarás:** `last_analyze` se actualiza. En query times, casi nada.
- **Check:** el SELECT de `n_live_tup` / `last_analyze` del propio archivo.

### 13. (Opcional) Deshacer lab — `99_revert_live_session.sql` (`psql`, no pgAdmin)

- **Por qué:** quita los dos HNSW, los ~100 extra, resetea `ef_search` y `pg_stat`. Deja los 30k. **No** toca `repository.py`.
- **Notarás:** los `hnsw` desaparecen. Count sintéticos vuelve a 30000.
- **Check:** `report_index_sizes_s08.py` otra vez: solo btree/GIN.

Cuando el sweep del **8** esté, pega la tabla aquí. El agente escribe `docs/sesion8_ef_search.md` con esos números. Luego paso 7 (`evolution.md`).
