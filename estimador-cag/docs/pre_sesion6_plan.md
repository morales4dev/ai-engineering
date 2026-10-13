# Pre-sesión 6

`docs/pre_pre_sesion_06_evals.md` is **closed**. That plan ported the `session_05_live` golden harness only. This file is the sesión 6 work.

Do not reopen `sesion5_port_plan.md`, `post_sesion_05_mejoras.md`, or the closed evals plan except to read RESULTS.

## Summary

| # | Title | OK |
|---|-------|----|
| 1 | Wrapper: real `tokens_*` / `cost_usd` (checkpoint 1, live eval) | [x] |
| 2 | `TurnObservation` + emit `turn_observed` / `response.observation` | [x] |
| 3 | Stress package (copy Lidr, fix imports) | [x] |
| 4 | Tests: unit + smoke | [ ] |
| 5 | Live eval + `REPORT.md` (checkpoint 2) | [ ] |

## Handoff

Frozen at plan start. Progress is the Summary table. Write **Handoff out** only when this plan closes — same rows, end state, not a mid-flight update.

| | Path / value |
|---|---|
| Ours | `/home/morales4dev/wsTakeoff/ai-engineering` branch `pre-session-06`, app `estimador-cag/` |
| Golden in | `estimador-cag/evals/` + `tests/test_evals_*.py` + `tests/conftest.py` (`FakeLLMWrapper`, `conversational_client`) |
| Seams in | `Depends(get_session_store)`, `Depends(get_llm_wrapper)`, `Depends(get_openai_client)` on session routes |
| Not in product | `TurnObservation` / `response.observation`. Wrapper `meta` is `{model, provider, latency_ms}` only. |
| Not in tree | `evals/stress/`, `fpdf2`, stress tests |

Lidr `session_05_live` @ `39f144e` has no `evals/stress/`. Copy-from is `origin/session_06` (same stress tree as `origin/session_06_live`): `estimator/evals/stress/{__init__,scenarios,metrics,run}.py`, `estimator/evals/stress/fixtures/{__init__,build_pdfs.py}`, `estimator/tests/test_stress_{metrics,runner}.py`.

| Piece | What it does |
|---|---|
| `scenarios.py` | `growing`, `pivot`, `contradiction` (≥20 turns) + fact-trackers |
| `metrics.py` | `LatencyBudgetMetric`, `CostBudgetMetric`, `MemoryDriftMetric` — read `TurnObservation` + GET snapshot, not `EstimationResult` |
| `run.py` | CLI: scenarios × attachment sizes × repeats → CSV. `--http` = live eval. In-process without fake still calls the LLM |
| `fixtures/build_pdfs.py` | `fpdf2>=2.7`. PDFs gitignored; script committed |
| `test_stress_metrics.py` | `unit` |
| `test_stress_runner.py` | `smoke` via `conversational_client` |

Lidr `evals/stress/run.py` does `payload["observation"]` and raises if missing. `LatencyBudgetMetric` / `CostBudgetMetric` take `TurnObservation`. That field is on the session `/estimate` response (optional; old clients ignore it). ACB leaves it `None`. The runner only hits `/estimate`, not `/estimate-acb`.

`GET /sessions/{id}` (ours and Lidr `session_06`) is inspect: `metadata`, `summary_chars`, `anchors_count`. No summary text, no anchors text. Lidr `MemoryDrift` for `growing` uses `project_name` on metadata.

Lidr `complete_structured` / `_chat` on `session_06` still put only `model`, `provider`, `latency_ms` in `meta`. `MODEL_COSTS` + tokens live on their free-text path. Their structured-path `observation.cost_usd` / `tokens_*` are 0 unless something else fills them. We fill usage (Step 1).

## Locked

- Path stays `estimate_conversational()` in `src/services/conversational.py`. No `EstimationService`.
- No DeepEval. No RAG. No CAG retune (`MAX_CONVERSATION_TURNS` stays 6). One provider. No matplotlib. CSV only. No LLM-as-judge. One-shot `/api/v1/estimate` stays out.
- ACB / Streamlit: no change (`observation` stays `None` or unused).
- Real tokens/cost from Instructor usage. Do not ship Lidr’s structured-path zeros.
- No ráfagas. The five blocks and Lidr `session_06` have none.
- MemoryDrift copies Lidr. Do not add summary/anchors text to `GET /sessions/{id}`. The runner tracks the turn-1 fact (`project_name` on `metadata`). Limit goes in `REPORT.md`.
- `REPORT.md` numbers are the last step (`live eval`). Ship the skeleton with the harness.
- Labels: `unit` / `smoke` / `live eval` (same table as the golden plan).

