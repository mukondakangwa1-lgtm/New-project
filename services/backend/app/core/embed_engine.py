"""
KUDOS Embed Engine — Generate embeddable widgets for any website
KUDOS can create embeds that let external sites connect to the platform.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_PATH = str(Path(__file__).resolve().parents[4])

# ──────────────────────────────────────────────
# EMBED TYPES
# ──────────────────────────────────────────────

EMBED_TYPES = {
    "chat": {
        "name": "KUDOS Chat Widget",
        "description": "Embeddable chat widget — users can chat with KUDOS from any website",
        "icon": "💬",
    },
    "courses": {
        "name": "Course Catalog",
        "description": "Display available courses on any site",
        "icon": "📚",
    },
    "attendance": {
        "name": "Attendance Check-in",
        "description": "Let students check in from any device",
        "icon": "✅",
    },
    "announcements": {
        "name": "Announcements Feed",
        "description": "Display latest announcements",
        "icon": "📢",
    },
    "calendar": {
        "name": "Calendar Widget",
        "description": "Show upcoming events and classes",
        "icon": "📅",
    },
    "login": {
        "name": "Login Widget",
        "description": "Embedded login form",
        "icon": "🔑",
    },
    "social_feed": {
        "name": "Social Feed",
        "description": "Display public posts from the Hub",
        "icon": "🌐",
    },
    "kudos": {
        "name": "KUDOS Assistant",
        "description": "Full KUDOS AI chat on any site",
        "icon": "🧠",
    },
}


def generate_embed_code(
    embed_type: str,
    base_url: str,
    options: dict = None,
) -> dict:
    """Generate embed code for a specific widget type."""
    if embed_type not in EMBED_TYPES:
        return {"error": f"Unknown embed type: {embed_type}"}

    options = options or {}
    width = options.get("width", "100%")
    height = options.get("height", "600px")
    theme = options.get("theme", "light")

    if embed_type == "chat":
        return _generate_chat_embed(base_url, width, height, theme)
    elif embed_type == "courses":
        return _generate_courses_embed(base_url, width, height, theme)
    elif embed_type == "attendance":
        return _generate_attendance_embed(base_url, width, height, theme)
    elif embed_type == "announcements":
        return _generate_announcements_embed(base_url, width, height, theme)
    elif embed_type == "calendar":
        return _generate_calendar_embed(base_url, width, height, theme)
    elif embed_type == "login":
        return _generate_login_embed(base_url, width, height, theme)
    elif embed_type == "social_feed":
        return _generate_social_embed(base_url, width, height, theme)
    elif embed_type == "kudos":
        return _generate_kudos_embed(base_url, width, height, theme)

    return {"error": "Embed type not implemented"}


def _generate_chat_embed(base_url, width, height, theme):
    return {
        "type": "chat",
        "name": "KUDOS Chat Widget",
        "html": f'''<!-- Digital Campus - KUDOS Chat Widget -->
<div id="dc-chat-widget" style="position:fixed;bottom:20px;right:20px;z-index:9999;">
  <button onclick="document.getElementById('dc-chat-frame').style.display=document.getElementById('dc-chat-frame').style.display==='none'?'block':'none'"
    style="width:60px;height:60px;border-radius:50%;background:#1e40af;color:white;font-size:24px;border:none;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,0.3);">
    🧠
  </button>
  <iframe id="dc-chat-frame" src="{base_url}/kudos" style="display:none;width:380px;height:500px;border:none;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,0.2);position:absolute;bottom:70px;right:0;"></iframe>
</div>''',
        "script": f'<script src="{base_url}/embed/chat.js"></script>',
        "instructions": "Paste the HTML code before the closing </body> tag on any website.",
    }


def _generate_courses_embed(base_url, width, height, theme):
    return {
        "type": "courses",
        "name": "Course Catalog",
        "html": f'''<!-- Digital Campus - Course Catalog -->
<iframe src="{base_url}/courses" style="width:{width};height:{height};border:none;border-radius:12px;"></iframe>''',
        "instructions": "Paste this iframe code where you want the course catalog to appear.",
    }


def _generate_attendance_embed(base_url, width, height, theme):
    return {
        "type": "attendance",
        "name": "Attendance Check-in",
        "html": f'''<!-- Digital Campus - Attendance Check-in -->
<iframe src="{base_url}/register/attendance" style="width:{width};height:{height};border:none;border-radius:12px;"></iframe>''',
        "instructions": "Students can check in from any device with this embed.",
    }


def _generate_announcements_embed(base_url, width, height, theme):
    return {
        "type": "announcements",
        "name": "Announcements Feed",
        "html": f'''<!-- Digital Campus - Announcements -->
<iframe src="{base_url}/hub/feed" style="width:{width};height:{height};border:none;border-radius:12px;"></iframe>''',
        "instructions": "Shows the latest public posts from the Social Hub.",
    }


def _generate_calendar_embed(base_url, width, height, theme):
    return {
        "type": "calendar",
        "name": "Calendar Widget",
        "html": f'''<!-- Digital Campus - Calendar -->
<iframe src="{base_url}/dashboard" style="width:{width};height:{height};border:none;border-radius:12px;"></iframe>''',
        "instructions": "Displays the user's calendar and upcoming events.",
    }


def _generate_login_embed(base_url, width, height, theme):
    return {
        "type": "login",
        "name": "Login Widget",
        "html": f'''<!-- Digital Campus - Login -->
<iframe src="{base_url}/login" style="width:{width};height:{height};border:none;border-radius:12px;"></iframe>''',
        "instructions": "Embedded login form for user authentication.",
    }


def _generate_social_embed(base_url, width, height, theme):
    return {
        "type": "social_feed",
        "name": "Social Feed",
        "html": f'''<!-- Digital Campus - Social Feed -->
<iframe src="{base_url}/hub/feed" style="width:{width};height:{height};border:none;border-radius:12px;"></iframe>''',
        "instructions": "Displays the public social feed.",
    }


def _generate_kudos_embed(base_url, width, height, theme):
    return {
        "type": "kudos",
        "name": "KUDOS AI Assistant",
        "html": f'''<!-- Digital Campus - KUDOS AI -->
<div id="kudos-embed" style="position:fixed;bottom:20px;right:20px;z-index:9999;">
  <button onclick="toggleKudos()" style="width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#1e40af);color:white;font-size:28px;border:none;cursor:pointer;box-shadow:0 4px 20px rgba(124,58,237,0.4);">
    🧠
  </button>
  <iframe id="kudos-frame" src="{base_url}/kudos" style="display:none;width:400px;height:600px;border:none;border-radius:16px;box-shadow:0 12px 40px rgba(0,0,0,0.3);position:absolute;bottom:80px;right:0;"></iframe>
</div>
<script>
function toggleKudos() {{
  var f = document.getElementById('kudos-frame');
  f.style.display = f.style.display === 'none' ? 'block' : 'none';
}}
</script>''',
        "instructions": "Adds a floating KUDOS AI button to any website. Users click to chat with KUDOS.",
    }


# ──────────────────────────────────────────────
# EMBED API ENDPOINT GENERATION
# ──────────────────────────────────────────────

def generate_api_embed(base_url: str, endpoint: str, format: str = "json") -> dict:
    """Generate an API embed URL that external sites can fetch."""
    embed_url = f"{base_url}/api/v1{endpoint}"
    return {
        "embed_url": embed_url,
        "format": format,
        "fetch_code": f'''// Fetch data from Digital Campus API
const response = await fetch("{embed_url}");
const data = await response.json();
console.log(data);''',
        "iframe_code": f'<iframe src="{embed_url}" style="width:100%;height:400px;border:none;"></iframe>',
    }


# ──────────────────────────────────────────────
# EMBED REGISTRY
# ──────────────────────────────────────────────

_embed_registry: list[dict] = []


def register_embed(embed_type: str, base_url: str, options: dict = None, created_by: int = 0) -> dict:
    """Register an embed and return its configuration."""
    result = generate_embed_code(embed_type, base_url, options)
    if "error" in result:
        return result

    embed_id = len(_embed_registry) + 1
    embed_record = {
        "id": embed_id,
        "type": embed_type,
        "base_url": base_url,
        "options": options or {},
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "views": 0,
    }
    _embed_registry.append(embed_record)

    return {**result, "embed_id": embed_id}


def list_embeds() -> list[dict]:
    """List all registered embeds."""
    return _embed_registry


def get_embed_types() -> list[dict]:
    """Get all available embed types."""
    return [
        {"id": k, "name": v["name"], "description": v["description"], "icon": v["icon"]}
        for k, v in EMBED_TYPES.items()
    ]
