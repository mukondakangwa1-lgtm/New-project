"""KUDOS device storage API — register devices, replicate memories, sync.

Devices lend their storage to KUDOS. The sync endpoints authenticate with the
device's own API token (X-Device-Token header), the rest with the user token.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.device_storage import (
    ack_pull,
    get_device_by_token,
    mark_offline,
    pull_manifest,
    reconcile,
    register_device,
    retire_device,
    sync_status,
)
from app.models import KudosDevice, User
from app.schemas.schemas import (
    DeviceCreate,
    DeviceResponse,
    DeviceUpdate,
    SyncAckRequest,
    SyncAckResponse,
    SyncManifestResponse,
    SyncStatusResponse,
)

router = APIRouter()
sync_router = APIRouter()


def _device_from_token(
    db: Session,
    token: str,
) -> KudosDevice:
    device = get_device_by_token(db, token)
    if not device:
        raise HTTPException(status_code=401, detail="Unknown device token")
    return device


@router.post("", response_model=DeviceResponse, status_code=201)
def register_device_endpoint(
    body: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register a device whose storage KUDOS can use for memory replicas."""
    device = register_device(
        db,
        user_id=current_user.id,
        name=body.name,
        platform=body.platform,
        storage_bytes=body.storage_bytes,
    )
    return DeviceResponse(
        id=device.id,
        name=device.name,
        platform=device.platform,
        status=device.status,
        storage_bytes=device.storage_bytes,
        used_storage_bytes=device.used_storage_bytes or 0,
        last_seen_at=device.last_seen_at,
        api_token=device.api_token,
    )


@router.get("", response_model=list[DeviceResponse])
def list_devices_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    devices = db.query(KudosDevice).filter(KudosDevice.user_id == current_user.id).all()
    return [
        DeviceResponse(
            id=d.id,
            name=d.name,
            platform=d.platform,
            status=d.status,
            storage_bytes=d.storage_bytes,
            used_storage_bytes=d.used_storage_bytes or 0,
            last_seen_at=d.last_seen_at,
        )
        for d in devices
    ]


@router.patch("/{device_id}", response_model=DeviceResponse)
def update_device_endpoint(
    device_id: int,
    body: DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = (
        db.query(KudosDevice)
        .filter(
            KudosDevice.id == device_id,
            KudosDevice.user_id == current_user.id,
        )
        .first()
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if body.name is not None:
        device.name = body.name
    if body.used_storage_bytes is not None:
        device.used_storage_bytes = body.used_storage_bytes
    if body.status == "offline":
        mark_offline(db, device)
    else:
        db.commit()
    return DeviceResponse(
        id=device.id,
        name=device.name,
        platform=device.platform,
        status=device.status,
        storage_bytes=device.storage_bytes,
        used_storage_bytes=device.used_storage_bytes or 0,
        last_seen_at=device.last_seen_at,
    )


@router.delete("/{device_id}", status_code=200)
def delete_device_endpoint(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = (
        db.query(KudosDevice)
        .filter(
            KudosDevice.id == device_id,
            KudosDevice.user_id == current_user.id,
        )
        .first()
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    released = retire_device(db, device)
    return {"released_memories": released}


@sync_router.get("/manifest", response_model=SyncManifestResponse)
def sync_manifest_endpoint(
    x_device_token: str = Header(default="", alias="X-Device-Token"),
    db: Session = Depends(get_db),
):
    """Everything this device must store locally (pending/stale replicas)."""
    device = _device_from_token(db, x_device_token)
    entries = pull_manifest(db, device)
    return SyncManifestResponse(device_id=device.id, entries=entries)


@sync_router.post("/ack", response_model=SyncAckResponse)
def sync_ack_endpoint(
    body: SyncAckRequest,
    x_device_token: str = Header(default="", alias="X-Device-Token"),
    db: Session = Depends(get_db),
):
    """Confirm a device stored the pulled memories."""
    device = _device_from_token(db, x_device_token)
    acknowledged = ack_pull(db, device, body.memory_ids)
    return SyncAckResponse(acknowledged=acknowledged)


@sync_router.get("/status", response_model=SyncStatusResponse)
def sync_status_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Replication health across the user's devices."""
    return sync_status(db, current_user.id)


@sync_router.post("/reconcile")
def sync_reconcile_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-balance replica sets after device changes."""
    return reconcile(db, current_user.id)
