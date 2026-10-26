"""pgvector persistence for the RAG layer.

``models`` defines the ``documents``/``chunks`` tables; ``repository`` is the
async data-access layer. Sessions are owned by the callers (ingest service /
retriever) so a whole ingest fits in one transaction. No vector index yet.
"""

from generation.rag.store.models import ChunkRow, DocumentRow
from generation.rag.store.repository import ChunkStore

__all__ = ["ChunkRow", "ChunkStore", "DocumentRow"]
