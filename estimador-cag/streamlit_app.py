"""HTTP client UI. Submits a typed form to POST /estimate."""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import httpx
import streamlit as st

from config import get_settings
from schemas.estimation import DetailLevel, OutputFormat, ProjectType

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

st.title("Software estimation")
st.caption("Fill in the form. The service returns a free-text estimation.")

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
        with st.spinner("Calling the estimator service…"):
            try:
                response = httpx.post(
                    ESTIMATE_ENDPOINT,
                    json=payload,
                    timeout=httpx.Timeout(120.0, connect=10.0),
                )
                response.raise_for_status()
                body = response.json()
            except httpx.HTTPStatusError as exc:
                st.error(
                    f"Service returned {exc.response.status_code}: {exc.response.text}"
                )
            except httpx.HTTPError as exc:
                st.error(f"Could not reach the estimator at `{ESTIMATE_ENDPOINT}`: {exc}")
            else:
                st.markdown(f"**Prompt version:** `{body.get('prompt_version', '?')}`")
                st.markdown(body.get("text", ""))

with st.sidebar:
    st.header("Service")
    st.code(ESTIMATE_ENDPOINT, language="text")
    st.markdown(f"**Primary model:** `{settings.PRIMARY_MODEL}`")
    st.markdown(f"**Fallback model:** `{settings.FALLBACK_MODEL}`")
    st.markdown(f"**Cache TTL:** `{settings.CACHE_TTL}s`")
