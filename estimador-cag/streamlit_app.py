"""HTTP client UI. Submits a typed form to POST /estimate and reopens history via GET."""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import httpx  # noqa: E402
import streamlit as st  # noqa: E402

from config import get_settings  # noqa: E402
from schemas.estimation import (  # noqa: E402
    OUT_OF_SCOPE_PREFIX,
    DetailLevel,
    OutputFormat,
    ProjectType,
)

st.set_page_config(
    page_title="Software estimation",
    page_icon=":material/calculate:",
    initial_sidebar_state="expanded",
)

try:
    settings = get_settings()
except ValueError as exc:
    st.error(str(exc))
    st.stop()

API_BASE_URL = settings.ESTIMATOR_API_BASE_URL.rstrip("/")
ESTIMATE_ENDPOINT = f"{API_BASE_URL}/api/v1/estimate"
HISTORY_ENDPOINT = f"{API_BASE_URL}/api/v1/estimations"
SESSIONS_ENDPOINT = f"{API_BASE_URL}/sessions"
COMPARE_ENDPOINT = f"{API_BASE_URL}/embeddings/compare"
COMPARISONS_ENDPOINT = f"{API_BASE_URL}/embeddings/comparisons"
CONFIG_ENDPOINT = f"{API_BASE_URL}/api/v1/config/models"
RAG_RUNS_ENDPOINT = f"{API_BASE_URL}/v1/estimate/runs"
COMPARE_TIMEOUT_SECONDS = 600
RAG_GENERATION_TIMEOUT_SECONDS = 600
_RAG_SECTORS = ("finance", "ecommerce", "healthcare", "industrial")

# Same six canned strings as data/test_queries.json. Hardcoded: they are demo
# questions, not the corpus. Judge by eye — no gold labels.
_DEMO_QUERIES = [
    "OAuth authentication for fintech mobile app",
    "real-time inventory synchronization",
    "GDPR compliance and audit logging",
    "database performance optimization",
    "frontend dashboard with charts",
    "payment gateway integration",
]

# Mirrors Lidr Rag::Strategy catalog (names + defaults + cost badges).
_STRATEGY_CATALOG = (
    {
        "name": "structural",
        "label": "Structural",
        "description": "One budget component = one chunk, with a context header.",
        "cost_tier": "free",
        "needs_key": None,
        "default": True,
    },
    {
        "name": "fixed_size",
        "label": "Fixed size",
        "description": "Fixed 512-token windows with overlap — the degenerate baseline.",
        "cost_tier": "free",
        "needs_key": None,
        "default": True,
    },
    {
        "name": "recursive",
        "label": "Recursive",
        "description": "Hierarchical separators (paragraph → line → sentence).",
        "cost_tier": "free",
        "needs_key": None,
        "default": True,
    },
    {
        "name": "sentence_window",
        "label": "Sentence window",
        "description": "One sentence per chunk, ±2-sentence window in metadata.",
        "cost_tier": "free",
        "needs_key": None,
        "default": False,
    },
    {
        "name": "hierarchical",
        "label": "Hierarchical",
        "description": "Two indexed levels: parent (budget) and children (components).",
        "cost_tier": "free",
        "needs_key": None,
        "default": False,
    },
    {
        "name": "semantic",
        "label": "Semantic",
        "description": "Cuts where inter-sentence embedding similarity drops.",
        "cost_tier": "cheap",
        "needs_key": "openai",
        "default": False,
    },
    {
        "name": "propositional",
        "label": "Propositional",
        "description": "An LLM splits each component into atomic propositions.",
        "cost_tier": "expensive",
        "needs_key": "openai",
        "default": False,
    },
    {
        "name": "contextual_retrieval",
        "label": "Contextual retrieval",
        "description": "Claude situates each chunk inside the parent budget.",
        "cost_tier": "expensive",
        "needs_key": "anthropic",
        "default": False,
    },
)

# Runtime-configurable knobs (no FALLBACK_MODEL: this wrapper does not retry).
_MODEL_KNOB_CATALOG = (
    {
        "key": "PRIMARY_MODEL",
        "label": "Primary model",
        "description": "Every estimation call (one-shot, conversation, ACB actor).",
    },
    {
        "key": "CRITIC_MODEL",
        "label": "Critic (ACB)",
        "description": "Read-only auditor in the Actor-Critic-Boss loop.",
    },
    {
        "key": "METADATA_EXTRACTOR_MODEL",
        "label": "Metadata extractor",
        "description": "Extracts project_name / tech / scope once per conversational turn.",
    },
    {
        "key": "COMPRESSION_MODEL",
        "label": "History compression",
        "description": "Cumulative summarizer for conversational memory.",
    },
    {
        "key": "PROPOSITIONAL_CHUNKER_MODEL",
        "label": "Propositional chunker",
        "description": "Splits components into atomic propositions (Chunking Lab).",
    },
    {
        "key": "CONTEXTUAL_CHUNKER_MODEL",
        "label": "Contextual chunker",
        "description": "Claude situates each chunk inside the parent budget (Chunking Lab).",
    },
)

WAIT_PHASES = ("Discovery", "Design", "Implementation", "QA", "Launch")
WAIT_PHASE_SECONDS = 2


_TIER_OPTIONS = ("auto", "executive", "pm", "developer", "default")


def _init_lab_state() -> None:
    st.session_state.setdefault("lab_budgets", None)
    st.session_state.setdefault("lab_corpus_label", None)
    st.session_state.setdefault("lab_result", None)


def _parse_budget_array(raw_text: str) -> list[dict]:
    from generation.rag.schemas import Budget

    data = json.loads(raw_text)
    if not isinstance(data, list):
        raise ValueError("JSON must be an array of Budget objects.")
    return [Budget.model_validate(item).model_dump(mode="json") for item in data]


def _strategy_badge(entry: dict) -> str:
    bits = [entry["label"]]
    if entry["cost_tier"] == "expensive":
        bits.append("$ · lento")
    elif entry["cost_tier"] == "cheap":
        bits.append("$")
    if entry["needs_key"]:
        bits.append(f"{entry['needs_key']}_key")
    return " · ".join(bits)


