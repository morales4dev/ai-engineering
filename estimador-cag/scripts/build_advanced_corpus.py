#!/usr/bin/env python3
"""Idempotently ingest the advanced-retrieval demo corpus into the existing tables.

No schema changes are required: document_type and chunk_type keep the three
collections separate while all chunks remain in the existing ``chunks`` table.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT / "src", ROOT):
    if (candidate / "config.py").exists():
        sys.path.insert(0, str(candidate))
        break

from dependencies import (
    get_chunk_store,
    get_embedder,
    get_rag_ingest_service,
    get_token_encoder,
)
from generation.rag.ingest_service import DuplicateDocumentError
from generation.rag.schemas import Budget, Chunk
from persistence.database import get_async_session_factory

BUDGETS_PATH = ROOT / "data" / "budgets_sample.json"
TRANSCRIPTS_PATH = ROOT / "data" / "transcripts_sample.json"
DOCS_PATH = ROOT / "data" / "technical_docs_sample.json"


def _chunks(encoder, *, kind: str, item: dict) -> list[Chunk]:
    if kind == "transcript":
        doc_id = item["transcript_id"]
        header = f"Meeting: {item['project']} ({item['meeting_date']})"
        return [
            _chunk(
                encoder,
                chunk_id=f"{doc_id}::{segment['segment_id']}",
                text=f"{header} — {segment['topic']}\n{segment['text']}",
                metadata={
                    "transcript_id": doc_id,
                    "segment_id": segment["segment_id"],
                    "project": item["project"],
                    "meeting_date": item["meeting_date"],
                    "speakers": segment.get("speakers", []),
                    "topic": segment["topic"],
                },
            )
            for segment in item["segments"]
        ]
    doc_id = item["doc_id"]
    header = f"Technical doc: {item['title']} ({item['version']})"
    return [
        _chunk(
            encoder,
            chunk_id=f"{doc_id}::{section['section_id']}",
            text=f"{header} — {section['heading']}\n{section['text']}",
            metadata={
                "doc_id": doc_id,
                "section_id": section["section_id"],
                "heading": section["heading"],
                "version": item["version"],
                "component": item.get("component", "unknown"),
            },
        )
        for section in item["sections"]
    ]


def _chunk(encoder, *, chunk_id: str, text: str, metadata: dict) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        text=text,
        metadata=metadata,
        token_count=len(encoder.encode(text)),
    )


async def _ingest_documents(items: list[dict], *, kind: str) -> tuple[int, int]:
    embedder = get_embedder()
    if embedder is None:
        raise RuntimeError("Set OPENAI_API_KEY before ingesting the advanced corpus.")
    store = get_chunk_store()
    session_factory = get_async_session_factory()
    encoder = get_token_encoder()
    document_type, chunk_type = (
        ("meeting_transcript", "meeting_segment")
        if kind == "transcript"
        else ("technical_doc", "doc_section")
    )
    created = skipped = 0
    for item in items:
        doc_id = item["transcript_id"] if kind == "transcript" else item["doc_id"]
        source_path = f"data/{kind}s_sample.json::{doc_id}"
        async with session_factory() as session:
            if await store.find_document_id(session, source_path) is not None:
                skipped += 1
                continue

        chunks = _chunks(encoder, kind=kind, item=item)
        embedded = await asyncio.to_thread(embedder.embed_many, chunks)
        async with session_factory() as session, session.begin():
            # Recheck after the embedding request; sequential re-runs stay
            # idempotent even if the row appeared while the API call was running.
            if await store.find_document_id(session, source_path) is not None:
                skipped += 1
                continue
            await store.persist_document_with_chunks(
                session,
                source_path=source_path,
                document_type=document_type,
                doc_metadata={"source_id": doc_id},
                embedded_chunks=embedded,
                chunk_type=chunk_type,
            )
        created += 1
    return created, skipped


async def main() -> int:
    ingest_service = get_rag_ingest_service()
    if ingest_service is None:
        raise RuntimeError("OpenAI embeddings and the database must be configured.")
    store = get_chunk_store()
    session_factory = get_async_session_factory()
    budgets = json.loads(BUDGETS_PATH.read_text(encoding="utf-8"))
    budget_created = budget_skipped = 0
    for payload in budgets:
        budget = Budget.model_validate(payload)
        source_path = f"data/budgets_sample.json::{budget.budget_id}"
        async with session_factory() as session:
            if await store.find_document_id(session, source_path) is not None:
                budget_skipped += 1
                continue
        try:
            await ingest_service.ingest(
                source_path=source_path,
                document_type="historical_budget",
                budget=budget,
            )
            budget_created += 1
        except DuplicateDocumentError:
            budget_skipped += 1

    transcripts = json.loads(TRANSCRIPTS_PATH.read_text(encoding="utf-8"))
    docs = json.loads(DOCS_PATH.read_text(encoding="utf-8"))
    transcript_created, transcript_skipped = await _ingest_documents(
        transcripts, kind="transcript"
    )
    docs_created, docs_skipped = await _ingest_documents(docs, kind="technical_doc")
    print(
        "Advanced corpus: "
        f"budgets {budget_created} created/{budget_skipped} skipped; "
        f"transcripts {transcript_created} created/{transcript_skipped} skipped; "
        f"technical docs {docs_created} created/{docs_skipped} skipped."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
