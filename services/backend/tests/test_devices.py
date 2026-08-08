"""
KUDOS device storage tests: ring placement, replication, pull/ack sync,
retirement re-balance, and per-user isolation.
"""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TestSessionLocal, login, register_user

client = TestClient(app)

EMAIL_A = "device_a@campus.edu"
EMAIL_B = "device_b@campus.edu"


def _uid(email: str) -> int:
    from app.models import User

    db = TestSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        return user.id
    finally:
        db.close()


def _wipe(email: str):
    from app.models import KudosDevice, KudosMemory, KudosMemoryReplica

    db = TestSessionLocal()
    try:
        uid = _uid(email)
        reps = db.query(KudosMemoryReplica).filter(KudosMemoryReplica.user_id == uid).all()
        for r in reps:
            db.delete(r)
        mems = db.query(KudosMemory).filter(KudosMemory.user_id == uid).all()
        for m in mems:
            db.delete(m)
        devs = db.query(KudosDevice).filter(KudosDevice.user_id == uid).all()
        for d in devs:
            db.delete(d)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _setup(email: str):
    try:
        register_user(client, email)
    except AssertionError:
        pass
    return login(client, email)


def _register_device(headers: dict, name: str, platform: str = "android"):
    r = client.post(
        "/api/v1/kudos/devices",
        json={"name": name, "platform": platform, "storage_bytes": 1073741824},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["api_token"], "device token should be issued on registration"
    return data


def test_device_registration_and_fleet_list():
    headers = _setup(EMAIL_A)
    _register_device(headers, "phone")
    _register_device(headers, "laptop", "desktop")
    r = client.get("/api/v1/kudos/devices", headers=headers)
    assert r.status_code == 200
    names = [d["name"] for d in r.json()]
    assert "phone" in names and "laptop" in names
    _wipe(EMAIL_A)


def test_replication_and_pull_ack_cycle():
    headers = _setup(EMAIL_A)
    phone = _register_device(headers, "phone")
    laptop = _register_device(headers, "laptop")

    from app.core.memory_store import write_memory

    db = TestSessionLocal()
    try:
        mem = write_memory(db, _uid(EMAIL_A), "distributed fact cached on devices")
        mem_id = mem.id
    finally:
        db.close()

    from app.models import KudosMemoryReplica

    db = TestSessionLocal()
    try:
        reps = db.query(KudosMemoryReplica).filter(KudosMemoryReplica.memory_id == mem_id).all()
        assert len(reps) == 2, f"expected 2 replicas, got {len(reps)}"
        device_ids = {r.device_id for r in reps}
        assert device_ids == {phone["id"], laptop["id"]}
        roles = {r.role for r in reps}
        assert "primary" in roles and "replica" in roles
    finally:
        db.close()

    # device pulls what it must store
    token = phone["api_token"]
    r = client.get(
        "/api/v1/kudos/sync/manifest", headers={"X-Device-Token": token}
    )
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["content"] == "distributed fact cached on devices"
    assert entries[0]["device_role"] in ("primary", "replica")

    # acknowledge the pull on both devices so replication is fully current
    for token in (phone["api_token"], laptop["api_token"]):
        r = client.post(
            "/api/v1/kudos/sync/ack",
            json={"memory_ids": [entries[0]["memory_id"]]},
            headers={"X-Device-Token": token},
        )
        assert r.status_code == 200
        assert r.json()["acknowledged"] == 1

    # nothing left to pull
    r = client.get(
        "/api/v1/kudos/sync/manifest", headers={"X-Device-Token": token}
    )
    assert r.json()["entries"] == []

    # status shows healthy replication
    r = client.get("/api/v1/kudos/sync/status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_memories"] == 1
    assert body["healthy_replicated"] >= 1
    _wipe(EMAIL_A)


def test_retired_device_loses_replicas_and_memory_survives():
    headers = _setup(EMAIL_A)
    _register_device(headers, "keep")
    phone = _register_device(headers, "phone")

    from app.core.memory_store import write_memory

    db = TestSessionLocal()
    try:
        mem = write_memory(db, _uid(EMAIL_A), content="important cross-device memory")
        mem_id = mem.id
    finally:
        db.close()

    r = client.delete(f"/api/v1/kudos/devices/{phone['id']}", headers=headers)
    assert r.status_code == 200
    assert r.json()["released_memories"] == 1

    from app.models import KudosMemoryReplica

    db = TestSessionLocal()
    try:
        reps = db.query(KudosMemoryReplica).filter(KudosMemoryReplica.memory_id == mem.id).all()
        assert all(r.device_id != phone["id"] for r in reps)
        assert len(reps) == 1
    finally:
        db.close()
    _wipe(EMAIL_A)


def test_local_policy_is_not_replicated():
    headers = _setup(EMAIL_A)
    _register_device(headers, "solo")

    from app.core.memory_store import write_memory

    from app.models import KudosMemoryReplica

    db = TestSessionLocal()
    try:
        mem = write_memory(
            db, _uid(EMAIL_A), content="private note stays in the vault",
            device_policy="local",
        )
        reps = db.query(KudosMemoryReplica).filter(KudosMemoryReplica.memory_id == mem.id).all()
        assert reps == []
    finally:
        db.close()
    _wipe(EMAIL_A)


def test_cross_user_isolation():
    headers_a = _setup(EMAIL_A)
    headers_b = _setup(EMAIL_B)
    _register_device(headers_a, "phone")

    from app.core.memory_store import write_memory

    db = TestSessionLocal()
    try:
        write_memory(db, _uid(EMAIL_A), content="secret memory of user A")
    finally:
        db.close()

    # user B's device must not be able to pull user A's memory
    phone_b = _register_device(headers_b, "phone_b")
    r = client.get("/api/v1/kudos/sync/manifest", headers={"X-Device-Token": phone_b["api_token"]})
    assert r.status_code == 200
    assert r.json()["entries"] == []

    # user B only ever sees their own devices
    assert [d["name"] for d in client.get("/api/v1/kudos/devices", headers=headers_b).json()] == ["phone_b"]

    # memory retrieval is per-user too
    r = client.get("/api/v1/kudos/memory?query=secret", headers=headers_b)
    assert r.json()["memories"] == []
    _wipe(EMAIL_A)
    _wipe(EMAIL_B)


def test_reconcile_after_device_loss():
    headers = _setup(EMAIL_A)
    d1 = _register_device(headers, "d1")
    _register_device(headers, "d2")

    from app.core.memory_store import write_memory

    from app.models import KudosMemoryReplica

    db = TestSessionLocal()
    try:
        mem = write_memory(db, _uid(EMAIL_A), content="memory needing re-balance")
        mem_id = mem.id
    finally:
        db.close()

    # retire d1 → its copy disappears and reconcile re-assigns from the ring
    client.delete(f"/api/v1/kudos/devices/{d1['id']}", headers=headers)
    r = client.post("/api/v1/kudos/sync/reconcile", headers=headers)
    assert r.status_code == 200

    db = TestSessionLocal()
    try:
        reps = db.query(KudosMemoryReplica).filter(KudosMemoryReplica.memory_id == mem.id).all()
        assert len(reps) == 1
        assert all(r.device_id != d1["id"] for r in reps)
    finally:
        db.close()
    _wipe(EMAIL_A)