"""Minimal MCP (Model Context Protocol) server for muse2api.

Exposes the running muse2api HTTP gateway as MCP tools over stdio, so it can
be plugged into OpenCode, Claude Desktop, Claude Code, etc.

Configuration (environment variables):
  MUSE_BASE_URL   base URL of the running muse2api instance (default http://127.0.0.1:18610)
  MUSE_API_KEY    Bearer API key (default: read data/api_key next to the project)
  MUSE_TIMEOUT    request timeout in seconds (default 300)
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "muse2api"
SERVER_VERSION = "0.4.0"


def _base_url() -> str:
    return os.environ.get("MUSE_BASE_URL", "http://127.0.0.1:18610").rstrip("/")


def _api_key() -> str:
    key = os.environ.get("MUSE_API_KEY")
    if key:
        return key
    # try to read the auto-generated key file
    for cand in (
        Path("data/api_key"),
        Path(__file__).resolve().parents[2] / "data" / "api_key",
    ):
        try:
            if cand.is_file():
                return cand.read_text().strip()
        except OSError:
            pass
    return ""


def _timeout() -> float:
    try:
        return float(os.environ.get("MUSE_TIMEOUT", "300"))
    except ValueError:
        return 300.0


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=_base_url(),
        headers={"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"},
        timeout=_timeout(),
    )


def _text_result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


# ---------- tool implementations ----------

def tool_list_models(arguments: dict | None = None) -> dict:
    with _client() as c:
        r = c.get("/v1/models")
        r.raise_for_status()
        return _text_result(_json(r.json()))


def tool_health(arguments: dict | None = None) -> dict:
    with _client() as c:
        r = c.get("/v1/models")
        return _text_result(f"OK - {_base_url()} (HTTP {r.status_code})")


def tool_chat(arguments: dict) -> dict:
    messages = arguments.get("messages")
    if not messages:
        prompt = arguments.get("prompt", "")
        messages = [{"role": "user", "content": prompt}]
    body = {
        "model": arguments.get("model", "muse-chat"),
        "messages": messages,
        "stream": False,
    }
    for k in ("temperature", "max_tokens", "user"):
        if k in arguments:
            body[k] = arguments[k]
    with _client() as c:
        r = c.post("/v1/chat/completions", json=body)
        r.raise_for_status()
        data = r.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        content = _json(data)
    return _text_result(content)


def tool_generate_image(arguments: dict) -> dict:
    transparent = arguments.get("background") == "transparent"
    prompt = arguments["prompt"]
    # For transparent cut-outs, generate on a chromakey background instead of
    # relying on muse.ai's (low-res) matting, so we can upscale before cutting.
    if transparent:
        prompt = (prompt.rstrip(". ") + ". Single subject, centered, fully visible, "
                  "at least 10% empty margin on every side. BACKGROUND: one solid, flat, "
                  "uniform pure green (#00FF00) filling the entire background. No shadow, "
                  "no floor, no gradient, no texture, no vignette. No rim light, no glow, "
                  "no outline or reflection in green; the subject contains no green. "
                  "Crisp clean edges.")
    body = {
        "model": arguments.get("model", "muse-image"),
        "prompt": prompt,
        "size": arguments.get("size", "1:1"),
        "n": arguments.get("n", 1),
        "async": True,
    }
    if arguments.get("response_format"):
        body["response_format"] = arguments["response_format"]
    if arguments.get("image"):
        body["image"] = arguments["image"]
    # Don't ask muse.ai to matte; we do it ourselves after upscaling.
    if not transparent and arguments.get("background"):
        body["background"] = arguments["background"]
    with _client() as c:
        r = c.post("/v1/images/generations", json=body)
        r.raise_for_status()
        task = r.json()
    task_id = task.get("id")
    # poll
    deadline = time.time() + _timeout()
    while time.time() < deadline:
        with _client() as c:
            r = c.get(f"/v1/images/generations/{task_id}")
            r.raise_for_status()
            task = r.json()
        status = task.get("status")
        if status in ("succeeded", "failed", "error", "cancelled"):
            break
        time.sleep(3)
    if task.get("status") != "succeeded":
        return _text_result(_json(task), is_error=True)
    try:
        url = task["result"]["data"][0]["url"]
    except (KeyError, IndexError, TypeError):
        return _text_result(_json(task), is_error=True)

    scale = int(arguments.get("upscale") or 4)
    if scale < 1:
        scale = 1
    out_dir = os.environ.get("MUSE_OUTPUT_DIR", "muse_output")
    os.makedirs(out_dir, exist_ok=True)

    # Download the generated image.
    try:
        with _client() as c:
            resp = c.get(url)
            resp.raise_for_status()
            data = resp.content
    except Exception as exc:
        return _text_result(f"Image ready: {url}\n(Download failed: {exc})")

    import io
    from PIL import Image, ImageFilter
    im = Image.open(io.BytesIO(data))
    if scale > 1:
        im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))

    ts = int(time.time())
    if transparent:
        # Save raw upscaled image, then remove background via remove_bg.py.
        raw_path = os.path.join(out_dir, f"raw_{ts}.png")
        im.save(raw_path, dpi=(300, 300))
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts", "remove_bg.py")
        if not os.path.isfile(script):
            script = os.path.join(os.getcwd(), "scripts", "remove_bg.py")
        out_path = os.path.join(out_dir, f"cutout_{ts}.png")
        try:
            import subprocess, sys
            proc = subprocess.run([sys.executable, script, raw_path, "-o", out_path],
                                  capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                return _text_result(f"Image ready: {url}\n(Upscale ok; remove_bg failed: {proc.stderr or proc.stdout})")
            # clean up raw
            try:
                os.remove(raw_path)
            except OSError:
                pass
            return _text_result(f"Image ready (upscaled {scale}x, bg removed): {os.path.abspath(out_path)} ({im.width}x{im.height})")
        except Exception as exc:
            return _text_result(f"Image saved: {os.path.abspath(raw_path)}\n(remove_bg failed: {exc})")
    else:
        ext = ".png" if im.mode in ("RGBA", "LA") else ".webp"
        path = os.path.join(out_dir, f"upscaled_{scale}x_{ts}{ext}")
        im.save(path, dpi=(300, 300))
        return _text_result(f"Image ready (upscaled {scale}x): {os.path.abspath(path)} ({im.width}x{im.height})")


def tool_get_image_task(arguments: dict) -> dict:
    task_id = arguments["task_id"]
    with _client() as c:
        r = c.get(f"/v1/images/generations/{task_id}")
        r.raise_for_status()
        return _text_result(_json(r.json()))


def tool_generate_video(arguments: dict) -> dict:
    body = {
        "model": arguments.get("model", "muse-video"),
        "prompt": arguments["prompt"],
        "async": True,
    }
    for k in ("size", "seconds", "duration", "image", "input_reference"):
        if k in arguments:
            body[k] = arguments[k]
    with _client() as c:
        r = c.post("/v1/videos", json=body)
        r.raise_for_status()
        task = r.json()
    task_id = task.get("id")
    deadline = time.time() + _timeout()
    while time.time() < deadline:
        with _client() as c:
            r = c.get(f"/v1/videos/{task_id}")
            r.raise_for_status()
            task = r.json()
        status = task.get("status")
        if status in ("succeeded", "failed", "error", "cancelled", "completed"):
            break
        time.sleep(5)
    if task.get("status") not in ("succeeded", "completed"):
        return _text_result(_json(task), is_error=True)
    try:
        url = task["result"]["data"][0]["url"] if "result" in task else task.get("url")
    except (KeyError, IndexError, TypeError):
        url = _json(task)
    return _text_result(f"Video ready: {url}")


def tool_get_video_task(arguments: dict) -> dict:
    task_id = arguments["task_id"]
    with _client() as c:
        r = c.get(f"/v1/videos/{task_id}")
        r.raise_for_status()
        return _text_result(_json(r.json()))


TOOLS = [
    {
        "name": "muse_health",
        "description": "Check that the muse2api service is reachable.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": tool_health,
    },
    {
        "name": "muse_list_models",
        "description": "List models available on the muse2api gateway.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": tool_list_models,
    },
    {
        "name": "muse_chat",
        "description": "Chat with a muse.ai model. Returns the assistant reply text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Single user message (shorthand)."},
                "messages": {
                    "type": "array",
                    "description": "OpenAI-style messages array.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["role", "content"],
                    },
                },
                "model": {"type": "string", "default": "muse-chat"},
            },
        },
        "handler": tool_chat,
    },
    {
        "name": "muse_generate_image",
        "description": "Generate an image via muse.ai and return its URL. Polls until done.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "size": {"type": "string", "default": "1:1", "description": "Aspect ratio, e.g. 1:1, 16:9, 9:16."},
                "model": {"type": "string", "default": "muse-image"},
                "image": {"type": "array", "items": {"type": "string"}, "description": "Reference image URLs or data URLs."},
                "background": {"type": "string", "description": "transparent or opaque."},
                "n": {"type": "integer", "default": 1, "description": "Number of images (1-4)."},
                "response_format": {"type": "string", "description": "url or b64_json."},
                "upscale": {"type": "integer", "default": 4, "description": "Upscale factor (Lanczos+sharpen). Default 4."},
            },
            "required": ["prompt"],
        },
        "handler": tool_generate_image,
    },
    {
        "name": "muse_get_image_task",
        "description": "Get status/result of an image generation task by id.",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
        "handler": tool_get_image_task,
    },
    {
        "name": "muse_generate_video",
        "description": "Generate a video via muse.ai and return its URL. Polls until done.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "model": {"type": "string", "default": "muse-video"},
                "size": {"type": "string"},
                "seconds": {"type": "number"},
                "duration": {"type": "number"},
                "image": {"type": "string", "description": "Reference image URL/data URL."},
                "input_reference": {"type": "string", "description": "OpenAI-style input reference."},
            },
            "required": ["prompt"],
        },
        "handler": tool_generate_video,
    },
    {
        "name": "muse_get_video_task",
        "description": "Get status/result of a video generation task by id.",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
        "handler": tool_get_video_task,
    },
]


def _handle_request(req: dict) -> dict | None:
    method = req.get("method")
    rid = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    if method in ("notifications/initialized", "notifications/cancelled"):
        return None

    if method == "tools/list":
        tools = [{"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]} for t in TOOLS]
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tools}}

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        tool = next((t for t in TOOLS if t["name"] == name), None)
        if tool is None:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Unknown tool: {name}"}}
        try:
            result = tool["handler"](arguments)
        except TypeError:
            result = tool["handler"]()
        except Exception as exc:  # noqa: BLE001
            result = _text_result(f"Error: {exc}", is_error=True)
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}

    # unknown method
    if rid is not None:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return None


def main() -> None:
    # unbuffered stdio
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = _handle_request(req)
        if resp is not None:
            out.write(json.dumps(resp, ensure_ascii=False) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
