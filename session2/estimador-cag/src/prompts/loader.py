"""Jinja2 loader for versioned prompt templates.

On-disk layout: ``prompts/<use_case>/<version>/<role>.j2``. Switching version
is a string at the call site, not a refactor.

Nothing in the session 03 HTTP/SSE/chat path calls this yet. The request is
duck-typed until the next cut lands the new schema.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_BASE_DIR = Path(__file__).resolve().parent

_env = Environment(
    loader=FileSystemLoader(_BASE_DIR),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
    keep_trailing_newline=True,
)


class PromptRequest(Protocol):
    """Duck-typed request for `render_estimation_prompt`.

    Expected string values:
    - project_type: mobile_app | web_saas | internal_tool | data_pipeline
    - detail_level: summary | medium | detailed
    - output_format: phases_table | line_items | narrative
    """

    description: str
    project_type: object
    detail_level: object
    output_format: object


def _enum_value(raw: object) -> str:
    value = getattr(raw, "value", raw)
    return str(value)


def render_estimation_prompt(
    request: PromptRequest,
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
