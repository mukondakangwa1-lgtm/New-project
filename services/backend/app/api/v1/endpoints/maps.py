"""
Digital Campus - KUDOS Maps API

KUDOS's internal world map (offline navigation) fused with its ground truth:
radio towers (radio.garden), precise device-network anchors (access points +
cell towers) and seeded world places. KUDOS never guesses a location — every
fix reports its measured source and accuracy.

Endpoints:
  GET  /maps/status     — layer counts + precision stats
  GET  /maps/search?q   — find places on the internal world map
  GET  /maps/place/{id} — one place + what KUDOS knows near it
  GET  /maps/nearby     — places within a radius of a coordinate
  GET  /maps/between?a&b— distance + bearing between two places
  GET  /maps/world      — fused snapshot of the internal world map
  GET  /maps/where      — best measured location for a device/user (honest)
  POST /maps/report-scan— a device feeds its Wi-Fi/cell/GPS scan
  POST /maps/seed       — (admin) seed/refresh the internal world map
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import network_map, world_map
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.device_storage import get_device_by_token
from app.models import KudosDevice, User
from app.models_extended import KudosMapPlace

router = APIRouter()


class GpsFix(BaseModel):
    lat: float | None = None
    lon: float | None = None
    accuracy: float | None = None


class ScanReport(BaseModel):
    gps: GpsFix | None = None
    wifi: list[dict] = Field(default_factory=list)
    cells: list[dict] = Field(default_factory=list)
    device_id: int | None = None


def _resolve_device(
    db: Session,
    x_device_token: str,
    current_user: User,
) -> tuple[KudosDevice | None, User]:
    if x_device_token:
        device = get_device_by_token(db, x_device_token)
        if not device:
            raise HTTPException(status_code=401, detail="Unknown device token")
        return device, device.user
    return None, current_user


@router.get("/status")
def maps_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {
        "world_map": world_map.status(db),
        "network_anchors": network_map.anchors_summary(db),
    }


@router.get("/search")
def maps_search(
    q: str = Query("", max_length=120),
    limit: int = Query(15, ge=1, le=60),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"query": q, "results": world_map.search(db, q, limit)}


@router.get("/place/{place_id}")
def maps_place(
    place_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = db.get(KudosMapPlace, place_id)
    if not p:
        raise HTTPException(status_code=404, detail="Place not on the internal map")
    near_places = world_map.near(db, p.lat, p.lon, radius_km=60) if p.lat is not None else []
    return {"place": world_map._as_dict(p), "nearby_world": near_places}


@router.get("/nearby")
def maps_nearby(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(250, gt=0, le=20000),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.radio_garden import near as radio_near
    return {
        "places": world_map.near(db, lat, lon, radius_km, limit),
        "radio_towers": radio_near(db, lat, lon, radius_km),
    }


@router.get("/between")
def maps_between(
    a: str = Query(...),
    b: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return world_map.between(db, a, b)


@router.get("/world")
def maps_world(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fused snapshot of KUDOS's own real-world map."""
    from app.core.radio_garden import overview as radio_overview
    return {
        "places": world_map.status(db),
        "radio": radio_overview(db),
        "network_anchors": network_map.anchors_summary(db),
        "links": network_mesh.links_summary(db),
    }


@router.get("/where")
def maps_where(
    x_device_token: str = Header(default="", alias="X-Device-Token"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = None
    if x_device_token:
        device, current_user = _resolve_device(db, x_device_token, current_user)
    fix = network_map.latest_fix(db, device.id) if device else network_map.best_fix_for_user(db, current_user.id)
    if fix.get("mode") == "none" or fix.get("lat") is None:
        return {
            "known": False, "location": None,
            "reason": "KUDOS has not measured a fix yet — share your location on the Maps panel so it can anchor your networks.",
        }
    area = world_map.country_for(db, fix.get("lat"), fix.get("lon"))
    return {"known": True, "location": fix, "area": area}


@router.post("/report-scan", status_code=201)
def maps_report_scan(
    body: ScanReport,
    x_device_token: str = Header(default="", alias="X-Device-Token"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = None
    if body.device_id:
        device = db.get(KudosDevice, body.device_id)
        if not device or device.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Device not found")
    elif x_device_token:
        device, current_user = _resolve_device(db, x_device_token, current_user)
    if device is None:
        raise HTTPException(status_code=400, detail="Register a KUDOS device first, or pass a device_id")

    payload = {
        "gps": {"lat": body.gps.lat, "lon": body.gps.lon, "accuracy": body.gps.accuracy} if body.gps else None,
        "wifi": body.wifi,
        "cells": body.cells,
    }
    return network_map.ingest_scan(db, device, current_user, payload)


@router.post("/seed")
def maps_seed(
    force: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    seeded = world_map.seed_world_map(db, force=force)
    return {"seeded": seeded, "status": world_map.status(db)}