MemoryDrift, in short: each later turn, the runner asks whether the turn-1 name (e.g. `Nimbus`) is still in `GET /sessions/{id}`. That GET has `metadata` and counts (`summary_chars`, `anchors_count`), not the summary or anchor words. A search in `metadata.project_name` works. A search in summary/anchors does not — Lidr’s `fact_field="summary"` unit test invents a `summary` key the real GET never returns.

## Work, in order

Product first (usage + `TurnObservation`). Then the Lidr stress package. Then tests. Then live + report.

### Step 1 — Wrapper: real `tokens_*` / `cost_usd`

Today `complete_structured` / `complete_structured_chat` call `instructor.chat.completions.create` and `meta` is only `{model, provider, latency_ms}`. Instructor 1.17 (in our `.venv`) also has `create_with_completion` → `(parsed_model, raw_completion)`.

- Switch both structured methods to `create_with_completion`.
- Read usage off `raw_completion` the same way Lidr’s free-text `_normalise_response` does: `usage.prompt_tokens` / `usage.completion_tokens` (fallback 0 if missing).
- Add Lidr’s `MODEL_COSTS` + `_estimate_cost` to `src/services/llm_wrapper.py` (we have neither).
- Put `tokens_in`, `tokens_out`, `cost_usd` on `meta`.
- `FakeLLMWrapper` in `tests/conftest.py`: add the three keys (canned). Smoke must not crash.

**Acceptance:** one live structured call (`complete_structured` or `_chat`, real provider, not `FakeLLMWrapper`) must leave `meta["tokens_in"] > 0` and a `cost_usd` that is not the fallback zero. `usage` is the provider’s token count on the raw completion (`prompt_tokens` / `completion_tokens` in Lidr’s free-text path). If that object is `None` or those names are missing, inspect the raw **once** and map the real fields. Do not invent tokens. Do not invent a second price table. Fallback `0` is only for a field that is still absent after that look — shipping all-zero `meta` on a successful live call fails this step.

That live check is **checkpoint 1** (`live eval`), same label as the golden RESULTS / Step 5 CSV. It is **not** a new pytest. Lidr’s `cost_usd > 0` test (`estimator/tests/test_llm_wrapper.py`) patches LiteLLM and injects a fake `usage` — that is `unit`, no keys, no network. `unit` / `smoke` = fake (`FakeLLMWrapper` or a patched completion); keys+red only in `live eval`. Do not promote smoke to live.

Observation cost is the **estimate** call’s `meta` only (same as Lidr). Metadata extractor + summarizer also call the wrapper; those tokens stay off `TurnObservation`. Shortcut: one-call cost, not session-total LLM spend.

### Step 2 — `TurnObservation` + emit

1. `TurnObservation` on `src/schemas/estimation.py` — Lidr’s 13 fields (`origin/session_06`).
2. Optional `observation` on `EstimationResponseReloaded` (not on one-shot `EstimationResponse`).
3. `_session_estimate_prelude`: count `attachments_total_chars = sum(len(text) for _, text in extracted)` and pass it in.
4. In `estimate_conversational`, after compression + metadata update, **before return**:
   - `turn_index = max(1, len(session.history.messages) // 2)` **after append, before compression** (post-compress the window plateaus at `max_turns`).
   - `messages_in_window = len(session.history.messages)` **after** compression.
   - `cache_hit_kind="none"` (conversational path has caches off).
   - `log.info("turn_observed", **observation.model_dump())` **and** `observation=observation` on the response.

The log is what the enunciado asks for. The runner reads `payload["observation"]` and raises if missing. Do not parse docker logs.

### Step 3 — Stress package (copy Lidr, fix imports)

Copy from `origin/session_06`:

| Lidr | Ours |
|---|---|
| `estimator/evals/stress/{__init__,scenarios,metrics,run}.py` | `estimador-cag/evals/stress/` |
| `estimator/evals/stress/fixtures/{__init__,build_pdfs.py}` | same |
| `estimator/tests/test_stress_{metrics,runner}.py` | `estimador-cag/tests/` |
| `estimator/evals/stress/REPORT.md` | skeleton only |

