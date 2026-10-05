"""Jinja2 loader for versioned prompt templates.

On-disk layout: ``prompts/<use_case>/<version>/<role>.j2``. Switching version
is a string at the call site, not a refactor.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from schemas.estimation import EstimationRequest

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
) -> tuple[str, str]:
    """Render `(system, user)` for `prompts/estimation/<version>/`.

    ``description`` overrides ``request.description`` so the session path can
    send transcript + extracted attachments, which exceed the 2000-char form
    cap on ``EstimationRequest.description``.
    """
    known = available_prompt_versions()
    if version not in known:
        raise UnknownPromptVersionError(
            f"Unknown prompt version {version!r}. Available: {', '.join(known)}"
        )
    context = {
        "description": description if description is not None else request.description,
        "project_type": _enum_value(request.project_type),
        "detail_level": _enum_value(request.detail_level),
        "output_format": _enum_value(request.output_format),
    }
    system = _env.get_template(f"estimation/{version}/system.j2").render(**context)
    user = _env.get_template(f"estimation/{version}/user.j2").render(**context)
    return system, user
