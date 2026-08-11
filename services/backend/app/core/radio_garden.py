"""
Digital Campus - KUDOS Radio Garden

KUDOS maps the entire world through Radio Garden's live radio towers: it scans
the planet's places (continents -> countries -> cities with lat/lon), records
the live radio stations broadcasting from each place (the "radio towers"), and
builds an internal geographic landscape KUDOS can query and tune into.

Public data source: https://radio.garden/ (community API /api/ara/content/...)
"""

import math
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.models import RadioPlace, RadioStation

_BASE = "https://radio.garden/api/ara/content"
_HEADERS = {"User-Agent": "Digital-Campus-KUDOS/1.0 (radio world map)"}
_STREAM_PREFIX = "https://radio.garden/api/ara/content/listen"


def stream_url_for(station: RadioStation) -> str:
    """Full playable stream URL for a station."""
    if station.stream_path:
        return f"{_STREAM_PREFIX}/{station.stream_path}/channel.mp3"
    return f"{_STREAM_PREFIX}/{station.station_id}/channel.mp3"


def _continent_for(lat: float, lon: float) -> str:
    """Rough continent from coordinates (radio.garden no longer groups places)."""
    if lon < -30 and lat > 20:
        return "North America"
    if lon < -60 and lat <= 20:
        return "South America"
    if lon < -30:
        return "South America"
    if -30 <= lon < 55:
        return "Africa" if -40 <= lat <= 40 else ("Europe" if lat > 40 else "Africa")
    if 55 <= lon < 100 and lat < 15:
        return "Asia"
    if 100 <= lon < 170 and lat >= 15:
        return "Asia"
    if lon >= 140 and lat < -30:
        return "Oceania"
    if lon >= 100:
        return "Oceania" if lat < -10 else "Asia"
    if lat > 35 and -30 <= lon < 55:
        return "Europe"
    return "Asia"


def _places_from_data(data: dict) -> list[dict]:
    """Parse the places payload in either the new (flat data.list) or legacy
    (grouped continents) format. New items carry geo=[lon,lat] and size."""
    d = data.get("data")
    items: list[dict] = []
    if isinstance(d, dict):
        items = d.get("list") or []
    elif isinstance(d, list):
        for group in d:
            items.extend(group.get("content", []) or [])
    return items


def _channels_from_page(data: dict) -> list[dict]:
    """Parse a place page into channel dicts for the new or legacy API format."""
    d = data.get("data") if isinstance(data, dict) else {}
    raw = d.get("content") if isinstance(d, dict) else None
    channels: list[dict] = []
    if isinstance(raw, list):
        for entry in raw:
            items = entry.get("items") if isinstance(entry, dict) else None
            if isinstance(items, list):
                for it in items:
                    page = it.get("page") if isinstance(it, dict) else None
                    if isinstance(page, dict):
                        url = page.get("url", "")
                        sid = url.rsplit("/", 1)[-1] or page.get("title", "")[:40]
                        place = page.get("place") or {}
                        country = page.get("country") or {}
                        channels.append(
                            {
                                "id": sid,
                                "url": url,
                                "title": page.get("title") or "",
                                "place_name": (place.get("title") if isinstance(place, dict) else "") or "",
                                "country": (country.get("title") if isinstance(country, dict) else "") or "",
                                "genre": page.get("subtitle") or page.get("genre") or "",
                            }
                        )
            elif isinstance(entry, dict):
                # Legacy: content entry is itself a channel.
                channels.append(entry)
    return channels


async def scan_world(db: Session, max_places: int = 8000, max_stations_per_place: int = 60) -> dict:
    """Full scan: harvest the world's places (fast, single API call). Live
    station counts come from the payload; individual tower details are fetched
    lazily when a place is opened.

    Returns {"places": n, "stations": n}. Re-runnable (idempotent upsert)."""
    from app.core import storage  # noqa: F401  (imports storage init/config)

    try:
        async with httpx.AsyncClient(timeout=30, headers=_HEADERS) as client:
            res = await client.get(f"{_BASE}/places")
            res.raise_for_status()
            data = res.json()
    except Exception as e:
        return {"error": f"radio.garden unreachable: {e}"}

    added_places = 0
    total_stations = 0
    now = datetime.now(UTC)

    for item in _places_from_data(data):
        place_id = item.get("id")
        if not place_id:
            continue
        name = item.get("title") or ""
        geo = item.get("geo") or item.get("coordinates") or []
        # geo is [lon, lat]; legacy coordinates may be [lat, lon].
        lon = float(geo[0]) if len(geo) > 0 else 0.0
        lat = float(geo[1]) if len(geo) > 1 else 0.0
        if not item.get("geo"):
            lat, lon = lon, lat
        country = item.get("country") or ""
        size = int(item.get("size") or 0)

        place = db.query(RadioPlace).filter(RadioPlace.place_id == place_id).first()
        if not place:
            place = RadioPlace(place_id=place_id)
            db.add(place)
        place.name = name[:200]
        place.country = (country or "")[:120]
        place.continent = _continent_for(lat, lon)[:60]
        place.lat = lat
        place.lon = lon
        place.live_station_count = max(place.live_station_count or 0, size)
        place.last_synced_at = now
        total_stations += size
        added_places += 1
        if added_places % 500 == 0:
            db.commit()
        if added_places >= max_places:
            break

    db.commit()
    return {"places": added_places, "stations": total_stations}