def _render_compare_result(payload: dict) -> None:
    """Paint stats, cost bars and playground from a CompareResponse dict."""
    stats = payload.get("stats_per_strategy") or {}
    playground = payload.get("queries_per_strategy") or {}

    if stats:
        st.subheader("Stats per strategy")
        rows = []
        for name, item in stats.items():
            td = item.get("token_distribution") or {}
            rows.append(
                {
                    "Strategy": name,
                    "n": item.get("n_chunks"),
                    "min": td.get("min"),
                    "p50": td.get("p50"),
                    "p95": td.get("p95"),
                    "max": td.get("max"),
                    "orphans": item.get("n_orphan_chunks"),
                    "obese": item.get("n_obese_chunks"),
                    "cost $": item.get("ingestion_cost_usd"),
                    "seconds": item.get("ingestion_seconds"),
                }
            )
        st.dataframe(rows, hide_index=True, use_container_width=True)
        st.caption("Orphans: chunks < 20 tokens. Obese: chunks > 800 tokens.")

        costs = {name: float(item.get("ingestion_cost_usd") or 0.0) for name, item in stats.items()}
        st.subheader("Ingestion cost")
        if max(costs.values(), default=0.0) == 0.0:
            st.caption("All selected strategies are free at chunk time (no extra LLM / embed pass).")
        else:
            st.bar_chart(costs)

    if not playground:
        st.caption("No playground — this run had no queries.")
        return

    st.subheader("Playground · top-k by query")
    st.caption(
        "Judge by eye. These phrases are canned demos (same as `data/test_queries.json`), "
        "not gold labels. Example: “OAuth authentication…” often ranks "
        "`BUD-2024-001::AUTH-001` first on structural — AUTH-001 is a real component_id "
        "in the sample, not a made-up id."
    )
    by_query: dict[str, dict[str, list]] = {}
    for strategy, results in playground.items():
        for qr in results:
            by_query.setdefault(qr.get("query", ""), {})[strategy] = qr.get("top_k") or []

    for query, per_strategy in by_query.items():
        with st.expander(query, expanded=True):
            cols = st.columns(min(2, max(1, len(per_strategy))))
            for index, (strategy, tops) in enumerate(per_strategy.items()):
                with cols[index % len(cols)]:
                    st.markdown(f"**{strategy}**")
                    for rank, top in enumerate(tops, 1):
                        chunk_id = top.get("chunk_id", "")
                        cosine = top.get("cosine", 0.0)
                        badge = " · parent" if chunk_id.endswith("::parent") else ""
                        st.markdown(f"{rank}. `{chunk_id}`{badge} · **{cosine:.4f}**")
                        st.caption(top.get("text_preview") or "")


def _init_conversational_state() -> None:
    st.session_state.setdefault("session_id", None)
    st.session_state.setdefault("conv_result", None)
    st.session_state.setdefault("conv_metadata", None)
    st.session_state.setdefault("conv_inspect", None)
    st.session_state.setdefault("conv_uploader_nonce", 0)
    st.session_state.setdefault("conv_session_warning", None)


