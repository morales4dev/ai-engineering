"""Streamlit interface for the persisted structure-and-hours wizard."""

from __future__ import annotations

import math

import httpx
import pandas as pd
import streamlit as st
from generation.rag.schemas import GroundedEstimate


def render_grounded_estimate(endpoint: str, api_key: str | None) -> None:
    """HTTP-only client for the independent, historically grounded pipeline."""
    st.subheader("Grounded RAG estimate")
    st.caption(
        "Independent of the Wizard. Generates effort and per-line sources from historical budgets. "
        "This action calls paid models."
    )
    if not api_key:
        st.error("Configure ESTIMATE_API_KEY to use grounded estimation.")
        return
    with st.form("grounded_rag"):
        transcript = st.text_area("Transcript for grounded estimation", height=200)
        submitted = st.form_submit_button("Generate grounded estimate")
    if submitted:
        st.session_state.pop("grounded_rag_result", None)
        if not 100 <= len(transcript.strip()) <= 50_000:
            st.error("The transcript must contain between 100 and 50,000 characters.")
        else:
            try:
                with st.spinner("Generating grounded estimate..."):
                    response = httpx.post(
                        endpoint, headers={"X-API-Key": api_key},
                        json={"transcript": transcript.strip()},
                        timeout=httpx.Timeout(600, connect=10),
                    )
                    response.raise_for_status()
                    body = response.json()
                    GroundedEstimate.model_validate(body)
            except httpx.HTTPStatusError as exc:
                st.error(f"Service returned {exc.response.status_code}: {exc.response.text}")
                st.caption(f"Request ID: {exc.response.headers.get('X-Request-ID', 'not returned')}")
            except (httpx.HTTPError, ValueError) as exc:
                st.error(f"Could not use the grounded RAG API: {exc}")
            else:
                st.session_state["grounded_rag_result"] = {
                    "estimate": body, "request_id": response.headers.get("X-Request-ID"),
                }

    saved = st.session_state.get("grounded_rag_result")
    if not saved:
        return
    estimate = GroundedEstimate.model_validate(saved["estimate"])
    st.caption(f"Request ID: {saved.get('request_id') or 'not returned'}")
    st.write(f"Confidence: {estimate.confidence}")
    if estimate.confidence == "low":
        st.warning("Low confidence: review this estimate and its sources before using it.")
    if estimate.insufficient_context_explanation:
        st.warning(estimate.insufficient_context_explanation)
    if estimate.total_engineer_days is not None:
        st.write(f"Total: {estimate.total_engineer_days} engineer-days")
    if estimate.duration_weeks is not None:
        st.write(f"Duration: {estimate.duration_weeks} weeks")
    st.write(estimate.reasoning)
    st.caption("Grounding checks are signals, not proof; review sources before using an estimate.")
    if estimate.citation_report:
        report = estimate.citation_report
        st.write(
            f"Citations: {report.grounded_lines} grounded, {report.dangling_lines} dangling, "
            f"{report.insufficient_lines} without data."
        )
    if estimate.hallucination_report:
        counts = {
            status: sum(line.status == status for line in estimate.hallucination_report.lines)
            for status in ("grounded", "degraded", "insufficient", "unverified")
        }
        st.write(
            f"Evidence check: {counts['grounded']} supported, {counts['degraded']} flagged, "
            f"{counts['insufficient']} without data, {counts['unverified']} unverified."
        )
        for line in estimate.hallucination_report.lines:
            if line.status in ("degraded", "unverified"):
                st.warning(f"{line.module} / {line.component}: {line.status} — {line.reason}")
        if estimate.hallucination_report.judge_error:
            st.warning(estimate.hallucination_report.judge_error)
    for module in estimate.modules:
        st.markdown(f"#### {module.name}")
        if module.description:
            st.write(module.description)
        for task in module.tasks:
            effort = (
                f"{task.engineer_days} engineer-days"
                if task.engineer_days is not None else "Insufficient source data"
            )
            st.write(f"{task.name}: {effort}")
            if task.description:
                st.write(task.description)
            st.caption(f"Declared grounded: {task.grounded}")
            for source in task.sources:
                st.write(f"Chunk: {source.chunk_id} | Document: {source.document_id}")
                st.code(source.evidence, language=None)
    if estimate.assumptions:
        st.write("Assumptions:", [a.model_dump() for a in estimate.assumptions])
    with st.expander("Response JSON"):
        st.json(saved["estimate"])


