from __future__ import annotations

from sqlalchemy.dialects import postgresql

from generation.rag.store.repository import ChunkStore


class Result:
    def scalar_one(self):
        return 2

    def all(self):
        return []


class Session:
    def __init__(self):
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return Result()


async def test_collection_constraints_scope_vector_and_lexical_queries_to_documents():
    session = Session()
    store = ChunkStore()
    await store.search_filtered(
        session,
        query_vector=[0.0] * 1536,
        document_types=["meeting_transcript"],
        chunk_types=["meeting_segment"],
        top_k=10,
    )
    await store.search_lexical(
        session,
        query_text="payment meeting",
        document_types=["meeting_transcript"],
        chunk_types=["meeting_segment"],
    )

    compiled = [statement.compile(dialect=postgresql.dialect()) for statement in session.statements]
    assert all("JOIN documents" in str(statement) for statement in compiled)
    assert all("meeting_transcript" in repr(statement.params) for statement in compiled)
    assert all("meeting_segment" in repr(statement.params) for statement in compiled)
