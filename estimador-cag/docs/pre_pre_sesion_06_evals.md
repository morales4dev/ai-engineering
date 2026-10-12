# Port evals — Lidr `session_05_live` + `session_06` harness → `estimador-cag`

Whole eval harness, same behavior as Lidr, no coverage dropped. Golden (`session_05_live` @ `39f144e`) and stress (`origin/session_06` / `origin/session_06_live`; those two trees match on `evals/stress/`). Enunciado PDF of pre-sesión 6 not read; steps below are from the repo. No implementar until the steps run in order. After each step, stop for review.

Do not reopen `sesion5_port_plan.md` (evals: out) nor `post_sesion_05_mejoras.md`.

## Handoff

| | Path / value |
|---|---|
| Ours | `/home/morales4dev/wsTakeoff/ai-engineering` branch `pre-session-06`, app `estimador-cag/` |
| Reference | `/home/morales4dev/wsTakeoff/ai-engineering-lidr` branch `session_05_live` @ `39f144e` |
| Why they are missing | `sesion5_port_plan.md` closed decisions: «Evals: out. Lidr test suite: rejected.» Three times. The port finished; evals were never in scope. |
| Lidr copy-from | Golden: `estimator/evals/*` + `tests/test_evals_*.py` @ `39f144e`. Stress: `estimator/evals/stress/` + `tests/test_stress_*.py` @ `origin/session_06`. |
| Lidr do not copy | `EstimationService` / `get_estimation_service`. Smoke behavior via wrapper override, not their bag class. |

Ours today: no `evals/` directory. Conversational endpoints exist and match what the runner hits:

- `POST /sessions` → 201 `{"session_id"}` (`src/routers/sessions.py`)
- `POST /sessions/{id}/estimate` and `/estimate-acb` (same multipart: transcript 20–2000, three enums, optional `tier`)
- 400 on `InputGuardrailViolation` → `{"detail": {"reason", "message"}}` with `reason` in `{moderation, prompt_injection, pii}`
- `EstimationResult` + `OUT_OF_SCOPE_PREFIX` in `src/schemas/estimation.py`
- `ACBResponse.acb.final_decision` exists (`src/schemas/acb.py`)
- `httpx` already in `pyproject.toml`

## What Lidr actually shipped (read from the files, not the comments)

Five files under `estimator/evals/` plus one unit-test file. Commit `39f144e` (*session 05 ended*). Not in homework `session_5` @ `4a4de0d`.

| Piece | What it does |
|---|---|
| `golden_dataset.json` | 16 cases. All transcripts 95–187 chars (under our 2000 form cap). Two `expected_out_of_scope`. Six carry `expected_tier`. |
| `dataset.py` | Pydantic `GoldenCase` + `load_dataset()`. |
| `metrics.py` | Three binary metrics. `run_all_metrics`. No LLM. |
| `run.py` | CLI `--mode actor\|acb`, `--limit`, `--http`, `--output`. Default: in-process `TestClient`. |
| `test_evals_metrics.py` | Unit tests of the three metrics against canned `EstimationResult`. No HTTP, no LLM. |

Comments in Lidr `metrics.py` / `__init__.py` say DeepEval `GEval` is wired as `LLMJudgeMetric` behind `--llm-judge`. **That is not in the code.** No `LLMJudgeMetric` class. No `--llm-judge` flag. `deepeval>=1.0` is only in Lidr `pyproject.toml` `[dependency-groups] dev`. No import of `deepeval` under `evals/` or the two eval test files.

`GoldenCase.expected_tier` comment: «asserted against last_resolved_tier». **No metric reads that field.** It only appears in `dataset.py` and in six JSON cases.

## Summary

| # | Title | OK |
|---|-------|----|
| 1 | Router: inject `SessionStore` via `Depends` | [ ] |
| 2 | Inject `LLMWrapper` (+ OpenAI client) via `Depends` | [ ] |
| 3 | `FakeLLMWrapper` + smoke fixture | [ ] |
| 4 | Dataset + three metrics | [ ] |
| 5 | CLI runner + README + pythonpath | [ ] |
| 6 | Tests: unit + smoke (golden) | [ ] |
| 7 | Stress package (scenarios, metrics, PDF fixture script) | [ ] |
| 8 | Stress runner | [ ] |
| 9 | Stress tests: unit + smoke | [ ] |

