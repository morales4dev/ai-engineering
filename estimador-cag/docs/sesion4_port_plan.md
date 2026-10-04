# Session 4 live — agreed incorporation plan

Bring `session_4_live` (Lidr) into `estimador-cag` without copying Rails. FastAPI is the only backend. Streamlit is HTTP-only. Do not implement until the steps are executed in order.

Reference: Lidr `origin/session_4_live` on `ai-engineering-lidr`.

## Summary

| # | Title | OK |
|---|-------|----|
| 1 | `EstimationResult` + Instructor | [x] |
| 2 | Input + output guardrails | [] |
| 3 | Exact-match cache | [] |
| 4 | Semantic cache | [] |
| 5 | Persistent history (FastAPI) | [] |
| 6 | Flashy Streamlit wait | [] |
| 7 | Clean-up | [] |

## Incorporation order (not runtime)

1. **`EstimationResult` + Instructor** — response is no longer free-text `text`.
2. **Input + output guardrails** — first stored result is already filtered.
3. **Exact-match cache** — Lidr typed-request key; stores `result`.
4. **Semantic cache** — bucket + cosine; stores the same `result`.
5. **Persistent history (FastAPI)** — PostgreSQL + GET list/show; Streamlit only consumes HTTP.
6. **Flashy Streamlit wait** — rotating phase messages while POST is in flight (Lidr Stimulus-style). Not streaming.
7. **Clean-up** — delete unused CAG/transcription code and anything with no callers.

Runtime after all steps: input guardrail → exact get → semantic get → LLM → output filter → cache writes → (step 5) persist on success.

Why this order: caches serialize `EstimationResult`, so the type comes first. Guardrails land before caches so we never ship a version that caches unchecked input or unfiltered output.

## Step 1 — EstimationResult + Instructor

- Schema: `Phase`, `EstimationResult`. Validators: sum of `phase.cost_eur` equals `total_cost_eur`; if `confidence_pct < 30`, `summary` must start with `"Out of scope:"`. `phases` is declared before the totals.
- `EstimationResponse`: `{ result, prompt_version, cached }`. Drop `text`. Until steps 3–4, `cached` is always `false`.
- `LLMWrapper.complete_structured()` via Instructor (`response_model=EstimationResult`, re-prompt up to `max_retries`).
- `<output_schema>` block in prompt versions v1 and v2.
- `estimate()` calls `complete_structured`, not `complete`.
- Streamlit renders `result` (summary, phases, totals, confidence). No history yet.
- Keep `?prompt_version=`, `prompt_boundary` on provider messages, boot without API keys, `/estimate` → 503 if no keys, provider / `InstructorRetryException` → 502. Do not catch bare `Exception`.
- Out of this step: guardrails, caches, Redis Stack, history.

## Step 2 — Guardrails

- **Input** (`check_input`): OpenAI moderation (fail-open on network errors), injection regex, PII regex. Policy **exception** → `InputGuardrailViolation`. Router: HTTP 400 `{ reason, message }`.
- **Output** (`enforce_scope_response`): policy **filter**. If confidence is low and the prefix is missing, rewrite (phase `"Not estimated"`, totals 0 / 1). Never raises.
- `prompt_boundary` stays: it still sends the text, marked as data. Input guardrails reject the request. Not the same thing.
- Streamlit: show 400 `reason` / `message` clearly.
- At this point `estimate()` is check → LLM → filter → return. Steps 3–4 hook lookup after input and write after filter.

## Step 3 — Exact-match cache

- Get/set in `estimate()`, not inside `complete_structured()`.
- Key: SHA-256 of canonical JSON (`description`, `project_type`, `detail_level`, `output_format`, `prompt_version`, `model`) → `estimation:v2:{digest}`.
- Value: dump of `EstimationResult`. Hit → `cached=true`.
- Old prompt-hash keys will miss. Acceptable.

## Step 4 — Semantic cache

- After exact-match miss.
- Hit only if the **bucket** matches (`prompt_version:project_type:detail_level:output_format`) **and** cosine similarity of the `description` embedding is ≥ threshold (`SEMANTIC_CACHE_THRESHOLD`, default **0.85**).
- `SEMANTIC_CACHE_LOG_ONLY`: look up and log; do not serve.
- Store `EstimationResult` as `result_json`. Hit → `cached=true`.
- Redis Stack image `redis/redis-stack:7.4.0-v0`. Publish **6379** and **8001** (RedisInsight, same as Lidr).
- Settings: `EMBEDDING_MODEL` (`text-embedding-3-small`), `SEMANTIC_CACHE_THRESHOLD`, `SEMANTIC_CACHE_TTL`, `SEMANTIC_CACHE_LOG_ONLY`.
- If there is no `OPENAI_API_KEY` or RediSearch setup fails, disable semantic cache and keep going. Exact-match does not depend on this.
- `.env.example` and compose Redis Stack changes belong in this step.

