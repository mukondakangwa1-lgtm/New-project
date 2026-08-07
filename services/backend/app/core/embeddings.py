"""Embedding provider used by optional semantic KUDOS retrieval."""

from __future__ import annotations

import os
from typing import List

from app.core.config import settings

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency import guard
    OpenAI = None


class EmbeddingsProvider:
    """Small provider-neutral boundary around the OpenAI embeddings API."""

    def __init__(self, provider: str | None = None):
        self.provider = (
            provider
            or os.getenv("EMBED_PROVIDER")
            or settings.EMBED_PROVIDER
        ).lower()
        if self.provider != "openai":
            raise NotImplementedError(
                f"Embeddings provider '{self.provider}' is not implemented"
            )
        if OpenAI is None:
            raise RuntimeError("The openai package is required for embeddings")

        api_key = os.getenv("OPENAI_API_KEY") or settings.OPENAI_API_KEY
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for semantic embeddings")

        self.model = os.getenv(
            "OPENAI_EMBEDDING_MODEL", settings.OPENAI_EMBEDDING_MODEL
        )
        self.client = OpenAI(api_key=api_key)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Return one embedding vector for each input text."""
        if not texts:
            return []

        response = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


_default: EmbeddingsProvider | None = None


def get_embeddings_provider() -> EmbeddingsProvider:
    """Return a lazily-created process-local embeddings provider."""
    global _default
    if _default is None:
        _default = EmbeddingsProvider()
    return _default
