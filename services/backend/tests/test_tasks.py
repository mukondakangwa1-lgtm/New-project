"""
Digital Campus - Celery Task Tests
Connector sync, embedding indexing, auto-learner. All run eagerly, no broker.
"""
import pytest

from app.models import KudosChunk, KudosConnector, KudosDocument, KudosSyncLog, User
from tests.conftest import TestSessionLocal


@pytest.fixture(autouse=True)
def task_env(monkeypatch):
    """Point task DB sessions at the test database and run tasks eagerly."""
    monkeypatch.setattr("app.tasks.SessionLocal", TestSessionLocal)
    from app.celery_app import celery

    celery.conf.task_always_eager = True


@pytest.fixture
def admin_id():
    """Return the test admin's id (int) to avoid detached-instance access."""
    db = TestSessionLocal()
    try:
        admin = db.query(User).filter(User.email == "task-admin@test.c").first()
        if admin is None:
            admin = User(email="task-admin@test.c", full_name="Task Admin", hashed_password="x")
            db.add(admin)
            db.commit()
            db.refresh(admin)
        admin.is_admin = True
        db.commit()
        db.refresh(admin)
        return admin.id
    finally:
        db.close()


def _add_connector(admin_id, connector_type="rss", config=None):
    import json

    db = TestSessionLocal()
    try:
        conn = KudosConnector(
            created_by=admin_id, name=f"Connector {connector_type}", connector_type=connector_type,
            source_url="https://example.com/feed.rss",
            config=json.dumps(config or {}), status="active", is_approved=True,
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        return conn.id
    finally:
        db.close()


# === sync_connector ===

def test_sync_connector_success(monkeypatch, admin_id):
    from app.api.v1.endpoints import connectors as connector_module

    async def fake_sync_rss(db, conn, config, user):
        return {"items_found": 5, "items_new": 3, "items_updated": 1, "details": "ok"}

    monkeypatch.setattr(connector_module, "_sync_rss", fake_sync_rss)
    cid = _add_connector(admin_id)

    from app.tasks import sync_connector

    result = sync_connector.apply(args=[cid], throw=False)
    assert result.successful(), result.traceback or result.result
    assert result.result["items_new"] == 3

    db = TestSessionLocal()
    try:
        conn = db.query(KudosConnector).get(cid)
        assert conn.status == "active"
        assert conn.items_learned == 3
        assert conn.last_synced_at is not None
        log = db.query(KudosSyncLog).filter_by(connector_id=cid).first()
        assert log is not None and log.items_new == 3
    finally:
        db.close()


def test_sync_connector_records_error(monkeypatch, admin_id):
    from app.api.v1.endpoints import connectors as connector_module

    async def fake_sync_rss(db, conn, config, user):
        raise ValueError("feed exploded")

    monkeypatch.setattr(connector_module, "_sync_rss", fake_sync_rss)
    cid = _add_connector(admin_id)

    from app.tasks import sync_connector

    # No retries needed to exercise the error path
    sync_connector.max_retries = 0
    result = sync_connector.apply(args=[cid], throw=False)
    assert result.failed()

    db = TestSessionLocal()
    try:
        conn = db.query(KudosConnector).get(cid)
        assert conn.status == "error"
        assert "feed exploded" in conn.error_message
    finally:
        db.close()


def test_sync_connector_missing_connector(monkeypatch):
    from app.tasks import sync_connector

    sync_connector.max_retries = 0
    result = sync_connector.apply(args=[999999], throw=False)
    assert result.failed()


# === index_document_embeddings ===

def test_index_document_embeddings(monkeypatch, admin_id):
    upserts = []

    class FakeProvider:
        def embed_texts(self, texts):
            return [[0.1, 0.2], [0.3, 0.4]]  # one vector per chunk

    def fake_ensure():
        pass

    def fake_upsert(document_id, chunk_index, vector, metadata_obj):
        upserts.append((document_id, chunk_index, vector))

    monkeypatch.setattr("app.core.embeddings.get_embeddings_provider", lambda: FakeProvider())
    monkeypatch.setattr("app.core.vector_store.ensure_vector_table", fake_ensure)
    monkeypatch.setattr("app.core.vector_store.upsert_vector", fake_upsert)

    db = TestSessionLocal()
    try:
        doc = KudosDocument(
            uploaded_by=admin_id, title="Embed Me", filename="embed.txt",
            file_type="txt", content="Some content", is_approved=True,
        )
        db.add(doc)
        db.flush()
        db.add(KudosChunk(document_id=doc.id, chunk_index=0, content="chunk one", keywords="one"))
        db.add(KudosChunk(document_id=doc.id, chunk_index=1, content="chunk two", keywords="two"))
        db.commit()
        doc_id = doc.id
    finally:
        db.close()

    from app.tasks import index_document_embeddings

    result = index_document_embeddings.apply(args=[doc_id], throw=False)
    assert result.successful(), result.traceback or result.result
    assert result.result["vectors"] == 2
    assert len(upserts) == 2
    assert upserts[0][0] == doc_id and upserts[0][1] == 0
    assert upserts[1][1] == 1


# === run_auto_learner ===

def test_run_auto_learner_ok(monkeypatch):
    monkeypatch.setattr(
        "app.core.auto_learner.trigger_learning_cycle",
        lambda: {"status": "ok", "items_learned": 3},
    )
    from app.tasks import run_auto_learner

    result = run_auto_learner.apply(throw=False)
    assert result.successful()
    assert result.result["items_learned"] == 3


def test_run_auto_learner_error(monkeypatch):
    monkeypatch.setattr(
        "app.core.auto_learner.trigger_learning_cycle",
        lambda: {"error": "no network"},
    )
    from app.tasks import run_auto_learner

    result = run_auto_learner.apply(throw=False)
    assert result.failed()
