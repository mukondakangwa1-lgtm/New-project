# KUDOS Device Sync Protocol

How any device (phone, laptop, desktop) connects to Digital Campus, lends its
storage to KUDOS, and keeps its memory replicas up to date.

Server-side implementation: `services/backend/app/core/device_storage.py`
and `services/backend/app/api/v1/endpoints/devices.py`.

---

## 1. Concepts

- **Device** — a registered client that volunteered storage space (default
  512 MB). Each device has a `status`: `online` | `offline` | `retired`.
- **Memory** — one unit of KUDOS's knowledge (`kudos_memories`). Every memory
  has a `device_policy`:
  - `local` — never leaves the server (Postgres is the only copy).
  - `replicated` (default) — one primary + one replica on live devices.
  - `critical` — three copies across devices.
- **Replica** — one copy of a memory held by one device; statuses:
  `pending` (created, not pulled yet), `current` (device acknowledged),
  `stale` (memory changed server-side since last pull).
- **Ring** — devices sorted by hashed ID (`md5("device:{id}")`). Memory
  placement is deterministic: `md5("memory:{id}") % len(ring)` picks the
  primary, walking the ring for further copies. Any device can compute where
  a memory lives — no scanning required. That is the "efficient lookup".

## 2. Registration

```
POST /api/v1/kudos/devices           (user auth)
{
  "name": "Pixel 8",
  "platform": "android",             // android|ios|desktop|web|linux
  "storage_bytes": 1073741824
}
→ 201
{
  "id": 17, "name": "Pixel 8", "platform": "android",
  "status": "online",
  "storage_bytes": ..., "used_storage_bytes": 0,
  "api_token": "<64-hex>",           // STORE THIS — shown only once
}
```

- The `api_token` is the device's credential for sync endpoints.
  Re-registering the same `name` keeps the token if one exists.
- Store the token in secure device storage (Keychain / Keystore / Keyring).
  There is no UI to re-read it; rotate by retiring and re-registering.

## 3. Management (user JWT)

```
GET    /api/v1/kudos/devices                     → fleet list
PATCH  /api/v1/kudos/devices/{id}                → rename / report storage
DELETE /api/v1/kudos/devices/{id}                → retire + free replicas
```

- `PATCH` with `{"status":"offline"}` marks the device offline (used by the
  client on shutdown). Its replicas stay until retire or reconcile.
- `DELETE` retires the device: status `retired`, token revoked, all its
  replicas removed. The remaining ring absorbs the freed copies on the next
  `reconcile`.

## 4. Sync (device token auth)

All sync calls authenticate with the device token:

```
X-Device-Token: <api_token>
```

### Pull the manifest

```
GET /api/v1/kudos/sync/manifest
→ 200
{
  "device_id": 17,
  "entries": [
    {
      "memory_id": 42,
      "content": "I prefer morning study…",
      "layer": "long_term",
      "kind": "preference",
      "importance": 0.7,
      "tags": "[\"study\"]",
      "source": "conversation",
      "summary": "",
      "expires_at": null,
      "device_role": "primary",      // primary | replica
      "device_status": "pending",    // pending | stale
      "embedding": null              // only when SEMANTIC_SEARCH_ENABLED
    }
  ]
}
```

Only entries the device does **not** have yet (`pending`) or must refresh
(`stale`) are returned — clients poll this endpoint, store everything, then:

### Acknowledge

```
POST /api/v1/kudos/sync/ack
{ "memory_ids": [42] }
→ { "acknowledged": 1 }
```

Acknowledged replicas become `current`; sync status (`/kudos/sync/status`)
counts them for the `healthy_replicated` figure.

### Rebalance

```
POST /api/v1/kudos/sync/reconcile    (user JWT)
```

Ensures every memory has its policy-defined set of replicas on live devices.
Call after device losses. Assignments also happen automatically on every
memory write.

## 5. Client behavior (recommended)

1. On app start: `POST /kudos/devices` (idempotent) — refreshes `online`.
2. On `PATCH`-able events: report `used_storage_bytes` from disk usage.
3. On idle/battery-friendly moments: `GET /kudos/sync/manifest`;
   store entries locally (SQLite/SQLite file, or any key-value store);
   `POST /kudos/sync/ack`. Retry with backoff (1s → 60s) on network errors.
4. On shutdown / offline signal: `PATCH {"status":"offline"}`.
5. Local retrieval suggestion: keep an index over `memory_id → path` so a
   user query can hit the device's own copies first; the server remains the
   authority and reconciles divergence via `updated_at` + reconcile.

## 6. Security notes

- Device tokens are 128-bit random, stored hashed optionally; never returned
  after registration. Retiring a device revokes its token.
- All sync endpoints enforce that the token's `user_id` matches the replicas
  being pulled — a user B device can never see user A's memory
  (even with A's token leaked — ownership is re-verified per row).
- Replicas never contain secrets: secret values should use `local` policy or
  stay outside memory entirely.