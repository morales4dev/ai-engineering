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

import httpx
import streamlit as st

from config import get_settings
from schemas.estimation import (
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
COMPARE_TIMEOUT_SECONDS = 600

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

WAIT_PHASES = ("Discovery", "Design", "Implementation", "QA", "Launch")
WAIT_PHASE_SECONDS = 2


_TIER_OPTIONS = ("auto", "executive", "pm", "developer", "default")


def _init_lab_state() -> None:
    st.session_state.setdefault("lab_budgets", None)
    st.session_state.setdefault("lab_corpus_label", None)
    st.session_state.setdefault("lab_result", None)


def _parse_budget_array(raw_text: str) -> list[dict]:
    from embedding_pipeline.schemas import Budget

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

st.title("Software estimation")
st.caption(
    "One-shot form, a conversational session, a saved estimation, or the chunking lab."
)

new_tab, conv_tab, history_tab, lab_tab = st.tabs(
    ["New estimation", "Conversational", "Recent", "Chunking Lab"],
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

with st.sidebar:
    st.header("Service")
    st.code(ESTIMATE_ENDPOINT, language="text")
    st.code(HISTORY_ENDPOINT, language="text")
    st.code(SESSIONS_ENDPOINT, language="text")
    st.code(COMPARE_ENDPOINT, language="text")
    st.code(COMPARISONS_ENDPOINT, language="text")
    st.markdown(f"**Primary model:** `{settings.PRIMARY_MODEL}`")
    st.markdown(f"**Fallback model:** `{settings.FALLBACK_MODEL}`")
    st.markdown(f"**Cache TTL:** `{settings.CACHE_TTL}s`")
