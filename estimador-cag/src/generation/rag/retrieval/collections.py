"""Metadata-backed collections sharing the student's single ``chunks`` table."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from sqlalchemy import or_

from generation.rag.schemas import RetrievedChunk
from generation.rag.store.models import ChunkRow


class Collection(StrEnum):
    BUDGET = "budget"
    TRANSCRIPT = "transcript"
    TECHNICAL_DOC = "technical_doc"


@dataclass(frozen=True)
class HardFilters:
    technologies: tuple[str, ...] = ()
    sectors: tuple[str, ...] = ()
    min_date: date | None = None
    version: str | None = None


@dataclass(frozen=True)
class CollectionSpec:
    collection: Collection
    document_types: tuple[str, ...]
    chunk_types: tuple[str, ...]
    source_id_key: str
    date_key: str | None = None
    date_kind: str | None = None

    def date_of(self, metadata: dict) -> date | None:
        raw = (metadata or {}).get(self.date_key) if self.date_key else None
        if raw in (None, ""):
            return None
        try:
            if self.date_kind == "year":
                return date(int(raw), 1, 1)
            if self.date_kind == "iso":
                return date.fromisoformat(str(raw))
        except (TypeError, ValueError):
            return None
        return None

    def to_chunk(self, row, *, distance: float | None) -> RetrievedChunk:
        metadata = row.metadata_ or {}
        year = metadata.get("year", 0)
        try:
            project_year = int(year or 0)
        except (TypeError, ValueError):
            project_year = 0
        return RetrievedChunk(
            id=row.id,
            content=row.content,
            sector=str(metadata.get("client_sector", "unknown")),
            project_year=project_year,
            chunk_type=row.chunk_type,
            distance=distance,
            has_vector_distance=distance is not None,
            budget_id=metadata.get("budget_id"),
            estimated_hours=metadata.get("estimated_hours"),
            collection=self.collection.value,
            source_id=metadata.get(self.source_id_key),
            document_date=self.date_of(metadata),
        )

    def hard_filter_clauses(self, filters: HardFilters) -> list:
        metadata = ChunkRow.metadata_
        clauses = []
        if self.collection is Collection.BUDGET:
            if filters.sectors:
                clauses.append(metadata["client_sector"].astext.in_(filters.sectors))
            if filters.technologies:
                clauses.append(
                    or_(
                        metadata["main_technology"].astext.in_(filters.technologies),
                        *(
                            metadata["tech_stack"].contains([technology])
                            for technology in filters.technologies
                        ),
                    )
                )
            if filters.min_date is not None:
                year = metadata["year"].astext
                clauses.append(year.op("~")(r"^\d{4}$"))
                clauses.append(year >= str(filters.min_date.year))
        elif self.collection is Collection.TRANSCRIPT and filters.min_date is not None:
            meeting_date = metadata["meeting_date"].astext
            clauses.extend(
                [
                    meeting_date.op("~")(r"^\d{4}-\d{2}-\d{2}$"),
                    meeting_date >= filters.min_date.isoformat(),
                ]
            )
        elif self.collection is Collection.TECHNICAL_DOC and filters.version is not None:
            clauses.append(metadata["version"].astext == filters.version)
        return clauses


COLLECTIONS: dict[Collection, CollectionSpec] = {
    Collection.BUDGET: CollectionSpec(
        collection=Collection.BUDGET,
        document_types=("historical_budget", "historical_task_breakdown"),
        chunk_types=("budget_component", "historical_task"),
        source_id_key="budget_id",
        date_key="year",
        date_kind="year",
    ),
    Collection.TRANSCRIPT: CollectionSpec(
        collection=Collection.TRANSCRIPT,
        document_types=("meeting_transcript",),
        chunk_types=("meeting_segment",),
        source_id_key="transcript_id",
        date_key="meeting_date",
        date_kind="iso",
    ),
    Collection.TECHNICAL_DOC: CollectionSpec(
        collection=Collection.TECHNICAL_DOC,
        document_types=("technical_doc",),
        chunk_types=("doc_section",),
        source_id_key="doc_id",
    ),
}

ALL_COLLECTIONS = tuple(COLLECTIONS)

_RULES: dict[Collection, tuple[str, ...]] = {
    Collection.BUDGET: (
        r"\bpresupuest\w*",
        r"\bcotizaci\w*",
        r"\bhoras?\b",
        r"\bestimaci\w*",
        r"\bcost\w*|\bprecio\w*",
        r"\bbudget\w*|\bquote\w*",
    ),
    Collection.TRANSCRIPT: (
        r"\btranscripci\w*",
        r"\breuni[oó]n(?:es)?\b",
        r"\bllamad\w*",
        r"\bdiscut\w*",
        r"\b(?:el )?cliente (?:dijo|pregunt[oó]|pidi[oó])\b",
        r"\bmeeting\w*|\btranscript\w*",
    ),
    Collection.TECHNICAL_DOC: (
        r"\bdocumentaci[oó]n\b",
        r"\bespecificaci[oó]n\w*",
        r"\bmanual\w*|\brunbook\b",
        r"\bAPI\b",
        r"\barchitecture\b|\barquitectura\b",
        r"\b(?:c[oó]mo|how) (?:implementar|configurar|integrar|implement|configure)\b",
    ),
}


def spec_for(collection: Collection) -> CollectionSpec:
    return COLLECTIONS[collection]


def match_rules(query_text: str) -> list[Collection]:
    text = query_text.lower()
    return [
        collection
        for collection, patterns in _RULES.items()
        if any(re.search(pattern, text) for pattern in patterns)
    ]
