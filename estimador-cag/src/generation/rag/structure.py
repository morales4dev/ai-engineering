"""Generate a reviewable project breakdown without assigning effort."""

import asyncio

from config import get_settings
from dependencies import get_llm_wrapper
from generation.rag.errors import GenerationError
from generation.rag.schemas import EstimationQuery
from generation.rag.wizard import StructureEstimate

_SYSTEM = (
    "You are a senior software delivery architect. Decompose the project brief into "
    "functional modules and concrete engineering tasks with short descriptions. "
    "Use only modules relevant to this project, and identify assumptions beyond "
    "the brief. Do not estimate hours, effort or cost and do not invent sources. "
    "If the brief is too vague, set confidence to insufficient, leave modules "
    "empty and explain what is missing."
)


async def generate_structure(query: EstimationQuery) -> StructureEstimate:
    settings = get_settings()
    try:
        result, _metadata = await asyncio.to_thread(
            get_llm_wrapper().complete_structured,
            system_prompt=_SYSTEM,
            user_message=query.model_dump_json(),
            response_model=StructureEstimate,
            model_override=settings.GENERATION_MODEL,
            reasoning_effort=settings.GENERATION_REASONING_EFFORT,
            max_tokens=settings.GENERATION_MAX_TOKENS,
        )
        return result
    except Exception as exc:
        raise GenerationError("Structure generation failed.") from exc
