"""HTTP client UI. Submits a typed form to POST /estimate and reopens history via GET."""

from __future__ import annotations

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

WAIT_PHASES = ("Discovery", "Design", "Implementation", "QA", "Launch")
WAIT_PHASE_SECONDS = 2


def _init_conversational_state() -> None:
    st.session_state.setdefault("session_id", None)
    st.session_state.setdefault("conv_result", None)
    st.session_state.setdefault("conv_metadata", None)
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
) -> httpx.Response:
    url = f"{SESSIONS_ENDPOINT}/{session_id}/estimate"
    response = _post_with_phase_wait(url, data=data, files=files)
    if response.status_code != 404:
        return response
    new_id = _create_session()
    if new_id is None:
        return response
    st.session_state.session_id = new_id
    st.session_state.conv_session_warning = (
        "The API no longer had that session (usually a restart). Started a new one."
    )
    return _post_with_phase_wait(
        f"{SESSIONS_ENDPOINT}/{new_id}/estimate",
        data=data,
        files=files,
    )


def _render_project_metadata(session_id: str, metadata: dict | None) -> None:
    with st.expander("Project metadata", expanded=True):
        st.caption(f"session_id `{session_id}`")
        st.json(metadata or {})
        st.caption(
            "Empty until cut 3 extracts facts. Leaving this tab does not clear the session."
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


_init_conversational_state()

st.title("Software estimation")
st.caption("One-shot form, a conversational session, or a saved estimation from the API history.")

new_tab, conv_tab, history_tab = st.tabs(
    ["New estimation", "Conversational", "Recent"],
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
            "Transcript plus optional PDF/DOCX. The API default prompt is v2. "
            "Turns do not share memory yet."
        )
        if st.session_state.conv_session_warning:
            st.warning(st.session_state.conv_session_warning)
        if st.button("New conversation", icon=":material/refresh:"):
            _confirm_new_conversation()
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
                submitted = st.form_submit_button("Generate estimation", type="primary")

            if submitted:
                if len(transcript.strip()) < 20:
                    st.error("The transcript must be at least 20 characters long.")
                elif len(transcript) > 2000:
                    st.error("The transcript must be at most 2000 characters long.")
                else:
                    form = {
                        "transcript": transcript.strip(),
                        "project_type": project_type,
                        "detail_level": detail_level,
                        "output_format": output_format,
                    }
                    try:
                        response = _post_session_estimate(
                            session_id,
                            data=form,
                            files=_attachment_parts(uploads),
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
            if st.session_state.conv_result:
                _render_result(st.session_state.conv_result)

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

with st.sidebar:
    st.header("Service")
    st.code(ESTIMATE_ENDPOINT, language="text")
    st.code(HISTORY_ENDPOINT, language="text")
    st.code(SESSIONS_ENDPOINT, language="text")
    st.markdown(f"**Primary model:** `{settings.PRIMARY_MODEL}`")
    st.markdown(f"**Fallback model:** `{settings.FALLBACK_MODEL}`")
    st.markdown(f"**Cache TTL:** `{settings.CACHE_TTL}s`")