## Test surface (label every adopted test and both CLIs)

First line of each test docstring (and the module docstring of `evals/run.py` / `evals/stress/run.py`):

| Label | Surface | Provider |
|---|---|---|
| `unit` | In-process objects only. No HTTP. | none |
| `smoke` | In-process HTTP (`TestClient`) + `FakeLLMWrapper`. | none |
| `live eval` | HTTP (in-process `TestClient` or `--http`) + real model. | real LLM |

Do not leave an unlabeled test. “I want to know which layer this is” = this table.

## Incorporation order

1. Router seam — FastAPI delivers the session store. Own commit.
2. Wrapper seam — FastAPI delivers the LLM wrapper (and the OpenAI client the guardrail uses). Own commit.
3. Fake LLM — `FakeLLMWrapper` + fixture that overrides store / wrapper / openai client. Own commit. This is what makes smokes **not** hit a provider. No `EstimationService`.
4. Load JSON and score an `EstimationResult` without HTTP. If this is wrong, the runner is noise.
5. Runner talks to our endpoints. README says how to invoke it. Live eval **does** hit the real LLM (same as Lidr `evals/run.py`).
6. Golden tests: unit metrics + smoke (HTTP yes, provider no).
7–9. Stress harness from `origin/session_06` (same behavior: in-process = smoke, `--http` = live eval). Not optional. Previous «stress is out» is **void**.

Runtime of a live run (Lidr `run.py`, unchanged behaviour):

for each case: `POST /sessions` → `POST /sessions/{id}/estimate` or `/estimate-acb` → parse `payload["result"]` as `EstimationResult` → three metrics. 400 + `expected_out_of_scope` + guardrail reason in `{prompt_injection, moderation, pii}` → synthetic envelope (cost=0, duration=1, summary starts with `Out of scope:`). Any other error is printed and the case is an ERROR row. Exit 0 only if every case passed every metric.

---

## Step 1 — Router: `Depends(get_session_store)`

**Alone.** No evals files, no README, no pythonpath, no tests. One commit, this step only. Start when told; commit when the parada is green; do not start step 2 in the same commit.

Why first: `origin/session_06` and `origin/session_06_live` still inject the store with `Depends` and swap it in `evals/run.py`, `evals/stress/run.py` (in-process) and the `conversational_client` smokes. Our `src/routers/sessions.py` calls `get_session_store()` itself (`create_session`, `get_session`, `_session_estimate_prelude`). FastAPI never hands over the box; `app.dependency_overrides[get_session_store]` does nothing. Previous decision «do not touch the router» is **void**.

Lidr copy-from (store only): `estimator/app/routers/sessions.py` on `session_05_live` / `session_06` — the `store: SessionStore = Depends(get_session_store)` parameter on `POST /sessions`, `GET /sessions/{id}`, `POST .../estimate`, `POST .../estimate-acb`. Pass that `store` into the prelude; do not call `get_session_store()` in this file.

- HTTP contract unchanged: same paths, same bodies, same 404 `session_not_found`.
- `get_session_store` stays `@lru_cache` in `dependencies.py` (production still one box per worker). Tests/runners may replace it via `dependency_overrides`.
- Do **not** add `Depends(get_estimation_service)` — we have no `EstimationService`. Do **not** inject the wrapper here. That is step 2, other commit.
- No Streamlit change.

**Parada:** `POST /sessions` + `GET /sessions/{id}` still work. A throwaway check (not committed as product test unless already there): `app.dependency_overrides[get_session_store] = lambda: SessionStore(max_turns=6)` then `POST /sessions` lands in that instance. Revert the override. Then **commit this step alone**.

## Step 2 — Wrapper: `Depends(get_llm_wrapper)`

**Alone.** No evals files, no FakeLLM, no README. One commit, this step only. Do not mix with step 1 or step 3.

