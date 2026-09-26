import time
from collections.abc import Generator
from dataclasses import dataclass

import structlog

from config import Settings, get_settings
from context.examples import format_examples_for_prompt, select_examples
from dependencies import get_llm_wrapper
from schemas.estimation import (
    EstimationRequest,
    EstimationResponse,
    ExampleFormat,
    PreprocessingMode,
)
from services.evaluation import evaluate_estimation_structure

log = structlog.get_logger()


DEFAULT_MAX_TOKENS = 4000
EXTRACTION_MAX_TOKENS = 1500


class LLMServiceError(Exception):
    """Raised when the LLM provider call fails."""

# ---------------------------------------------------------------------------
# Prompt building blocks
#
# The two ACTIVE_OUTPUT_PROMPT variants live side by side so the instructor
# can switch between them in the live session (Block 3.4) by editing the
# ACTIVE_OUTPUT_PROMPT assignment below. Uvicorn `--reload` picks up the
# change automatically.
# ---------------------------------------------------------------------------

PROMPT_OUTPUT_BASIC = "Generate an estimation for the project described above."

PROMPT_OUTPUT_STRUCTURED = """\
Generate the estimation with this exact structure:

## Project summary
[2-3 sentences describing the project scope and goals]

## Task breakdown
| Task | Hours | Cost (EUR) |
[one row per task; cost = hours * 62.50 EUR for developer tasks]

## Totals
- Total hours: [number]
- Total cost: [number] EUR
- Recommended team: [composition]
- Estimated duration: [weeks]

## Risks and assumptions
- [3-5 bullet points covering technical risks, scope assumptions, and external dependencies]
"""

# >>> Block 3.4 live switch: change the right-hand side to PROMPT_OUTPUT_STRUCTURED
ACTIVE_OUTPUT_PROMPT = PROMPT_OUTPUT_STRUCTURED #PROMPT_OUTPUT_BASIC


INLINE_CLEANING_BLOCK = """\
The transcription you receive is from a real meeting and may contain:
- Informal small talk you must ignore
- Implicit requirements you must surface explicitly
- Contradictions where you must trust the most recent statement
- Non-technical jargon you must interpret

Extract ONLY the functional and technical requirements relevant to the estimation."""


EXTRACTION_SYSTEM_PROMPT = (
    "You are an analyst. Read the meeting transcription and produce a clean, "
    "deduplicated bullet list of functional requirements, non-functional "
    "requirements, integrations, constraints and explicit deadlines. Ignore "
    "fillers, divagations and off-topic remarks. Output Markdown only."
)


@dataclass
class GenerationOptions:
    """Per-request knobs that drive prompt construction and the LLM call."""

    preprocessing: PreprocessingMode = "none"
    example_format: ExampleFormat = "markdown"
    num_examples: int = 3
    use_examples: bool = True
    model: str | None = None
    max_tokens: int = DEFAULT_MAX_TOKENS
    thinking_budget: int | None = None


def options_from_request(request: EstimationRequest) -> GenerationOptions:
    """Map the public request DTO to the internal generation knobs."""
    return GenerationOptions(
        preprocessing=request.preprocessing,
        example_format=request.example_format,
        num_examples=request.num_examples,
        use_examples=request.use_examples,
        model=request.model,
        max_tokens=request.max_tokens,
        thinking_budget=request.thinking_budget,
    )


def build_estimation_response(request: EstimationRequest, result: dict) -> EstimationResponse:
    """Wrap a generate_estimation result dict as the public response DTO."""
    validation = (
        evaluate_estimation_structure(result["estimation"], result["finish_reason"])
        if request.evaluate
        else None
    )
    return EstimationResponse(**result, validation=validation)


def estimate(request: EstimationRequest) -> EstimationResponse:
    """Non-streaming estimation used by the FastAPI adapter."""
    result = generate_estimation(request.transcription, options_from_request(request))
    return build_estimation_response(request, result)


@dataclass
class CagContext:
    """Static CAG pieces derived from generation options (no LLM call)."""

    system_prompt: str
    examples_text: str