def _post_with_phase_wait(
    url: str,
    *,
    json: dict | None = None,
    data: dict | None = None,
    files: list | None = None,
) -> httpx.Response:
    """POST while rotating phase labels. Wait UX, not SSE."""
    box: dict = {}

    def _call() -> None:
        try:
            box["response"] = httpx.post(
                url,
                json=json,
                data=data,
                files=files,
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        except Exception as exc:  # noqa: BLE001 — re-raised in the UI thread
            box["error"] = exc

    worker = threading.Thread(target=_call, daemon=True)
    worker.start()
    started = time.monotonic()
    with st.status("Discovery…", expanded=True) as status:
        phase_line = st.empty()
        while worker.is_alive():
            elapsed = int(time.monotonic() - started)
            phase = WAIT_PHASES[(elapsed // WAIT_PHASE_SECONDS) % len(WAIT_PHASES)]
            minutes, seconds = divmod(elapsed, 60)
            status.update(label=f"{phase}…")
            phase_line.markdown(f"{phase} · `{minutes:02d}:{seconds:02d}`")
            worker.join(timeout=0.4)
        if "error" in box:
            status.update(label="Could not generate the estimation", state="error")
        else:
            status.update(label="Estimation ready", state="complete", expanded=False)

    if "error" in box:
        raise box["error"]
    return box["response"]


def _post_estimate_with_phase_wait(payload: dict) -> httpx.Response:
    """POST /estimate JSON. Same wait UX as the session multipart path."""
    return _post_with_phase_wait(ESTIMATE_ENDPOINT, json=payload)


def _show_http_error(exc: httpx.HTTPStatusError) -> None:
    """Render structured API errors; fall back to the raw body."""
    if exc.response.status_code in {400, 415, 422}:
        try:
            detail = exc.response.json().get("detail")
        except ValueError:
            detail = None
        if isinstance(detail, dict):
            reason = detail.get("reason") or "blocked"
            filename = detail.get("filename")
            message = detail.get("message")
            if filename and message:
                text = f"{filename}: {message}"
            elif message:
                text = message
            elif filename:
                text = f"Unsupported file: {filename}"
            else:
                text = exc.response.text
            st.badge(str(reason), icon=":material/block:", color="orange")
            st.error(text)
            return
    st.error(f"Service returned {exc.response.status_code}: {exc.response.text}")


def _rag_api_request(
    method: str,
    path: str = "",
    *,
    payload: dict | None = None,
    timeout_seconds: int = 15,
) -> dict | list:
    response = httpx.request(
        method,
        f"{RAG_RUNS_ENDPOINT}{path}",
        headers={"X-API-Key": settings.ESTIMATE_API_KEY or ""},
        json=payload,
        timeout=httpx.Timeout(float(timeout_seconds), connect=10.0),
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, (dict, list)):
        raise ValueError("The RAG API returned an unexpected response.")
    return body


def _rag_update_run(run: dict) -> None:
    st.session_state.rag_run = run
    st.session_state.rag_run_id = run["id"]
    st.session_state.rag_run_revision = st.session_state.get("rag_run_revision", 0) + 1


def _rag_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _rag_editor_rows(breakdown: dict) -> list[dict]:
    rows = []
    for module in breakdown.get("modules") or []:
        tasks = module.get("tasks") or []
        if not tasks:
            rows.append(
                {
                    "Module": module.get("name", ""),
                    "Module description": module.get("description", ""),
                    "Task": "",
                    "Task description": "",
                    "Engineer days": 0,
                    "Source IDs": "",
                }
            )
        for task in tasks:
            rows.append(
                {
                    "Module": module.get("name", ""),
                    "Module description": module.get("description", ""),
                    "Task": task.get("name", ""),
                    "Task description": task.get("description", ""),
                    "Engineer days": task.get("engineer_days", 0),
                    "Source IDs": ", ".join(str(source) for source in task.get("sources") or []),
                }
            )
    return rows or [
        {
            "Module": "",
            "Module description": "",
            "Task": "",
            "Task description": "",
            "Engineer days": 0,
            "Source IDs": "",
        }
    ]


def _rag_modules_from_editor(rows: list[dict]) -> list[dict]:
    modules: dict[str, dict] = {}
    for row in rows:
        name = _rag_text(row.get("Module"))
        module_description = _rag_text(row.get("Module description"))
        task_name = _rag_text(row.get("Task"))
        task_description = _rag_text(row.get("Task description"))
        sources_text = _rag_text(row.get("Source IDs"))
        raw_days = row.get("Engineer days", 0)
        if not any(
            (name, module_description, task_name, task_description, sources_text)
        ) and raw_days in (
            0,
            None,
            "",
        ):
            continue
        if not name:
            raise ValueError("Every non-empty row needs a module name.")
        if not task_name:
            if task_description or sources_text or raw_days not in (0, None, ""):
                raise ValueError("Every task needs a task name.")
            modules.setdefault(name, {"name": name, "description": module_description, "tasks": []})
            continue
        try:
            days = int(raw_days)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Engineer days must be a whole number for task {task_name}.") from exc
        if days < 0:
            raise ValueError("Engineer days cannot be negative.")
        try:
            sources = [int(value.strip()) for value in sources_text.split(",") if value.strip()]
        except ValueError as exc:
            raise ValueError(
                f"Source IDs must be comma-separated integers for task {task_name}."
            ) from exc

        module = modules.setdefault(
            name, {"name": name, "description": module_description, "tasks": []}
        )
        if module_description:
            module["description"] = module_description
        module["tasks"].append(
            {
                "name": task_name,
                "description": task_description,
                "engineer_days": days,
                "sources": sources,
            }
        )
    return list(modules.values())


def _create_session() -> str | None:
    try:
        response = httpx.post(SESSIONS_ENDPOINT, timeout=httpx.Timeout(15.0, connect=5.0))
        response.raise_for_status()
        session_id = response.json().get("session_id")
    except httpx.HTTPStatusError as exc:
        _show_http_error(exc)
        return None
    except httpx.HTTPError as exc:
        st.error(f"Could not create a session at `{SESSIONS_ENDPOINT}`: {exc}")
        return None
    if not session_id:
        st.error("The API created a session without a session_id.")
        return None
    return session_id


def _ensure_conversational_session() -> str | None:
    session_id = st.session_state.get("session_id")
    if session_id:
        return session_id
    session_id = _create_session()
    if session_id:
        st.session_state.session_id = session_id
    return session_id


def _reset_conversational_widgets(session_id: str) -> None:
    st.session_state.session_id = session_id
    st.session_state.conv_result = None
    st.session_state.conv_metadata = None
    st.session_state.conv_inspect = None
    st.session_state.conv_transcript = ""
    st.session_state.conv_uploader_nonce = st.session_state.get("conv_uploader_nonce", 0) + 1
    st.session_state.conv_session_warning = None


@st.dialog("New conversation")
def _confirm_new_conversation() -> None:
    st.write(
        "This creates a new API session and clears the transcript, files, "
        "last result and metadata shown here."
    )
    if st.button("Start new conversation", type="primary"):
        session_id = _create_session()
        if session_id:
            _reset_conversational_widgets(session_id)
            st.rerun()


def _attachment_parts(uploads: list | None) -> list[tuple[str, tuple[str, bytes, str]]] | None:
    if not uploads:
        return None
    parts: list[tuple[str, tuple[str, bytes, str]]] = []
    for upload in uploads:
        filename = getattr(upload, "name", None)
        if not filename:
            continue
        content_type = getattr(upload, "type", None) or "application/octet-stream"
        parts.append(("attachments", (filename, upload.getvalue(), content_type)))
    return parts or None


def _post_session_estimate(
    session_id: str,
    *,
    data: dict,
    files: list | None,
    path: str = "estimate",
) -> httpx.Response:
    url = f"{SESSIONS_ENDPOINT}/{session_id}/{path}"
    response = _post_with_phase_wait(url, data=data, files=files)
    if response.status_code != 404:
        return response
    new_id = _create_session()
    if new_id is None:
        return response
    st.session_state.session_id = new_id
    st.session_state.conv_inspect = None
    st.session_state.conv_session_warning = (
        "The API no longer had that session (usually a restart). Started a new one."
    )
    return _post_with_phase_wait(
        f"{SESSIONS_ENDPOINT}/{new_id}/{path}",
        data=data,
        files=files,
    )


def _inspect_session(session_id: str) -> None:
    """GET inspect. Cheap spinner. 404 starts a new session and keeps the last JSON."""
    try:
        with st.spinner("Inspecting session…"):
            response = httpx.get(
                f"{SESSIONS_ENDPOINT}/{session_id}",
                timeout=httpx.Timeout(15.0, connect=5.0),
            )
    except httpx.HTTPError as exc:
        st.error(f"Could not inspect the session at `{SESSIONS_ENDPOINT}`: {exc}")
        return
    if response.status_code == 404:
        new_id = _create_session()
        if new_id is not None:
            st.session_state.session_id = new_id
            st.session_state.conv_session_warning = (
                "The API no longer had that session (usually a restart). Started a new one."
            )
        return
    try:
        response.raise_for_status()
        st.session_state.conv_inspect = response.json()
    except httpx.HTTPStatusError as exc:
        _show_http_error(exc)
    except ValueError:
        st.error("The API returned inspect JSON that could not be parsed.")


def _render_project_metadata(session_id: str, metadata: dict | None) -> None:
    with st.expander("Project metadata", expanded=True):
        st.caption(f"session_id `{session_id}`")
        st.json(metadata or {})
        st.caption(
            "Filled from the API after each turn. Leaving this tab does not clear the session."
        )


def _render_result(body: dict) -> None:
    result = body.get("result") or {}
    prompt_version = body.get("prompt_version", "?")
    st.badge(f"prompt {prompt_version}", icon=":material/description:")
    if body.get("cached"):
        st.badge("cached", icon=":material/cached:", color="green")

    summary = result.get("summary", "")
    if summary.startswith(OUT_OF_SCOPE_PREFIX):
        st.warning(summary)
    else:
        st.markdown(summary)

    with st.container(horizontal=True):
        st.metric(
            "Duration",
            f"{result.get('total_duration_weeks', '?')} wk",
            border=True,
        )
        cost = result.get("total_cost_eur")
        st.metric(
            "Cost",
            f"{cost:,} €" if isinstance(cost, int) else "?",
            border=True,
        )
        confidence = result.get("confidence_pct")
        st.metric(
            "Confidence",
            f"{confidence}%" if isinstance(confidence, int) else "?",
            border=True,
        )

    phases = result.get("phases") or []
    st.subheader("Phases")
    st.table(
        [
            {
                "Phase": phase.get("name", ""),
                "Weeks": phase.get("duration_weeks"),
                "Cost (EUR)": phase.get("cost_eur"),
                "Summary": phase.get("summary", ""),
            }
            for phase in phases
        ]
    )

    observation = body.get("observation")
    if isinstance(observation, dict) and observation:
        with st.expander("Turn observation"):
            st.caption(
                "API call telemetry for this turn — not the project Cost € above. "
                "ACB and one-shot do not send this object."
            )
            st.json(observation)


def _render_review_trail(acb: dict) -> None:
    with st.expander("Review trail"):
        st.caption(
            f"final_decision `{acb.get('final_decision')}` · "
            f"{acb.get('iterations_run')} run(s)"
        )
        for item in acb.get("iterations") or []:
            st.markdown(
                f"**Round {item.get('iteration')}** — "
                f"{item.get('critic_verdict')} "
                f"({item.get('critic_confidence')}%) → "
                f"{item.get('decision_after')}"
            )
            issues = item.get("issue_summary") or []
            if issues:
                st.write(issues)


_init_conversational_state()
_init_lab_state()
st.session_state.setdefault("rag_run", None)
st.session_state.setdefault("rag_run_id", None)
st.session_state.setdefault("rag_run_revision", 0)

st.title("Software estimation")
st.caption(
    "One-shot form, a conversational session, a saved estimation, the chunking lab, or Ajustes."
)

new_tab, conv_tab, history_tab, lab_tab, rag_tab, ajustes_tab = st.tabs(
    ["New estimation", "Conversational", "Recent", "Chunking Lab", "RAG Wizard", "Ajustes"],
    on_change="rerun",
)

with new_tab:
    with st.form("estimation_form", clear_on_submit=False):
        description = st.text_area(
            "Project description",
            height=200,
            placeholder="Describe the project: goals, key features, constraints…",
            help="Between 20 and 2000 characters.",
        )
        project_type = st.selectbox(
            "Project type",
            options=[item.value for item in ProjectType],
            index=1,
        )
        detail_level = st.radio(
            "Detail level",
            options=[item.value for item in DetailLevel],
            index=1,
            horizontal=True,
        )
        output_format = st.selectbox(
            "Output format",
            options=[item.value for item in OutputFormat],
            index=0,
        )
        submitted = st.form_submit_button("Generate estimation", type="primary")

    if submitted:
        if len(description.strip()) < 20:
            st.error("The description must be at least 20 characters long.")
        elif len(description) > 2000:
            st.error("The description must be at most 2000 characters long.")
        else:
            payload = {
                "description": description.strip(),
                "project_type": project_type,
                "detail_level": detail_level,
                "output_format": output_format,
            }
            try:
                response = _post_estimate_with_phase_wait(payload)
                response.raise_for_status()
                body = response.json()
            except httpx.HTTPStatusError as exc:
                _show_http_error(exc)
            except httpx.HTTPError as exc:
                st.error(
                    f"Could not reach the estimator at `{ESTIMATE_ENDPOINT}`: {exc}"
                )
            else:
                _render_result(body)

if conv_tab.open:
    with conv_tab:
        session_id = _ensure_conversational_session()
        st.caption(
            "Transcript plus optional PDF/DOCX. The API default prompt is v3. "
            "Project facts persist in metadata. Prior turns stay in a sliding window."
        )
        if st.session_state.conv_session_warning:
            st.warning(st.session_state.conv_session_warning)
        if st.button("New conversation", icon=":material/refresh:"):
            _confirm_new_conversation()
        if session_id and st.button("Inspect session", icon=":material/search:"):
            _inspect_session(session_id)
        if session_id:
            uploader_key = f"conv_attachments_{st.session_state.conv_uploader_nonce}"
            with st.form("conversational_form", clear_on_submit=False):
                transcript = st.text_area(
                    "Transcript",
                    height=200,
                    key="conv_transcript",
                    persist_state="session",
                    placeholder="Describe the project or refine the previous turn…",
                    help="Between 20 and 2000 characters. Attachment text is added after this.",
                )
                uploads = st.file_uploader(
                    "Attachments",
                    type=["pdf", "docx"],
                    accept_multiple_files=True,
                    key=uploader_key,
                    help="Optional PDF or Word documents. Extracted locally in the API.",
                )
                project_type = st.selectbox(
                    "Project type",
                    options=[item.value for item in ProjectType],
                    index=1,
                    key="conv_project_type",
                    persist_state="session",
                )
                detail_level = st.radio(
                    "Detail level",
                    options=[item.value for item in DetailLevel],
                    index=1,
                    horizontal=True,
                    key="conv_detail_level",
                    persist_state="session",
                )
                output_format = st.selectbox(
                    "Output format",
                    options=[item.value for item in OutputFormat],
                    index=0,
                    key="conv_output_format",
                    persist_state="session",
                )
                tier_choice = st.selectbox(
                    "Audience tier",
                    options=list(_TIER_OPTIONS),
                    index=0,
                    key="conv_tier",
                    persist_state="session",
                    help="auto lets the API derive the audience. Any other value is sent as an override.",
                )
                with st.container(horizontal=True):
                    submitted = st.form_submit_button("Generate estimation", type="primary")
                    submitted_acb = st.form_submit_button("Estimate with review")

            if submitted or submitted_acb:
                if len(transcript.strip()) < 20:
                    st.error("The transcript must be at least 20 characters long.")
                elif len(transcript) > 2000:
                    st.error("The transcript must be at most 2000 characters long.")
                elif tier_choice not in _TIER_OPTIONS:
                    st.error("Invalid audience tier.")
                else:
                    form = {
                        "transcript": transcript.strip(),
                        "project_type": project_type,
                        "detail_level": detail_level,
                        "output_format": output_format,
                    }
                    if tier_choice != "auto":
                        form["tier"] = tier_choice
                    path = "estimate-acb" if submitted_acb else "estimate"
                    try:
                        response = _post_session_estimate(
                            session_id,
                            data=form,
                            files=_attachment_parts(uploads),
                            path=path,
                        )
                        response.raise_for_status()
                        body = response.json()
                    except httpx.HTTPStatusError as exc:
                        _show_http_error(exc)
                    except httpx.HTTPError as exc:
                        st.error(
                            f"Could not reach the session estimate at `{SESSIONS_ENDPOINT}`: {exc}"
                        )
                    else:
                        st.session_state.conv_result = body
                        st.session_state.conv_metadata = body.get("project_metadata") or {}
                        st.session_state.session_id = (
                            st.session_state.session_id or session_id
                        )

            _render_project_metadata(
                st.session_state.session_id or session_id,
                st.session_state.conv_metadata,
            )
            if st.session_state.conv_inspect is not None:
                with st.expander("Session inspect"):
                    st.json(st.session_state.conv_inspect)
            if st.session_state.conv_result:
                _render_result(st.session_state.conv_result)
                acb = st.session_state.conv_result.get("acb")
                if isinstance(acb, dict):
                    _render_review_trail(acb)

with history_tab:
    st.subheader("Recent estimations")
    st.caption("Loaded from GET /api/v1/estimations. Reopen uses GET /api/v1/estimations/{id}.")
    try:
        listing = httpx.get(HISTORY_ENDPOINT, timeout=httpx.Timeout(15.0, connect=5.0))
        listing.raise_for_status()
        items = listing.json().get("items") or []
    except httpx.HTTPStatusError as exc:
        _show_http_error(exc)
        items = []
    except httpx.HTTPError as exc:
        st.error(f"Could not reach history at `{HISTORY_ENDPOINT}`: {exc}")
        items = []

    if not items:
        st.caption("No saved estimations yet.")
    else:
        st.table(
            [
                {
                    "Id": item.get("id"),
                    "Preview": item.get("description_preview", ""),
                    "Type": item.get("project_type", ""),
                    "Prompt": item.get("prompt_version", ""),
                    "Cached": item.get("cached"),
                    "Created": item.get("created_at", ""),
                }
                for item in items
            ]
        )
        labels = {
            f"#{item['id']} · {item.get('description_preview', '')}": item["id"]
            for item in items
        }
        chosen = st.selectbox("Open an estimation", options=list(labels))
        if st.button("Open estimation", type="primary"):
            estimation_id = labels[chosen]
            try:
                detail = httpx.get(
                    f"{HISTORY_ENDPOINT}/{estimation_id}",
                    timeout=httpx.Timeout(15.0, connect=5.0),
                )
                detail.raise_for_status()
                body = detail.json()
            except httpx.HTTPStatusError as exc:
                _show_http_error(exc)
            except httpx.HTTPError as exc:
                st.error(f"Could not load estimation {estimation_id}: {exc}")
            else:
                if body.get("description"):
                    st.markdown(f"**Description:** {body['description']}")
                _render_result(body)

with lab_tab:
    st.subheader("Chunking Lab")
    st.caption(
        "POST /embeddings/compare · GET /embeddings/comparisons. HTTP only. "
        "FastAPI never reads the sample file — you upload or load it here."
    )

    sample_path = Path.cwd() / "data" / "budgets_sample.json"
    uploaded = st.file_uploader("Corpus (JSON array of Budget)", type=["json"])
    if uploaded is not None:
        try:
            st.session_state.lab_budgets = _parse_budget_array(
                uploaded.getvalue().decode("utf-8")
            )
            st.session_state.lab_corpus_label = uploaded.name
        except Exception as exc:  # noqa: BLE001 — show parse errors in the tab
            st.error(f"Could not parse upload: {exc}")
    if sample_path.is_file():
        if st.button("Use data/budgets_sample.json"):
            try:
                st.session_state.lab_budgets = _parse_budget_array(
                    sample_path.read_text(encoding="utf-8")
                )
                st.session_state.lab_corpus_label = "budgets_sample.json"
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not read sample: {exc}")
    else:
        st.caption("No `data/budgets_sample.json` in the Streamlit cwd.")

    if st.session_state.lab_budgets:
        st.caption(
            f"Corpus ready: `{st.session_state.lab_corpus_label}` · "
            f"{len(st.session_state.lab_budgets)} budgets"
        )
    else:
        st.caption("No corpus loaded yet.")

    selected: list[str] = []
    for entry in _STRATEGY_CATALOG:
        checked = st.checkbox(
            _strategy_badge(entry),
            value=entry["default"],
            help=entry["description"],
            key=f"lab_strat_{entry['name']}",
        )
        if checked:
            selected.append(entry["name"])

    chosen_queries = st.multiselect(
        "Demo queries (chips from test_queries.json — not gold answers)",
        options=_DEMO_QUERIES,
        default=[],
    )
    top_k = st.slider("top_k", min_value=1, max_value=10, value=3)

    if st.button("Compare strategies", type="primary"):
        if not st.session_state.lab_budgets:
            st.error("Load a corpus first (upload or sample shortcut).")
        elif not selected:
            st.error("Pick at least one strategy.")
        else:
            payload = {
                "budgets": st.session_state.lab_budgets,
                "queries": chosen_queries,
                "strategies": selected,
                "top_k": top_k,
                "corpus_label": st.session_state.lab_corpus_label or "budgets_sample",
            }
            try:
                with st.spinner(f"Comparing (timeout {COMPARE_TIMEOUT_SECONDS}s)…"):
                    response = httpx.post(
                        COMPARE_ENDPOINT,
                        json=payload,
                        timeout=httpx.Timeout(float(COMPARE_TIMEOUT_SECONDS), connect=10.0),
                    )
                    response.raise_for_status()
                st.session_state.lab_result = response.json()
            except httpx.HTTPStatusError as exc:
                _show_http_error(exc)
            except httpx.HTTPError as exc:
                st.error(f"Could not reach `{COMPARE_ENDPOINT}`: {exc}")

    if st.session_state.lab_result:
        _render_compare_result(st.session_state.lab_result)

    st.subheader("History")
    st.caption("GET /embeddings/comparisons · reopen does not run compare again.")
    try:
        listing = httpx.get(
            COMPARISONS_ENDPOINT, timeout=httpx.Timeout(15.0, connect=5.0)
        )
        listing.raise_for_status()
        comparisons = listing.json().get("items") or []
    except httpx.HTTPStatusError as exc:
        _show_http_error(exc)
        comparisons = []
    except httpx.HTTPError as exc:
        st.error(f"Could not reach history at `{COMPARISONS_ENDPOINT}`: {exc}")
        comparisons = []

    if not comparisons:
        st.caption("No saved comparisons yet.")
    else:
        st.table(
            [
                {
                    "Id": item.get("id"),
                    "Created": item.get("created_at", ""),
                    "Strategies": ", ".join(item.get("strategies") or []),
                    "Queries": len(item.get("queries") or []),
                    "top_k": item.get("top_k"),
                    "Corpus": item.get("corpus_label", ""),
                    "n": item.get("corpus_count"),
                    "Cost $": item.get("cost_total_usd"),
                    "ms": item.get("duration_ms"),
                }
                for item in comparisons
            ]
        )
        labels = {
            f"#{item['id']} · {item.get('corpus_label', '')} · "
            f"{', '.join(item.get('strategies') or [])}": item["id"]
            for item in comparisons
        }
        chosen = st.selectbox("Open a comparison", options=list(labels))
        if st.button("Open comparison", type="primary"):
            comparison_id = labels[chosen]
            try:
                detail = httpx.get(
                    f"{COMPARISONS_ENDPOINT}/{comparison_id}",
                    timeout=httpx.Timeout(15.0, connect=5.0),
                )
                detail.raise_for_status()
                body = detail.json()
            except httpx.HTTPStatusError as exc:
                _show_http_error(exc)
            except httpx.HTTPError as exc:
                st.error(f"Could not load comparison {comparison_id}: {exc}")
            else:
                st.session_state.lab_result = body.get("response") or {}
                st.rerun()

if rag_tab.open:
    with rag_tab:
        st.subheader("RAG Wizard")
        st.caption(
            "Guided transcript-to-estimate flow. The UI uses the FastAPI execution API; "
            "the server stores each execution and its stage results."
        )
        if not settings.ESTIMATE_API_KEY:
            st.error("Configure ESTIMATE_API_KEY in estimador-cag/.env to use the RAG Wizard.")
        else:
            current_run = st.session_state.rag_run
            if current_run:
                st.caption(
                    f"Execution **#{current_run['id']}** · "
                    f"status `{current_run.get('status', 'started')}` · "
                    f"current step `{current_run.get('current_step', 'transcript')}`"
                )
                if st.button("New execution", key="rag_new_execution"):
                    st.session_state.rag_run = None
                    st.session_state.rag_run_id = None
                    st.rerun()
            else:
                with st.form("rag_start_form", clear_on_submit=False):
                    transcript = st.text_area(
                        "Transcript",
                        height=200,
                        placeholder="Paste the project meeting transcript here…",
                        help="At least 100 characters. Alternatively upload a .txt file.",
                        key="rag_transcript",
                    )
                    transcript_file = st.file_uploader(
                        "Or upload a transcript",
                        type=["txt"],
                        key="rag_transcript_upload",
                    )
                    start_run = st.form_submit_button("Start guided estimation", type="primary")
                if start_run:
                    selected_transcript = transcript.strip()
                    valid_transcript = True
                    if transcript_file is not None:
                        try:
                            selected_transcript = transcript_file.getvalue().decode("utf-8").strip()
                        except UnicodeDecodeError:
                            st.error("The transcript file must be UTF-8 encoded.")
                            valid_transcript = False
                    if valid_transcript and len(selected_transcript) < 100:
                        st.error("The transcript must contain at least 100 characters.")
                    elif valid_transcript and len(selected_transcript) > 50_000:
                        st.error("The transcript must be at most 50,000 characters.")
                    elif valid_transcript:
                        try:
                            with st.spinner("Starting execution and reformulating the transcript…"):
                                body = _rag_api_request(
                                    "POST",
                                    payload={"transcript": selected_transcript},
                                )
                                if not isinstance(body, dict):
                                    raise ValueError(
                                        "The RAG API returned an unexpected execution."
                                    )
                                _rag_update_run(body)
                        except httpx.HTTPStatusError as exc:
                            _show_http_error(exc)
                        except httpx.HTTPError as exc:
                            st.error(f"Could not reach the RAG API at `{RAG_RUNS_ENDPOINT}`: {exc}")
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            st.rerun()

            current_run = st.session_state.rag_run
            if current_run:
                run_id = current_run["id"]
                st.markdown("#### 1. Transcript")
                with st.expander("Original transcript"):
                    st.write(current_run.get("transcript", ""))
                st.markdown("#### 2. Reformulation")
                reformulation = current_run.get("reformulation") or {}
                if reformulation:
                    st.markdown("**Brief**")
                    st.json(reformulation.get("query") or {})
                    st.markdown("**Search text**")
                    st.write(reformulation.get("search_text") or "")
                    if st.button("Re-run reformulation", key=f"rag_reformulate_{run_id}"):
                        try:
                            with st.spinner("Reformulating…"):
                                body = _rag_api_request("POST", f"/{run_id}/reformulate")
                                if not isinstance(body, dict):
                                    raise ValueError(
                                        "The RAG API returned an unexpected execution."
                                    )
                                _rag_update_run(body)
                        except httpx.HTTPStatusError as exc:
                            _show_http_error(exc)
                        except httpx.HTTPError as exc:
                            st.error(f"Could not reach the RAG API: {exc}")
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            st.rerun()

                retrieval = current_run.get("retrieval") or {}
                saved_filters = retrieval.get("filters") or {}
                st.markdown("#### 3. Retrieval")
                with st.form(f"rag_retrieval_form_{run_id}"):
                    top_k = st.number_input(
                        "top_k",
                        min_value=1,
                        max_value=30,
                        value=saved_filters.get("top_k", 10),
                        step=1,
                        key=f"rag_top_k_{run_id}",
                    )
                    threshold = st.number_input(
                        "Distance threshold",
                        min_value=0.0,
                        max_value=2.0,
                        value=float(saved_filters.get("distance_threshold", 0.6)),
                        step=0.05,
                        key=f"rag_threshold_{run_id}",
                    )
                    sectors = st.multiselect(
                        "Sectors",
                        options=list(_RAG_SECTORS),
                        default=saved_filters.get("sectors") or [],
                        key=f"rag_sectors_{run_id}",
                    )
                    year_col1, year_col2 = st.columns(2)
                    with year_col1:
                        year_min = st.number_input(
                            "Project year minimum",
                            min_value=2010,
                            max_value=2100,
                            value=saved_filters.get("project_year_min"),
                            step=1,
                            key=f"rag_year_min_{run_id}",
                        )
                    with year_col2:
                        year_max = st.number_input(
                            "Project year maximum",
                            min_value=2010,
                            max_value=2100,
                            value=saved_filters.get("project_year_max"),
                            step=1,
                            key=f"rag_year_max_{run_id}",
                        )
                    retrieve = st.form_submit_button(
                        "Run / re-run retrieval",
                        type="primary",
                        disabled=not bool(reformulation),
                    )
                if retrieve:
                    if year_min is not None and year_max is not None and year_min > year_max:
                        st.error("The minimum project year cannot exceed the maximum.")
                    else:
                        filters = {
                            "top_k": int(top_k),
                            "distance_threshold": float(threshold),
                            "sectors": sectors or None,
                            "project_year_min": year_min,
                            "project_year_max": year_max,
                        }
                        try:
                            with st.spinner("Retrieving historical evidence…"):
                                body = _rag_api_request(
                                    "POST", f"/{run_id}/retrieve", payload=filters
                                )
                                if not isinstance(body, dict):
                                    raise ValueError(
                                        "The RAG API returned an unexpected execution."
                                    )
                                _rag_update_run(body)
                        except httpx.HTTPStatusError as exc:
                            _show_http_error(exc)
                        except httpx.HTTPError as exc:
                            st.error(f"Could not reach the RAG API: {exc}")
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            st.rerun()

                if retrieval:
                    chunks = retrieval.get("chunks") or []
                    if retrieval.get("low_confidence"):
                        st.warning(
                            "Low confidence: no historical chunk passed the threshold. "
                            "The retrieved set is empty; it is not evidence for the estimate."
                        )
                    st.caption(
                        f"{len(chunks)} hit(s) · "
                        f"{retrieval.get('candidates_evaluated', 0)} candidate(s) evaluated"
                    )
                    if chunks:
                        st.dataframe(
                            [
                                {
                                    "ID": item.get("id"),
                                    "Sector": item.get("sector"),
                                    "Year": item.get("project_year"),
                                    "Type": item.get("chunk_type"),
                                    "Distance": item.get("distance"),
                                    "Content": item.get("content"),
                                }
                                for item in chunks
                            ],
                            hide_index=True,
                            use_container_width=True,
                        )

                st.markdown("#### 4. Context assembly")
                augmentation = current_run.get("augmentation") or {}
                if retrieval and not augmentation:
                    if st.button("Assemble context", key=f"rag_assemble_{run_id}", type="primary"):
                        try:
                            with st.spinner("Assembling the source context…"):
                                body = _rag_api_request("POST", f"/{run_id}/assemble", payload={})
                                if not isinstance(body, dict):
                                    raise ValueError(
                                        "The RAG API returned an unexpected execution."
                                    )
                                _rag_update_run(body)
                        except httpx.HTTPStatusError as exc:
                            _show_http_error(exc)
                        except httpx.HTTPError as exc:
                            st.error(f"Could not reach the RAG API: {exc}")
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            st.rerun()
                if augmentation:
                    kept = augmentation.get("kept_chunks") or []
                    st.caption(
                        f"Kept {len(kept)} chunk(s), dropped "
                        f"{augmentation.get('dropped_count', 0)} · "
                        f"{augmentation.get('token_count', 0)} token(s)"
                    )
                    with st.expander("Assembled <source> block"):
                        st.code(augmentation.get("context_block") or "", language="xml")

                st.markdown("#### 5. Grounded generation")
                generation = current_run.get("generation") or {}
                if augmentation and not generation:
                    if st.button("Generate estimate", key=f"rag_generate_{run_id}", type="primary"):
                        try:
                            with st.spinner(
                                f"Generating grounded estimate (timeout "
                                f"{RAG_GENERATION_TIMEOUT_SECONDS}s)…"
                            ):
                                body = _rag_api_request(
                                    "POST",
                                    f"/{run_id}/generate",
                                    timeout_seconds=RAG_GENERATION_TIMEOUT_SECONDS,
                                )
                                if not isinstance(body, dict):
                                    raise ValueError(
                                        "The RAG API returned an unexpected execution."
                                    )
                                _rag_update_run(body)
                        except httpx.HTTPStatusError as exc:
                            _show_http_error(exc)
                        except httpx.HTTPError as exc:
                            st.error(f"Could not reach the RAG API: {exc}")
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            st.rerun()
                if generation:
                    if generation.get("fabricated_source_ids"):
                        st.warning(
                            "The model cited unknown source IDs: "
                            + ", ".join(str(item) for item in generation["fabricated_source_ids"])
                        )
                    if generation.get("coherent") is False:
                        st.warning("The generated estimate failed the coherence check.")
                    estimate = generation.get("estimate") or {}
                    model_total = estimate.get("total_engineer_days")
                    model_total_label = (
                        f"{model_total} engineer-days"
                        if model_total is not None
                        else "Insufficient context"
                    )
                    st.caption(
                        f"Confidence: **{estimate.get('confidence', 'unknown')}** · "
                        f"Model total: **{model_total_label}**"
                    )
                    st.write(estimate.get("reasoning") or "")
                    estimate_rows = [
                        {
                            "Module": module.get("name", ""),
                            "Task": task.get("name", ""),
                            "Engineer days": task.get("engineer_days", 0),
                            "Source IDs": ", ".join(
                                str(source) for source in task.get("sources") or []
                            ),
                        }
                        for module in estimate.get("modules") or []
                        for task in module.get("tasks") or []
                    ]
                    if estimate_rows:
                        st.dataframe(estimate_rows, hide_index=True, use_container_width=True)
                    if estimate.get("sources"):
                        with st.expander("Source citations"):
                            st.json(estimate["sources"])
                    if estimate.get("assumptions"):
                        with st.expander("Assumptions"):
                            st.json(estimate["assumptions"])

                    st.markdown("#### 6. Human verification")
                    st.caption(
                        "The model output remains unchanged. Edit the human version; "
                        "the API recomputes and stores its total on save."
                    )
                    adjusted = current_run.get("adjusted_breakdown") or {}
                    model_col, human_col = st.columns(2)
                    with model_col:
                        st.markdown("**Model version**")
                        st.metric(
                            "Model engineer-days",
                            estimate.get("total_engineer_days")
                            if estimate.get("total_engineer_days") is not None
                            else "Insufficient",
                        )
                    with human_col:
                        st.markdown("**Human version**")
                        st.metric(
                            "Saved human engineer-days",
                            adjusted.get("total_engineer_days", 0),
                        )
                    editor_key = f"rag_editor_{run_id}_{st.session_state.rag_run_revision}"
                    edited = st.data_editor(
                        _rag_editor_rows(adjusted),
                        num_rows="dynamic",
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "Module": st.column_config.TextColumn(required=True),
                            "Module description": st.column_config.TextColumn(),
                            "Task": st.column_config.TextColumn(required=True),
                            "Task description": st.column_config.TextColumn(),
                            "Engineer days": st.column_config.NumberColumn(
                                min_value=0, step=1, format="%d"
                            ),
                            "Source IDs": st.column_config.TextColumn(
                                help="Comma-separated chunk IDs."
                            ),
                        },
                        key=editor_key,
                    )
                    try:
                        edited_modules = _rag_modules_from_editor(edited.to_dict(orient="records"))
                    except ValueError as exc:
                        st.error(str(exc))
                        edited_modules = []
                        edited_total = 0
                        valid_edit = False
                    else:
                        edited_total = sum(
                            task["engineer_days"]
                            for module in edited_modules
                            for task in module["tasks"]
                        )
                        valid_edit = True
                    st.metric("Current human engineer-days", edited_total)
                    save_verification = st.button(
                        "Save human version",
                        key=f"rag_save_verification_{run_id}",
                        type="primary",
                        disabled=not valid_edit,
                    )
                    if save_verification:
                        try:
                            with st.spinner("Saving verified estimate…"):
                                body = _rag_api_request(
                                    "PATCH",
                                    f"/{run_id}/verify",
                                    payload={"modules": edited_modules},
                                )
                                if not isinstance(body, dict):
                                    raise ValueError(
                                        "The RAG API returned an unexpected execution."
                                    )
                                _rag_update_run(body)
                        except httpx.HTTPStatusError as exc:
                            _show_http_error(exc)
                        except httpx.HTTPError as exc:
                            st.error(f"Could not reach the RAG API: {exc}")
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            st.success(
                                f"Saved human estimate: "
                                f"{body.get('adjusted_breakdown', {}).get('total_engineer_days', 0)} "
                                "engineer-days."
                            )
                            st.rerun()

            st.markdown("#### 7. Execution history")
            try:
                history = _rag_api_request("GET", timeout_seconds=15)
                if not isinstance(history, list):
                    raise ValueError("The RAG API returned an unexpected execution history.")
            except httpx.HTTPStatusError as exc:
                _show_http_error(exc)
                history = []
            except httpx.HTTPError as exc:
                st.error(f"Could not load RAG execution history: {exc}")
                history = []
            except ValueError as exc:
                st.error(str(exc))
                history = []

            if history:
                st.dataframe(
                    [
                        {
                            "ID": item.get("id"),
                            "Status": item.get("status"),
                            "Step": item.get("current_step"),
                            "Created": item.get("created_at"),
                            "Updated": item.get("updated_at"),
                        }
                        for item in history
                    ],
                    hide_index=True,
                    use_container_width=True,
                )
                history_labels = {
                    f"#{item['id']} · {item.get('status', '')} · "
                    f"{item.get('created_at', '')}": item["id"]
                    for item in history
                }
                selected_history = st.selectbox(
                    "Reopen execution",
                    options=list(history_labels),
                    key="rag_history_selection",
                )
                if st.button("Open execution", key="rag_open_execution"):
                    selected_id = history_labels[selected_history]
                    try:
                        body = _rag_api_request("GET", f"/{selected_id}")
                        if not isinstance(body, dict):
                            raise ValueError("The RAG API returned an unexpected execution.")
                        _rag_update_run(body)
                    except httpx.HTTPStatusError as exc:
                        _show_http_error(exc)
                    except httpx.HTTPError as exc:
                        st.error(f"Could not open execution #{selected_id}: {exc}")
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.rerun()
            else:
                st.caption("No RAG executions yet.")

with ajustes_tab:
    st.subheader("Ajustes")
    st.caption(
        "GET/PUT /api/v1/config/models. Overrides live in Redis "
        "(`estimator:runtime_config`) and apply on the next LLM call — "
        "no .env edit, no container recreate. «Por defecto» restores the .env value."
    )

    try:
        catalog_resp = httpx.get(
            CONFIG_ENDPOINT, timeout=httpx.Timeout(15.0, connect=5.0)
        )
        catalog_resp.raise_for_status()
        catalog = catalog_resp.json()
    except httpx.HTTPStatusError as exc:
        _show_http_error(exc)
        catalog = None
    except httpx.HTTPError as exc:
        st.error(f"Could not reach `{CONFIG_ENDPOINT}`: {exc}")
        catalog = None

    if catalog is not None:
        snapshot = catalog.get("models") or {}
        available = list(catalog.get("available_models") or [])
        primary = (snapshot.get("PRIMARY_MODEL") or {}).get("effective")
        if primary:
            st.caption(f"Effective primary: `{primary}`")

        with st.form("ajustes_form"):
            chosen: dict[str, str] = {}
            rows = []
            for entry in _MODEL_KNOB_CATALOG:
                item = snapshot.get(entry["key"]) or {}
                default = item.get("default") or ""
                effective = item.get("effective") or default
                overridden = bool(item.get("overridden"))
                default_label = f"Por defecto ({default})"
                options = [default_label]
                for model in available:
                    if model not in options:
                        options.append(model)
                if overridden and effective not in options:
                    options.append(effective)
                current = effective if overridden else default_label
                chosen[entry["key"]] = st.selectbox(
                    entry["label"],
                    options=options,
                    index=options.index(current) if current in options else 0,
                    help=f"{entry['description']} · `{entry['key']}`",
                    key=f"ajustes_{entry['key']}",
                )
                rows.append(
                    {
                        "Knob": entry["label"],
                        "Key": entry["key"],
                        "Effective": effective,
                        "Default": default,
                        "State": "override" if overridden else "default",
                    }
                )
            st.dataframe(rows, hide_index=True, use_container_width=True)
            st.markdown(f"**EMBEDDING_MODEL** (read-only): `{catalog.get('embedding_model')}`")
            st.caption(catalog.get("embedding_model_note") or "")
            saved = st.form_submit_button("Guardar", type="primary")

        if saved:
            payload: dict[str, str | None] = {}
            for entry in _MODEL_KNOB_CATALOG:
                selected = chosen[entry["key"]]
                item = snapshot.get(entry["key"]) or {}
                default = item.get("default") or ""
                if selected == f"Por defecto ({default})":
                    payload[entry["key"]] = None
                else:
                    payload[entry["key"]] = selected
            try:
                put = httpx.put(
                    CONFIG_ENDPOINT,
                    json={"models": payload},
                    timeout=httpx.Timeout(15.0, connect=5.0),
                )
                put.raise_for_status()
            except httpx.HTTPStatusError as exc:
                _show_http_error(exc)
            except httpx.HTTPError as exc:
                st.error(f"Could not save at `{CONFIG_ENDPOINT}`: {exc}")
            else:
                st.success("Models updated. The change applies on the next call.")
                st.rerun()

    st.caption(
        "No automatic provider fallback. The catalog only lists models whose "
        "provider key is configured."
    )

with st.sidebar:
    st.header("Service")
    st.caption("Estimate")
    st.code(ESTIMATE_ENDPOINT, language="text")
    st.caption("Recent")
    st.code(HISTORY_ENDPOINT, language="text")
    st.caption("Sessions")
    st.code(SESSIONS_ENDPOINT, language="text")
    st.caption("Compare")
    st.code(COMPARE_ENDPOINT, language="text")
    st.caption("Comparisons")
    st.code(COMPARISONS_ENDPOINT, language="text")
    st.caption("Settings")
    st.code(CONFIG_ENDPOINT, language="text")
    st.markdown(f"**Cache TTL:** `{settings.CACHE_TTL}s`")
