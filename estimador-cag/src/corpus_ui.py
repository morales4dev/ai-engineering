"""HTTP-only Streamlit controls for corpus expansion."""

import json

import httpx
import streamlit as st


def render_corpus(base_url: str, api_key: str | None) -> None:
    st.subheader("Corpus / index")
    st.caption("Add budget JSON documents asynchronously. Existing IDs of the same type are skipped.")
    if not api_key:
        st.error("Configure ESTIMATE_API_KEY to manage the corpus.")
        return
    headers = {"X-API-Key": api_key}
    endpoint = f"{base_url}/embeddings/index"
    try:
        response = httpx.get(f"{endpoint}/stats", headers=headers, timeout=15)
        response.raise_for_status()
        stats = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        st.error(f"Could not load corpus statistics: {exc}")
        return
    st.write(f"{stats['total_chunks']} chunks · HNSW: {'indexed' if stats['hnsw_indexed'] else 'not indexed'}")
    st.dataframe(stats["collections"], hide_index=True)

    with st.form("corpus_expansion"):
        chunk_type = st.selectbox("Document type", ["budget_component", "historical_task"])
        documents_json = st.text_area("Budget JSON object or array", height=200)
        submitted = st.form_submit_button("Add to corpus")
    if submitted:
        try:
            documents = json.loads(documents_json)
            if isinstance(documents, dict):
                documents = [documents]
            if not isinstance(documents, list) or not documents:
                raise ValueError("Provide a JSON object or a non-empty array.")
            response = httpx.post(
                f"{endpoint}/runs", headers=headers,
                json={"documents": documents, "chunk_type": chunk_type}, timeout=30,
            )
            response.raise_for_status()
            st.session_state["corpus_index_job"] = response.json()["job_id"]
            st.session_state["corpus_index_finished"] = False
        except httpx.HTTPStatusError as exc:
            st.error(f"Could not start indexing: {exc.response.status_code} {exc.response.text}")
        except (ValueError, httpx.HTTPError) as exc:
            st.error(f"Could not start indexing: {exc}")

    job_id = st.session_state.get("corpus_index_job")
    if job_id:
        @st.fragment(run_every=None if st.session_state.get("corpus_index_finished") else "2s")
        def show_job() -> None:
            try:
                response = httpx.get(f"{endpoint}/runs/{job_id}", headers=headers, timeout=15)
                response.raise_for_status()
                job = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                st.error(f"Could not load indexing progress: {exc}")
                return
            st.write(f"Run {job_id}: {job['status']}")
            st.progress(job["processed"] / job["total"], text=f"{job['processed']} / {job['total']}")
            st.write(
                f"Indexed: {job['indexed']} · Skipped: {job['skipped']} · "
                f"New chunks: {job['chunks_created']}"
            )
            if job["error_message"]:
                st.error(job["error_message"])
            if job["status"] in ("completed", "failed") and not st.session_state.get(
                "corpus_index_finished"
            ):
                st.session_state["corpus_index_finished"] = True
                st.rerun()
            if job["after_stats"] is not None:
                st.write("Before")
                st.json(job["before_stats"])
                st.write("After")
                st.json(job["after_stats"])

        show_job()
    try:
        response = httpx.get(f"{endpoint}/runs", headers=headers, timeout=15)
        response.raise_for_status()
        runs = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        st.error(f"Could not load indexing history: {exc}")
    else:
        if runs:
            selected = st.selectbox(
                "Recent runs", [run["job_id"] for run in runs],
                format_func=lambda value: next(
                    f"{r['created_at']} · {r['status']} · {value}" for r in runs
                    if r["job_id"] == value
                ),
            )
            if st.button("Show selected run"):
                st.session_state["corpus_index_job"] = selected
                st.session_state["corpus_index_finished"] = False
                st.rerun()