def build_cag_context(opts: GenerationOptions | None = None) -> CagContext:
    """Assemble the system prompt and the injected examples from the same options."""
    opts = opts or GenerationOptions()

    examples_text = ""
    if opts.use_examples and opts.num_examples > 0:
        examples_text = format_examples_for_prompt(
            select_examples(opts.num_examples),
            opts.example_format,
        )

    examples_block = ""
    if examples_text:
        examples_block = (
            "Below are reference estimations from previous projects. Use them as a guide "
            "for structure, level of detail, and realistic pricing. Adapt the content to "
            "match the specific project described in the transcription.\n\n"
            + examples_text
        )

    cleaning_block = INLINE_CLEANING_BLOCK if opts.preprocessing == "inline_cleaning" else ""
    role = (
        "You are a senior software consultant with 15+ years of experience in project "
        "estimation. Your task is to produce a detailed software project estimation based "
        "on a meeting transcription provided by the user."
    )
    rates = (
        "Use a developer rate of approximately 62.50 EUR/hour (500 EUR/day) and a designer "
        "rate of approximately 50 EUR/hour (400 EUR/day). Provide realistic, well-justified "
        "numbers."
    )
    system_prompt = "\n\n".join(
        s for s in (role, cleaning_block, rates, ACTIVE_OUTPUT_PROMPT, examples_block) if s
    )
    return CagContext(system_prompt=system_prompt, examples_text=examples_text)


def build_system_prompt(
    example_format: ExampleFormat = "markdown",
    num_examples: int = 3,
    use_examples: bool = True,
    inline_cleaning: bool = False,
) -> str:
    """Assemble the system prompt with role, rates, output spec and (optionally) examples."""
    return build_cag_context(
        GenerationOptions(
            preprocessing="inline_cleaning" if inline_cleaning else "none",
            example_format=example_format,
            num_examples=num_examples,
            use_examples=use_examples,
        )
    ).system_prompt


def _invoke_llm(
    *,
    system_prompt: str,
    user_message: str,
    model_override: str | None,
    max_tokens: int,
    thinking_budget: int | None,
) -> dict:
    """Single seam through which every blocking LLM call passes."""
    wrapper = get_llm_wrapper()
    return wrapper.complete(
        system_prompt=system_prompt,
        user_message=user_message,
        model_override=model_override,
        max_tokens=max_tokens,
        thinking_budget=thinking_budget,
    )


def extract_requirements(
    transcription: str,
    opts: GenerationOptions,
) -> tuple[str, dict, float]:
    """Run the cheap phase-1 LLM call that turns a raw transcription into clean requirements.

    Returns ``(requirements_text, usage_dict, cost_usd)``.
    """
    log.info("extracting_requirements", model_override=opts.model)

    result = _invoke_llm(
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_message=transcription,
        model_override=opts.model,
        max_tokens=EXTRACTION_MAX_TOKENS,
        thinking_budget=None,
    )

    return (
        result["estimation"],
        {
            "input": result["usage"]["input_tokens"],
            "output": result["usage"]["output_tokens"],
        },
        float(result.get("cost_usd", 0.0)),
    )


@dataclass
class _PreparedGeneration:
    settings: Settings
    t0: float
    prep_usage: dict
    prep_cost: float
    extracted_requirements: str | None
    user_input: str
    system_prompt: str
    model: str
    opts: GenerationOptions


def _prepare_generation(transcription: str, opts: GenerationOptions) -> _PreparedGeneration:
    """Shared prompt/preprocessing setup for blocking and streaming generation."""
    settings = get_settings()
    t0 = time.perf_counter()

    prep_usage = {"input": 0, "output": 0}
    prep_cost = 0.0
    extracted_requirements: str | None = None
    user_input = transcription

    if opts.preprocessing == "two_phase":
        extracted_requirements, prep_usage, prep_cost = extract_requirements(transcription, opts)
        user_input = extracted_requirements

    system_prompt = build_cag_context(opts).system_prompt

    model = opts.model or settings.LLM_MODEL

    log.info(
        "generating_estimation",
        provider=settings.LLM_PROVIDER,
        model=model,
        preprocessing=opts.preprocessing,
        example_format=opts.example_format,
        num_examples=opts.num_examples,
        use_examples=opts.use_examples,
        max_tokens=opts.max_tokens,
        thinking_budget=opts.thinking_budget,
    )

    return _PreparedGeneration(
        settings=settings,
        t0=t0,
        prep_usage=prep_usage,
        prep_cost=prep_cost,
        extracted_requirements=extracted_requirements,
        user_input=user_input,
        system_prompt=system_prompt,
        model=model,
        opts=opts,
    )


def _finalize_result(result: dict, prepared: _PreparedGeneration) -> dict:
    result["usage"]["preprocessing_input_tokens"] = prepared.prep_usage["input"]
    result["usage"]["preprocessing_output_tokens"] = prepared.prep_usage["output"]
    result["preprocessing"] = prepared.opts.preprocessing
    result["extracted_requirements"] = prepared.extracted_requirements
    result["latency_ms"] = int((time.perf_counter() - prepared.t0) * 1000)
    result["cost_usd"] = round(float(result.get("cost_usd", 0.0)) + prepared.prep_cost, 6)
    return result


