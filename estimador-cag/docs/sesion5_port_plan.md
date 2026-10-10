# Session 5 live — agreed incorporation plan

Bring Lidr `session_05_live` (`39f144e`, parent homework `4a4de0d`) into `estimador-cag` without copying Rails, without an `EstimationService` class, and without rewriting the homework we already shipped. FastAPI is the only backend. Streamlit is HTTP-only. Do not implement until the steps are executed in order. After each step, stop for review. Do not start the next step until told.

This file is the handoff. A later session should need only this plan plus the two repos. Do not reopen closed decisions.

## Handoff (start here in a new session)

| | Path / value |
|---|---|
| Ours | `/home/morales4dev/wsTakeoff/ai-engineering` branch `session_05_forense`, app `estimador-cag/` |
| Reference | `/home/morales4dev/wsTakeoff/ai-engineering-lidr` branch `session_05_live` @ `39f144e` |
| Homework we already shipped | in-process sessions, Camino B, LLM metadata extractor, sliding window trim-in-`append`, Streamlit Conversational tab, `project_metadata` on the estimate body. No GET. No compression / tier / ACB. |
| Homework plan (do not reopen) | `estimador-cag/docs/pre_sesion5_plan.md` |
| Lidr copy-from files | listed per step below. Layout is `estimator/app/…`; ours is `estimador-cag/src/…`. |

Entry points today (ours):

- `src/sessions.py` — `ConversationHistory.append` still calls `_trim()`
- `src/routers/sessions.py` — `POST /sessions` 201, `POST /sessions/{id}/estimate` multipart, no GET
- `src/services/conversational.py` — session pipeline; `append` today stores the rendered `user_message`
- `src/services/metadata_extractor.py` — fail-open second call
- `src/services/llm_wrapper.py` — `complete_structured` + `complete_structured_chat` (boundary on latest user)
- `streamlit_app.py` — tabs New / Conversational / Recent; Conversational uses `session_id`, `conv_result`, `conv_metadata`

## Summary

| # | Title | OK |
|---|-------|----|
| 1 | Dumb `append` + window policy seam | [x] |
| 2 | `GET /sessions/{id}` inspect (read-only) | [x] |
| 3 | Compression: anchors + cumulative summary | [x] |
| 4 | Dynamic tier + conversational prompt `v3` | [x] |
| 5 | Actor-Critic-Boss + `POST /sessions/{id}/estimate-acb` | [ ] |
| 6 | Streamlit surfaces (inspect button, tier, ACB trail) | [ ] |
| 7 | Clean-up | [ ] |

## Incorporation order (not runtime)

1. History seam — `append()` only stores the pair. Eviction lives in one policy. Without this, step 3 trims twice.
2. GET inspect — read RAM, no LLM. Streamlit calls it from its own button (step 6).
3. Compression — policy grows: peel oldest pair → promote anchors or fold into summary.
4. Tier + v3 — rule chain, optional Form override, `<audience>` on a new conversational prompt.
5. ACB — new endpoint; session history stores one turn: enriched transcript + final assistant.
6. Streamlit — HTTP client only.
7. Clean-up. README travels with the step that changes the contract.

Why this order: compression cannot land on a history that still trims inside `append()`. GET before compression/tier so the inspect payload can grow without changing the estimate response. Tier before ACB because v3 `<audience>` and `<critic_feedback>` share that prompt. ACB last among backend steps because it reuses render + compression + metadata update.

Runtime after all steps (regular conversational path):

input guardrail → resolve tier → render conversational prompt → `complete_structured_chat(messages)` → output filter → `history.append` → `CompressionPolicy.apply` → metadata extractor → return `EstimationResponseReloaded`.

ACB path: same prelude, then Boss(actor, critic); persist **one** turn (enriched transcript + final assistant); same compression + metadata. Intermediate actor drafts and rendered `user_message`s (including `<critic_feedback>`) are not stored.

---

## `GET /sessions/{id}`

Read-only inspect of the in-memory session. No LLM. Not a second estimate. Not `GET /api/v1/estimations/{id}`.

Estimate stays the write path and still returns `project_metadata`. GET is inspect: window size, anchors, summary length, last tier, plus the metadata the server holds.

Streamlit does **not** GET after every estimate. Button **Inspect session** (outside the form) fires GET and paints the JSON. 404 → new `POST /sessions`, same `conv_session_warning` as an estimate restart; do not retry the GET; do not clear `conv_result`; leave the inspect expander as it was.

---

## Step 1 — Dumb `append` + window policy seam

Lidr copy-from: `estimator/app/sessions/models.py` (`append` without trim), `estimator/app/sessions/compression/policy.py` (the while-loop peel; ignore anchors/summary this step).

