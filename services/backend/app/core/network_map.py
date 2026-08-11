"""
Digital Campus - KUDOS Real-World Map (device networks)

KUDOS maps the area AROUND its own devices. Every device (phone, laptop) that
uses KUDOS reports what it can sense: Wi-Fi access points (BSSID + RSSI),
cellular towers and — when the user allows — a GPS fix. KUDOS fuses these into
a precise, crowdsourced position for the device, and grows a real-world network
map (access points + towers) that lets later devices locate themselves WITHOUT
GPS, using the anchors its devices have already placed.

Precision ladder — KUDOS reports the best honesty it has:
  gps-fix          (device GPS, accuracy <= 200 m)
  wifi-fingerprint (matched known access points, path-loss weighted centroid)
  cell             (matched known cell towers, centroid)
  last-known       (this device's previous fix)
  unknown          (nothing measured yet — KUDOS says so, never guesses)
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import KudosDevice, User
from app.models_extended import KudosAccessPoint, KudosCellTower, KudosScan


# ──────────────────────────────────────────────
# PATH-LOSS / DISTANCE ESTIMATION
# ──────────────────────────────────────────────

def _dist_from_rssi(rssi: float) -> float:
    """Log-distance path-loss: RSSI -> metres from the anchor."""
    a, n = -40.0, 3.0  # RSSI at 1 m, indoor exponent
    d = 10 ** ((a - rssi) / (10 * n))
    return max(3.0, min(300.0, d))


def _weighted_centroid(points: list[dict]) -> dict:
    """points: [{lat,lon,weight,contributing}] -> fused fix + accuracy.
    Weights come from observed distance; accuracy grows with spread."""
    if not points:
        return {"lat": None, "lon": None, "accuracy_m": None, "matches": 0, "spread_km": 0.0}
    wsum = sum(p["weight"] for p in points)
    if wsum <= 0:
        return {"lat": None, "lon": None, "accuracy_m": None, "matches": 0, "spread_km": 0.0}
    lat = sum(p["lat"] * p["weight"] for p in points) / wsum
    lon = sum(p["lon"] * p["weight"] for p in points) / wsum
    lat2 = sum((p["lat"] - lat) ** 2 for p in points) / len(points)
    lon2 = sum((p["lon"] - lon) ** 2 for p in points) / len(points)
    spread_km = math.sqrt(max(lat2, 0.0) * 111.0 ** 2 + max(lon2, 0.0) * (111.0 * max(math.cos(math.radians(lat)), 0.01)) ** 2)
    matches = len(points)
    # Conservative accuracy: more anchors shrink it, spread grows it.
    accuracy = 120.0 / math.sqrt(max(matches, 1)) + spread_km * 1000.0 * 0.6
    return {"lat": lat, "lon": lon, "accuracy_m": round(min(accuracy, 2500.0), 1), "matches": matches, "spread_km": round(spread_km, 2)}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ──────────────────────────────────────────────
# ANCHOR LEARNING (crowdsourced)
# ──────────────────────────────────────────────

def _learn_wifi(db: Session, device: KudosDevice, wifi: list[dict], gps_ok: bool, gps_lat: float, gps_lon: float):
    """Place/refine Wi-Fi anchors from a device report that carries GPS."""
    if not wifi or not gps_ok:
        return
    now = datetime.now(timezone.utc)
    for ap in wifi:
        bssid = ((ap.get("bssid") or "").replace("-", ":") or "").lower()
        if len(bssid) < 11 or ":" not in bssid:
            continue
        try:
            rssi = int(ap.get("rssi") or ap.get("level") or -70)
        except (TypeError, ValueError):
            rssi = -70
        row = db.query(KudosAccessPoint).filter(KudosAccessPoint.bssid == bssid).first()
        if row is None:
            row = KudosAccessPoint(bssid=bssid, ssid=(ap.get("ssid") or "")[:120],
                                   lat=gps_lat, lon=gps_lon, first_seen_at=now)
            db.add(row)
        else:
            if row.first_seen_at is None:
                row.first_seen_at = now
        # Confidence-weighted moving merge: newer + more observations pull the anchor.
        n = row.observations or 0
        w_new = 0.35 / (1 + n * 0.02)
        row.lat = (row.lat or gps_lat) * (1 - w_new) + gps_lat * w_new
        row.lon = (row.lon or gps_lon) * (1 - w_new) + gps_lon * w_new
        row.accuracy_m = max(30.0, min(row.accuracy_m or 120.0, 250.0) * 0.98)
        row.last_signal_dbm = rssi
        row.observations = n + 1
        row.last_seen_at = now


def _learn_cells(db: Session, device: KudosDevice, cells: list[dict], gps_ok: bool, gps_lat: float, gps_lon: float):
    """Place/refine cell-tower anchors from a device report that carries GPS."""
    if not cells or not gps_ok:
        return
    now = datetime.now(timezone.utc)
    for tower in cells:
        mcc = int(tower.get("mcc") or 0)
        mnc = int(tower.get("mnc") or 0)
        lac = int(tower.get("lac") or 0)
        cid = int(tower.get("cid") or tower.get("cell_id") or 0)
        if not (mcc or mnc or lac or cid):
            continue
        key = f"{mcc}-{mnc}-{lac}-{cid}"
        row = db.query(KudosCellTower).filter(KudosCellTower.cell_key == key).first()
        if row is None:
            row = KudosCellTower(cell_key=key, mcc=mcc, mnc=mnc, lac=lac, cid=cid,
                                 lat=gps_lat, lon=gps_lon)
            db.add(row)
        n = row.observations or 0
        w_new = 0.3 / (1 + n * 0.03)
        row.lat = (row.lat or gps_lat) * (1 - w_new) + gps_lat * w_new
        row.lon = (row.lon or gps_lon) * (1 - w_new) + gps_lon * w_new
        row.accuracy_m = max(250.0, min(row.accuracy_m or 1500.0, 2500.0) * 0.99)
        row.observations = n + 1
        row.last_seen_at = now


# ──────────────────────────────────────────────
# ESTIMATION
# ──────────────────────────────────────────────

def _from_wifi(db: Session, wifi: list[dict]) -> dict:
    """Fingerprint a scan against known anchors (works without GPS)."""
    points = []
    used = 0
    for ap in wifi:
        bssid = ((ap.get("bssid") or "").replace("-", ":") or "").lower()
        if len(bssid) < 11 or ":" not in bssid:
            continue
        try:
            rssi = int(ap.get("rssi") or ap.get("level") or -70)
        except (TypeError, ValueError):
            rssi = -70
        row = db.query(KudosAccessPoint).filter(KudosAccessPoint.bssid == bssid).first()
        if row is None or row.lat == 0.0 or row.observations < 2:
            continue
        d = _dist_from_rssi(rssi)
        points.append({"lat": row.lat, "lon": row.lon, "weight": 1.0 / (d * d)})
        used += 1
    fix = _weighted_centroid(points)
    fix["matches"] = used
    return fix


def _from_cells(db: Session, cells: list[dict]) -> dict:
    towers = []
    used = 0
    for tower in cells:
        mcc = int(tower.get("mcc") or 0)
        mnc = int(tower.get("mnc") or 0)
        lac = int(tower.get("lac") or 0)
        cid = int(tower.get("cid") or tower.get("cell_id") or 0)
        if not (mcc or mnc or lac or cid):
            continue
        row = db.query(KudosCellTower).filter(KudosCellTower.cell_key == f"{mcc}-{mnc}-{lac}-{cid}").first()
        if row is None or row.observations < 2:
            continue
        towers.append({"lat": row.lat, "lon": row.lon, "weight": 1.0})
        used += 1
    fix = _weighted_centroid(towers)
    fix["accuracy_m"] = max(fix["accuracy_m"] or 0, 800.0)
    fix["matches"] = used
    return fix


def ingest_scan(
    db: Session,
    device: KudosDevice,
    user: User | None,
    payload: dict,
) -> dict:
    """Record a device's network scan and decide its best location fix."""
    gps = payload.get("gps") or {}
    gps_lat = gps.get("lat")
    gps_lon = gps.get("lon")
    try:
        gps_accuracy = float(gps.get("accuracy") or gps.get("accuracy_m") or 1000.0)
    except (TypeError, ValueError):
        gps_accuracy = 1000.0
    gps_ok = bool(gps_lat is not None and gps_lon is not None and gps_accuracy <= 500)

    wifi = payload.get("wifi") or payload.get("aps") or []
    cells = payload.get("cells") or payload.get("towers") or []

    # Learn anchors from GPS-backed scans so other devices can later locate themselves.
    _learn_wifi(db, device, wifi, gps_ok, gps_lat or 0.0, gps_lon or 0.0)
    _learn_cells(db, device, cells, gps_ok, gps_lat or 0.0, gps_lon or 0.0)

    # Precision ladder.
    fix = {}
    if gps_ok:
        fix = {"mode": "gps-fix", "lat": gps_lat, "lon": gps_lon, "accuracy_m": max(gps_accuracy, 5.0),
               "source": "device GPS", "matches": 1, "spread_km": 0.0}
    else:
        wfix = _from_wifi(db, wifi)
        if wfix["matches"] >= 1:
            fix = {"mode": "wifi-fingerprint", **wfix, "source": f"{wfix['matches']} known Wi-Fi anchors"}
        else:
            cfix = _from_cells(db, cells)
            if cfix["matches"] >= 1:
                fix = {"mode": "cell", **cfix, "source": f"{cfix['matches']} known cell towers"}
            else:
                prev = latest_fix(db, device.id)
                if prev and prev.get("lat") is not None:
                    fix = {**prev, "mode": "last-known", "source": "previous known location"}
                else:
                    fix = {"mode": "unknown", "lat": None, "lon": None, "accuracy_m": None,
                           "source": "no measured signal yet", "matches": 0, "spread_km": 0.0}

    scan = KudosScan(
        device_id=device.id,
        user_id=user.id if user else None,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        gps_accuracy_m=gps_accuracy,
        wifi_json=json.dumps(wifi),
        cells_json=json.dumps(cells),
        result_json=json.dumps(fix, default=str),
    )
    db.add(scan)
    db.commit()

    return {
        "location": fix,
        "true": "never-guessing",
        "device_id": device.id,
        "anchors_learned": {"wifi": (wifi and gps_ok), "cells": (cells and gps_ok)},
    }