def generate_estimation(
    transcription: str,
    opts: GenerationOptions | None = None,
) -> dict:
    """Generate a software estimation from a meeting transcription using the configured LLM."""
    opts = opts or GenerationOptions()
    prepared = _prepare_generation(transcription, opts)

    try:
        result = _invoke_llm(
            system_prompt=prepared.system_prompt,
            user_message=prepared.user_input,
            model_override=opts.model,
            max_tokens=opts.max_tokens,
            thinking_budget=opts.thinking_budget,
        )
    except LLMServiceError:
        raise
    except Exception as exc:
        log.error("llm_call_failed", error=str(exc), provider=prepared.settings.LLM_PROVIDER)
        raise LLMServiceError(f"LLM call failed: {exc}") from exc

    return _finalize_result(result, prepared)


class EstimationTokenStream:
    """Iterable of estimation text deltas. `.result` is set after the iterator is consumed."""

    def __init__(self, transcription: str, opts: GenerationOptions | None = None):
        self._transcription = transcription
        self._opts = opts or GenerationOptions()
        self.result: dict | None = None

    def __iter__(self) -> Generator[str, None, None]:
        prepared = _prepare_generation(self._transcription, self._opts)

        try:
            if prepared.settings.LLM_PROVIDER == "openai":
                if self._opts.thinking_budget is not None:
                    log.warning("thinking_budget_ignored_for_provider", provider="openai")
                result = yield from _stream_openai(
                    messages=[
                        {"role": "system", "content": prepared.system_prompt},
                        {"role": "user", "content": prepared.user_input},
                    ],
                    model=prepared.model,
                    max_tokens=self._opts.max_tokens,
                )
            else:
                result = yield from _stream_anthropic(
                    system=prepared.system_prompt,
                    user_message=prepared.user_input,
                    model=prepared.model,
                    max_tokens=self._opts.max_tokens,
                    thinking_budget=self._opts.thinking_budget,
                )
        except LLMServiceError:
            raise
        except Exception as exc:
            log.error("llm_call_failed", error=str(exc), provider=prepared.settings.LLM_PROVIDER)
            raise LLMServiceError(f"LLM call failed: {exc}") from exc

        self.result = _finalize_result(result, prepared)


def _stream_openai(
    messages: list[dict],
    model: str,
    max_tokens: int,
) -> Generator[str, None, dict]:
    """Stream a chat completion from OpenAI and return the same result dict as `_call_openai`."""
    from openai import OpenAI

    settings = get_settings()
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        stream=True,
        stream_options={"include_usage": True},
    )

    pieces: list[str] = []
    finish_reason = "stop"
    response_model = model
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for chunk in stream:
        if chunk.model:
            response_model = chunk.model
        if chunk.usage is not None:
            usage = {
                "input_tokens": chunk.usage.prompt_tokens or 0,
                "output_tokens": chunk.usage.completion_tokens or 0,
                "total_tokens": chunk.usage.total_tokens or 0,
            }
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        if choice.finish_reason:
            finish_reason = choice.finish_reason
        delta = choice.delta.content
        if delta:
            pieces.append(delta)
            yield delta

    log.info(
        "llm_response_received",
        provider="openai",
        model=response_model,
        finish_reason=finish_reason,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
    )

    return {
        "estimation": "".join(pieces),
        "model": response_model,
        "provider": "openai",
        "finish_reason": finish_reason,
        "usage": usage,
    }


def _stream_anthropic(
    system: str,
    user_message: str,
    model: str,
    max_tokens: int,
    thinking_budget: int | None,
) -> Generator[str, None, dict]:
    """Stream a message from Anthropic and return the same result dict as `_call_anthropic`."""
    from anthropic import Anthropic

    settings = get_settings()
    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    anthropic_model = model.removeprefix("anthropic/")

    kwargs: dict = {
        "model": anthropic_model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_message}],
    }
    if thinking_budget is not None:
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
        kwargs["max_tokens"] = max(max_tokens, thinking_budget + 1024)

    pieces: list[str] = []
    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            if text:
                pieces.append(text)
                yield text
        final = stream.get_final_message()

    finish_reason = final.stop_reason or "stop"
    usage = {
        "input_tokens": final.usage.input_tokens,
        "output_tokens": final.usage.output_tokens,
        "total_tokens": final.usage.input_tokens + final.usage.output_tokens,
    }

    log.info(
        "llm_response_received",
        provider="anthropic",
        model=final.model,
        finish_reason=finish_reason,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
    )

    return {
        "estimation": "".join(pieces),
        "model": final.model,
        "provider": "anthropic",
        "finish_reason": finish_reason,
        "usage": usage,
    }