- Split now (not optional): `src/sessions.py` → `src/sessions/{__init__.py, models.py, store.py}`. Re-export the same names so current imports keep working, then fix imports if needed (`routers/sessions.py`, `conversational.py`, `metadata_extractor.py`, `dependencies.py`, `prompts/loader.py`, `schemas/estimation.py`).
- `append(user=, assistant=)` only appends two `Message`s. Delete `_trim` in this step.
- New `src/sessions/compression/policy.py`: `CompressionPolicy.apply` window-only — while `len(messages) > max_turns * 2`, delete the oldest pair (same pair-safe overflow). `apply_compression(history)` helper with no LLM args yet.
- `estimate_conversational` calls `apply_compression` after `append`.
- `append(user=transcript, assistant=result.model_dump_json())` — `transcript` is the already-enriched text (form + attachments). Not the rendered `user.j2`. Not the raw 20–2000 form field.
- `to_messages_list()` unchanged (no system).
- No `EstimationService`.

Out of this step: anchors, summary, GET, v3, ACB. Window size ≤6 turns identical. Turn 7 still drops the oldest pair; it happens in the policy.

## Step 2 — `GET /sessions/{id}` inspect

Lidr copy-from: `estimator/app/routers/sessions.py` `get_session` + `SessionInfoResponse`.

`GET /sessions/{session_id}` → 200:

```json
{
  "session_id": "…",
  "message_count": 4,
  "max_turns": 6,
  "metadata": { "project_name": "Nimbus", "assumed_team_size": 3, "mentioned_technologies": ["React"], "agreed_scope": "…" },
  "anchors_count": 0,
  "summary_chars": 0,
  "last_resolved_tier": null,
  "last_tier_rule": null
}
```

- 404 `{"detail": "session_not_found"}`. No LLM. Same detail on `POST /sessions/{id}/estimate` (today it says `"Session not found"` — change it in this step) and later on `/estimate-acb`.
- Schema matches Lidr live fields. Do not add `summary` text. `anchors_count` / `summary_chars` / tier are zeros / null until steps 3–4.
- `Session` gains `last_resolved_tier: str | None` and `last_tier_rule: str | None` here (written in step 4).
- Keep `project_metadata` on `EstimationResponseReloaded`.
- No `DELETE /sessions`. No list endpoint.
- README: GET inspect exists; it is not a second estimate.

## Step 3 — Compression: anchors + cumulative summary

Lidr copy-from (behaviour and regex, not package names):

- `estimator/app/sessions/compression/{policy.py,anchors.py,summarizer.py}`
- `estimator/app/prompts/conversation_summary/v1/{system,user}.j2`

Ours:

- `src/sessions/compression/{__init__.py,policy.py,anchors.py,summarizer.py}`
- `src/prompts/conversation_summary/v1/{system,user}.j2`

- `ConversationHistory` gains `anchors: list[Message]` and `summary: str | None`.
- `to_messages_list()` order: optional synthetic user `"[Earlier conversation summary — the recent turns below are the live thread]\n" + summary`, then anchors in order, then the recent window. Caller still prepends system.
- Policy after append: while over cap, peel oldest pair; `AnchorDetector` on the **user** message; if anchor, move **both** messages to `anchors`; else queue for summarizer. Then `CumulativeSummarizer` replaces `history.summary` if anything was queued.
- `ANCHOR_DETECTION_MODE`: default `heuristic`. Copy Lidr regex tuples. `llm`: one Instructor classify (`_AnchorClassification`: `is_anchor`, `reason`) on the evicted user turn via `complete_structured_chat`; failure or no wrapper → heuristic. Implement both in this step.
- Summarizer: `COMPRESSION_MODEL` default `gpt-4o-mini`, Instructor `{summary}` max 4000 chars, `max_retries=1`. Fail-open: log, keep previous summary or `""`.
- `apply_compression(history, llm_wrapper, compression_model, anchor_detection_mode)` — conversational path passes the real wrapper. Settings + `.env.example` here.
- GET fields `anchors_count` / `summary_chars` become real.
- README: window peel, anchors, cumulative summary. Memory still process-local.

## Step 4 — Dynamic tier + conversational prompt `v3`

Lidr copy-from: `estimator/app/sessions/tier_resolver.py` (enum, predicates, rule order), `estimator/app/prompts/estimation/v3/{system,user}.j2` **only for `<audience>` and `<critic_feedback>`**.