Why: Lidr smokes (`test_evals_run.py`, fixture `conversational_client` used by `test_stress_runner.py` on `session_06` / `session_06_live`) do `dependency_overrides[get_llm_wrapper] = FakeLLMWrapper` (and `get_openai_client` → `None`). That is how they fake the LLM. Live evals (`evals/run.py`, stress `--http`) do **not** override the wrapper; they want the real model.

Today `estimate_conversational` and `estimate_conversational_acb` call `get_llm_wrapper()` and `get_openai_client()` themselves. Same hole as the box: FastAPI never hands them over; the smoke override would not apply. We still do not add `EstimationService`. We thread the two factories Lidr already overrides.

- `POST .../estimate` and `POST .../estimate-acb`: `wrapper = Depends(get_llm_wrapper)`, `openai_client = Depends(get_openai_client)`. Pass both into `estimate_conversational` / `estimate_conversational_acb`. Those functions stop importing/calling the factories.
- `get_llm_wrapper` / `get_openai_client` stay `@lru_cache` in `dependencies.py`. Production unchanged.
- One-shot `llm_service.py` untouched.
- Do not write `FakeLLMWrapper` in this step. Only the seam.
- HTTP contract unchanged.

**Parada:** grep — no `get_llm_wrapper()` / `get_openai_client()` inside `conversational.py` or `acb.py`. Endpoints still accept the same multipart. Then **commit this step alone**.

## Step 3 — `FakeLLMWrapper` + smoke fixture

**Alone.** No golden JSON, no runner, no metric tests. One commit, this step only.

Goal: when a Lidr **smoke** is adopted and run, it must behave like Lidr’s smoke — `TestClient` hits `/sessions` + `/estimate`, **no real LLM**. Live eval (`evals/run.py`, stress `--http`) keeps hitting the real model. Same split as Lidr.

`EstimationService` is **not** required. In Lidr it is a bag that holds the wrapper; the router does `Depends(get_estimation_service)`. We have no bag. After step 2, overriding `get_llm_wrapper` is the same switch: the fake is what answers `complete_structured_chat`. Copying `EstimationService` would be a product rewrite, not more smoke fidelity.

Lidr copy-from: `estimator/tests/conftest.py` (`FakeLLMWrapper`, `make_canned_result`, `fake_wrapper`, `session_store_factory`, `conversational_client`).

Ours: `estimador-cag/tests/conftest.py` (create if missing).

- Copy `FakeLLMWrapper` + `make_canned_result`. Imports → `schemas.estimation`, `sessions` metadata, our summarizer/anchor types.
- Lidr’s fake only implements `complete_structured_chat`. Our `metadata_extractor` calls `complete_structured`. The fake **must** implement `complete_structured` too (same canned path). Without that, a smoke 500s on the extractor and is not Lidr-equivalent.
- Fixture `conversational_client`: `dependency_overrides` on `get_session_store`, `get_llm_wrapper`, `get_openai_client` (→ `None`). **No** `get_estimation_service`. Yield `(client, store)` like Lidr.
- Our prelude `_ensure_llm_configured()` → 503 if no keys, **before** the wrapper runs. Lidr session routes have no such check; their smoke gets 200 without a provider. The fixture must make 503 not fire (dummy key on settings **or** skip the check when the injected wrapper is the fake). Do not remove 503 from production when the real `LLMWrapper` has no keys.
- Do not add `EstimationService`.

**Parada:** with the fixture, `POST /sessions` + `POST /sessions/{id}/estimate` (one golden-shaped form) → 200 and `FakeLLMWrapper.chat_calls` non-empty. No provider traffic. Then **commit this step alone**.

## Step 4 — Dataset + metrics

Lidr copy-from: `dataset.py`, `metrics.py`, `__init__.py`, `golden_dataset.json`.

Ours:

```
estimador-cag/evals/
  __init__.py
  dataset.py
  metrics.py
  golden_dataset.json
```

Sibling of `src/` and `tests/`, same as Lidr (`evals/` next to `app/`, not inside it).

