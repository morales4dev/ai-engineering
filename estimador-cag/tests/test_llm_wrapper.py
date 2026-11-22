"""Exercise native LiteLLM Responses against an in-process HTTP transport."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import litellm
import pytest
from litellm.llms.custom_httpx.http_handler import HTTPHandler
from pydantic import ValidationError
from structlog.testing import capture_logs

from generation.agentic.agent import FinalExplanation, run_agent
from generation.agentic.tools import TOOL_SCHEMAS
from generation.rag.schemas import Estimate, SourceReference, TaskItem, WorkModule
from services.llm_wrapper import LLMWrapper


def _estimate() -> Estimate:
    return Estimate(
        confidence="high", reasoning="Based on the supplied budget.",
        total_engineer_days=15,
        modules=[WorkModule(name="Authentication", tasks=[TaskItem(
            name="JWT authentication", engineer_days=15, grounded=True,
            sources=[SourceReference(
                chunk_id="1", document_id="BUD-2024-001", evidence="Estimated hours: 120",
            )],
        )])],
    )


def _response(*, estimate: dict | None = None, status: str = "completed") -> dict:
    text = json.dumps(estimate if estimate is not None else _estimate().model_dump())
    return {
        "id": "resp_test", "object": "response", "created_at": 0,
        "model": "gpt-5", "status": status,
        "error": None,
        "incomplete_details": {"reason": "max_output_tokens"} if status == "incomplete" else None,
        "output": [{
            "id": "msg_test", "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }],
        "usage": {
            "input_tokens": 100, "output_tokens": 50, "total_tokens": 150,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 20},
        },
        "parallel_tool_calls": False, "tools": [], "tool_choice": "auto",
    }


@pytest.fixture
def responses_transport(monkeypatch):
    requests: list[dict] = []
    calls: list[dict] = []
    clients: list[httpx.Client] = []
    original_responses = litellm.responses

    def wire(payloads: list[dict], *, status_code: int = 200):
        def handle(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/responses"
            assert request.extensions["timeout"]["read"] == 37
            requests.append(json.loads(request.content))
            return httpx.Response(
                status_code, json=payloads[min(len(requests) - 1, len(payloads) - 1)],
            )

        client = httpx.Client(transport=httpx.MockTransport(handle))
        clients.append(client)
        handler = HTTPHandler(client=client)

        def responses(**kwargs):
            calls.append(kwargs)
            return original_responses(**kwargs)

        monkeypatch.setattr(
            "litellm.llms.custom_httpx.llm_http_handler._get_httpx_client",
            lambda **kwargs: handler,
        )
        monkeypatch.setattr("services.llm_wrapper.litellm.responses", responses)
        return requests, calls

    yield wire
    for client in clients:
        client.close()


def _wrapper(*, model: str = "gpt-5", key: str | None = "test-key") -> LLMWrapper:
    return LLMWrapper(
        openai_api_key=key, anthropic_api_key=None, primary_model=model, timeout=37,
    )


def _call(wrapper: LLMWrapper, **kwargs):
    return wrapper.complete_structured_responses(
        system_prompt="Use only retrieved sources.",
        user_message='<source id="1">Estimated hours: 120</source>',
        response_model=Estimate, **kwargs,
    )


def test_responses_sends_strict_schema_boundary_and_reasoning_budget(responses_transport):
    requests, calls = responses_transport([_response()])
    with capture_logs() as logs:
        estimate, meta = _call(
            _wrapper(model="gpt-4o-mini"), model_override="openai/gpt-5",
            reasoning_effort="high", max_tokens=64_000,
        )

    assert estimate == _estimate()
    request = requests[0]
    assert request["model"] == "gpt-5"
    assert request["max_output_tokens"] == 64_000
    assert request["reasoning"] == {"effort": "high"}
    assert "untrusted meeting data" in request["instructions"]
    assert request["input"].startswith("<datos-")
    assert 'Estimated hours: 120</source>' in request["input"]
    output_format = request["text"]["format"]
    assert output_format["type"] == "json_schema"
    assert output_format["strict"] is True
    assert output_format["schema"]["additionalProperties"] is False
    task_schema = output_format["schema"]["$defs"]["TaskItem"]
    assert set(task_schema["required"]) == set(task_schema["properties"])
    assert calls[0]["api_key"] == "test-key"
    assert calls[0]["custom_llm_provider"] == "openai"
    assert calls[0]["use_chat_completions_api"] is False
    assert calls[0]["drop_params"] is False
    assert (meta["tokens_in"], meta["tokens_out"]) == (100, 50)
    assert meta["model"] == "gpt-5" and meta["provider"] == "openai"
    assert meta["cost_usd"] == 0.000625
    assert logs[-1]["event"] == "llm_responses_call_completed"


def test_agent_responses_sends_tools_and_chains_without_leaking_transcript(responses_transport):
    payload = _response()
    payload["output"] = [{
        "type": "function_call", "id": "fc_1", "call_id": "call_1",
        "name": "search_budgets", "arguments": '{"query":"api","filters":null}',
        "status": "completed",
    }]
    requests, calls = responses_transport([payload, payload])
    wrapper = _wrapper()
    instructions, transcript = wrapper.prepare_agent_input("Estimate.", "Untrusted transcript")
    response = wrapper.agent_response(
        instructions=instructions, input_items=transcript, tools=TOOL_SCHEMAS,
        response_model=FinalExplanation, model="gpt-5", reasoning_effort="medium",
    )
    wrapper.agent_response(
        instructions=instructions,
        input_items=[{"type": "function_call_output", "call_id": "call_1", "output": "{}"}],
        previous_response_id=response.id, tools=TOOL_SCHEMAS, response_model=FinalExplanation,
        model="gpt-5", reasoning_effort="medium",
    )
    assert "untrusted meeting data" in requests[0]["instructions"]
    assert requests[0]["input"].startswith("<datos-")
    assert requests[0]["reasoning"] == {"effort": "medium", "summary": "auto"}
    assert requests[0]["tools"][0]["name"] == "search_budgets"
    assert requests[0]["tools"][0]["strict"] is True
    assert requests[0]["text"]["format"]["type"] == "json_schema"
    assert calls[1]["previous_response_id"] == response.id
    assert requests[1]["previous_response_id"] == "resp_test"
    assert requests[1]["input"][0]["call_id"] == "call_1"
    assert requests[1]["instructions"] == requests[0]["instructions"]


async def test_real_wrapper_drives_agent_loop_over_mock_http(responses_transport):
    def tool_response(name, call_id, arguments):
        response = _response()
        response["id"] = f"resp_{call_id}"
        response["output"] = [{
            "type": "function_call", "id": f"fc_{call_id}", "call_id": call_id,
            "name": name, "arguments": json.dumps(arguments), "status": "completed",
        }]
        return response

    responses = [
        tool_response("search_budgets", "search", {"query": "api", "filters": None}),
        tool_response("calculate_estimate", "calculate", {"components": [
            {"name": "API", "reference_amounts": [100]},
        ]}),
        tool_response("validate_estimate", "validate", {"components": [
            {"name": "API", "reference_amounts": [100], "estimated_hours": 115},
        ], "total_hours": 115}),
        _response(estimate={
            "explanation": "Based on the historical reference.",
            "assumptions": [],
            "confidence": "medium",
        }),
    ]
    requests, _ = responses_transport(responses)

    async def backend(args):
        return [{"id": 1, "estimated_hours": 100}]

    result = await run_agent("meeting", wrapper=_wrapper(), retrieval_backend=backend)
    assert result.status == "completed", result.error
    assert result.estimate["total_hours"] == 115
    assert [request.get("previous_response_id") for request in requests[1:]] == [
        "resp_search", "resp_calculate", "resp_validate",
    ]
    assert [request["input"][0]["call_id"] for request in requests[1:]] == [
        "search", "calculate", "validate",
    ]


@pytest.mark.parametrize("supported", [True, False])
def test_responses_retries_business_validation_without_fabricating_data(
    responses_transport, supported,
):
    invalid = _estimate().model_dump()
    task = invalid["modules"][0]["tasks"][0]
    task["grounded"] = supported
    task["sources"] = []
    # True without sources, or False with numeric effort, must both be rejected.
    requests, _ = responses_transport([_response(estimate=invalid), _response()])
    with capture_logs() as logs:
        estimate, _ = _call(_wrapper(), max_attempts=3)

    assert estimate == _estimate()
    assert len(requests) == 2
    assert requests[0]["input"] == requests[1]["input"]
    assert "Correct the previous response's validation errors" in requests[1]["instructions"]
    assert "JWT authentication" not in requests[1]["instructions"]
    validation_log = next(
        entry for entry in logs if entry["event"] == "llm_responses_validation_failed"
    )
    assert (validation_log["tokens_in"], validation_log["tokens_out"]) == (100, 50)
    assert logs[-1]["attempts"] == 2


def test_responses_validation_retries_are_bounded(responses_transport):
    invalid = _estimate().model_dump()
    invalid["modules"][0]["tasks"][0]["sources"] = []
    requests, _ = responses_transport([_response(estimate=invalid)])
    with capture_logs() as logs, pytest.raises(ValidationError):
        _call(_wrapper(), max_attempts=3)

    assert len(requests) == 3
    assert logs[-1]["event"] == "llm_responses_call_failed"


@pytest.mark.parametrize("status", ["completed", "incomplete"])
def test_invalid_json_retries_only_for_completed_responses(responses_transport, status):
    payload = _response(status=status)
    payload["output"][0]["content"][0]["text"] = '{"modules":'
    requests, _ = responses_transport([payload, _response()])
    with capture_logs():
        if status == "incomplete":
            with pytest.raises(ValueError, match="output is incomplete"):
                _call(_wrapper())
            assert len(requests) == 1
        else:
            estimate, _ = _call(_wrapper())
            assert estimate == _estimate()
            assert len(requests) == 2


def test_responses_returns_unsupported_scope_without_invented_effort(responses_transport):
    expected = _estimate()
    expected.modules[0].tasks = [
        TaskItem(name="Unsupported scope", grounded=False, engineer_days=None, sources=[]),
    ]
    expected.total_engineer_days = None
    responses_transport([_response(estimate=expected.model_dump())])
    result, _ = _call(_wrapper())
    assert result.modules[0].tasks[0].engineer_days is None
    assert result.modules[0].tasks[0].sources == []


def test_responses_provider_error_is_logged_and_propagated(responses_transport):
    requests, _ = responses_transport(
        [{"error": {
            "message": "Incorrect API key provided: test-key.",
            "type": "invalid_request_error", "code": "invalid_api_key",
        }}],
        status_code=401,
    )
    with capture_logs() as logs, pytest.raises(litellm.AuthenticationError):
        _call(_wrapper())
    assert len(requests) == 1
    assert logs[-1]["event"] == "llm_responses_call_failed"


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("incomplete", "output is incomplete"),
        ("refusal", "output was refused"),
        ("empty", "no text to parse"),
        ("usage", "no usage metadata"),
    ],
)
def test_responses_failure_is_not_a_valid_empty_estimate(
    responses_transport, failure, message,
):
    payload = _response(status="incomplete" if failure == "incomplete" else "completed")
    if failure == "refusal":
        payload["output"][0]["content"] = [{"type": "refusal", "refusal": "Request refused."}]
    elif failure == "empty":
        payload["output"] = []
    elif failure == "usage":
        payload["usage"] = None
    requests, _ = responses_transport([payload])
    with capture_logs() as logs, pytest.raises(ValueError, match=message):
        _call(_wrapper())

    assert len(requests) == 1
    assert logs[-1]["event"] == "llm_responses_call_failed"


@pytest.mark.parametrize(
    ("model", "key", "message"),
    [
        ("claude-sonnet-4-5", "test-key", "require an OpenAI model"),
        ("gpt-5", None, "require OPENAI_API_KEY"),
    ],
)
def test_responses_does_not_fall_back_to_another_provider(
    responses_transport, model, key, message,
):
    requests, calls = responses_transport([_response()])
    with capture_logs(), pytest.raises(ValueError, match=message):
        _call(_wrapper(model=model, key=key))
    assert requests == [] and calls == []


def test_existing_structured_methods_still_use_instructor(monkeypatch):
    calls: list[dict] = []
    estimate = _estimate()

    def completion(**kwargs):
        calls.append(kwargs)
        return estimate, SimpleNamespace(usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50))

    wrapper = _wrapper()
    monkeypatch.setattr(
        wrapper._instructor.chat.completions, "create_with_completion", completion,
    )
    result, meta = wrapper.complete_structured(
        system_prompt="Existing prompt", user_message="Existing input",
        response_model=Estimate, model_override="gpt-4o-mini",
    )
    chat_result, chat_meta = wrapper.complete_structured_chat(
        messages=[{"role": "user", "content": "Existing conversation"}],
        response_model=Estimate, model_override="gpt-4o-mini",
    )

    assert result == chat_result == estimate
    assert len(calls) == 2
    assert all(call["model"] == "gpt-4o-mini" for call in calls)
    assert meta["cost_usd"] == chat_meta["cost_usd"] == 0.000045
