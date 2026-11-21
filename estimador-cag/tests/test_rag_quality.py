import json
from types import SimpleNamespace

import dependencies
from generation.rag.quality import Verdict, VerdictPanel, augment_chunks, gate_estimate
from generation.rag.schemas import Estimate, RetrievedChunk


def _chunk(id=1, content="Component: Login\nEstimated hours: 40"):
    return RetrievedChunk(
        id=id, content=content, sector="finance", project_year=2024,
        chunk_type="budget_component", budget_id="BUD-1", estimated_hours=40,
    )


def _estimate(evidence="Estimated hours: 40", days=5, document="BUD-1"):
    return Estimate(
        confidence="high", reasoning="Estimate",
        modules=[{"name": "Auth", "tasks": [{
            "name": "Login", "grounded": True, "engineer_days": days,
            "sources": [{"chunk_id": "1", "document_id": document, "evidence": evidence}],
        }]}],
    )


def test_augmentation_retains_ids_and_places_relevant_chunks_at_edges():
    chunks = [_chunk(id=i, content=f"Filler\nComponent {i}: 40 hours") for i in range(1, 5)]
    result = augment_chunks(chunks)
    assert [chunk.id for chunk in result] == [1, 3, 4, 2]
    assert all("Filler" not in chunk.content for chunk in result)


def test_augmentation_preserves_scope_even_without_digits():
    chunk = _chunk(content=(
        "Project introduction\nModule: Authentication\nComponent: Login\n"
        "Description: OAuth sign-in\nTech stack: Python\nEstimated hours: 40"
    ))
    content = augment_chunks([chunk])[0].content
    assert "Component: Login" in content
    assert "Description: OAuth sign-in" in content
    assert "Module: Authentication" in content
    assert "Tech stack: Python" in content
    assert "Estimated hours: 40" in content
    assert "Project introduction" not in content


async def test_semantic_check_uses_actual_source_and_flags_mismatches(monkeypatch):
    seen = []

    def judge(**kwargs):
        seen.append(json.loads(kwargs["user_message"]))
        return VerdictPanel(verdicts=[
            Verdict(module="Auth", component="Login", entailed=False, reason="different scope")
        ]), {}

    monkeypatch.setattr(dependencies, "get_llm_wrapper", lambda: SimpleNamespace(complete_structured=judge))
    report = await gate_estimate(_estimate(), [_chunk()], tolerance=0.5, model="test")
    assert report.lines[0].status == "degraded"
    assert report.lines[0].reason == "different scope"
    assert seen[0][0]["sources"] == [_chunk().content]
    report = await gate_estimate(_estimate(evidence="invented"), [_chunk()], tolerance=0.5, model="test")
    assert report.lines[0].status == "degraded"
    assert len(seen) == 1
    report = await gate_estimate(_estimate(days=20), [_chunk()], tolerance=0.5, model="test")
    assert report.lines[0].status == "degraded"
    assert len(seen) == 1


async def test_judge_failure_and_missing_verdict_are_not_success(monkeypatch):
    def fail(**_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(dependencies, "get_llm_wrapper", lambda: SimpleNamespace(complete_structured=fail))
    report = await gate_estimate(_estimate(), [_chunk()], tolerance=0.5, model="test")
    assert report.lines[0].status == "unverified"
    assert report.judge_error
    monkeypatch.setattr(
        dependencies, "get_llm_wrapper",
        lambda: SimpleNamespace(complete_structured=lambda **_: (VerdictPanel(), {})),
    )
    report = await gate_estimate(_estimate(), [_chunk()], tolerance=0.5, model="test")
    assert report.lines[0].status == "unverified"