- Imports: `from schemas.estimation import EstimationResult, OUT_OF_SCOPE_PREFIX` (not `app.schemas…`).
- Copy `golden_dataset.json` byte-for-byte. Do not retune ranges. Do not drop `expected_tier` (present on six cases and on `GoldenCase`; no metric reads it; same as Lidr).
- Copy the three metric classes as-is, including the phase-sum check in `SchemaAdherenceMetric`. On our `EstimationResult` that check is redundant today (`phases_sum_matches_total` overwrites the totals) — still copy it; it is a regression tripwire if someone removes the overwrite.
- Do not add a fourth metric for `expected_tier`.
- Do not add DeepEval. Lidr lists it in `pyproject` and mentions `GEval` / `LLMJudgeMetric` / `--llm-judge` in comments; no class, no flag, no `import deepeval` (same on `session_06` / `session_06_live`). Dead dep. Add it later if an enunciado actually uses it.

`pytest` `pythonpath` is currently `["src"]` (`pyproject.toml`). After this step, `from evals.dataset import …` only works if `.` is also on the path. Add `"."` in step 5, when the tests need it. This step has no pytest yet.

**Parada:** `GoldenCase` loads the 16 cases; `run_all_metrics` returns the three names. No HTTP.

## Step 5 — CLI runner

Lidr copy-from: `run.py` (behaviour, flags, table, JSON report, guardrail synthetic payload).

Ours: `estimador-cag/evals/run.py`.

Adapt only what our code forces:

| Lidr | Ours |
|---|---|
| `from app.main import app` | `from main import app` |
| `from app.schemas.estimation import EstimationResult` | `from schemas.estimation import EstimationResult` |
| `from app.dependencies import get_session_store` + `app.dependency_overrides[get_session_store] = lambda: eval_store` | **Keep** (step 1 made this apply). Isolated box, same comment as Lidr: override must be a singleton store, not a new store per request, or POST + estimate 404. |
| `SessionStore(max_turns=6)` | Same. |

Keep: `_form_body`, `_maybe_guardrail_payload`, in-process `TestClient`, `--http` via `httpx`, `--mode`, `--limit`, `--output`, exit code.

`TestClient(app)` runs our lifespan → `init_db()`. That function returns if `DATABASE_URL` is unset. Session path does not write Postgres. No extra stub.

In-process without keys: our prelude raises 503 (`_ensure_llm_configured`). The runner will mark those cases ERROR. Same as hitting a server with no keys. Document it. Do not teach the runner to skip 503.

`pyproject.toml`: `pythonpath = ["src", "."]` so `uv run python -m evals.run` and pytest both see `evals` and `src`.

README (travels with this step): commands, two transports, keys required for a real run, `--http` needs a server already up. Add `evals/` to the layout tree. Do not edit `docs/evolution.md`.

```bash
cd estimador-cag
PYTHONPATH=src:. uv run python -m evals.run --mode actor
PYTHONPATH=src:. uv run python -m evals.run --mode acb --limit 5 --output /tmp/acb.json
PYTHONPATH=src:. uv run python -m evals.run --mode actor --http http://localhost:8000
```

If `pythonpath` in pyproject is enough for `uv run python -m evals.run` without the env var, drop `PYTHONPATH=src:.` from the README and keep the shorter command. Check at implementation time; do not guess.

**Parada:** `--help` works. Then one live run (keys required; `--limit` ok for a first pass, full 16 when you can pay). **Do not** retune JSON or prompts to force 16/16. **Do** read every FAIL: which metric, which case, whether it matches the suspicions below. Write the tally in the step notes or the JSON `--output`. Closing the step = harness ran and the reds were looked at, not “all green”.

Suspected reds (not measured — we have not run):

- `cost_bounds` / duration: our v3 cheatsheet `T × W × 2000` (`src/rates.py`) vs Lidr golden ranges written for a looser hourly hint. Example: case-010 band 3 000–18 000 €; 2 people × 8 weeks × 2000 = 32 000.
- `content_recall`: v3 wording may omit a required substring (`CRM`, `KYC`, …).
- `case-005`: model estimates instead of OoS.
- `schema_adherence` phase-sum: unlikely after our overwrite; phase-*count* range can still fail.

## Step 6 — Tests

Copy `estimator/tests/test_evals_metrics.py` → `estimador-cag/tests/test_evals_metrics.py`. Fix imports. Label each function `unit`.

