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


def render_estimation_prompt(
    request: EstimationRequest,
    version: str = "v1",
) -> tuple[str, str]:
    """Render `(system, user)` for `prompts/estimation/<version>/`."""
    context = {
        "description": request.description,
        "project_type": _enum_value(request.project_type),
        "detail_level": _enum_value(request.detail_level),
        "output_format": _enum_value(request.output_format),
    }
    system = _env.get_template(f"estimation/{version}/system.j2").render(**context)
    user = _env.get_template(f"estimation/{version}/user.j2").render(**context)
    return system, user
