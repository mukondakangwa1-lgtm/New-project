"""Background tasks for connector synchronization and KUDOS learning."""

import asyncio
import json
from datetime import datetime, timezone

from app.celery_app import celery
from app.core.database import SessionLocal
from app.models import KudosConnector, KudosDocument, KudosSyncLog, User


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def sync_connector(self, connector_id: int):
    """Synchronize one approved connector in a worker process.

    The HTTP endpoint and Celery task share the connector implementations, but
    the task supplies its own short-lived database session and admin identity.
    """
    db = SessionLocal()
    connector = None
    try:
        connector = db.query(KudosConnector).filter(KudosConnector.id == connector_id).first()
        if connector is None:
            raise ValueError(f"Connector {connector_id} not found")

        admin = db.query(User).filter(User.is_admin.is_(True)).first()
        if admin is None:
            raise ValueError("No admin user is available to approve learned content")

        config = json.loads(connector.config) if connector.config else {}
        from app.api.v1.endpoints import connectors as connector_module

        sync_fn = {
            "github": connector_module._sync_github,
            "gitlab": connector_module._sync_gitlab,
            "website": connector_module._sync_website,
            "api": connector_module._sync_api,
            "rss": connector_module._sync_rss,
            "npm": connector_module._sync_npm,
            "pypi": connector_module._sync_pypi,
        }.get(connector.connector_type)
        if sync_fn is None:
            raise ValueError(f"Unsupported connector type: {connector.connector_type}")

        result = asyncio.run(sync_fn(db, connector, config, admin))
        connector.last_synced_at = datetime.now(timezone.utc)
        connector.items_learned += result["items_new"]
        connector.status = "active"
        connector.error_message = ""
        db.add(KudosSyncLog(
            connector_id=connector.id,
            action="celery-sync",
            items_found=result["items_found"],
            items_new=result["items_new"],
            items_updated=result["items_updated"],
            details=result["details"],
        ))
        db.commit()
        return {"status": "ok", "connector_id": connector_id, **result}
    except Exception as exc:
        db.rollback()
        if connector is not None:
            connector.status = "error"
            connector.error_message = str(exc)[:500]
            db.commit()
        raise
    finally:
        db.close()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def index_document_embeddings(self, document_id: int):
    """Generate and store semantic vectors for one learned document."""
    db = SessionLocal()
    try:
        from app.core.embeddings import get_embeddings_provider
        from app.core.vector_store import ensure_vector_table, upsert_vector

        document = db.query(KudosDocument).filter_by(id=document_id).first()
        if document is None:
            raise ValueError(f"Document {document_id} not found")
        chunks = sorted(document.chunks, key=lambda chunk: chunk.chunk_index or 0)
        if not chunks:
            return {"status": "ok", "document_id": document_id, "vectors": 0}

        ensure_vector_table()
        vectors = get_embeddings_provider().embed_texts([chunk.content for chunk in chunks])
        for chunk, vector in zip(chunks, vectors):
            upsert_vector(
                document_id=document_id,
                chunk_index=chunk.chunk_index or 0,
                vector=vector,
                metadata_obj={"title": document.title, "chunk_id": chunk.id},
            )
        return {"status": "ok", "document_id": document_id, "vectors": len(vectors)}
    finally:
        db.close()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def run_auto_learner(self):
    """Run one complete autonomous learning cycle in a worker process."""
    from app.core.auto_learner import trigger_learning_cycle

    result = trigger_learning_cycle()
    if result.get("error"):
        raise RuntimeError(result["error"])
    return result
