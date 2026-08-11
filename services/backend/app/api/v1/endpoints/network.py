"""
Digital Campus - KUDOS Link Switching API

KUDOS switches each connected device between terrestrial (Wi-Fi / cellular)
and satellite (Starlink / Android NTN) networks. Devices report the links they
ACTUALLY see; KUDOS records, grades the tier and applies the switch mode.

Endpoints:
  GET  /network/status  — per-device link + switch state for the user
  GET  /network/links   — aggregate view of what KUDOS's devices are on
  POST /network/report  — device reports its current measured link
  POST /network/mode    — set the switch mode (auto / terrestrial / satellite)
  POST /network/probe   — live RTT probe to any host (honest measurement)
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import network_mesh
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.device_storage import get_device_by_token
from app.models import KudosDevice, User

router = APIRouter()


class NetworkReport(BaseModel):
    primary_transport: str = Field("unknown", description="wifi | cellular | satellite | ethernet | unknown")
    transports: list[str] | None = None
    signal_dbm: int | None = Field(None, ge=-140, le=0)
    metered: bool | None = True
    constrained: bool = False
    satellite: bool = False
    satellite_backhaul: bool = False
    bandwidth_kbps: int | None = Field(None, ge=0, le=100_000_000)
    rtt_ms: float | None = Field(None, ge=0, le=60000)
    provider: str = ""
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
def network_status(
    x_device_token: str = Header(default="", alias="X-Device-Token"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-device link + switch state for the current user (or one device)."""
    if x_device_token:
        device, _ = _resolve_device(db, x_device_token, current_user)
        status = network_mesh.status_for_user(db, device.user_id)
        status["devices"] = [d for d in status["devices"] if d["device_id"] == device.id]
        return status
    return network_mesh.status_for_user(db, current_user.id)


@router.get("/links")
def network_links(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The aggregate connectivity world KUDOS sees across its devices."""
    return {
        "mesh": network_mesh.links_summary(db),
        "tiers": {
            t: network_mesh.tier_label(t)
            for t in ("ethernet", "wifi", "cellular", "satellite", "unknown")
        },
    }


@router.post("/report")
def network_report(
    body: NetworkReport,
    x_device_token: str = Header(default="", alias="X-Device-Token"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """A device reports its measured link; KUDOS decides the switch."""
    device = None
    if body.device_id:
        device = db.get(KudosDevice, body.device_id)
        if not device or device.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Device not found")
    elif x_device_token:
        device, current_user = _resolve_device(db, x_device_token, current_user)
    if device is None:
        raise HTTPException(status_code=400, detail="Register a KUDOS device first, or pass a device_id")

    payload = body.model_dump()
    return network_mesh.record_state(db, device, current_user.id, payload)


@router.post("/mode")
def network_mode(
    mode: str = Query("auto", description="auto | terrestrial | satellite"),
    reason: str = Query("", max_length=200),
    device_id: int | None = Query(None),
    x_device_token: str = Header(default="", alias="X-Device-Token"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Switch how KUDOS picks the link for a device."""
    device = None
    if device_id:
        device = db.get(KudosDevice, device_id)
        if not device or device.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Device not found")
    elif x_device_token:
        device, current_user = _resolve_device(db, x_device_token, current_user)
    if device is None:
        raise HTTPException(status_code=400, detail="Register a KUDOS device first, or pass a device_id")
    return network_mesh.set_mode(db, device, mode, reason)


@router.post("/probe")
def network_probe(
    host: str = Query("1.1.1.1", max_length=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Live RTT probe KUDOS runs to measure a link honestly."""
    rtt = network_mesh.probe_rtt(host)
    if rtt is None:
        return {"measured": False, "host": host, "rtt_ms": None,
                "detail": "unreachable — switch link or try again"}
    return {"measured": True, "host": host, "rtt_ms": rtt, "tier_hint": "satellite" if rtt > 60 else "terrestrial"}