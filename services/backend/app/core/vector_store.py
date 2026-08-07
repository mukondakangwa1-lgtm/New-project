"""Optional pgvector-backed semantic storage for KUDOS chunks."""

from __future__ import annotations

import json
import os
from typing import Any, List

from sqlalchemy import Column, Integer, MetaData, Table, Text, select

from app.core.config import settings
from app.core.database import engine

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover - optional dependency import guard
    Vector = None


VEC_DIM = int(os.getenv("EMBED_DIM") or settings.EMBED_DIM)
metadata = MetaData()

kudos_vectors = Table(
    "kudos_vectors",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("document_id", Integer, nullable=False, index=True),
    Column("chunk_index", Integer, nullable=False, index=True),
    Column("vector", Vector(VEC_DIM) if Vector else Text, nullable=False),
    Column("metadata", Text, nullable=True),
)


def _require_pgvector() -> None:
    if Vector is None:
        raise RuntimeError(
            "pgvector is not installed — add pgvector to requirements.txt"
        )


def ensure_vector_table() -> None:
    """Create the optional vector table after the Postgres extension exists."""
    _require_pgvector()
    metadata.create_all(bind=engine, tables=[kudos_vectors])


def upsert_vector(
    document_id: int,
    chunk_index: int,
    vector: List[float],
    metadata_obj: dict | None = None,
) -> None:
    """Insert or replace a vector for one document chunk."""
    _require_pgvector()
    if len(vector) != VEC_DIM:
        raise ValueError(f"Expected an embedding of {VEC_DIM} dimensions")

    with engine.begin() as conn:
        conn.execute(
            kudos_vectors.delete().where(
                (kudos_vectors.c.document_id == document_id)
                & (kudos_vectors.c.chunk_index == chunk_index)
            )
        )
        conn.execute(
            kudos_vectors.insert().values(
                document_id=document_id,
                chunk_index=chunk_index,
                vector=vector,
                metadata=json.dumps(metadata_obj or {}),
            )
        )


def query_vectors(embedding: List[float], top_k: int = 5) -> List[dict[str, Any]]:
    """Return nearest chunks ordered by cosine distance."""
    _require_pgvector()
    if len(embedding) != VEC_DIM:
        raise ValueError(f"Expected an embedding of {VEC_DIM} dimensions")
    if top_k < 1:
        return []

    distance = kudos_vectors.c.vector.cosine_distance(embedding).label("distance")
    statement = (
        select(
            kudos_vectors.c.document_id,
            kudos_vectors.c.chunk_index,
            kudos_vectors.c.metadata,
            distance,
        )
        .order_by(distance)
        .limit(top_k)
    )

    with engine.connect() as conn:
        rows = []
        for row in conn.execute(statement):
            mapping = row._mapping
            try:
                row_metadata = json.loads(mapping["metadata"] or "{}")
            except (TypeError, json.JSONDecodeError):
                row_metadata = {}
            rows.append(
                {
                    "document_id": mapping["document_id"],
                    "chunk_index": mapping["chunk_index"],
                    "metadata": row_metadata,
                    "distance": float(mapping["distance"]),
                }
            )
        return rows