def latest_fix(db: Session, device_id: int) -> dict:
    scan = (
        db.query(KudosScan)
        .filter(KudosScan.device_id == device_id)
        .order_by(KudosScan.created_at.desc())
        .first()
    )
    if not scan or not (scan.result_json and scan.result_json != "{}"):
        return {"lat": None, "lon": None, "accuracy_m": None, "mode": "none", "source": ""}
    try:
        result = json.loads(scan.result_json)
    except ValueError:
        return {"lat": None, "lon": None, "accuracy_m": None, "mode": "none", "source": ""}
    return result


def best_fix_for_user(db: Session, user_id: int) -> dict:
    """The most precise fix among a user's devices."""
    device_ids = [d.id for d in db.query(KudosDevice).filter(KudosDevice.user_id == user_id).all()]
    if not device_ids:
        return {"lat": None, "lon": None, "accuracy_m": None, "mode": "none", "source": "no devices"}
    best = None
    for did in device_ids:
        f = latest_fix(db, did)
        if f.get("lat") is None:
            continue
        if best is None or (f.get("accuracy_m") or 99999) < (best.get("accuracy_m") or 99999):
            best = f
    return best or {"lat": None, "lon": None, "accuracy_m": None, "mode": "none", "source": "no fix yet"}


def anchors_summary(db: Session) -> dict:
    """The real-world map KUDOS has built from its devices' networks."""
    aps = db.query(func.count(KudosAccessPoint.id)).scalar() or 0
    towers = db.query(func.count(KudosCellTower.id)).scalar() or 0
    scans = db.query(func.count(KudosScan.id)).scalar() or 0
    fixed = (
        db.query(func.count(KudosScan.id))
        .filter(KudosScan.result_json.like('%"lat"%'), ~KudosScan.result_json.like('%"mode": "unknown"%'))
        .scalar() or 0
    )
    return {
        "access_points": aps, "cell_towers": towers, "total_scans": scans,
        "located_scans": fixed, "method": "crowdsourced from KUDOS devices",
    }