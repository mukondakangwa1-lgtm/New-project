"""
Digital Campus - Community API Tests
Social posts, comments, reactions, chat rooms, study groups, forums.
"""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import login, register_user

client = TestClient(app)

ALICE_EMAIL = "comm-alice@test.c"
BOB_EMAIL = "comm-bob@test.c"
PASSWORD = "pass1234"

H_ALICE = {}
H_BOB = {}


def setup_module():
    register_user(client, ALICE_EMAIL, PASSWORD, "Comm Alice")
    register_user(client, BOB_EMAIL, PASSWORD, "Comm Bob")
    H_ALICE.update(login(client, ALICE_EMAIL, PASSWORD))
    H_BOB.update(login(client, BOB_EMAIL, PASSWORD))


# === Social: posts ===

def test_post_lifecycle():
    r = client.post(
        "/api/v1/social/",
        json={"title": "My first post", "description": "hello", "storage_url": "https://drive.example.com/1"},
        headers=H_ALICE,
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    r = client.get("/api/v1/social/feed")
    assert r.status_code == 200 and any(p["id"] == pid for p in r.json())

    r = client.get("/api/v1/social/my", headers=H_ALICE)
    assert r.status_code == 200 and any(p["id"] == pid for p in r.json())

    r = client.get(f"/api/v1/social/{pid}", headers=H_BOB)
    assert r.status_code == 200 and r.json()["id"] == pid

    # Non-owner update is rejected
    r = client.patch(f"/api/v1/social/{pid}", json={"title": "hacked"}, headers=H_BOB)
    assert r.status_code == 404

    r = client.patch(f"/api/v1/social/{pid}", json={"title": "Renamed"}, headers=H_ALICE)
    assert r.status_code == 200 and r.json()["title"] == "Renamed"

    # Preview cache is populated
    r = client.get(f"/api/v1/social/{pid}/preview")
    assert r.status_code == 200 and r.json()["source"] == "cache"
    assert r.json()["preview"]["post_id"] == pid

    r = client.delete(f"/api/v1/social/{pid}", headers=H_ALICE)
    assert r.status_code == 204
    assert client.get(f"/api/v1/social/{pid}", headers=H_ALICE).status_code == 404


# === Social: comments & reactions ===

def test_comments_and_reactions():
    r = client.post(
        "/api/v1/social/",
        json={"title": "Discussion", "storage_url": "https://youtube.example.com/v"},
        headers=H_ALICE,
    )
    pid = r.json()["id"]

    r = client.post(f"/api/v1/social/{pid}/comments", json={"content": "Great post!"}, headers=H_BOB)
    assert r.status_code == 201, r.text

    r = client.get(f"/api/v1/social/{pid}/comments")
    assert r.status_code == 200 and len(r.json()) == 1
    assert r.json()[0]["user"]["email"] == BOB_EMAIL

    r = client.post(f"/api/v1/social/{pid}/react", json={"emoji": "👍"}, headers=H_ALICE)
    assert r.status_code == 201, r.text
    first_id = r.json()["id"]
    # Toggle off returns the same reaction id — the reaction was removed, not recreated
    r = client.post(f"/api/v1/social/{pid}/react", json={"emoji": "👍"}, headers=H_ALICE)
    assert r.status_code == 201 and r.json()["id"] == first_id


# === Chat ===

def test_chat_room_lifecycle():
    bob_id = client.get("/api/v1/users/me", headers=H_BOB).json()["id"]

    r = client.post(
        "/api/v1/chat/rooms",
        json={"name": "Study Buddies", "is_group": True, "member_ids": [bob_id]},
        headers=H_ALICE,
    )
    assert r.status_code == 201, r.text
    rid = r.json()["id"]

    r = client.get("/api/v1/chat/rooms", headers=H_ALICE)
    assert r.status_code == 200 and any(room["id"] == rid for room in r.json())

    r = client.get(f"/api/v1/chat/rooms/{rid}", headers=H_ALICE)
    assert r.status_code == 200 and len(r.json()["members"]) == 2

    # Bob joins a room he was added to
    r = client.post(f"/api/v1/chat/rooms/{rid}/join", headers=H_BOB)
    assert r.status_code == 200 and r.json()["message"] == "Already a member"

    # A third user is not a member -> forbidden
    register_user(client, "comm-carla@test.c", PASSWORD, "Comm Carla")
    h_carla = login(client, "comm-carla@test.c", PASSWORD)
    r = client.get(f"/api/v1/chat/rooms/{rid}", headers=h_carla)
    assert r.status_code == 403

    r = client.post(f"/api/v1/chat/rooms/{rid}/join", headers=h_carla)
    assert r.status_code == 200 and r.json()["message"] == "Joined room"

    # Messages
    r = client.post(f"/api/v1/chat/rooms/{rid}/messages", json={"content": "Hello room!"}, headers=H_ALICE)
    assert r.status_code == 201, r.text

    r = client.get(f"/api/v1/chat/rooms/{rid}/messages", headers=H_BOB)
    assert r.status_code == 200 and len(r.json()) == 1
    assert r.json()[0]["user"]["email"] == ALICE_EMAIL

    # Offline sync
    r = client.post(
        f"/api/v1/chat/rooms/{rid}/sync",
        json={"room_id": rid, "messages": [{"content": "offline 1"}, {"content": "offline 2"}]},
        headers=H_BOB,
    )
    assert r.status_code == 200 and len(r.json()) == 2

    r = client.get(f"/api/v1/chat/rooms/{rid}/messages", headers=H_BOB)
    assert len(r.json()) == 3


# === Study groups ===

def test_study_group_and_forums():
    r = client.post(
        "/api/v1/groups/groups",
        json={"name": "Physics Squad", "description": "study", "max_members": 5},
        headers=H_ALICE,
    )
    assert r.status_code == 201, r.text
    gid = r.json()["id"]

    r = client.get("/api/v1/groups/groups")
    assert any(g["id"] == gid for g in r.json())

    r = client.post(f"/api/v1/groups/groups/{gid}/join", headers=H_BOB)
    assert r.status_code == 200 and r.json()["message"] == "Joined group"

    r = client.get(f"/api/v1/groups/groups/{gid}")
    assert r.status_code == 200 and len(r.json()["members"]) == 2

    # Forums (course_id 1 is fine — FK not enforced in SQLite)
    r = client.post(
        "/api/v1/groups/forums/1",
        json={"course_id": 1, "title": "Help with homework", "content": "Stuck on Q3"},
        headers=H_ALICE,
    )
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    r = client.get("/api/v1/groups/forums/1")
    assert r.status_code == 200 and any(t["id"] == tid for t in r.json())

    r = client.post(f"/api/v1/groups/forums/thread/{tid}/reply", json={"content": "Try using F=ma"}, headers=H_BOB)
    assert r.status_code == 201, r.text

    r = client.get(f"/api/v1/groups/forums/thread/{tid}")
    assert r.status_code == 200 and len(r.json()["replies"]) == 1
