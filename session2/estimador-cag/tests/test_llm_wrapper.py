from types import SimpleNamespace
from unittest.mock import patch

from services.llm_wrapper import LLMWrapper


def _fake_completion(model: str, content: str = "the answer", input_tokens: int = 100, output_tokens: int = 50):
    return SimpleNamespace(
        model=model,
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
    )


def _wrapper(primary_model: str = "gpt-4o-mini") -> LLMWrapper:
    return LLMWrapper(
        openai_api_key="fake-openai",
        anthropic_api_key="fake-anthropic",
        primary_model=primary_model,
        fallback_model="claude-haiku-4-5-20251001",
        timeout=30,
        num_retries=2,
    )


def test_complete_uses_router_and_returns_normalised_dict() -> None:
    wrapper = _wrapper()
    fake = _fake_completion(model="gpt-4o-mini", content="hello world")
    with patch.object(wrapper.router, "completion", return_value=fake) as mocked:
        result = wrapper.complete(
            system_prompt="sys",
            user_message="usr",
            model_override=None,
            max_tokens=4000,
            thinking_budget=None,
        )
    assert mocked.call_count == 1
    assert mocked.call_args.kwargs["model"] == "estimator"
    assert result["estimation"] == "hello world"
    assert result["model"] == "gpt-4o-mini"
    assert result["provider"] == "openai"
    assert result["finish_reason"] == "stop"
    assert result["usage"]["input_tokens"] == 100
    assert result["usage"]["output_tokens"] == 50
    assert "cache_hit" not in result
    assert "cost_usd" not in result


def test_router_deployments_use_key_matching_each_model() -> None:
    wrapper = _wrapper()
    primary, fallback = wrapper.router.model_list
    assert primary["litellm_params"]["model"] == "gpt-4o-mini"
    assert primary["litellm_params"]["api_key"] == "fake-openai"
    assert primary["litellm_params"]["timeout"] == 30
    assert fallback["litellm_params"]["model"] == "claude-haiku-4-5-20251001"
    assert fallback["litellm_params"]["api_key"] == "fake-anthropic"


def test_complete_with_model_override_bypasses_router() -> None:
    wrapper = _wrapper()
    fake = _fake_completion(model="claude-haiku-4-5", content="overridden")
    with (
        patch("services.llm_wrapper.litellm.completion", return_value=fake) as direct,
        patch.object(wrapper.router, "completion") as router_call,
    ):
        result = wrapper.complete(
            system_prompt="sys",
            user_message="usr",
            model_override="claude-haiku-4-5",
            max_tokens=4000,
            thinking_budget=None,
        )
    assert direct.call_count == 1
    assert router_call.call_count == 0
    assert direct.call_args.kwargs["model"] == "claude-haiku-4-5"
    assert direct.call_args.kwargs["api_key"] == "fake-anthropic"
    assert direct.call_args.kwargs["timeout"] == 30
    assert direct.call_args.kwargs["num_retries"] == 2
    assert result["provider"] == "anthropic"


def test_complete_forwards_custom_timeout_and_retries_on_override() -> None:
    wrapper = LLMWrapper(
        openai_api_key="fake-openai",
        anthropic_api_key="fake-anthropic",
        primary_model="gpt-4o-mini",
        fallback_model="claude-haiku-4-5-20251001",
        timeout=12,
        num_retries=4,
    )
    fake = _fake_completion(model="gpt-4o-mini", content="ok")
    with patch("services.llm_wrapper.litellm.completion", return_value=fake) as mocked:
        wrapper.complete(system_prompt="sys", user_message="usr", model_override="gpt-4o-mini")
    assert mocked.call_args.kwargs["timeout"] == 12
    assert mocked.call_args.kwargs["num_retries"] == 4


def test_thinking_budget_ignored_for_openai_primary() -> None:
    wrapper = _wrapper()
    fake = _fake_completion(model="gpt-4o-mini", content="ok")
    with patch.object(wrapper.router, "completion", return_value=fake) as mocked:
        wrapper.complete(
            system_prompt="sys",
            user_message="usr",
            model_override=None,
            max_tokens=4000,
            thinking_budget=2048,
        )
    assert "thinking" not in mocked.call_args.kwargs


def test_thinking_budget_pads_max_tokens_when_anthropic_override() -> None:
    wrapper = _wrapper()
    fake = _fake_completion(model="claude-haiku-4-5-20251001", content="ok")
    with patch("services.llm_wrapper.litellm.completion", return_value=fake) as direct:
        wrapper.complete(
            system_prompt="sys",
            user_message="usr",
            model_override="claude-haiku-4-5-20251001",
            max_tokens=1000,
            thinking_budget=4096,
        )
    kwargs = direct.call_args.kwargs
    assert kwargs["thinking"] == {"type": "enabled", "budget_tokens": 4096}
    assert kwargs["max_tokens"] == 4096 + 1024
