"""HTTP layer for the runtime model configuration (Ajustes tab).

Thin router: validation of the partial update is the only logic here — the
override store lives in ``services/runtime_config.py``. Changing a model
takes effect on the NEXT LLM call (wrapper/service read the store per call);
nothing is rebuilt and no restart is needed.
"""

from __future__ import annotations

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config import Settings, get_settings
from dependencies import get_runtime_config, get_runtime_retrieval_config
from routers.security import require_estimate_key
from services.llm_wrapper import MODEL_COSTS, _catalog_model_name, _provider_from_model
from services.runtime_config import (
    MODEL_KEYS,
    RuntimeConfigUnavailable,
    RuntimeModelConfig,
    RuntimeRetrievalConfig,
)

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/config", tags=["config"])

EMBEDDING_MODEL_NOTE = "Read-only: changing it would invalidate all stored vectors."

PROVIDER_KEY_FIELDS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


class ModelUpdateRequest(BaseModel):
    """Partial update: only the keys present are touched; ``null`` resets."""

    models: dict[str, str | None] = Field(min_length=1)


class RetrievalUpdateRequest(BaseModel):
    """Partial retrieval update: omitted keys stay unchanged; null resets."""

    search_mode: Literal["vector", "hybrid"] | None = None
    rerank: bool | None = None
    routing_enabled: bool | None = None
    query_transform_enabled: bool | None = None
    temporal_decay_enabled: bool | None = None
    hallucination_gate_enabled: bool | None = None
    augmentation_enabled: bool | None = None
    synthesis_enabled: bool | None = None
    task_hours_top_k: int | None = Field(default=None, ge=1, le=30)
    task_hours_distance_threshold: float | None = Field(default=None, ge=0, le=2)


def _available_models(settings: Settings) -> list[str]:
    """``MODEL_COSTS`` keys, filtered by the API keys actually configured."""
    available = []
    for model in MODEL_COSTS:
        key_field = PROVIDER_KEY_FIELDS.get(_provider_from_model(model))
        if key_field and getattr(settings, key_field):
            available.append(model)
    return available


def _config_payload(runtime_config: RuntimeModelConfig, settings: Settings) -> dict:
    return {
        "models": runtime_config.snapshot(),
        "available_models": _available_models(settings),
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_model_note": EMBEDDING_MODEL_NOTE,
    }


@router.get("/models")
def get_models(
    runtime_config: RuntimeModelConfig = Depends(get_runtime_config),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Current model configuration: effective/default/overridden per knob."""
    return _config_payload(runtime_config, settings)


@router.put("/models")
def update_models(
    request: ModelUpdateRequest,
    runtime_config: RuntimeModelConfig = Depends(get_runtime_config),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Apply a partial override update. All-or-nothing: every key/value in the
    payload is validated BEFORE anything is written."""
    available = _available_models(settings)

    # Validate everything first — a bad entry must not half-apply the batch.
    for key, value in request.models.items():
        if key not in MODEL_KEYS:
            raise HTTPException(status_code=422, detail=f"Unknown model key: {key}")
        if value is None:
            continue  # reset is always valid
        if _catalog_model_name(value) not in MODEL_COSTS:
            raise HTTPException(status_code=422, detail=f"Model '{value}' is not in the catalog")
        if value not in available:
            key_field = PROVIDER_KEY_FIELDS.get(_provider_from_model(value), "API key")
            raise HTTPException(
                status_code=400,
                detail=f"Model '{value}' requires {key_field}, which is not configured",
            )

    try:
        for key, value in request.models.items():
            old_effective = runtime_config.effective(key)
            runtime_config.set(key, value)
            log.info(
                "runtime_config_changed",
                key=key,
                old_effective=old_effective,
                new_value=value,
                reset=value is None,
            )
    except RuntimeConfigUnavailable as exc:
        log.error("runtime_config_write_failed", error=str(exc)[:200])
        raise HTTPException(status_code=503, detail="Runtime config store unavailable") from exc

    return _config_payload(runtime_config, settings)


def _retrieval_payload(
    runtime_config: RuntimeRetrievalConfig, settings: Settings
) -> dict:
    return {
        "retrieval": runtime_config.snapshot(),
        "reranker_model": settings.RERANKER_MODEL,
    }


@router.get("/retrieval", dependencies=[Depends(require_estimate_key)])
def get_retrieval_config(
    runtime_config: Annotated[RuntimeRetrievalConfig, Depends(get_runtime_retrieval_config)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Current retrieval defaults and Redis overrides."""
    return _retrieval_payload(runtime_config, settings)


@router.put("/retrieval", dependencies=[Depends(require_estimate_key)])
def update_retrieval_config(
    request: RetrievalUpdateRequest,
    runtime_config: Annotated[RuntimeRetrievalConfig, Depends(get_runtime_retrieval_config)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Apply a validated partial override update; null restores the .env value."""
    setters = {
        "search_mode": runtime_config.set_search_mode,
        "rerank": runtime_config.set_rerank,
        "routing_enabled": runtime_config.set_routing,
        "query_transform_enabled": runtime_config.set_query_transform,
        "temporal_decay_enabled": runtime_config.set_temporal_decay,
        "hallucination_gate_enabled": runtime_config.set_hallucination_gate,
        "augmentation_enabled": runtime_config.set_augmentation,
        "synthesis_enabled": runtime_config.set_synthesis,
        "task_hours_top_k": runtime_config.set_task_hours_top_k,
        "task_hours_distance_threshold": runtime_config.set_task_hours_distance_threshold,
    }
    try:
        for field in request.model_fields_set:
            value = getattr(request, field)
            setters[field](value)
            log.info(
                "runtime_retrieval_config_changed",
                key=field,
                value=value,
                reset=value is None,
            )
    except RuntimeConfigUnavailable as exc:
        log.error("runtime_retrieval_config_write_failed", error=str(exc)[:200])
        raise HTTPException(status_code=503, detail="Runtime config store unavailable") from exc

    return _retrieval_payload(runtime_config, settings)
