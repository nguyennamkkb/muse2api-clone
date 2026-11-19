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
    body = {
        "model": arguments.get("model", "muse-image"),
        "prompt": arguments["prompt"],
        "size": arguments.get("size", "1:1"),
        "n": arguments.get("n", 1),
        "async": True,
    }
    if arguments.get("image"):
        body["image"] = arguments["image"]
    if arguments.get("background"):
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
        url = _json(task)
    return _text_result(f"Image ready: {url}")


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
    for k in ("size", "seconds", "image"):
        if k in arguments:
            body[k] = arguments[k]
    with _client() as c:
        r = c.post("/v1/videos/generations", json=body)
        r.raise_for_status()
        task = r.json()
    task_id = task.get("id")
    deadline = time.time() + _timeout()
    while time.time() < deadline:
        with _client() as c:
            r = c.get(f"/v1/videos/generations/{task_id}")
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
        r = c.get(f"/v1/videos/generations/{task_id}")
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
                "image": {"type": "string", "description": "Reference image URL/data URL."},
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
