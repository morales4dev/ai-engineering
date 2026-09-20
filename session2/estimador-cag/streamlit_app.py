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

    st.subheader("Last call")
    last_response = st.session_state.last_response
    if last_response is None:
        st.caption("No estimation yet.")
    else:
        usage = last_response["usage"]
        st.metric("Model", last_response["model"])
        st.metric("Input tokens", usage["input_tokens"])
        st.metric("Output tokens", usage["output_tokens"])
        st.metric("Response time", f"{last_response['latency_ms']} ms")

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
