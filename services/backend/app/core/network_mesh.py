"""
Digital Campus - KUDOS Link Switching

KUDOS switches between terrestrial and satellite (Starlink / Android NTN)
networks for every connected device. The device reports the links it can
ACTUALLY see (ConnectivityManager transports / SatelliteManager on Android);
KUDOS records the measurement, classifies the link tier and applies a mode:

  * auto        — best available link (KUDOS grades Wi-Fi > cellular > satellite)
  * terrestrial — prefer Wi-Fi/cellular; satellite only if nothing else
  * satellite   — prefer satellite (Starlink/NTN); terrestrial as fallback

KUDOS never claims a link it has not seen. A link that rides a satellite
backhaul (e.g. a house with a roofless Starlink terminal feeding Wi-Fi) is
treated as satellite-constrained for data purposes.

Satellite links are bandwidth-constrained (Android NET_CAPABILITY
NOT_BANDWIDTH_CONSTRAINED is absent), so KUDOS adapts: answers from the
offline brain, concise replies, deferred media uploads, compressed audio.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import KudosDevice, User
from app.models_extended import KudosNetworkSetting, KudosNetworkState

# Tier ranking for a transport: higher is better.
_TRANSPORT_RANK = {"ethernet": 4, "wifi": 3, "cellular": 2, "satellite": 1, "unknown": 0}
_TIERS = ["satellite", "marine", "ethernet", "wifi", "cellular"]
_TIER_LABELS = {
    "ethernet": "Fiber/Wired",
    "wifi": "Wi-Fi",
    "cellular": "Cellular",
    "satellite": "Satellite (Starlink/NTN)",
    "unknown": "Unknown",
}
_VALID_TRANSPORTS = {"wifi", "cellular", "satellite", "ethernet", "unknown"}

# How KUDOS plays a task on each link tier: the data strategy.
_STRATEGY = {
    "chat": {"satellite": "text-priority", "cellular": "normal", "wifi": "normal", "ethernet": "normal"},
    "voice": {"satellite": "compressed-opus", "cellular": "normal", "wifi": "normal", "ethernet": "normal"},
    "media": {"satellite": "defer", "cellular": "normal", "wifi": "normal", "ethernet": "normal"},
    "video": {"satellite": "defer", "cellular": "slow", "wifi": "normal", "ethernet": "normal"},
    "sync": {"satellite": "defer", "cellular": "chunked", "wifi": "normal", "ethernet": "normal"},
    "emergency": {"satellite": "always", "cellular": "always", "wifi": "always", "ethernet": "always"},
}


def tier_for(primary_transport: str) -> str:
    """Best tier a reported primary transport supports."""
    return primary_transport if primary_transport in _STRATEGY["chat"] else "unknown"


def tier_label(tier: str) -> str:
    return _TIER_LABELS.get(tier, tier or "Unknown")


def _primary_of(payload: dict) -> str:
    t = (payload.get("primary_transport") or payload.get("primary") or "unknown").lower().strip()
    return t if t in _VALID_TRANSPORTS else "unknown"


def _is_constrained(payload: dict, primary: str) -> bool:
    """Satellite links are constrained; a satellite backhaul constrains the
    primary terrestrial hop the same way."""
    if primary == "satellite":
        return True
    return bool(payload.get("constrained") or payload.get("satellite") or payload.get("satellite_backhaul"))


def rank_transport(t: str) -> int:
    return _TRANSPORT_RANK.get(t, 0)


def best_transport(transports: list[str]) -> str:
    """Best transport among the ones a device can actually see."""
    known = [t for t in transports if t in _VALID_TRANSPORTS]
    if not known:
        return "unknown"
    return max(known, key=rank_transport)


def choose_link(db: Session, device_id: int, requested_mode: str = "") -> dict:
    """What KUDOS would use for a device right now, given its latest report
    and the device's switch mode."""
    state = (
        db.query(KudosNetworkState)
        .filter(KudosNetworkState.device_id == device_id)
        .order_by(KudosNetworkState.created_at.desc())
        .first()
    )
    setting = db.query(KudosNetworkSetting).filter(KudosNetworkSetting.device_id == device_id).first()
    mode = (requested_mode or (setting.mode if setting else "auto") or "auto").lower()
    if mode not in ("auto", "terrestrial", "satellite"):
        mode = "auto"

    transports = [t.strip() for t in (state.transports.split(",") if state and state.transports else []) if t.strip()]
    primary = _primary_of(vars(state) if state else {})

    if mode == "satellite":
        if (state and (state.satellite or state.primary_transport == "satellite")) or "satellite" in transports:
            chosen = "satellite"
        elif not transports:
            chosen = "unknown"
        else:
            chosen = primary
    elif mode == "terrestrial":
        terrestrial = [t for t in transports if t in ("wifi", "cellular", "ethernet")]
        chosen = (
            max(terrestrial, key=rank_transport)
            if terrestrial
            else ("satellite" if state and state.satellite else "unknown")
        )
        if chosen == "satellite":
            chosen = "satellite"
    else:  # auto
        if transports:
            chosen = best_transport(transports)
        elif state and state.satellite:
            chosen = "satellite"
        else:
            chosen = primary if primary != "unknown" else "unknown"

    constrained = bool(state and state.satellite) or bool(state and state.satellite_backhaul) or (chosen == "satellite")
    return {
        "mode": mode,
        "link": chosen,
        "tier": tier_for(chosen),
        "tier_label": tier_label(chosen),
        "constrained": constrained,
        "transports": transports,
        "signal_dbm": state.signal_dbm if state else 0,
        "reported_at": state.reported_at.isoformat() if state and state.reported_at else None,
    }


