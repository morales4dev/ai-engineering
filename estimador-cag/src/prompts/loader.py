"""Jinja2 loader for versioned prompt templates.

On-disk layout: ``prompts/<use_case>/<version>/<role>.j2``. Switching version
is a string at the call site, not a refactor.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from schemas.estimation import EstimationRequest, EstimationResult
from sessions import ProjectMetadata

_BASE_DIR = Path(__file__).resolve().parent

_env = Environment(
    loader=FileSystemLoader(_BASE_DIR),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
    keep_trailing_newline=True,
)


def _enum_value(raw: object) -> str:
    value = getattr(raw, "value", raw)
    return str(value)


def available_prompt_versions() -> tuple[str, ...]:
    """Folder names under ``prompts/estimation/``."""
    estimation_dir = _BASE_DIR / "estimation"
    return tuple(sorted(path.name for path in estimation_dir.iterdir() if path.is_dir()))


class UnknownPromptVersionError(ValueError):
    """Raised when ``version`` does not match a template folder."""


def render_estimation_prompt(
    request: EstimationRequest,
    version: str = "v1",
    *,
    description: str | None = None,
    metadata: ProjectMetadata | None = None,
) -> tuple[str, str]:
    """One-shot: render `(system, user)` for `prompts/estimation/<version>/`.

    ``description`` overrides ``request.description`` so a caller can send
    text longer than the 2000-char form cap. ``metadata`` is injected into
    ``<project_metadata>``; the one-shot path leaves it empty.
    """
    known = available_prompt_versions()
    if version not in known:
        raise UnknownPromptVersionError(
            f"Unknown prompt version {version!r}. Available: {', '.join(known)}"
        )
    project_metadata = metadata if metadata is not None else ProjectMetadata()
    context = {
        "description": description if description is not None else request.description,
        "project_type": _enum_value(request.project_type),
        "detail_level": _enum_value(request.detail_level),
        "output_format": _enum_value(request.output_format),
        "metadata": project_metadata,
        "metadata_is_empty": project_metadata.is_empty(),
        "tier": "default",
        "critic_feedback": None,
    }
    system = _env.get_template(f"estimation/{version}/system.j2").render(**context)
    user = _env.get_template(f"estimation/{version}/user.j2").render(**context)
    return system, user


def render_conversational_prompt(
    request: EstimationRequest,
    version: str,
    *,
    description: str,
    metadata: ProjectMetadata,
    tier: object | None = None,
    critic_feedback: object | None = None,
) -> tuple[str, str]:
    """Conversational: render the session-path system/user prompts.

    v3 uses ``<audience>`` (from ``tier``) and optional ``<critic_feedback>``.
    v1/v2 ignore those extras.
    """
    known = available_prompt_versions()
    if version not in known:
        raise UnknownPromptVersionError(
            f"Unknown prompt version {version!r}. Available: {', '.join(known)}"
        )
    context = {
        "description": description,
        "project_type": _enum_value(request.project_type),
        "detail_level": _enum_value(request.detail_level),
        "output_format": _enum_value(request.output_format),
        "metadata": metadata,
        "metadata_is_empty": metadata.is_empty(),
        "tier": _enum_value(tier) if tier is not None else "default",
        "critic_feedback": critic_feedback,
    }
    system = _env.get_template(f"estimation/{version}/system.j2").render(**context)
    user = _env.get_template(f"estimation/{version}/user.j2").render(**context)
    return system, user


def render_metadata_extraction_prompt(
    *,
    transcript: str,
    result: EstimationResult,
    previous: ProjectMetadata,
    version: str = "v1",
) -> tuple[str, str]:
    """Render `(system, user)` for ``prompts/metadata_extraction/<version>/``."""
    context = {
        "transcript": transcript,
        "result": result,
        "phases": result.phases,
        "previous": previous,
        "previous_is_empty": previous.is_empty(),
    }
    system = _env.get_template(f"metadata_extraction/{version}/system.j2").render(**context)
    user = _env.get_template(f"metadata_extraction/{version}/user.j2").render(**context)
    return system, user


def render_conversation_summary_prompt(
    *,
    previous_summary: str | None,
    evicted: list,
    version: str = "v1",
) -> tuple[str, str]:
    """Render the prompts used by the ``CumulativeSummarizer``.

    ``evicted`` is a list of ``Message``-like objects (``role``, ``content``).
    """
    context = {
        "previous_summary": previous_summary or "",
        "evicted": evicted,
    }
    system = _env.get_template(f"conversation_summary/{version}/system.j2").render(**context)
    user = _env.get_template(f"conversation_summary/{version}/user.j2").render(**context)
    return system, user