Adopt Lidr `test_evals_run.py` as **smoke** (same behavior, not the same `EstimationService` imports):

- `load_dataset()` length ≥ 15 and at least one `expected_out_of_scope` (`unit` is fine for this one — no HTTP).
- The HTTP loop: `conversational_client` + two golden cases + `POST /estimate` + `run_all_metrics` → 3 names. Label `smoke`. Override the wrapper/store/client, **not** `get_estimation_service`.

Label every function with the surface table (`unit` / `smoke` / `live eval`). Stress tests are step 9.

**Parada:** `uv run pytest tests/test_evals_metrics.py tests/test_evals_run.py` green. Metrics labeled `unit`. HTTP cases labeled `smoke`. No provider calls.

## Step 7 — Stress package

**After** golden (steps 4–6). Own commit. Lidr copy-from `origin/session_06`: `evals/stress/{__init__,scenarios,metrics}.py`, `evals/stress/fixtures/{__init__,build_pdfs.py}`. Not `REPORT.md` numbers (placeholders).

Ours: `estimador-cag/evals/stress/…`

- Three scenarios: `growing`, `pivot`, `contradiction` (≥20 turns). Same fact-trackers.
- Metrics: `LatencyBudgetMetric`, `CostBudgetMetric`, `MemoryDriftMetric`. Copy as-is.
- `build_pdfs.py` needs `fpdf2` (Lidr `session_06` `pyproject`: `fpdf2>=2.7`). Add that dep here. PDFs gitignored; script committed.
- Imports: our `schemas.estimation`, not `app.schemas…`.

**Parada:** scenarios load; metric unit logic can be exercised by step 9. No HTTP in this commit if you only land the package — or wait for step 9. Then **commit this step alone**.

## Step 8 — Stress runner

**Alone.** Lidr `evals/stress/run.py`.

- `--http` → real server = `live eval`.
- No `--http` → `TestClient` + isolated store override (step 1) = in-process. Lidr comments call that smoke; **with a real wrapper it still calls the LLM**. Same as Lidr: default in-process without fake is live-in-process unless tests inject `FakeLLMWrapper`. Document both in the module docstring (`live eval` vs `smoke` when the fixture overrides the wrapper).
- Same flags: `--repeats`, `--latency-budget-ms`, `--cost-budget-usd`, CSV.
- No `EstimationService`.

**Parada:** `--help`. Then **commit this step alone**.

## Step 9 — Stress tests

Lidr `tests/test_stress_metrics.py` (`unit`) and `tests/test_stress_runner.py` (`smoke` via `conversational_client`). Adapt imports; no `EstimationService`. Label every test.

**Parada:** `uv run pytest tests/test_stress_metrics.py tests/test_stress_runner.py` green. No provider calls.

---

## Closed decisions

- Layout: `estimador-cag/evals/`, not under `src/`.
- Golden JSON copied as-is. No range retune to force a green board. First live run is for **reading FAILs**, not for 16/16.
- Three metrics only. `expected_tier` travels in the JSON (six cases). **No metric scores it, because Lidr’s code never does** — only a comment on `GoldenCase` says «asserted against last_resolved_tier». We copy the field so the dataset matches; we do not invent the check. Revisit only if we decide to *add* coverage Lidr does not have.
- No `deepeval` dependency (unused in Lidr; comment only).
- Router delivers `SessionStore` via `Depends(get_session_store)` (step 1, own commit). Previous «do not touch the router» is void.
- Session estimate/ACB receive `LLMWrapper` + OpenAI client via `Depends` (step 2, own commit).
- `FakeLLMWrapper` + `conversational_client` (step 3, own commit). Smokes must not hit a provider. Live eval must. No `EstimationService`.
- Full harness: golden **and** stress. Same behavior as Lidr. Previous «stress is out» is void. Enunciado PDF not used; `origin/session_06` code is.
- Do not change `/estimate`, `/estimate-acb`, guardrails, or `EstimationResult`.
- README with both runners. No `evolution.md`.
- Every adopted test and both CLIs labeled `unit` / `smoke` / `live eval` (surface table above).
- One-shot `/api/v1/estimate` stays out of this harness (Lidr’s runner only hits session endpoints).

