from datetime import date
from types import SimpleNamespace

import pytest

from generation.rag.retrieval.collections import Collection, HardFilters, spec_for
from generation.rag.schemas import Budget


def test_collection_chunk_mapping_includes_hours_and_date():
    row = SimpleNamespace(
        id=4,
        content="historical work",
        chunk_type="budget_component",
        metadata_={
            "budget_id": "BUD-4",
            "client_sector": "finance",
            "year": 2024,
            "estimated_hours": 24,
        },
    )
    chunk = spec_for(Collection.BUDGET).to_chunk(row, distance=0.25)
    assert chunk.collection == "budget"
    assert chunk.estimated_hours == 24
    assert chunk.document_date == date(2024, 1, 1)
    assert chunk.has_vector_distance is True


def test_lexical_collection_mapping_does_not_invent_vector_score():
    row = SimpleNamespace(
        id=9,
        content="meeting segment",
        chunk_type="meeting_segment",
        metadata_={"transcript_id": "TR-1", "meeting_date": "2025-01-02"},
    )
    chunk = spec_for(Collection.TRANSCRIPT).to_chunk(row, distance=None)
    assert chunk.distance is None
    assert chunk.has_vector_distance is False
    assert chunk.source_id == "TR-1"
    assert chunk.document_date == date(2025, 1, 2)


def test_registry_hard_filters_are_scoped_by_collection():
    filters = HardFilters(
        technologies=("python",), sectors=("finance",), min_date=date(2023, 1, 1), version="v2"
    )
    assert len(spec_for(Collection.BUDGET).hard_filter_clauses(filters)) == 4
    assert len(spec_for(Collection.TRANSCRIPT).hard_filter_clauses(filters)) == 2
    assert len(spec_for(Collection.TECHNICAL_DOC).hard_filter_clauses(filters)) == 1


@pytest.mark.parametrize(
    "sector",
    ["finance", "ecommerce", "healthcare", "industrial", "logistics", "education", "media", "government"],
)
def test_budget_sector_supports_original_and_expanded_catalog(sector):
    budget = Budget.model_validate(
        {
            "budget_id": "B-1",
            "client_metadata": {"name": "Client", "sector": sector, "country": "ES"},
            "project_summary": "Demo project",
            "main_technology": "python",
            "year": 2024,
            "total_estimated_hours": 1,
            "components": [
                {
                    "component_id": "C-1",
                    "name": "Demo",
                    "description": "Demo task",
                    "estimated_hours": 1,
                    "complexity": "low",
                }
            ],
        }
    )
    assert budget.client_metadata.sector == sector
