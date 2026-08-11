"""
Digital Campus - KUDOS Video Generation

Generates videos up to ``MAX_VIDEO_SECONDS`` (5 minutes) using whichever
provider is configured:

- Google Veo via the Gemini API (long-running operation + polling).
- OpenAI Sora via /videos/generations (async job + polling).

Videos longer than a single clip are produced by generating consecutive clips
and stitching them with ffmpeg (when available). Without ffmpeg the clips are
returned as a playlist the frontend plays back-to-back.
"""

import base64
import shutil
import subprocess
import tempfile

import httpx

from app.core.config import settings
from app.core.llm_engine import get_api_key

_OPERATION_SLEEP = 3.0
_OPERATION_MAX_WAIT = 300  # seconds


async def _poll_operation(client: httpx.AsyncClient, name: str, api_key: str) -> dict:
    """Poll a Gemini long-running operation until it finishes."""
    import asyncio

    base = "https://generativelanguage.googleapis.com/v1beta"
    endpoint = f"{base}/operations/{name}?key={api_key}"
    for _ in range(int(_OPERATION_MAX_WAIT / _OPERATION_SLEEP)):
        res = await client.get(endpoint)
        if res.status_code != 200:
            return {"error": f"Operation poll failed ({res.status_code})"}
        data = res.json()
        if data.get("done"):
            return data
        await asyncio.sleep(_OPERATION_SLEEP)
    return {"error": "Operation timed out"}


async def _veo_clips(prompt: str, clip_count: int) -> list[dict]:
    api_key = get_api_key("google_gemini")
    if not api_key:
        return []
    clips: list[dict] = []
    base = "https://generativelanguage.googleapis.com/v1beta/models"
    async with httpx.AsyncClient(timeout=60) as client:
        for _ in range(clip_count):
            res = await client.post(
                f"{base}/{settings.GEMINI_VIDEO_MODEL}:predictLongRunning?key={api_key}",
                json={
                    "instances": [{"prompt": prompt}],
                    "parameters": {"durationSeconds": settings.VIDEO_CLIP_MAX_SECONDS, "aspectRatio": "16:9"},
                },
            )
            if res.status_code != 200:
                break
            name = res.json().get("name")
            if not name:
                break
            done = await _poll_operation(client, name, api_key)
            if done.get("error"):
                break
            samples = done.get("response", {}).get("generatedSamples", [])
            if not samples:
                break
            video = samples[0].get("video", {})
            uri = video.get("uri")
            mime = video.get("mimeType", "video/mp4")
            if uri:
                dl = await client.get(uri)
                if dl.status_code == 200:
                    clips.append({"data": base64.b64encode(dl.content).decode(), "mime_type": mime})
    return clips


async def _sora_clips(prompt: str, clip_count: int) -> list[dict]:
    api_key = get_api_key("openai")
    if not api_key:
        return []
    clips: list[dict] = []
    async with httpx.AsyncClient(timeout=60) as client:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        for _ in range(clip_count):
            res = await client.post(
                "https://api.openai.com/v1/videos/generations",
                json={"model": settings.OPENAI_VIDEO_MODEL, "prompt": prompt, "size": "1280x720"},
                headers=headers,
            )
            if res.status_code != 200:
                break
            vid_id = res.json().get("id")
            if not vid_id:
                break
            for _ in range(int(_OPERATION_MAX_WAIT / _OPERATION_SLEEP)):
                status_res = await client.get(f"https://api.openai.com/v1/videos/{vid_id}", headers=headers)
                if status_res.status_code != 200:
                    break
                status = status_res.json()
                if status.get("status") == "completed":
                    for out in status.get("output", []):
                        dl = await client.get(out.get("url", ""))
                        if dl.status_code == 200:
                            clips.append({"data": base64.b64encode(dl.content).decode(), "mime_type": "video/mp4"})
                    break
                if status.get("status") in ("failed", "cancelled"):
                    break
            else:
                break
    return clips


def _stitch_clips(clips: list[dict]) -> bytes | None:
    """Concatenate clip bytes with ffmpeg. Returns None if ffmpeg is missing."""
    if not shutil.which("ffmpeg") or len(clips) < 2:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for i, clip in enumerate(clips):
            p = f"{tmp}/clip{i}.mp4"
            with open(p, "wb") as f:
                f.write(base64.b64decode(clip["data"]))
            paths.append(p)
        list_file = f"{tmp}/list.txt"
        with open(list_file, "w") as f:
            for p in paths:
                f.write(f"file '{p}'\n")
        out = f"{tmp}/stitched.mp4"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", out],
                capture_output=True,
                timeout=180,
                check=True,
            )
            with open(out, "rb") as f:
                return f.read()
        except Exception:
            return None


async def generate_video(prompt: str, duration_seconds: int = 8) -> dict:
    """Generate a video (up to settings.MAX_VIDEO_SECONDS). Returns a dict with
    ``data`` (base64 mp4) + ``clips`` list, or ``error``."""
    duration = max(1, min(int(duration_seconds), settings.MAX_VIDEO_SECONDS))
    clip_seconds = max(1, settings.VIDEO_CLIP_MAX_SECONDS)
    clip_count = max(1, -(-duration // clip_seconds))

    if get_api_key("google_gemini"):
        clips = await _veo_clips(prompt, clip_count)
        provider = "google_gemini"
    elif get_api_key("openai"):
        clips = await _sora_clips(prompt, clip_count)
        provider = "openai"
    else:
        return {"error": "No video provider configured (set Gemini or OpenAI key in the LLM panel)"}

    if not clips:
        return {"error": f"{provider}: video generation failed — check the API key and model"}

    stitched = _stitch_clips(clips)
    if stitched and len(clips) > 1:
        return {
            "data": base64.b64encode(stitched).decode(),
            "mime_type": "video/mp4",
            "provider": provider,
            "clips": len(clips),
            "stitched": True,
        }
    if len(clips) == 1:
        return {"data": clips[0]["data"], "mime_type": clips[0]["mime_type"], "provider": provider, "clips": 1}
    return {
        "data": clips[0]["data"],
        "mime_type": "video/mp4",
        "provider": provider,
        "clips": len(clips),
        "playlist": clips,
        "stitched": False,
    }