def _text(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def _rows(modules: list[dict], *, cost: bool) -> list[dict]:
    rows = []
    for module in modules:
        for task in module.get("tasks") or [{}]:
            row = {
                "Module": module.get("name", ""),
                "Module description": module.get("description", ""),
                "Task": task.get("name", ""),
                "Task description": task.get("description", ""),
            }
            if cost:
                row["Hours"] = task.get("estimated_hours")
                row["Rate EUR/h"] = task.get("rate_eur_per_hour", 75)
            rows.append(row)
    if not rows:
        rows.append({
            "Module": "", "Module description": "", "Task": "", "Task description": "",
            **({"Hours": None, "Rate EUR/h": 75} if cost else {}),
        })
    return rows


def _modules(rows: list[dict], *, cost: bool) -> list[dict]:
    modules: dict[str, dict] = {}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        name, task_name = _text(row.get("Module")), _text(row.get("Task"))
        description = _text(row.get("Module description"))
        task_description = _text(row.get("Task description"))
        if not any((name, task_name, description, task_description)):
            continue
        if not name or not task_name:
            raise ValueError("Every row needs a module and a task name.")
        if (name, task_name) in seen:
            raise ValueError(f"Duplicate task '{task_name}' in module '{name}'.")
        seen.add((name, task_name))
        module = modules.setdefault(name, {"name": name, "description": description, "tasks": []})
        if module["description"] != description:
            raise ValueError(f"Use the same description for every row of module '{name}'.")
        task = {"name": task_name, "description": task_description}
        if cost:
            for label, key in (("Hours", "estimated_hours"), ("Rate EUR/h", "rate_eur_per_hour")):
                value = row.get(label)
                if value is None or (isinstance(value, float) and math.isnan(value)):
                    raise ValueError(f"{label} is required for task '{task_name}'.")
                try:
                    number = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{label} must be a non-negative whole number.") from exc
                if not math.isfinite(number) or not number.is_integer() or number < 0:
                    raise ValueError(f"{label} must be a non-negative whole number.")
                task[key] = int(number)
        module["tasks"].append(task)
    if not modules:
        raise ValueError("Add at least one task.")
    return list(modules.values())


def render_wizard(endpoint: str, api_key: str | None) -> None:
    st.subheader("RAG Wizard")
    st.caption("Transcript → structure → human review → task hours → confirmation.")
    if not api_key:
        st.error("Configure ESTIMATE_API_KEY to use the RAG Wizard.")
        return

    st.session_state.setdefault("rag_run", None)
    st.session_state.setdefault("rag_run_revision", 0)

    def call(method: str, path: str = "", payload: dict | None = None, timeout: int = 60):
        try:
            response = httpx.request(
                method, endpoint + path, headers={"X-API-Key": api_key},
                json=payload, timeout=httpx.Timeout(timeout, connect=10),
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            st.error(f"Service returned {exc.response.status_code}: {exc.response.text}")
        except (httpx.HTTPError, ValueError) as exc:
            st.error(f"Could not use the RAG API: {exc}")
        return None

    def update(body):
        if not isinstance(body, dict):
            st.error("The RAG API returned an unexpected execution.")
            return
        st.session_state.rag_run = body
        st.session_state.rag_run_revision += 1
        st.rerun()

    run = st.session_state.rag_run
    if run:
        st.caption(f"Execution #{run['id']} · {run['status']} · {run['current_step']}")
        if st.button("New execution", key="rag_new"):
            st.session_state.rag_run = None
            st.rerun()
    else:
        with st.form("rag_start"):
            transcript = st.text_area("Transcript", height=200)
            upload = st.file_uploader("Or upload a UTF-8 transcript", type=["txt"])
            start = st.form_submit_button("Start guided estimation")
        if start:
            try:
                text = upload.getvalue().decode("utf-8").strip() if upload else transcript.strip()
            except UnicodeDecodeError:
                st.error("The transcript file must be UTF-8 encoded.")
                text = ""
            if not 100 <= len(text) <= 50_000:
                st.error("The transcript must contain between 100 and 50,000 characters.")
            else:
                with st.spinner("Reformulating…"):
                    body = call("POST", payload={"transcript": text}, timeout=600)
                if body is not None:
                    update(body)

    if run:
        run_id = run["id"]
        revision = st.session_state.rag_run_revision
        with st.expander("Original transcript"):
            st.write(run["transcript"])
        st.markdown("#### 1. Reformulation")
        reformulation = run.get("reformulation") or {}
        if reformulation:
            st.json(reformulation.get("query", {}))
            st.caption(reformulation.get("search_text", ""))
        if st.button("Re-run reformulation", key=f"rag_reform_{run_id}"):
            with st.spinner("Reformulating…"):
                body = call("POST", f"/{run_id}/reformulate", timeout=600)
            if body is not None:
                update(body)

        st.markdown("#### 2. Generate structure")
        if st.button("Generate / regenerate structure", key=f"rag_generate_{run_id}"):
            with st.spinner("Generating structure…"):
                body = call("POST", f"/{run_id}/generate", timeout=600)
            if body is not None:
                update(body)
        generation = (run.get("generation") or {}).get("estimate") or {}
        if generation:
            st.caption(f"Structure confidence: {generation.get('confidence', 'unknown')}")
            st.write(generation.get("reasoning", ""))
            if generation.get("insufficient_context_explanation"):
                st.warning(generation["insufficient_context_explanation"])
            if generation.get("assumptions"):
                st.write("Assumptions:", generation["assumptions"])

            st.markdown("#### 3. Review structure")
            st.caption("Add, remove or edit modules and tasks before estimating hours.")
            structure = run.get("structure") or {}
            edited = st.data_editor(
                pd.DataFrame(_rows(structure.get("modules") or [], cost=False)),
                num_rows="dynamic", hide_index=True, use_container_width=True,
                key=f"rag_structure_{run_id}_{revision}",
            )
            with st.expander("Task search settings"):
                override = st.checkbox("Override retrieval settings for this estimation")
                search_options: dict[str, object] = {}
                if override:
                    search_options = {
                        "top_k": st.number_input("Neighbors per task", 1, 30, 5),
                        "distance_threshold": st.number_input(
                            "Maximum cosine distance", 0.0, 2.0, 0.45, 0.05
                        ),
                        "search_mode": st.selectbox("Search mode", ["vector", "hybrid"]),
                        "rerank": st.checkbox("Cross-encoder reranking"),
                    }
                else:
                    st.caption("Uses the current values in Settings → Retrieval.")
            if st.button("Estimate hours", key=f"rag_hours_{run_id}"):
                try:
                    modules = _modules(edited.to_dict(orient="records"), cost=False)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    with st.spinner("Searching historical tasks…"):
                        payload = {"modules": modules, **search_options}
                        body = call("POST", f"/{run_id}/hours", payload, timeout=600)
                    if body is not None:
                        update(body)

        task_hours = run.get("task_hours") or {}
        if task_hours:
            st.markdown("#### 4. Task hours")
            st.caption(
                "Hours come from similar tasks. The bundled task corpus is synthetic; "
                "the similarity score is not a calibrated probability."
            )
            for result in task_hours.get("tasks", []):
                if not result.get("has_match"):
                    st.warning(f"{result['module']} / {result['task']}: no matching task.")
                else:
                    hour_range = result.get("hours_range")
                    if hour_range:
                        st.warning(
                            f"{result['module']} / {result['task']}: "
                            f"{hour_range['low']}–{hour_range['high']} h. {hour_range['reason']}"
                        )
                    st.write(
                        f"{result['module']} / {result['task']}: "
                        f"{result['estimated_hours']} h · similarity/agreement "
                        f"{result['reliability']:.1%}"
                    )
                    with st.expander(f"Neighbors: {result['module']} / {result['task']}"):
                        st.dataframe(result.get("neighbors", []), hide_index=True)

            st.markdown("#### 5. Confirm hours and rates")
            adjusted = run.get("adjusted_breakdown") or {}
            edited = st.data_editor(
                pd.DataFrame(_rows(adjusted.get("modules") or [], cost=True)),
                num_rows="dynamic", hide_index=True, use_container_width=True,
                column_config={
                    "Hours": st.column_config.NumberColumn(min_value=0, step=1),
                    "Rate EUR/h": st.column_config.NumberColumn(min_value=0, step=1),
                },
                key=f"rag_cost_{run_id}_{revision}",
            )
            try:
                modules = _modules(edited.to_dict(orient="records"), cost=True)
            except ValueError as exc:
                st.warning(str(exc))
                modules = None
            if modules:
                total_hours = sum(t["estimated_hours"] for m in modules for t in m["tasks"])
                total_cost = sum(
                    t["estimated_hours"] * t["rate_eur_per_hour"]
                    for m in modules for t in m["tasks"]
                )
                st.metric("Current total", f"{total_hours} h · €{total_cost}")
            if st.button("Confirm and save", disabled=modules is None, key=f"rag_verify_{run_id}"):
                body = call("PATCH", f"/{run_id}/verify", {"modules": modules})
                if body is not None:
                    update(body)
            if adjusted.get("confirmed_at"):
                st.success(f"Confirmed: {adjusted['confirmed_at']}")

    st.markdown("#### Execution history")
    history = call("GET")
    if isinstance(history, list) and history:
        labels = {f"#{item['id']} · {item['status']} · {item['created_at']}": item["id"]
                  for item in history}
        selected = st.selectbox("Open execution", list(labels))
        if st.button("Open", key="rag_open"):
            body = call("GET", f"/{labels[selected]}")
            if body is not None:
                update(body)
    elif history == []:
        st.caption("No session 10 executions yet.")
