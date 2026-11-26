#!/usr/bin/env python3
"""Install muse2api MCP for every supported agent CLI found on this machine."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
ENV = {
    "PYTHONPATH": str(ROOT / "src"),
    "MUSE_BASE_URL": "http://127.0.0.1:18610",
}


def load_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def run(args: list[str]) -> None:
    subprocess.run(args, check=True)


def env_flags() -> list[str]:
    return [item for key, value in ENV.items() for item in ("--env", f"{key}={value}")]


def install_opencode() -> None:
    run([
        "opencode", "mcp", "add", "muse2api", "--global",
        "--env", f"PYTHONPATH={ENV['PYTHONPATH']}",
        "--env", f"MUSE_BASE_URL={ENV['MUSE_BASE_URL']}",
        "--", str(PY), "-m", "muse2api.mcp_server",
    ])
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = config_home / "opencode" / "opencode.json"
    cfg = load_json(path, {"$schema": "https://opencode.ai/config.json", "mcp": {}})
    mcp = cfg.setdefault("mcp", {})
    servers = mcp.setdefault("servers", {})
    mcp.pop("muse2api", None)  # legacy V1 entry
    entry = servers.setdefault("muse2api", {})
    entry.update({
        "type": "local",
        "command": [str(PY), "-m", "muse2api.mcp_server"],
        "cwd": ".",
    })
    env = entry.setdefault("environment", {})
    env.update(ENV)
    env.pop("MUSE_API_KEY", None)
    env.pop("MUSE_OUTPUT_DIR", None)
    save_json(path, cfg)


def install_claude_code() -> None:
    subprocess.run(["claude", "mcp", "remove", "muse2api", "--scope", "user"], check=False)
    run([
        "claude", "mcp", "add", "--scope", "user",
        "-e", f"PYTHONPATH={ENV['PYTHONPATH']}",
        "-e", f"MUSE_BASE_URL={ENV['MUSE_BASE_URL']}",
        "--transport", "stdio",
        "muse2api", "--", str(PY), "-m", "muse2api.mcp_server",
    ])


def claude_desktop_config() -> Path | None:
    candidates = []
    if os.name == "nt" and os.environ.get("APPDATA"):
        candidates.append(Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json")
    if sys.platform == "darwin":
        candidates.append(
            Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        )
    candidates.append(Path.home() / ".config" / "Claude" / "claude_desktop_config.json")
    for path in candidates:
        if path.parent.exists():
            return path
    return None


def install_claude_desktop() -> None:
    path = claude_desktop_config()
    if path is None:
        raise FileNotFoundError("Claude Desktop config directory not found")
    cfg = load_json(path, {"mcpServers": {}})
    cfg.setdefault("mcpServers", {})["muse2api"] = {
        "command": str(PY),
        "args": ["-m", "muse2api.mcp_server"],
        "env": ENV,
    }
    save_json(path, cfg)


def install_pi() -> None:
    run([
        "pi", "mcp", "add", "--cwd", ".",
        "--env", f"PYTHONPATH={ENV['PYTHONPATH']}",
        "--env", f"MUSE_BASE_URL={ENV['MUSE_BASE_URL']}",
        "--exposure", "direct",
        "--description", "muse.ai chat, image and video gateway",
        "muse2api", "--", str(PY), "-m", "muse2api.mcp_server",
    ])


def install_omp() -> None:
    path = Path.home() / ".omp" / "agent" / "mcp.json"
    cfg = load_json(path, {})
    cfg.setdefault(
        "$schema",
        "https://raw.githubusercontent.com/can1357/oh-my-pi/main/packages/coding-agent/src/config/mcp-schema.json",
    )
    cfg.setdefault("mcpServers", {})["muse2api"] = {
        "type": "stdio",
        "command": str(PY),
        "args": ["-m", "muse2api.mcp_server"],
        "cwd": ".",
        "env": ENV,
        "timeout": 600000,
    }
    save_json(path, cfg)


def install_agy() -> None:
    run([
        "agy", "mcp", "add",
        "--env", f"PYTHONPATH={ENV['PYTHONPATH']}",
        "--env", f"MUSE_BASE_URL={ENV['MUSE_BASE_URL']}",
        "muse2api", "--", str(PY), "-m", "muse2api.mcp_server",
    ])


def install_codex() -> None:
    run([
        "codex", "mcp", "add",
        "--env", f"PYTHONPATH={ENV['PYTHONPATH']}",
        "--env", f"MUSE_BASE_URL={ENV['MUSE_BASE_URL']}",
        "muse2api", "--", str(PY), "-m", "muse2api.mcp_server",
    ])


def main() -> int:
    if not PY.is_file():
        print(f"No virtualenv Python found at {PY}. Run ./run.sh or run.bat first.", file=sys.stderr)
        return 1

    targets = [
        ("OpenCode", "opencode", install_opencode),
        ("Claude Code", "claude", install_claude_code),
        ("Pi", "pi", install_pi),
        ("OMP", "omp", install_omp),
        ("agy", "agy", install_agy),
        ("Codex", "codex", install_codex),
    ]
    installed: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    for label, command, handler in targets:
        if not shutil.which(command):
            skipped.append(label)
            print(f"- {label}: skipped (not installed)")
            continue
        try:
            handler()
            installed.append(label)
            print(f"- {label}: installed")
        except Exception as exc:
            failed.append(label)
            print(f"- {label}: failed ({exc})", file=sys.stderr)

    if claude_desktop_config() is not None:
        try:
            install_claude_desktop()
            installed.append("Claude Desktop")
            print("- Claude Desktop: installed")
        except Exception as exc:
            failed.append("Claude Desktop")
            print(f"- Claude Desktop: failed ({exc})", file=sys.stderr)
    else:
        skipped.append("Claude Desktop")
        print("- Claude Desktop: skipped (not installed)")

    print(f"\nInstalled: {', '.join(installed) if installed else 'none'}")
    print(f"Skipped: {', '.join(skipped) if skipped else 'none'}")
    if failed:
        print(f"Failed: {', '.join(failed)}", file=sys.stderr)
    print("Restart or reload the installed agents to load muse2api.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
