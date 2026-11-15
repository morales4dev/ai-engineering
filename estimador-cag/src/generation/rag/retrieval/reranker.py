"""Lazy-loading cross-encoder wrapper for query/document relevance scoring."""

from __future__ import annotations

import threading
import time

import structlog

from config import get_settings

log = structlog.get_logger()


class CrossEncoderReranker:
    """Load one cross-encoder on first use and reorder candidate chunks."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None
        self._load_lock = threading.Lock()

    @classmethod
    def from_settings(cls) -> CrossEncoderReranker:
        return cls(get_settings().RERANKER_MODEL)

    @property
    def model_name(self) -> str:
        return self._model_name

    def load(self) -> None:
        self._ensure_loaded()

    def _ensure_loaded(self):
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is not None:
                return self._model
            from sentence_transformers import CrossEncoder

            started = time.perf_counter()
            self._model = CrossEncoder(self._model_name, device="cpu")
            log.info(
                "reranker_loaded",
                model=self._model_name,
                load_ms=int((time.perf_counter() - started) * 1000),
            )
            return self._model

    def score(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        scores = self._ensure_loaded().predict([(query, document) for document in documents])
        return [float(score) for score in scores]

    def rerank(self, query: str, candidates: list, *, top_n: int) -> list:
        if not candidates:
            return []
        scores = self.score(query, [candidate.content for candidate in candidates])
        ranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
        return [candidate for candidate, _score in ranked[:top_n]]
