"""
Digital Campus - KUDOS Network Doctor (client)

Talks to the `networkops` sidecar container (docker CLI + docker.sock) so
KUDOS can diagnose and heal the network (Tailscale funnel, TLS probe, DERP,
container health). Disabled when NETWORKOPS_URL is empty.
"""
import httpx

from app.core.config import settings

_TIMEOUT = 20.0


def _enabled() -> bool:
    return bool(settings.NETWORKOPS_URL.strip())


async def network_status() -> dict:
    if not _enabled():
        return {"error": "networkops sidecar not configured (set NETWORKOPS_URL)"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.get(f"{settings.NETWORKOPS_URL.rstrip('/')}/status")
            return res.json() if res.status_code == 200 else {"error": f"sidecar status {res.status_code}"}
    except Exception as e:
        return {"error": f"networkops unreachable: {e}"}


async def network_diagnose() -> dict:
    if not _enabled():
        return {"error": "networkops sidecar not configured (set NETWORKOPS_URL)"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT + 10) as client:
            res = await client.post(f"{settings.NETWORKOPS_URL.rstrip('/')}/diagnose")
            return res.json() if res.status_code == 200 else {"error": f"sidecar diagnose {res.status_code}"}
    except Exception as e:
        return {"error": f"networkops unreachable: {e}"}


async def network_fix() -> dict:
    if not _enabled():
        return {"error": "networkops sidecar not configured (set NETWORKOPS_URL)"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT + 30) as client:
            res = await client.post(f"{settings.NETWORKOPS_URL.rstrip('/')}/fix")
            return res.json() if res.status_code == 200 else {"error": f"sidecar fix {res.status_code}"}
    except Exception as e:
        return {"error": f"networkops unreachable: {e}"}


async def network_events(limit: int = 50) -> dict:
    if not _enabled():
        return {"error": "networkops sidecar not configured (set NETWORKOPS_URL)"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.get(f"{settings.NETWORKOPS_URL.rstrip('/')}/events", params={"limit": limit})
            return res.json() if res.status_code == 200 else {"error": f"sidecar events {res.status_code}"}
    except Exception as e:
        return {"error": f"networkops unreachable: {e}"}
