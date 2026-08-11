"""KUDOS Maps + Link Switching tests: internal world map, offline geo answers,
crowdsourced network location, and terrestrial<->satellite switching."""

from fastapi.testclient import TestClient

from app.main import app

from tests.conftest import (
    TestSessionLocal,
    login,
    promote_to_admin,
    register_user,
)

client = TestClient(app)


def _admin_headers(client, email):
    register_user(client, email)
    promote_to_admin(email)
    return login(client, email)


def _register_device(client, headers, name="Phone"):
    r = client.post(
        "/api/v1/kudos/devices",
        json={"name": name, "platform": "android", "storage_bytes": 536870912},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["api_token"]


def _seed(db=None):
    from app.core.world_map import seed_world_map

    s = db or TestSessionLocal()
    try:
        return seed_world_map(s, force=True)
    finally:
        s.close()


# ──────────────────────────────────────────────
# WORLD MAP
# ──────────────────────────────────────────────

def test_seed_map_and_status():
    h = _admin_headers(client, "maps.seed@test.io")
    r = client.post("/api/v1/maps/seed?force=true", headers=h)
    assert r.status_code == 200, r.text
    seeded = r.json()["seeded"]
    assert seeded["country"] > 150
    assert seeded["capital"] > 150
    assert seeded["continent"] == 7
    assert r.json()["status"]["total"] > 500

    r = client.get("/api/v1/maps/status", headers=h)
    assert r.status_code == 200
    assert r.json()["world_map"]["total"] > 500
    assert r.json()["network_anchors"]["access_points"] == 0


def test_map_search_and_between():
    h = _admin_headers(client, "maps.search@test.io")
    client.post("/api/v1/maps/seed?force=true", headers=h)

    r = client.get("/api/v1/maps/search?q=Paris", headers=h)
    names = [x["name"] for x in r.json()["results"]]
    assert "Paris" in names

    r = client.get("/api/v1/maps/between?a=Paris&b=London", headers=h)
    data = r.json()
    assert data["found"] is True
    assert 300 < data["distance_km"] < 400
    assert data["direction"] in ("NW", "N", "W")

    r = client.get("/api/v1/maps/between?a=Atlantis&b=London", headers=h)
    assert r.json()["found"] is False


def test_nearby_places():
    h = _admin_headers(client, "maps.nearby@test.io")
    client.post("/api/v1/maps/seed?force=true", headers=h)
    r = client.get("/api/v1/maps/nearby?lat=51.5074&lon=-0.1278&radius_km=200", headers=h)
    names = {x["name"] for x in r.json()["places"]}
    assert "London" in names


def test_world_map_offline_brain():
    from app.core.kudos_brain import answer_offline

    _seed()
    db = TestSessionLocal()
    try:
        by_id = answer_offline(db, "where is Nairobi?", user_id=None)
        assert by_id["mode"] == "internal-map"
        assert "Nairobi" in by_id["answer"]
        assert by_id["grounded"] is True
        assert "internal-map" in {s["source_type"] for s in by_id["sources"]}

        nothing = answer_offline(db, "what is the best pizza recipe?", user_id=None)
        assert nothing["mode"] == "offline-brain"
    finally:
        db.close()


# ──────────────────────────────────────────────
# CROWDSOURCED LOCATION (device networks)
# ──────────────────────────────────────────────

def test_scan_learns_then_located_without_gps():
    _seed()
    h = _admin_headers(client, "maps.brain@test.io")
    token = _register_device(client, h)
    dheaders = {**h, "X-Device-Token": token}

    # Scan 1 + 2: GPS-backed, teaches anchor BSSID.
    for _ in range(2):
        r = client.post(
            "/api/v1/maps/report-scan",
            json={
                "gps": {"lat": 48.8566, "lon": 2.3522, "accuracy": 12},
                "wifi": [{"bssid": "aa:bb:cc:dd:ee:01", "ssid": "KUDOS-Home", "rssi": -55}],
            },
            headers=dheaders,
        )
        assert r.status_code == 201, r.text
        assert r.json()["location"]["mode"] == "gps-fix"

    # Scan 3: NO GPS, but the anchor is known -> wifi fingerprint.
    r = client.post(
        "/api/v1/maps/report-scan",
        json={"wifi": [{"bssid": "aa:bb:cc:dd:ee:01", "ssid": "KUDOS-Home", "rssi": -58}]},
        headers=dheaders,
    )
    loc = r.json()["location"]
    assert loc["mode"] == "wifi-fingerprint"
    assert loc["lat"] is not None

    # Unknown area -> KUDOS never guesses: falls back to its last measured fix
    # (clearly labelled) because this device has one already.
    r = client.post(
        "/api/v1/maps/report-scan",
        json={"wifi": [{"bssid": "00:11:22:33:44:55", "ssid": "stranger", "rssi": -70}]},
        headers=dheaders,
    )
    assert r.json()["location"]["mode"] == "last-known"
    assert r.json()["location"]["source"] == "previous known location"

    # /maps/where returns the measured fix.
    r = client.get("/api/v1/maps/where", headers=dheaders)
    assert r.json()["known"] is True
    assert r.json()["location"]["lat"] is not None
    assert r.json()["area"]["nearest"]["name"] == "France"
    assert r.json()["area"]["continent"] == "Europe"


# ──────────────────────────────────────────────
# LINK SWITCHING (terrestrial <-> satellite)
# ──────────────────────────────────────────────

def test_satellite_report_adapts_strategy():
    h = _admin_headers(client, "maps.scan@test.io")
    token = _register_device(client, h)
    dheaders = {**h, "X-Device-Token": token}

    r = client.post(
        "/api/v1/network/report",
        json={
            "primary_transport": "satellite",
            "transports": ["satellite"],
            "constrained": True,
            "rtt_ms": 45.0,
        },
        headers=dheaders,
    )
    data = r.json()
    assert data["link"] == "satellite"
    assert data["constrained"] is True
    assert data["strategy"]["chat"] == "text-priority"
    assert data["strategy"]["media"] == "defer"
    assert data["strategy"]["emergency"] == "always"

    r = client.get("/api/v1/network/status", headers=dheaders)
    devices = r.json()["devices"]
    assert len(devices) == 1
    assert devices[0]["latest"]["satellite"] is True
    assert devices[0]["choice"]["link"] == "satellite"


def test_mode_switch_and_measured_link_honesty():
    h = _admin_headers(client, "maps.mode@test.io")
    token = _register_device(client, h, name="Laptop")
    dheaders = {**h, "X-Device-Token": token}

    # Device on Wi-Fi.
    client.post(
        "/api/v1/network/report",
        json={"primary_transport": "wifi", "transports": ["wifi", "cellular"]},
        headers=dheaders,
    )

    # Force satellite preference: not visible -> KUDOS reports the measured link.
    r = client.post("/api/v1/network/mode?mode=satellite", headers=dheaders)
    assert r.json()["mode"] == "satellite"
    assert r.json()["link"] == "wifi"  # honest: satellite not measured

    # Back to auto on Wi-Fi.
    r = client.post("/api/v1/network/mode?mode=auto", headers=dheaders)
    assert r.json()["link"] == "wifi"

    # A cellular-capable device with satellite backhaul is constrained.
    client.post(
        "/api/v1/network/report",
        json={"primary_transport": "wifi", "transports": ["wifi", "cellular"],
              "satellite_backhaul": True, "constrained": True},
        headers=dheaders,
    )
    s = client.get("/api/v1/network/status", headers=dheaders).json()["devices"][0]
    assert s["choice"]["constrained"] is True


def test_links_summary():
    h = _admin_headers(client, "maps.links@test.io")
    r = client.get("/api/v1/network/links", headers=h)
    assert "mesh" in r.json()
    assert "tiers" in r.json()
    assert r.json()["tiers"]["satellite"] == "Satellite (Starlink/NTN)"