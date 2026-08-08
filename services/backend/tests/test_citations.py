"""
KUDOS source citation tests: [n] marker parsing and ask-flow citations.
"""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TestSessionLocal, login, register_user

client = TestClient(app)

EMAIL = "cite_user@campus.edu"


def _seed_sources():
    """Create an approved document with two chunks in the test DB."""
    from app.models import KudosChunk, KudosDocument

    db = TestSessionLocal()
    try:
        doc = KudosDocument(
            title="Vector DB Guide",
            user_id=1,
            filename="vectors.pdf",
            file_path="/tmp/vectors.pdf",
            status="processed",
            is_approved=True,
            is_active=True,
        )
        db.add(doc)
        db.flush()
        db.add(KudosChunk(document_id=doc.id, chunk_index=0,
                          content="pgvector adds semantic search on top of Postgres."))
        db.add(KudosChunk(document_id=doc.id, chunk_index=1,
                          content="Cosine distance ranks results by meaning similarity."))
        db.commit()
        return doc.id
    finally:
        db.close()


def _setup():
    try:
        register_user(client, EMAIL)
    except AssertionError:
        pass
    return login(client, EMAIL)


def test_extract_citations_mapping():
    from app.core.llm_engine import extract_citations

    sources = [
        {"document_id": 10, "title": "Doc A", "content": "alpha"},
        {"document_id": 11, "title": "Doc B", "content": "beta"},
        {"document_id": 12, "title": "Doc C", "content": "gamma"},
    ]
    text = "Use [2] for details, also [1]. Repeated [2] ignored. [9] out of range."
    cited = extract_citations(text, sources)
    assert [c["citation"] for c in cited] == [2, 1]
    assert cited[0]["document_id"] == 11
    assert cited[0]["preview"] == "beta"
    assert extract_citations("no markers here", sources) == []


def test_ask_flow_returns_cited_sources(monkeypatch):
    from app.core import conversation_engine

    headers = _setup()
    doc_id = _setup_sources()

    async def fake_llm(**kwargs):
        return {"response": (
            "Vector databases index by meaning. [1] "
            "Cosine distance ranks results. [2]"
        )}

    monkeypatch.setattr("app.core.llm_engine.get_llm_response", fake_llm)
    monkeypatch.setattr(
        conversation_engine, "generate_human_response", lambda *a, **k: "fallback"
    )

    headers = _setup()
    r = client.post(
        "/api/v1/kudos/ask",
        json={"question": "what are vector databases"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    answer = r.json()["answer"]
    assert "[1]" in answer and "[2]" in answer
    cited = r.json()["sources"]
    assert cited, "expected cited sources"
    assert [c["citation"] for c in cited] == [1, 2]
    assert cited[0]["document_id"] == doc_id
    assert cited[0]["title"] == "Vector DB Guide"

    cleanup(all_chunks=True)


def _setup_sources():
    from app.models import KudosChunk, KudosDocument

    db = TestSessionLocal()
    try:
        doc = KudosDocument(
            title="Vector DB Guide",
            uploaded_by=_first_user_id(),
            filename="vectors.pdf",
            file_type="pdf",
            is_approved=True,
            is_active=True,
        )
        db.add(doc)
        db.flush()
        db.add(KudosChunk(document_id=doc.id, chunk_index=0,
                          content="Vector databases add semantic search over similarity."))
        db.add(KudosChunk(document_id=doc.id, chunk_index=1,
                          content="Vector databases rank embedding results by cosine distance."))
        db.commit()
        return doc.id
    finally:
        db.close()


def _first_user_id():
    from app.models import User

    db = TestSessionLocal()
    try:
        return db.query(User).first().id
    finally:
        db.close()


def cleanup(all_chunks: bool = False):
    from app.models import KudosChunk, KudosDocument

    db = TestSessionLocal()
    try:
        for doc in db.query(KudosDocument).all():
            for ch in db.query(KudosChunk).filter(KudosChunk.document_id == doc.id).all():
                db.delete(ch)
            db.delete(doc)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def test_fallback_answer_appends_sources(monkeypatch):
    from app.core import conversation_engine

    headers = _setup()
    monkeypatch.setattr("app.core.llm_engine.get_llm_response", lambda *k: None)
    _setup_sources()
    r = client.post(
        "/api/v1/kudos/ask",
        json={"question": "what are vector databases"},
        headers=headers,
    )
    assert r.status_code == 200
    assert "Sources:" in r.json()["answer"]
    assert "Vector DB Guide" in r.json()["answer"]
    cleanup(all_chunks=True)