async def scan_place(db: Session, place_id: str) -> dict:
    """Scan a single place's live radio towers (used by the KUDOS chat/globe)."""
    try:
        async with httpx.AsyncClient(timeout=25, headers=_HEADERS) as client:
            page = await client.get(f"{_BASE}/page/{place_id}")
            page.raise_for_status()
            data = page.json()
    except Exception as e:
        return {"error": f"radio.garden page unreachable: {e}"}

    now = datetime.now(UTC)
    title = (data.get("data") or {}).get("title") if isinstance(data, dict) else ""
    place = db.query(RadioPlace).filter(RadioPlace.place_id == place_id).first()
    if not place:
        place = RadioPlace(place_id=place_id, name=title or place_id, lat=0.0, lon=0.0)
        db.add(place)
    place.name = (title or place.name)[:200]
    place.last_synced_at = now
    db.flush()

    stations = []
    for ch in _channels_from_page(data)[:60]:
        sid = ch.get("id") or ""
        if not sid:
            continue
        station = db.query(RadioStation).filter(RadioStation.station_id == sid).first()
        if not station:
            station = RadioStation(station_id=sid)
            db.add(station)
        station.title = (ch.get("title") or place.name)[:200]
        station.place_id = place.id
        station.place_name = (ch.get("place_name") or place.name)[:200]
        station.country = (ch.get("country") or place.country)[:120]
        station.stream_path = (ch.get("url") or ch.get("stream_path") or sid).rsplit("/", 1)[-1][:255]
        station.genre = (ch.get("genre") or "")[:200]
        station.current_track = (ch.get("now_playing") or ch.get("track") or "")[:255]
        station.frequency = (ch.get("freq") or "")[:30]
        station.last_seen_at = now
        station.is_live = True
        stations.append(
            {
                "id": station.station_id,
                "title": station.title,
                "genre": station.genre,
                "frequency": station.frequency,
                "current_track": station.current_track,
                "stream_url": stream_url_for(station),
            }
        )
    place.live_station_count = len(stations)
    db.commit()
    return {"place": place.name, "lat": place.lat, "lon": place.lon, "stations": stations}


def overview(db: Session) -> dict:
    """World landscape: continents with place/station counts."""
    places = db.query(RadioPlace).all()
    continents: dict[str, dict] = {}
    total_stations = 0
    for p in places:
        key = p.continent or "Unknown"
        c = continents.setdefault(key, {"places": 0, "stations": 0})
        c["places"] += 1
        c["stations"] += p.live_station_count or 0
        total_stations += p.live_station_count or 0
    return {
        "continents": [{"name": k, **v} for k, v in sorted(continents.items())],
        "total_places": len(places),
        "total_stations": total_stations,
    }


def search(db: Session, q: str, limit: int = 20) -> dict:
    """Find places + stations matching a query (KUDOS knows where things are)."""
    like = f"%{q}%"
    places = (
        db.query(RadioPlace)
        .filter(RadioPlace.name.ilike(like) | RadioPlace.country.ilike(like))
        .order_by(RadioPlace.name)
        .limit(limit)
        .all()
    )
    stations = (
        db.query(RadioStation)
        .filter(RadioStation.title.ilike(like) | RadioStation.genre.ilike(like))
        .order_by(RadioStation.title)
        .limit(limit)
        .all()
    )
    return {
        "places": [
            {
                "place_id": p.place_id,
                "name": p.name,
                "country": p.country,
                "continent": p.continent,
                "lat": p.lat,
                "lon": p.lon,
                "stations": p.live_station_count or 0,
            }
            for p in places
        ],
        "stations": [
            {
                "id": s.station_id,
                "title": s.title,
                "place": s.place_name,
                "country": s.country,
                "genre": s.genre,
                "stream_url": stream_url_for(s),
            }
            for s in stations
        ],
    }


def near(db: Session, lat: float, lon: float, radius_km: float = 250) -> list[dict]:
    """Places within a radius of a coordinate (nearest radio towers first)."""
    places = db.query(RadioPlace).all()
    results = []
    for p in places:
        d = _haversine_km(lat, lon, p.lat, p.lon)
        if d <= radius_km:
            results.append(
                {
                    "place_id": p.place_id,
                    "name": p.name,
                    "country": p.country,
                    "distance_km": round(d, 1),
                    "lat": p.lat,
                    "lon": p.lon,
                    "stations": p.live_station_count or 0,
                }
            )
    results.sort(key=lambda r: r["distance_km"])
    return results[:30]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))
