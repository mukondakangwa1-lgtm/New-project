"""Device storage: replicate KUDOS memories across a user's registered devices.

Placement uses a consistent-hash ring over online devices so any device can
find which memory belongs where without scanning every node. Replicas are
pulled by the device (the server never pushes); Postgres stays the
authoritative store and the ring is the efficient lookup index.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from app.core.config import settings
from app.models import KudosDevice, KudosMemory, KudosMemoryReplica

REPLICA_COPIES = {"local": 1, "replicated": 2, "critical": 3}
DEFAULT_CAPACITY_BYTES = 512 * 1024 * 1024


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_seed(seed: str) -> int:
    return int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16)


def register_device(
    db,
    user_id: int | None,
    name: str,
    platform: str = "generic",
    storage_bytes: int = DEFAULT_CAPACITY_BYTES,
    api_token: str | None = None,
) -> KudosDevice:
    """Register a device that lends its storage to KUDOS.

    Anonymous devices (user_id=None) are keyed purely by their API token so a
    guest browser can report its link without an account; a returned token is
    always unique and the device stays bound to that token until retired.
    """
    if user_id is None:
        token = api_token or secrets.token_hex(16)
        device = (
            db.execute(
                select(KudosDevice).where(
                    KudosDevice.api_token == token,
                    KudosDevice.status != "retired",
                )
            )
            .scalars()
            .first()
        )
        if device is None:
            device = KudosDevice(
                user_id=None,
                name=name,
                platform=platform,
                api_token=token,
                status="online",
                storage_bytes=storage_bytes,
                last_seen_at=_now(),
            )
            db.add(device)
        device.status = "online"
        device.last_seen_at = _now()
        db.commit()
        db.refresh(device)
        return device

    existing = (
        db.execute(
            select(KudosDevice).where(
                KudosDevice.user_id == user_id,
                KudosDevice.name == name,
                KudosDevice.status != "retired",
            )
        )
        .scalars()
        .all()
    )
    if existing:
        device = existing[0]
        if not device.api_token:
            device.api_token = api_token or secrets.token_hex(16)
        device.status = "online"
        device.last_seen_at = _now()
    else:
        device = KudosDevice(
            user_id=user_id,
            name=name,
            platform=platform,
            api_token=api_token or secrets.token_hex(16),
            status="online",
            storage_bytes=storage_bytes,
            last_seen_at=_now(),
        )
        db.add(device)
    db.commit()
    db.refresh(device)
    return device


def get_device_by_token(db, token: str) -> KudosDevice | None:
    if not token:
        return None
    return (
        db.execute(
            select(KudosDevice).where(
                KudosDevice.api_token == token,
                KudosDevice.status != "retired",
            )
        )
        .scalars()
        .first()
    )


def _ring(db, user_id: int) -> list[KudosDevice]:
    """Active devices sorted by hashed ID — the consistent-hash ring."""
    devices = (
        db.execute(
            select(KudosDevice).where(
                KudosDevice.user_id == user_id,
                KudosDevice.status == "online",
            )
        )
        .scalars()
        .all()
    )
    return sorted(devices, key=lambda d: _hash_seed(f"device:{d.id}"))


def _pick_targets(ring: list[KudosDevice], memory_id: int, copies: int) -> list[KudosDevice]:
    """Deterministically pick `copies` devices from the ring for a memory."""
    if not ring:
        return []
    start = _hash_seed(f"memory:{memory_id}") % len(ring)
    picks = []
    for i in range(len(ring)):
        if len(picks) >= copies:
            break
        device = ring[(start + i) % len(ring)]
        if device not in picks:
            picks.append(device)
    return picks


def assign_replicas(db, memory: KudosMemory) -> int:
    """Create replica rows for a memory on its ring targets.

    Also removes rows for devices no longer in the target set (a device left
    the ring). Returns the number of replica rows created.
    """
    policy = (memory.device_policy or "replicated").lower()
    if policy == "local":
        # local-only memories never leave the authoritative store
        for replica in (
            db.execute(select(KudosMemoryReplica).where(KudosMemoryReplica.memory_id == memory.id)).scalars().all()
        ):
            db.delete(replica)
        db.commit()
        return 0
    copies = REPLICA_COPIES.get(policy, REPLICA_COPIES["replicated"])
    ring = _ring(db, memory.user_id)
    targets = _pick_targets(ring, memory.id, copies)

    target_ids = {d.id for d in targets}
    current = db.execute(select(KudosMemoryReplica).where(KudosMemoryReplica.memory_id == memory.id)).scalars().all()

    for replica in current:
        if replica.device_id not in target_ids:
            db.delete(replica)

    existing_device_ids = {r.device_id for r in current}
    created = 0
    for idx, device in enumerate(targets):
        if device.id not in existing_device_ids:
            db.add(
                KudosMemoryReplica(
                    memory_id=memory.id,
                    device_id=device.id,
                    user_id=memory.user_id,
                    role="primary" if idx == 0 else "replica",
                    status="pending",
                )
            )
            created += 1
    db.commit()
    return created


def pull_manifest(db, device: KudosDevice) -> list[dict[str, Any]]:
    """Entries this device must have locally: pending or stale replicas."""
    rows = db.execute(
        select(KudosMemoryReplica, KudosMemory)
        .join(KudosMemory, KudosMemory.id == KudosMemoryReplica.memory_id)
        .where(
            KudosMemoryReplica.device_id == device.id,
            KudosMemoryReplica.user_id == device.user_id,
            KudosMemoryReplica.status.in_(["pending", "stale"]),
        )
    ).all()
    entries = []
    for replica, memory in rows:
        entry: dict[str, Any] = {
            "memory_id": memory.id,
            "content": memory.content,
            "layer": memory.layer,
            "kind": memory.kind,
            "importance": float(memory.importance or 0.5),
            "tags": memory.tags or "[]",
            "source": memory.source or "",
            "summary": memory.summary or "",
            "expires_at": memory.expires_at.isoformat() if memory.expires_at else None,
            "device_role": replica.role,
            "device_status": replica.status,
        }
        if settings.SEMANTIC_SEARCH_ENABLED and memory.embedding:
            try:
                embedding = memory.embedding
                if isinstance(embedding, str):
                    embedding = json.loads(embedding)
                entry["embedding"] = embedding
            except Exception:
                pass
        entries.append(entry)
    return entries


def ack_pull(db, device: KudosDevice, memory_ids: list[int]) -> int:
    """Mark replicas as acknowledged after the device stored them."""
    rows = (
        db.execute(
            select(KudosMemoryReplica).where(
                KudosMemoryReplica.device_id == device.id,
                KudosMemoryReplica.user_id == device.user_id,
                KudosMemoryReplica.memory_id.in_(memory_ids),
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        row.status = "current"
        row.synced_at = _now()
    device.last_seen_at = _now()
    db.commit()
    return len(rows)


def mark_offline(db, device: KudosDevice) -> None:
    device.status = "offline"
    device.last_seen_at = _now()
    db.commit()


def retire_device(db, device: KudosDevice) -> int:
    """Take a device out of the ring, freeing its replicas for re-balance.
    Returns the number of memories whose replicas were released."""
    device.status = "retired"
    device.api_token = ""
    replicas = db.execute(select(KudosMemoryReplica).where(KudosMemoryReplica.device_id == device.id)).scalars().all()
    released = len(replicas)
    for r in replicas:
        db.delete(r)
    db.commit()
    return released


def purge_memory_replicas(db, memory_id: int) -> int:
    rows = db.execute(select(KudosMemoryReplica).where(KudosMemoryReplica.memory_id == memory_id)).scalars().all()
    for row in rows:
        db.delete(row)
    db.commit()
    return len(rows)


def reconcile(db, user_id: int) -> dict[str, int]:
    """Ensure every memory has its policy-defined replica set on live devices."""
    memories = db.execute(select(KudosMemory).where(KudosMemory.user_id == user_id)).scalars().all()
    created = 0
    for memory in memories:
        created += assign_replicas(db, memory)
    row_count = (
        db.execute(
            select(func.count()).select_from(KudosMemoryReplica).where(KudosMemoryReplica.user_id == user_id)
        ).scalar()
        or 0
    )
    return {"created": created, "replicas": int(row_count)}


def memory_replica_map(db, user_id: int, memory_ids: list[int]) -> dict[int, list[dict]]:
    """Device info per memory for the retrieval view."""
    rows = db.execute(
        select(KudosMemoryReplica, KudosDevice)
        .join(KudosDevice, KudosDevice.id == KudosMemoryReplica.device_id)
        .where(
            KudosMemoryReplica.user_id == user_id,
            KudosMemoryReplica.memory_id.in_(memory_ids),
        )
    ).all()
    out: dict[int, list[dict]] = {}
    for replica, device in rows:
        out.setdefault(replica.memory_id, []).append(
            {
                "device_id": device.id,
                "device_name": device.name,
                "role": replica.role,
                "status": replica.status,
            }
        )
    return out


def sync_status(db, user_id: int) -> dict[str, Any]:
    """Storage/replication health for a user's device fleet."""
    devices = db.execute(select(KudosDevice).where(KudosDevice.user_id == user_id)).scalars().all()
    device_rows = []
    for device in devices:
        replicas = (
            db.execute(select(KudosMemoryReplica).where(KudosMemoryReplica.device_id == device.id)).scalars().all()
        )
        device_rows.append(
            {
                "id": device.id,
                "name": device.name,
                "status": device.status,
                "replicas_held": len(replicas),
                "pending": sum(1 for r in replicas if r.status == "pending"),
                "storage_used_bytes": device.used_storage_bytes or 0,
                "storage_capacity_bytes": device.storage_bytes or 0,
            }
        )

    memories = db.execute(select(KudosMemory).where(KudosMemory.user_id == user_id)).scalars().all()
    healthy = 0
    for memory in memories:
        if memory.device_policy == "local":
            continue
        copies = (
            db.execute(
                select(func.count())
                .select_from(KudosMemoryReplica)
                .where(
                    KudosMemoryReplica.memory_id == memory.id,
                    KudosMemoryReplica.status == "current",
                )
            ).scalar()
            or 0
        )
        needed = REPLICA_COPIES.get(memory.device_policy or "replicated", 1)
        if int(copies) >= needed:
            healthy += 1
    return {
        "devices": device_rows,
        "total_memories": len(memories),
        "healthy_replicated": healthy,
        "last_check": _now().isoformat(),
    }