- `src/sessions/tier_resolver.py`. `Tier`: `executive | pm | developer | default`.
- `resolve_tier(transcript, metadata, override) -> (tier, rule_name)`. Override wins (`explicit_override`). Else first hit: `nda_detected` / `regulatory_context` → executive; `technical_audience` (≥2 distinct infra keywords) → developer; `low_budget_pm` (team size ≤ 2) → pm; else `default`. Predicate error: log, skip rule. Copy Lidr regexes.
- Write `session.last_resolved_tier` / `last_tier_rule` (string values) for GET.
- **v3 construction:** copy **our** `estimation/v2/system.j2` and splice Lidr’s `<audience>` block after `<project_metadata>`. Copy **our** `v2/user.j2` and splice Lidr’s `{% if critic_feedback %}` block. Do not adopt Lidr’s “senior estimator” persona. Do not change v1/v2 files.
- `render_conversational_prompt(...)` in `src/prompts/loader.py`. Session path uses it.
- `CONVERSATIONAL_PROMPT_VERSION` default `v3`. Both session estimate endpoints take `?prompt_version=` (v1|v2|v3; unknown → 422). Omitted query → the setting. A present query wins. One-shot stays `render_estimation_prompt`, default v1.
- Optional multipart `tier: Tier | None = Form(default=None)`. Streamlit override is step 6.
- Regular session `/estimate` uses the resolved tier in v3. No ACB yet.
- README: dynamic tier + conversational default v3; `?prompt_version=` still accepted.

## Step 5 — Actor-Critic-Boss

Lidr copy-from: `estimator/app/services/{boss.py,critic.py}`, `estimator/app/schemas/{acb.py,critic.py}`, `estimator/app/prompts/critic/v1/`, `estimator/app/routers/sessions.py` `estimate_in_session_acb`. Copy schemas and Boss decision table as-is. Do not copy `EstimationService`.

Ours:

- `src/schemas/acb.py`, `src/schemas/critic.py`
- `src/services/boss.py`, `src/services/critic.py`
- `src/services/acb.py` (or a function next to `estimate_conversational`) — orchestration only
- `src/prompts/critic/v1/{system,user}.j2`
- `POST /sessions/{session_id}/estimate-acb`

- Same multipart as `/estimate` (transcript 20–2000, 3 enums, optional attachments, optional tier) and the same `?prompt_version=` rule (setting default, present query wins). Shared prelude with `/estimate` (404, Camino B, enrich, 415/422, 503 if no keys).
- Response: subclass of `EstimationResponseReloaded` named `ACBResponse` = `{ result, prompt_version, cached, project_metadata, acb }` where `acb` is `BossTrace` (`iterations`, `final_decision`, `iterations_run`). `cached` always false.
- Actor: re-render conversational prompt with optional `critic_feedback`, `complete_structured_chat`, output filter.
- Critic: Instructor → `CriticFeedback`. Validators: `needs_iteration` needs a critical/major issue; `reject` needs ≥1 issue. Fail-open: log, `accept` + `confidence_in_review=0`.
- Boss: `BOSS_MAX_ITERATIONS=3`. accept / iterate / synthesize. Synthesize: prefix last draft summary with caveats, floor `confidence_pct` at 30. Never an empty result.
- Persist one turn: `append(user=transcript, assistant=final.model_dump_json())` then compression + metadata. Same user text as `/estimate` (enriched transcript). Intermediate drafts discarded. Do not persist the rendered `user_message`.
- Errors: same map as `/estimate`. Named provider errors only → 502.
- Settings: `CRITIC_MODEL=gpt-4o-mini`, `BOSS_MAX_ITERATIONS=3`.
- Evals (`estimator/evals/`): out.
- README: `POST /sessions/{id}/estimate-acb`. Caches off.

## Step 6 — Streamlit surfaces

File: `estimador-cag/streamlit_app.py`. Conversational tab only. New / Recent untouched.

- Estimate / ACB still paint `result` + `project_metadata` from the POST body. Do not GET on submit.
- `st.session_state.conv_inspect` (new). Cleared on “Nueva conversación”.
- Caption on the Conversational tab: API default prompt is **v3** (today it still says v2).
- **Inspect session** — button **outside** the estimate form. `GET {SESSIONS_ENDPOINT}/{session_id}`. Paint the **full JSON** with `st.json` inside an expander “Session inspect”. Keep it until the next successful inspect or new conversation. 404 → new `POST /sessions` + the same `conv_session_warning` as an estimate restart; do not retry the GET; do not clear `conv_result`; leave `conv_inspect` as it was. Cheap GET: `st.spinner`, not the flashy wait.
- In the estimate form: optional `tier` select. Options `auto` + `executive|pm|developer|default`. `auto` omits the form field (server derives). Persist with the other conv keys.
- Same form, two `st.form_submit_button`: **Generate estimation** → `POST .../estimate`; **Estimate with review** → `POST .../estimate-acb`. Flashy wait on both. If `acb` in the body, expander “Review trail” with iterations (verdict, confidence, issue_summary, final_decision).
- New conversation: unchanged, and also clears `conv_inspect`.
- Estimate 404-restart: unchanged (new session, warning, retry the POST); also clears `conv_inspect`.
- README: Inspect button, tier select, two submit buttons, review trail.

