"""
KUDOS Device Analyzer — Analyze connecting devices, learn, and protect
Fingerprints devices, monitors connections, learns patterns, blocks threats.
"""
import hashlib
import json
import os
import platform
import socket
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional


# ──────────────────────────────────────────────
# DEVICE REGISTRY
# ──────────────────────────────────────────────

_connected_devices: dict[str, dict] = {}
_device_history: list[dict] = []
_connection_log: list[dict] = []
_blocked_devices: set = set()
_device_fingerprints: dict[str, str] = {}


def _log(category: str, message: str, severity: str = "info"):
    _connection_log.append({
        "category": category,
        "message": message,
        "severity": severity,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(_connection_log) > 1000:
        _connection_log[:] = _connection_log[-500:]


# ──────────────────────────────────────────────
# DEVICE FINGERPRINTING
# ──────────────────────────────────────────────

def fingerprint_request(request_data: dict) -> dict:
    """Create a fingerprint from an incoming request."""
    components = [
        request_data.get("user_agent", ""),
        request_data.get("accept_language", ""),
        request_data.get("accept_encoding", ""),
        request_data.get("ip", ""),
    ]
    fingerprint = hashlib.sha256("|".join(components).encode()).hexdigest()[:16]

    device = {
        "fingerprint": fingerprint,
        "ip": request_data.get("ip", "unknown"),
        "user_agent": request_data.get("user_agent", "unknown"),
        "accept_language": request_data.get("accept_language", "unknown"),
        "first_seen": datetime.now(timezone.utc).isoformat(),
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "request_count": 1,
        "pages_visited": [],
        "is_bot": _detect_bot(request_data.get("user_agent", "")),
        "os": _detect_os(request_data.get("user_agent", "")),
        "browser": _detect_browser(request_data.get("user_agent", "")),
        "threat_level": "low",
    }

    if fingerprint in _connected_devices:
        existing = _connected_devices[fingerprint]
        existing["last_seen"] = datetime.now(timezone.utc).isoformat()
        existing["request_count"] += 1
        return existing

    _connected_devices[fingerprint] = device
    _device_history.append(device)
    _log("device", f"New device: {device['os']} {device['browser']} from {device['ip']}")
    return device


def _detect_bot(user_agent: str) -> bool:
    """Detect if request is from a bot."""
    bot_indicators = ["bot", "crawler", "spider", "scraper", "curl", "wget", "python-requests", "httpx"]
    return any(indicator in user_agent.lower() for indicator in bot_indicators)


def _detect_os(user_agent: str) -> str:
    """Detect operating system from user agent."""
    ua = user_agent.lower()
    if "windows" in ua:
        return "Windows"
    elif "mac os" in ua or "macos" in ua:
        return "macOS"
    elif "linux" in ua:
        if "android" in ua:
            return "Android"
        return "Linux"
    elif "iphone" in ua or "ipad" in ua:
        return "iOS"
    elif "android" in ua:
        return "Android"
    return "Unknown"


def _detect_browser(user_agent: str) -> str:
    """Detect browser from user agent."""
    ua = user_agent.lower()
    if "firefox" in ua:
        return "Firefox"
    elif "edg" in ua:
        return "Edge"
    elif "chrome" in ua:
        return "Chrome"
    elif "safari" in ua:
        return "Safari"
    elif "opera" in ua or "opr" in ua:
        return "Opera"
    elif "brave" in ua:
        return "Brave"
    return "Unknown"


# ──────────────────────────────────────────────
# NETWORK ANALYSIS
# ──────────────────────────────────────────────

def get_system_info() -> dict:
    """Get information about the system KUDOS is running on."""
    info = {
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
    }

    try:
        info["ip_address"] = socket.gethostbyname(socket.gethostname())
    except Exception:
        info["ip_address"] = "unknown"

    try:
        import shutil
        disk = shutil.disk_usage("/")
        info["disk_total_gb"] = round(disk.total / (1024**3), 1)
        info["disk_free_gb"] = round(disk.free / (1024**3), 1)
    except Exception:
        pass

    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
            total = int(lines[0].split()[1]) / 1024  # MB
            available = int(lines[2].split()[1]) / 1024
            info["ram_total_mb"] = round(total)
            info["ram_available_mb"] = round(available)
            info["ram_usage_percent"] = round((1 - available / total) * 100, 1)
    except Exception:
        pass

    return info


def get_network_info() -> dict:
    """Get network information."""
    info = {"interfaces": [], "connections": []}

    try:
        result = subprocess.run(["ip", "addr"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info["interfaces_raw"] = result.stdout[:2000]
    except Exception:
        pass

    try:
        result = subprocess.run(["ss", "-tuln"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info["listening_ports"] = result.stdout[:2000]
    except Exception:
        pass

    return info


def scan_open_ports(host: str = "127.0.0.1", ports: list[int] = None) -> list[dict]:
    """Scan common ports on a host."""
    if ports is None:
        ports = [22, 80, 443, 3000, 3306, 5432, 8000, 8080, 8443]

    open_ports = []
    for port in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            if result == 0:
                service = _guess_service(port)
                open_ports.append({"port": port, "status": "open", "service": service})
            sock.close()
        except Exception:
            pass

    return open_ports


def _guess_service(port: int) -> str:
    """Guess service name from port number."""
    services = {
        22: "SSH", 80: "HTTP", 443: "HTTPS", 3000: "Dev Server",
        3306: "MySQL", 5432: "PostgreSQL", 6379: "Redis",
        8000: "Python Server", 8080: "HTTP Alt", 8443: "HTTPS Alt",
        27017: "MongoDB", 5672: "RabbitMQ", 9200: "Elasticsearch",
    }
    return services.get(port, "Unknown")


# ──────────────────────────────────────────────
# THREAT DETECTION
# ──────────────────────────────────────────────

def analyze_threat(device: dict) -> str:
    """Analyze threat level of a device."""
    score = 0

    # Bot detection
    if device.get("is_bot"):
        score += 30

    # High request count
    if device.get("request_count", 0) > 100:
        score += 20

    # Unknown user agent
    if device.get("user_agent") == "unknown":
        score += 40

    # Known malicious patterns
    ua = device.get("user_agent", "").lower()
    malicious = ["sqlmap", "nikto", "nmap", "masscan", "zgrab", "nuclei"]
    if any(m in ua for m in malicious):
        score += 80

    if score >= 70:
        return "critical"
    elif score >= 40:
        return "high"
    elif score >= 20:
        return "medium"
    return "low"


def block_device(fingerprint: str):
    """Block a device by fingerprint."""
    _blocked_devices.add(fingerprint)
    _log("security", f"Blocked device: {fingerprint}", "warning")


def is_device_blocked(fingerprint: str) -> bool:
    """Check if a device is blocked."""
    return fingerprint in _blocked_devices


# ──────────────────────────────────────────────
# DEVICE REPORT
# ──────────────────────────────────────────────

def get_device_report() -> dict:
    """Generate a device connection report."""
    devices = list(_connected_devices.values())
    return {
        "total_devices": len(devices),
        "active_devices": len([d for d in devices if _is_active(d)]),
        "bots_detected": len([d for d in devices if d.get("is_bot")]),
        "blocked_devices": len(_blocked_devices),
        "os_breakdown": _count_by_field(devices, "os"),
        "browser_breakdown": _count_by_field(devices, "browser"),
        "threat_levels": _count_by_field(devices, "threat_level"),
        "recent_devices": sorted(devices, key=lambda d: d.get("last_seen", ""), reverse=True)[:10],
    }


def _is_active(device: dict) -> bool:
    """Check if device was active in last 30 minutes."""
    try:
        last = datetime.fromisoformat(device.get("last_seen", ""))
        return (datetime.now(timezone.utc) - last).total_seconds() < 1800
    except Exception:
        return False


def _count_by_field(devices: list, field: str) -> dict:
    """Count devices by a field value."""
    counts = {}
    for d in devices:
        val = d.get(field, "unknown")
        counts[val] = counts.get(val, 0) + 1
    return counts


def get_device_log(limit: int = 50) -> list[dict]:
    """Get connection log."""
    return _connection_log[-limit:]


def get_connected_devices() -> list[dict]:
    """Get all connected devices."""
    return list(_connected_devices.values())
