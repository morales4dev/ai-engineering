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

WAIT_PHASES = ("Discovery", "Design", "Implementation", "QA", "Launch")
WAIT_PHASE_SECONDS = 2


def _post_estimate_with_phase_wait(payload: dict) -> httpx.Response:
    """POST /estimate while rotating phase labels. Wait UX, not SSE."""
    box: dict = {}

    def _call() -> None:
        try:
            box["response"] = httpx.post(
                ESTIMATE_ENDPOINT,
                json=payload,
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


def _show_http_error(exc: httpx.HTTPStatusError) -> None:
    """Render a 400 guardrail payload as reason + message; fall back to the raw body."""
    if exc.response.status_code == 400:
        try:
            detail = exc.response.json().get("detail")
        except ValueError:
            detail = None
        if isinstance(detail, dict) and detail.get("message"):
            reason = detail.get("reason") or "blocked"
            st.badge(str(reason), icon=":material/block:", color="orange")
            st.error(detail["message"])
            return
    st.error(f"Service returned {exc.response.status_code}: {exc.response.text}")


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


st.title("Software estimation")
st.caption("Fill in the form or reopen a saved estimation from the API history.")

new_tab, history_tab = st.tabs(["New estimation", "Recent"])

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
    st.markdown(f"**Primary model:** `{settings.PRIMARY_MODEL}`")
    st.markdown(f"**Fallback model:** `{settings.FALLBACK_MODEL}`")
    st.markdown(f"**Cache TTL:** `{settings.CACHE_TTL}s`")