## Step 5 — Persistent history (FastAPI)

PostgreSQL. FastAPI is the only process that talks to the DB.

- After a successful `/estimate` (including `cached=true`): INSERT. Do not persist 400 / 422 / 502.
- Table `estimations`: `description`, three enums, `response_payload` (full `/estimate` JSON), `prompt_version`, `cached`, timestamps.
- Compose: add `postgres`. Settings: `DATABASE_URL`. Update `.env.example` here.

`GET /api/v1/estimations` — last 20 by `created_at` desc. No `result` in the list:

```json
{
  "items": [
    {
      "id": 1,
      "description_preview": "first 80 chars of description",
      "project_type": "web_saas",
      "detail_level": "medium",
      "output_format": "phases_table",
      "prompt_version": "v1",
      "cached": false,
      "created_at": "2026-05-14T12:00:00Z"
    }
  ]
}
```

`GET /api/v1/estimations/{id}` — 404 if missing. Same fields plus full `description` and `result` (`EstimationResult`, same as `/estimate`).

Streamlit: list + reopen via those two GETs. No SQL, Redis, or LLM in Streamlit.

## Step 6 — Flashy wait (Streamlit)

While `/estimate` is in flight, rotate phase labels (Discovery, Implementation, …). This is wait UX, not SSE. A static `st.spinner` is not enough. Does not change the API contract.

## Step 7 — Clean-up

No keep-for-later dead code. After steps 1–6 the only product path is FastAPI + Streamlit HTTP.

Delete anything with no callers from `/estimate`, history GETs, Streamlit, or `/health`. At least:

- `llm_service.py`: `generate_estimation`, `extract_requirements`, `build_cag_context`, `GenerationOptions`, `ACTIVE_OUTPUT_PROMPT` / `PROMPT_OUTPUT_*`, two-phase, `INLINE_CLEANING_*`.
- `context/examples.py` if only that path uses it (live few-shot lives in the `.j2` files).
- `evaluation.py` + `StructureCheck` if unused (free-text scorer).
- `complete()` if it has no callers after CAG is gone. Keep `complete_structured()`.
- Orphan schema leftovers (`PreprocessingMode`, `ExampleFormat`) if unused.

Do not delete Jinja templates or `docs/` forensics notes. Keep `prompt_boundary` **because it is used** (`complete_structured` / `/estimate` wraps the user message). If a later grep finds no callers, delete it (same rule as the rest). Finish with a grep: no dead imports.

## Closed decisions

- FastAPI is the only backend / facade (LLM, guardrails, caches, Postgres). Streamlit is an HTTP client. curl and `/docs` hit the same API.
- No Rails. No `EstimationService` class. Orchestration stays in `estimate()` as a sequence of named steps.
- `/estimate` contract: `{ result, prompt_version, cached }`.
- Keep `?prompt_version=`. `description` stays 20–2000 (Lidr uses 80k; we do not).
- Keep session-3 forensics: boot without API keys; `/health` is liveness + `llm_configured` only (no Redis/Postgres probe); 503 if no keys; 502 only for provider + `InstructorRetryException`; never `except Exception`; `cost_usd` stays `None` when the model is missing from the price table (legacy wrapper).
- `prompt_boundary`: Lidr never had it (checked s2–s4_live). We keep it because the new path uses it.
- No new tests. Do not port Lidr tests. Touch existing tests only if a step breaks them.
- Do not add `reference_projects` or a render hash/log (not in live).
- structlog events (`cache_hit`, guardrail blocked, …) go in each step; not a separate task.
- README updates (new contract, compose, history) go with the steps that change them.

## Lidr client (context)

Lidr did not evolve Streamlit. Session 4 added a new Rails app. `session_4_live` evolved that Rails app: Postgres persist, last-20 index, typed `show`, guardrail flash, `cached`. Their Streamlit still paints `text`. Ours: UI in steps 1–2 and 6; history UI over FastAPI in step 5.