Import rewrite (our pytest `pythonpath` is `src` + `.`; `uv run python -m` still needs `PYTHONPATH=src:.`):

- `app.schemas.estimation` → `schemas.estimation`
- `app.dependencies` / `app.main` / `app.sessions.store` → `dependencies` / `main` / `sessions.store`

Lidr’s API, not the enunciado sketch:

- Metrics live in `evals/stress/metrics.py` (they take `TurnObservation` + GET dict, not `(GoldenCase, EstimationResult)`). Reuse `MetricResult` from `evals.metrics`. Do not add them to `evals/metrics.py` / `run_all_metrics`.
- `MemoryDriftMetric(fact, fact_field=...)` — not `where: list[str]`.
- Scenarios are always ≥20 turns. The `N ∈ {1,3,6,10,20}` in the enunciado are **points on the curve**, not five script lengths. The runner walks 20; REPORT samples 1 / 5 / 10 / 15 / 20.
- Same PDF on **every** turn of a session (Lidr `_run_one_session`). Attachment stress is `scenarios × sizes`, not a one-shot per size.

`fpdf2>=2.7` in `pyproject.toml` (Lidr: main deps). PDFs are generated, not committed.

Gitignore (repo root `.gitignore`; there is no `estimador-cag/.gitignore`):

```
estimador-cag/evals/stress/fixtures/*.pdf
estimador-cag/evals/stress/results.csv
estimador-cag/evals/stress/smoke.csv
```

### Step 4 — Tests

- `tests/test_stress_metrics.py`: copy Lidr unit (pass / fail / boundary). Label `unit`.
- `tests/test_stress_runner.py`: copy Lidr smoke via `conversational_client`. Truncate turns like they do. Label `smoke`.
- Product check: `POST /sessions/{id}/estimate` returns `observation` with the 13 keys (existing conversational test or a tiny new one). `tokens_*` / `cost_usd` on the fake may be canned.

### Step 5 — Live eval + `REPORT.md`

**Checkpoint 2.** Harness done ≠ exercise done. Real model, one provider.

`pyproject.toml` `pythonpath` is pytest-only. Same prefix as README / golden evals:

```
PYTHONPATH=src:. uv run python -m evals.stress.fixtures.build_pdfs
PYTHONPATH=src:. uv run python -m evals.stress.run --http http://localhost:8000 \
    --scenarios growing,pivot,contradiction \
    --attachment-sizes 0,5,20,50,100 \
    --repeats 3 \
    --output evals/stress/results.csv
```

Floor: ≥50 CSV rows. Full matrix is 3 × 5 × 3 × 20 = 900 if every turn succeeds. Do not shrink the 20-turn scripts to hit the floor.

`REPORT.md` (1–2 pages), from **our** CSV, not Lidr placeholders:

1. Summary table: scenario × KB → P50/P95 latency, total $, exact/semantic cache hit rate, mean MemoryDrift.
2. Three tables: latency vs `tokens_in`; cumulative $ vs `turn_index` (size 0); MemoryDrift vs N.
3. Two reading paragraphs with one hard number (“from turn N=…”, “turn 20 costs × the first”).

Cache hit rates on this path will be 0 / `none`. That is a measurement, not a bug. 100 KB cell: `MAX_ATTACHMENT_CHARS=60000` — report the truncated regime.

## Done when

- `POST /sessions/{id}/estimate` emits `turn_observed` (13 fields) and returns `observation`.
- `PYTHONPATH=src:. uv run python -m evals.stress.run --http http://localhost:8000` writes a CSV with ≥50 rows.
- The three metrics exist in `evals/stress/metrics.py` with green unit tests.
- `REPORT.md` has the table, the three curves, and two paragraphs with a real number from our run.
- All of that is in the repo.

## Do not do

RAG. Shorten the system prompt. Change `MAX_CONVERSATION_TURNS`. Compare providers. Jupyter/matplotlib. Postgres/SQLite for results. LLM-as-judge. New UI. Parse `docker compose logs` for the runner. Invent a burst scenario. Fill `REPORT.md` with invented P50s.
