"""Offline tests for the Session 12 agent."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from generation.agentic.agent import FinalExplanation, run_agent
from generation.agentic.tools import (
    TOOL_SCHEMAS,
    CalculateArgs,
    SearchArgs,
    ValidateArgs,
    calculate_estimate,
    real_retrieval,
    validate_estimate,
)


def call(name, call_id, arguments):
    return {
        "type": "function_call",
        "name": name,
        "call_id": call_id,
        "arguments": json.dumps(arguments),
    }


class FakeWrapper:
    def __init__(self, outputs):
        self.outputs = outputs
        self.requests = []

    def prepare_agent_input(self, prompt, transcript):
        return "bounded instructions", f"bounded: {transcript}"

    def agent_response(self, **kwargs):
        self.requests.append(kwargs)
        output, text = self.outputs[min(len(self.requests) - 1, len(self.outputs) - 1)]
        return SimpleNamespace(id=f"response_{len(self.requests)}", output=output, output_text=text)


async def backend(args):
    return [{"id": 1 if args.query == "backend" else 2, "estimated_hours": 100.0}]


def finished():
    return json.dumps(
        {"explanation": "Based on historical data.", "assumptions": [], "confidence": "medium"}
    )


def script():
    components = [
        {"name": "backend", "reference_amounts": [100]},
        {"name": "mobile", "reference_amounts": [100]},
    ]
    validated = [{**component, "estimated_hours": 115.0} for component in components]
    return [
        (
            [
                {"type": "reasoning", "summary": [{"text": "Search both components."}]},
                call("search_budgets", "search-1", {"query": "backend", "filters": None}),
                call("search_budgets", "search-2", {"query": "mobile", "filters": None}),
            ],
            "",
        ),
        ([call("calculate_estimate", "calc", {"components": components})], ""),
        (
            [call("validate_estimate", "validate", {"components": validated, "total_hours": 230})],
            "",
        ),
        ([], finished()),
    ]


async def test_loop_runs_multiple_calls_and_keeps_calculated_result():
    wrapper = FakeWrapper(script())
    result = await run_agent("transcript", wrapper=wrapper, retrieval_backend=backend)
    assert result.status == "completed"
    assert result.estimate["total_hours"] == 230
    assert result.estimate["validation"]["ok"]
    assert [step.tool for step in result.steps] == [
        "search_budgets",
        "search_budgets",
        "calculate_estimate",
        "validate_estimate",
    ]
    assert result.steps[0].reasoning == "Search both components."
    assert result.steps[1].reasoning == "Same model turn as STEP 1."
    assert result.steps[2].reasoning is None
    assert "no reasoning summary emitted" in result.render()
    assert wrapper.requests[1]["previous_response_id"] == "response_1"
    assert [x["call_id"] for x in wrapper.requests[1]["input_items"]] == ["search-1", "search-2"]
    assert all(x["type"] == "function_call_output" for x in wrapper.requests[1]["input_items"])
    assert all(request["instructions"] == "bounded instructions" for request in wrapper.requests)
    assert wrapper.requests[0]["response_model"] is FinalExplanation


async def test_limit_and_premature_final_do_not_return_estimate():
    wrapper = FakeWrapper(
        [([call("search_budgets", "c", {"query": "backend", "filters": None})], "")]
    )
    limited = await run_agent("text", wrapper=wrapper, retrieval_backend=backend, max_iterations=2)
    assert limited.status == "max_iterations"
    assert limited.estimate is None
    assert len(limited.steps) == 2
    premature = await run_agent(
        "text", wrapper=FakeWrapper([([], finished())]), retrieval_backend=backend
    )
    assert premature.status == "incomplete"
    assert premature.estimate is None


async def test_invalid_args_and_invented_hours_are_returned_as_tool_errors():
    outputs = [
        ([call("search_budgets", "s", {"query": "backend", "filters": None})], ""),
        (
            [
                call(
                    "calculate_estimate",
                    "c",
                    {"components": [{"name": "x", "reference_amounts": [999]}]},
                )
            ],
            "",
        ),
        ([call("calculate_estimate", "bad", {"components": [{"name": "x"}]})], ""),
        ([], finished()),
    ]
    wrapper = FakeWrapper(outputs)
    result = await run_agent("text", wrapper=wrapper, retrieval_backend=backend)
    assert "must come from search results" in result.steps[1].observation["error"]
    assert "error" in result.steps[2].observation
    assert result.status == "incomplete"
    assert json.loads(wrapper.requests[2]["input_items"][0]["output"])["error"]


async def test_validation_must_match_latest_calculation():
    outputs = script()
    outputs[2] = (
        [
            call(
                "validate_estimate",
                "v",
                {
                    "components": [
                        {"name": "backend", "reference_amounts": [100], "estimated_hours": 1}
                    ],
                    "total_hours": 1,
                },
            )
        ],
        "",
    )
    result = await run_agent("text", wrapper=FakeWrapper(outputs), retrieval_backend=backend)
    assert "latest calculated" in result.steps[-1].observation["error"]
    assert result.status == "incomplete"


async def test_invalid_final_response_cannot_be_a_success():
    outputs = script()
    outputs[-1] = ([], '{"explanation": "unfinished"}')
    result = await run_agent("text", wrapper=FakeWrapper(outputs), retrieval_backend=backend)
    assert result.status == "invalid_final"
    assert result.estimate is None


async def test_unbudgeted_estimate_is_reported_as_validation_issues():
    outputs = [
        (
            [
                call(
                    "calculate_estimate",
                    "c",
                    {
                        "components": [
                            {"name": "unknown", "reference_amounts": []},
                        ]
                    },
                )
            ],
            "",
        ),
        (
            [
                call(
                    "validate_estimate",
                    "v",
                    {
                        "components": [
                            {"name": "unknown", "reference_amounts": [], "estimated_hours": 0},
                        ],
                        "total_hours": 0,
                    },
                )
            ],
            "",
        ),
        ([], finished()),
    ]
    result = await run_agent("text", wrapper=FakeWrapper(outputs), retrieval_backend=backend)
    assert result.status == "validation_issues"
    assert result.estimate["components"][0]["unbudgeted"]
    assert not result.estimate["validation"]["ok"]


async def test_provider_and_retrieval_failures_are_explicit():
    class BrokenWrapper(FakeWrapper):
        def agent_response(self, **kwargs):
            raise RuntimeError("provider unavailable")

    result = await run_agent("text", wrapper=BrokenWrapper([]), retrieval_backend=backend)
    assert result.status == "response_error" and result.estimate is None

    async def broken_backend(args):
        raise RuntimeError("database unavailable")

    result = await run_agent(
        "text", wrapper=FakeWrapper(script()), retrieval_backend=broken_backend
    )
    assert result.status == "tool_error"
    assert "database unavailable" in result.steps[0].observation["error"]


def test_calculation_and_guardrails_flag_missing_references():
    calculated = calculate_estimate(
        CalculateArgs.model_validate(
            {
                "components": [
                    {"name": "A", "reference_amounts": [100, 200, 300]},
                    {"name": "B", "reference_amounts": []},
                ],
            }
        )
    )
    assert calculated["total_hours"] == 230
    assert calculated["components"][1]["unbudgeted"]
    validated = validate_estimate(
        ValidateArgs.model_validate(
            {
                "components": [
                    {
                        key: component[key]
                        for key in ("name", "reference_amounts", "estimated_hours")
                    }
                    for component in calculated["components"]
                ],
                "total_hours": 999,
            }
        )
    )
    assert not validated["ok"]
    assert any("no historical reference" in issue for issue in validated["issues"])
    assert any("does not match" in issue for issue in validated["issues"])


async def test_real_retrieval_forces_hybrid_and_reranking(monkeypatch):
    import dependencies
    from generation.rag import retriever

    captured = {}
    monkeypatch.setattr(
        dependencies, "get_embedder", lambda: SimpleNamespace(embed_one=lambda q: [0.1])
    )

    async def search(embedding, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            chunks=[
                SimpleNamespace(
                    id=3,
                    content="scope",
                    sector="logistics",
                    project_year=2024,
                    budget_id="b",
                    estimated_hours=50,
                    has_vector_distance=False,
                    distance=1.0,
                )
            ]
        )

    monkeypatch.setattr(retriever, "search_chunks", search)
    result = await real_retrieval(
        SearchArgs.model_validate(
            {
                "query": "mobile",
                "filters": {"sectors": ["logistics"], "project_year_min": 2020},
            }
        )
    )
    assert captured["search_mode"] == "hybrid" and captured["rerank"] is True
    assert captured["chunk_types"] == ["historical_task"]
    assert captured["sectors"] == ["logistics"] and captured["project_year_min"] == 2020
    assert result[0]["estimated_hours"] == 50 and result[0]["distance"] is None


def test_flat_strict_tool_schemas():
    for tool in TOOL_SCHEMAS:
        assert tool["type"] == "function" and tool["strict"] is True
        assert "name" in tool and "function" not in tool
        assert tool["parameters"]["additionalProperties"] is False


async def test_cli_stub_loads_example_data_and_rejects_unsupported_year_filter():
    from scripts.run_agent_s12 import _stub_backend

    stub = _stub_backend()
    items = await stub(SearchArgs.model_validate({"query": "SAP integration", "filters": None}))
    assert any(item["estimated_hours"] for item in items)
    with pytest.raises(ValueError, match="does not support year filters"):
        await stub(
            SearchArgs.model_validate({"query": "SAP", "filters": {"project_year_min": 2020}})
        )


def test_cli_saves_failed_trace_and_refuses_to_overwrite(tmp_path, monkeypatch, capsys):
    import sys

    from generation.agentic.agent import AgentResult
    from scripts import run_agent_s12

    transcript = tmp_path / "transcript.txt"
    transcript.write_text("test transcript")
    output = tmp_path / "trace.txt"

    async def failed_run(*args, **kwargs):
        return AgentResult(status="max_iterations", error="Maximum reached.")

    monkeypatch.setattr(run_agent_s12, "get_llm_wrapper", lambda: object())
    monkeypatch.setattr(run_agent_s12, "run_agent", failed_run)
    monkeypatch.setattr(sys, "argv", ["agent", str(transcript), "--out", str(output)])
    assert run_agent_s12.main() == 1
    assert "STOP: max_iterations" in output.read_text()
    with pytest.raises(SystemExit) as exc:
        run_agent_s12.main()
    assert exc.value.code == 2
    assert "STOP: max_iterations" in output.read_text()
    assert "must be a new file" in capsys.readouterr().err