def strategy_for(link: str, task: str = "chat") -> str:
    return _STRATEGY.get(task, _STRATEGY["chat"]).get(link, "normal")


def record_state(
    db: Session,
    device: KudosDevice,
    user_id: int | None,
    payload: dict,
) -> dict:
    """Persist a measured transport report and return the decision."""
    primary = _primary_of(payload)
    transports = payload.get("transports") or ([primary] if primary != "unknown" else [])
    if isinstance(transports, str):
        transports = [t.strip() for t in transports.split(",") if t.strip()]
    transports = [t.lower() for t in transports if t in _VALID_TRANSPORTS]
    if primary not in transports:
        transports.append(primary) if primary != "unknown" else None

    try:
        signal_dbm = int(payload.get("signal_dbm") or 0)
    except (TypeError, ValueError):
        signal_dbm = 0
    try:
        bandwidth_kbps = int(payload.get("bandwidth_kbps") or 0)
    except (TypeError, ValueError):
        bandwidth_kbps = 0
    try:
        rtt_ms = float(payload.get("rtt_ms") or 0)
    except (TypeError, ValueError):
        rtt_ms = 0.0

    now = datetime.now(UTC)
    state = KudosNetworkState(
        device_id=device.id,
        user_id=user_id or device.user_id,
        primary_transport=primary,
        transports=",".join(transports),
        signal_dbm=signal_dbm,
        metered=bool(payload.get("metered", True)),
        constrained=bool(_is_constrained(payload, primary)),
        satellite=bool(payload.get("satellite") or primary == "satellite"),
        satellite_backhaul=bool(payload.get("satellite_backhaul")),
        bandwidth_kbps=bandwidth_kbps,
        rtt_ms=rtt_ms,
        provider=(payload.get("provider") or "")[:120],
        reported_at=now,
    )
    db.add(state)
    device.last_seen_at = now
    db.commit()

    choice = choose_link(db, device.id)
    choice["recorded"] = True
    choice["strategy"] = {}
    for task in ("chat", "voice", "media", "video", "sync", "emergency"):
        choice["strategy"][task] = strategy_for(choice["link"], task)
    return choice


