"""In-process UI. Streams via EstimationTokenStream (SDKs), not POST /estimate/stream.

Kept next to streamlit_app.py so both paths can be compared.
"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st
from pydantic import ValidationError

from config import get_settings
from schemas.estimation import EstimationRequest
from services.llm_service import (
    EstimationTokenStream,
    LLMServiceError,
    build_cag_context,
    build_estimation_response,
    options_from_request,
)

_STRUCTURE_CHECKS = (
    ("Title", "has_title"),
    ("Breakdown table", "has_breakdown_table"),
    ("Totals section", "has_totals_section"),
    ("Team section", "has_team_section"),
    ("Duration section", "has_duration_section"),
    ("Hours match", "hours_match"),
    ("Cost match", "cost_match"),
    ("Finish reason", "finish_reason_ok"),
)


def _status_icon(value: bool | None) -> str:
    if value is True:
        return ":green[:material/check_circle:]"
    if value is False:
        return ":red[:material/cancel:]"
    return ":gray[:material/remove:]"


st.set_page_config(
    page_title="Software estimation",
    page_icon=":material/calculate:",
    initial_sidebar_state="expanded",
)

st.session_state.setdefault("messages", [])
st.session_state.setdefault("last_response", None)

try:
    get_settings()
except ValueError as exc:
    st.error(str(exc))
    st.stop()

cag = build_cag_context()

st.title("Software estimation")
st.caption("Paste a meeting transcription to generate a CAG software estimation.")

with st.sidebar:
    st.header("CAG context")

    with st.expander("Active system prompt", expanded=False):
        st.code(cag.system_prompt, language="markdown")

    with st.expander("Injected CAG examples", expanded=False):
        if cag.examples_text:
            st.code(cag.examples_text, language="markdown")
        else:
            st.caption("No CAG examples are injected for the current request defaults.")

    last_call_slot = st.empty()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Paste a meeting transcription", submit_mode="disable"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        request = EstimationRequest(transcription=prompt)
    except ValidationError as exc:
        st.error(" ".join(err["msg"] for err in exc.errors()))
    else:
        with st.chat_message("assistant"):
            try:
                token_stream = EstimationTokenStream(
                    request.transcription,
                    options_from_request(request),
                )
                estimation_text = st.write_stream(token_stream)
            except LLMServiceError as exc:
                st.error(str(exc))
            else:
                if token_stream.result is None:
                    st.error("The estimation stream finished without a result.")
                else:
                    response = build_estimation_response(request, token_stream.result)
                    st.session_state.last_response = response.model_dump()
                    st.session_state.messages.append(
                        {"role": "assistant", "content": estimation_text}
                    )

with last_call_slot.container():
    last_response = st.session_state.last_response
    validation = last_response.get("validation") if last_response else None

    with st.expander("Validation", expanded=False):
        if validation is None:
            st.caption("No validation yet.")
        else:
            st.metric("Score", f"{validation['score']:.0%}")
            st.markdown(
                "\n".join(
                    f"{_status_icon(validation[key])} {label}"
                    for label, key in _STRUCTURE_CHECKS
                )
            )
            declared_hours = validation["declared_total_hours"]
            sum_hours = validation["sum_row_hours"]
            declared_cost = validation["declared_total_cost"]
            sum_cost = validation["sum_row_cost"]
            st.caption(
                "Hours: declared "
                f"{declared_hours if declared_hours is not None else '—'}, "
                f"sum {sum_hours if sum_hours is not None else '—'}"
            )
            st.caption(
                "Cost: declared "
                f"{declared_cost if declared_cost is not None else '—'}, "
                f"sum {sum_cost if sum_cost is not None else '—'}"
            )
            issues = validation.get("issues") or []
            if issues:
                st.markdown("**Issues**")
                for issue in issues:
                    st.caption(f":red[:material/error:] {issue}")

    st.subheader("Last call")
    if last_response is None:
        st.caption("No estimation yet.")
    else:
        usage = last_response["usage"]
        st.metric("Model", last_response["model"])
        st.metric("Input tokens", usage["input_tokens"])
        st.metric("Output tokens", usage["output_tokens"])
        st.metric("Response time", f"{last_response['latency_ms']} ms")
