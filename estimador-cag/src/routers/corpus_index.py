"""Incremental, persisted corpus expansion jobs."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from dependencies import get_rag_ingest_service
from generation.rag.ingest_service import DuplicateDocumentError, RagIngestService
from generation.rag.schemas import Budget
from generation.rag.store.models import ChunkRow, DocumentRow
from persistence.database import get_async_session_factory, get_engine, get_session
from persistence.models import CorpusIndexRunRow
from routers.security import require_estimate_key

log = structlog.get_logger()
router = APIRouter(prefix="/embeddings/index", tags=["corpus-index"],
                   dependencies=[Depends(require_estimate_key)])


class IndexRequest(BaseModel):
    documents: list[Budget] = Field(min_length=1, max_length=100)
    chunk_type: Literal["budget_component", "historical_task"] = "budget_component"


class IndexRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    job_id: uuid.UUID
    chunk_type: str
    status: str
    total: int
    processed: int
    indexed: int
    skipped: int
    chunks_created: int
    error_message: str | None
    before_stats: dict
    after_stats: dict | None
    created_at: datetime
    finished_at: datetime | None


async def corpus_stats() -> dict:
    factory = get_async_session_factory()
    if factory is None:
        raise HTTPException(status_code=503, detail="database is unavailable")
    async with factory() as session:
        rows = (await session.execute(
            select(ChunkRow.chunk_type, func.count(), func.count(func.distinct(ChunkRow.document_id)))
            .group_by(ChunkRow.chunk_type).order_by(ChunkRow.chunk_type)
        )).all()
        indexed = (await session.execute(text(
            "SELECT EXISTS (SELECT 1 FROM pg_index i "
            "JOIN pg_class idx ON idx.oid = i.indexrelid "
            "JOIN pg_class tbl ON tbl.oid = i.indrelid "
            "JOIN pg_namespace n ON n.oid = tbl.relnamespace "
            "WHERE n.nspname = current_schema() AND tbl.relname = 'chunks' "
            "AND idx.relname = 'chunks_embedding_halfvec_idx' "
            "AND i.indisvalid AND i.indisready)"
        ))).scalar_one()
    return {
        "collections": [{"chunk_type": kind, "chunks": chunks, "documents": docs}
                        for kind, chunks, docs in rows],
        "total_chunks": sum(row[1] for row in rows),
        "hnsw_indexed": bool(indexed),
    }


async def document_exists(budget_id: str, chunk_type: str) -> bool:
    factory = get_async_session_factory()
    if factory is None:
        raise RuntimeError("database is unavailable")
    async with factory() as session:
        stmt = (
            select(DocumentRow.id)
            .join(ChunkRow, ChunkRow.document_id == DocumentRow.id)
            .where(DocumentRow.metadata_["budget_id"].as_string() == budget_id)
            .where(ChunkRow.chunk_type == chunk_type)
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None


def _update(job_id: uuid.UUID, **fields) -> None:
    engine = get_engine()
    if engine is None:
        raise RuntimeError("database is unavailable")
    with Session(engine) as session:
        row = session.get(CorpusIndexRunRow, job_id)
        if row is None:
            raise RuntimeError(f"Corpus index run {job_id} not found")
        for key, value in fields.items():
            setattr(row, key, value)
        session.commit()


async def _expand(job_id: uuid.UUID, request: IndexRequest, service: RagIngestService) -> None:
    processed = indexed = skipped = chunks = 0
    try:
        await asyncio.to_thread(_update, job_id, status="running")
        for document in request.documents:
            try:
                if await document_exists(document.budget_id, request.chunk_type):
                    skipped += 1
                else:
                    result = await service.ingest(
                        source_path=f"corpus-expansion::{request.chunk_type}::{document.budget_id}",
                        document_type=("historical_task_breakdown"
                                       if request.chunk_type == "historical_task"
                                       else "historical_budget"),
                        budget=document, chunk_type=request.chunk_type,
                    )
                    indexed += 1
                    chunks += result.chunks_created
            except DuplicateDocumentError:
                skipped += 1
            processed += 1
            await asyncio.to_thread(
                _update, job_id, processed=processed, indexed=indexed,
                skipped=skipped, chunks_created=chunks,
            )
        after = await corpus_stats()
        await asyncio.to_thread(
            _update, job_id, status="completed", after_stats=after,
            finished_at=datetime.now(UTC),
        )
    except Exception as exc:  # noqa: BLE001
        log.error("corpus_index_failed", job_id=str(job_id), error=str(exc)[:400])
        await asyncio.to_thread(
            _update, job_id, status="failed", error_message=str(exc)[:2048],
            finished_at=datetime.now(UTC),
        )


@router.get("/stats")
async def stats() -> dict:
    return await corpus_stats()


@router.get("/runs", response_model=list[IndexRun])
def list_runs(session: Annotated[Session, Depends(get_session)]) -> list[CorpusIndexRunRow]:
    return list(session.scalars(
        select(CorpusIndexRunRow).order_by(CorpusIndexRunRow.created_at.desc()).limit(20)
    ))


@router.get("/runs/{job_id}", response_model=IndexRun)
def get_run(job_id: uuid.UUID, session: Annotated[Session, Depends(get_session)]) -> CorpusIndexRunRow:
    row = session.get(CorpusIndexRunRow, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Corpus index run not found")
    return row


@router.post("/runs", response_model=IndexRun, status_code=202)
async def create_run(
    request: IndexRequest,
    background: BackgroundTasks,
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[RagIngestService | None, Depends(get_rag_ingest_service)],
) -> CorpusIndexRunRow:
    if service is None:
        raise HTTPException(status_code=503, detail="Embedding service is unavailable")
    before = await corpus_stats()
    row = CorpusIndexRunRow(
        chunk_type=request.chunk_type, total=len(request.documents), status="pending",
        processed=0, indexed=0, skipped=0, chunks_created=0, before_stats=before,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    background.add_task(_expand, row.job_id, request, service)
    return row