def set_mode(db: Session, device: KudosDevice, mode: str, reason: str = "") -> dict:
    mode = (mode or "auto").lower()
    if mode not in ("auto", "terrestrial", "satellite"):
        mode = "auto"
    setting = db.query(KudosNetworkSetting).filter(KudosNetworkSetting.device_id == device.id).first()
    if setting is None:
        setting = KudosNetworkSetting(device_id=device.id)
        db.add(setting)
    setting.mode = mode
    setting.reason = (reason or "")[:200]
    setting.updated_at = datetime.now(UTC)
    db.commit()
    choice = choose_link(db, device.id)
    choice["io"] = True
    return choice


def status_for_user(db: Session, user_id: int) -> dict:
    devices = db.query(KudosDevice).filter(KudosDevice.user_id == user_id).all()
    out = []
    for d in devices:
        latest = (
            db.query(KudosNetworkState)
            .filter(KudosNetworkState.device_id == d.id)
            .order_by(KudosNetworkState.created_at.desc())
            .first()
        )
        setting = db.query(KudosNetworkSetting).filter(KudosNetworkSetting.device_id == d.id).first()
        out.append(
            {
                "device_id": d.id,
                "device_name": d.name,
                "platform": d.platform,
                "status": d.status,
                "mode": (setting.mode if setting else "auto"),
                "latest": {
                    "primary_transport": latest.primary_transport if latest else "unknown",
                    "transports": latest.transports if latest else "",
                    "signal_dbm": latest.signal_dbm,
                    "metered": latest.metered,
                    "satellite": latest.satellite,
                    "satellite_backhaul": latest.satellite_backhaul,
                    "bandwidth_kbps": latest.bandwidth_kbps,
                    "rtt_ms": latest.rtt_ms,
                    "provider": latest.provider,
                    "reported_at": latest.reported_at.isoformat() if latest and latest.reported_at else None,
                }
                if latest
                else None,
                "choice": choose_link(db, d.id),
            }
        )
    return {"devices": out}


def links_summary(db: Session) -> dict:
    """The world KUDOS's devices are connected through (aggregate)."""
    rows = (
        db.query(
            KudosNetworkState.primary_transport,
            func.count(KudosNetworkState.id),
            func.max(KudosNetworkState.created_at),
        )
        .group_by(KudosNetworkState.primary_transport)
        .all()
    )
    by_transport = {t: {"count": c, "last_reported": ts.isoformat() if ts else None} for t, c, ts in rows}
    device_count = db.query(func.count(KudosDevice.id)).filter(KudosDevice.status == "online").scalar() or 0
    satellite_devices = (
        db.query(func.count(KudosNetworkState.id)).filter(KudosNetworkState.satellite.is_(True)).scalar() or 0
    )
    return {
        "device_count": device_count,
        "by_transport": by_transport,
        "satellite_reports": satellite_devices,
    }


def network_note(db: Session, user: User) -> str:
    """Self-knowledge note: does this user's device ride satellite right now?"""
    state = (
        db.query(KudosNetworkState)
        .filter(KudosNetworkState.user_id == user.id)
        .order_by(KudosNetworkState.created_at.desc())
        .first()
    )
    if not state:
        return ""
    on_sat = bool(state.satellite or state.satellite_backhaul or state.primary_transport == "satellite")
    if not on_sat:
        return ""
    return (
        "- This user's active device is currently on a CONSTRAINED satellite link (Starlink/NTN). "
        "Keep answers brief and low-data. Prefer your offline brain instead of fetching heavy material. "
        "Do NOT generate or download large media, video or long audio for this user right now. "
        "Chunk any long content. Text and compressed audio are fine."
    )


def probe_rtt(host: str = "1.1.1.1", timeout_s: float = 4.0) -> float | None:
    """Optional live RTT check KUDOS can run against any host (honest measure)."""
    import time

    import httpx

    try:
        t0 = time.perf_counter()
        with httpx.Client(timeout=timeout_s) as c:
            c.get(f"https://{host}", follow_redirects=True)
        return round((time.perf_counter() - t0) * 1000, 1)
    except Exception:
        return None
