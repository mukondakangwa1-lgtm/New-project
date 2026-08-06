"""
Vector store adapter using pgvector (Postgres). This module provides minimal
helpers to create a vector table, upsert vectors, and query nearest neighbors.

This implementation requires the `pgvector` package and a Postgres database with
pgvector extension installed.
"""
from __future__ import annotations

import json
import os
from typing import Any, List

from sqlalchemy import Table, Column, Integer, Text, MetaData
from sqlalchemy import text

from app.core.database import engine

try:
    # pgvector provides a SQLAlchemy Vector type
    from pgvector.sqlalchemy import Vector
except Exception:
    Vector = None


VEC_DIM = int(os.getenv("EMBED_DIM", "1536"))
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


def ensure_vector_table():
    if Vector is None:
        raise RuntimeError("pgvector is not installed — add pgvector to requirements.txt for pgvector support")
    metadata.create_all(bind=engine, tables=[kudos_vectors])


def upsert_vector(document_id: int, chunk_index: int, vector: List[float], metadata_obj: dict | None = None):
    """Insert or replace a single vector row."""
    if Vector is None:
        raise RuntimeError("pgvector not available")

    with engine.begin() as conn:
        # delete any existing for this doc+chunk
        conn.execute(text("DELETE FROM kudos_vectors WHERE document_id = :d AND chunk_index = :c"), {"d": document_id, "c": chunk_index})
        # insert new
        conn.execute(
            text("INSERT INTO kudos_vectors (document_id, chunk_index, vector, metadata) VALUES (:d, :c, :v, :m)"),
            {"d": document_id, "c": chunk_index, "v": vector, "m": json.dumps(metadata_obj or {})},
        )


def query_vectors(embedding: List[float], top_k: int = 5) -> List[dict[str, Any]]:
    """Query nearest vectors using pgvector `<=>` operator.

    Returns list of dicts: {document_id, chunk_index, metadata, distance}.
    """
    if Vector is None:
        raise RuntimeError("pgvector not available")

    # Postgres array parameterization varies; we'll pass as JSON and cast
    sql = text(
        "SELECT document_id, chunk_index, metadata, (vector <=> :q) AS distance "
        "FROM kudos_vectors ORDER BY distance ASC LIMIT :k"
    )
    with engine.connect() as conn:
        result = conn.execute(sql, {"q": embedding, "k": top_k})
        rows = []
        for r in result:
            try:
                meta = json.loads(r["metadata"]) if r["metadata"] else {}
            except Exception:
                meta = {}
            rows.append({"document_id": r["document_id"], "chunk_index": r["chunk_index"], "metadata": meta, "distance": float(r["distance"])})
        return rows