## Do not copy from Lidr

- `EstimationService` / `get_estimation_service`.
- DeepEval / the unimplemented judge.
- Rails.

## Out of this port

- Retuning golden ranges or prompts so the board is 16/16 green. Seeing reds and studying them is **in** scope (step 5 parada).
- Asserting `last_resolved_tier` against `expected_tier`. Why out: Lidr does not. The JSON field is dead there too. Scoring it would be a new metric, not a port. Dataset still carries the field (step 4).
- Filling `evals/stress/REPORT.md` with real numbers (Lidr ships placeholders). Why out: that is the **sesión 6 / post-sesión 6** lab (run stress on a real model, write P50/P95/$/drift). Not pre-sesión 6 and not this port. We copy the skeleton; we do not run the experiment or fill the table.

## Known limits (evidence, not guesses)

- `SchemaAdherenceMetric` phase-sum: always passes on a result that went through our validator. Still useful if the overwrite goes away.
- `case-006` transcript starts with «Ignore previous instructions…» — matches `_PROMPT_INJECTION_PATTERNS` in `src/guardrails/input.py`. Runner 400 → synthetic OoS. `case-005` (vague) is not an injection; OoS depends on the model.
- In-process and `--http` both call the real LLM when keys exist. Cost and time are not in this plan; Lidr’s runner has no dry-run.
- I have not run Lidr’s evals or ours. I do not know the pass rate.

# RESULTS

## checkpoint 4 (steps 4/5/6)

Live run 2026-10-12. Command: `PYTHONPATH=src:. uv run python -m evals.run --mode actor --output /tmp/golden-actor.json`. In-process `TestClient`, real `gpt-4o-mini`, no range retune. Exit 1.

**Tally:** 6/16 cases all-green. `schema_adherence` 16/16. `cost_bounds` 6/16. `content_recall` 15/16. Zero ERROR rows.

| Case | Result | Fail details |
|---|---|---|
| case-001-web-saas-crm | PASS | |
| case-002-mobile-loyalty | FAIL | `cost_bounds`: cost 18000 outside [25000, 120000] |
| case-003-internal-tool-hr | PASS | |
| case-004-data-pipeline-etl | PASS | |
| case-005-out-of-scope-vague | PASS | model OoS (`prompt_version=v3`) |
| case-006-out-of-scope-adversarial | PASS | guardrail `prompt_injection` → synthetic envelope |
| case-007-nda-executive | PASS | |
| case-008-hipaa-executive | FAIL | `cost_bounds`: cost 29000 outside [60000, 250000]; `content_recall`: missing `patient` |
| case-009-gdpr-executive | FAIL | `cost_bounds`: cost 24000 outside [50000, 200000] |
| case-010-small-team-pm | FAIL | `cost_bounds`: cost 20000 outside [3000, 18000] |
| case-011-developer-microservices | FAIL | `cost_bounds`: cost 24000 outside [40000, 200000] |
| case-012-data-pipeline-kafka | FAIL | `cost_bounds`: cost 24000 outside [30000, 140000] |
| case-013-mobile-fintech | FAIL | `cost_bounds`: duration 12w outside [14, 32] |
| case-014-internal-tool-knowledge | FAIL | `cost_bounds`: duration 7w outside [10, 22] |
| case-015-web-saas-marketplace | FAIL | `cost_bounds`: cost 18000 outside [35000, 140000] |
| case-016-edge-tight-deadline | FAIL | `cost_bounds`: duration 5w outside [1, 4] |

Vs plan suspicions (this run only; LLM is not a law):

- `cost_bounds` / v3 `T×W×2000`: most reds were costs **below** the golden floor (002, 008, 009, 011, 012, 015), not the high-side cheat the plan guessed. 010 was slightly over the ceiling (20000 > 18000), not 32000.
- `content_recall`: one miss (`patient` on 008). Not a CRM/KYC wipe.
- `case-005`: passed (model refused). Suspicion that it would estimate did not hold this run.
- `schema_adherence` phase-sum: 16/16, as expected after our overwrite.

Not run: `--mode acb`. Not compared to a Lidr live board. Report left in `/tmp/golden-actor.json` (not in the repo).
