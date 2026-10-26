"""RAG lab (`generation.rag`).

Turns historical budget JSON into embedding vectors: a structural chunker
(one budget component = one chunk) plus an OpenAI embedder. Ingest persists
those vectors in pgvector; they no longer travel over HTTP.

The package also holds the comparison lab: ``Chunker`` ABC, seven extra
strategies, cosine/percentile helpers, and ``ChunkingComparator``.
``POST /embeddings/ingest`` still uses the structural chunker only.
"""
