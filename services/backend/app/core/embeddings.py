"""
Embeddings adapter — provides a simple interface to generate embeddings.
Supports OpenAI as the primary provider. Reads API key from environment.
"""
from __future__ import annotations

import os
from typing import List

try:
    import openai
except Exception:
    openai = None

from app.core.config import settings


class EmbeddingsProvider:
    def __init__(self, provider: str | None = None):
        self.provider = provider or os.getenv("EMBED_PROVIDER", "openai")
        if self.provider == "openai":
            if not openai:
                raise RuntimeError("openai library not installed — add 'openai' to requirements.txt")
            openai.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
            # model choice can be overridden by env
            self.model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        else:
            raise NotImplementedError(f"Embeddings provider '{self.provider}' is not implemented")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Return embeddings for a list of texts.

        This is synchronous and batches requests where appropriate.
        """
        if self.provider == "openai":
            # OpenAI's Python SDK supports batching
            resp = openai.Embedding.create(model=self.model, input=texts)
            return [r["embedding"] for r in resp["data"]]
        raise NotImplementedError("No embeddings implementation available")


# Convenience singleton
_default = None


def get_embeddings_provider() -> EmbeddingsProvider:
    global _default
    if _default is None:
        _default = EmbeddingsProvider()
    return _default