## Step 7 — Clean-up

- Grep: no `_trim`, no unused compression imports, no dead ACB helpers. `from sessions import …` still works.
- Do not copy Lidr’s stale README. Do not edit `docs/evolution.md` unless asked.
- Do not delete `docs/`.

---

## Settings to add (ours `src/config.py` + `.env.example`)

| Name | Default | Step |
|---|---|---|
| `ANCHOR_DETECTION_MODE` | `heuristic` | 3 |
| `COMPRESSION_MODEL` | `gpt-4o-mini` | 3 |
| `CONVERSATIONAL_PROMPT_VERSION` | `v3` | 4 |
| `CRITIC_MODEL` | `gpt-4o-mini` | 5 |
| `BOSS_MAX_ITERATIONS` | `3` | 5 |

Existing stay: `MAX_CONVERSATION_TURNS=6`, `MAX_ATTACHMENT_CHARS=60000`, `METADATA_EXTRACTOR_MODEL=gpt-4o-mini`.

---

## Closed decisions

- FastAPI only. Streamlit HTTP-only. No Rails. No `EstimationService`.
- Homework path stays: Camino B, LLM extractor fail-open (leave the extractor as it is), caches off, no Postgres on the session path, `transcript` 20–2000, attachment text after that cap, `prompt_boundary` on the newest user message (already in `complete_structured_chat`; summarizer / critic / llm-anchor go through that wrapper), boot without keys, 503 if no keys, 502 only for named provider errors + `InstructorRetryException`.
- Session `?prompt_version=` on `/estimate` and `/estimate-acb`. Default is `CONVERSATIONAL_PROMPT_VERSION` (`v3`). A present query wins.
- Router endpoints do not catch bare `Exception` for 502. Fail-open helpers (extractor, summarizer, critic, llm-anchor, tier predicate skip) log and continue; same pattern as the extractor.
- `project_metadata` stays on the conversational estimate response. GET is extra inspect. Streamlit inspects only on **Inspect session**.
- GET body = Lidr live fields only (no summary text).
- Every session 404 (`GET /sessions/{id}`, `POST .../estimate`, `POST .../estimate-acb`) is `{"detail": "session_not_found"}`.
- Split `src/sessions/` in step 1. Delete `_trim` in step 1.
- v3 = our v2 + Lidr `<audience>` / `<critic_feedback>`. Session prompt default is the setting (`v3`) in step 4. One-shot default stays v1. Do not edit v1/v2 templates.
- Anchor default `heuristic`; implement `llm` in step 3. Summarizer and critic fail-open.
- Session history user side is the enriched transcript on `/estimate` and `/estimate-acb`. Assistant stays `result.model_dump_json()`. Do not persist the rendered `user.j2`. `BOSS_MAX_ITERATIONS=3`.
- Inspect: full GET JSON via `st.json` in an expander. Inspect 404: new session + restart warning; no GET retry; `conv_result` and `conv_inspect` stay. ACB: two submit buttons in the same form. Conversational caption states default v3.
- Evals: out. Lidr test suite: rejected. Do not add a suite in any step.
- Do not raise Settings on missing API keys. Do not widen session 502. Do not change one-shot `/api/v1/estimate`.
- README updates travel with the step that changes the contract. Step 7 is grep / leftover only. No `evolution.md` in this port.
- Copy Lidr regexes, tier predicates, critic/ACB schemas, Boss decide/synthesize. Do not copy their class-as-bag, Rails, Streamlit, Settings key-required validator, or `except Exception` → 502.

## Do not copy from Lidr

- Rails chat + Postgres mirror.
- `EstimationService`.
- Their Streamlit (still one-shot).
- Settings validator that refuses to boot.
- `except Exception` → 502.
- Lidr `/estimate` persisting the rendered `user_message`.
- Dead `_trim`.
- Their README / leftover “v2 template” docstrings.
- Evals.

## Out of this port

- Persistence of sessions across process restart.
- Cumulative-summary strategy beyond what Lidr’s `CompressionPolicy` already does.
- Changing `transcript` max to 80k.
- `DELETE /sessions` or session list.
- Putting inspect fields on the estimate response instead of GET.
