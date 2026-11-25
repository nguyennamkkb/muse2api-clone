"""MCP output defaults to the current project unless explicitly overridden."""

from __future__ import annotations

from pathlib import Path

from muse2api import mcp_server


def test_output_dir_defaults_to_current_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MUSE_OUTPUT_DIR", raising=False)

    assert mcp_server._output_dir({}) == tmp_path / "muse_output"


def test_output_dir_argument_overrides_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MUSE_OUTPUT_DIR", raising=False)

    assert mcp_server._output_dir({"output_dir": "assets/generated"}) == (
        tmp_path / "assets" / "generated"
    )


def test_output_dir_environment_overrides_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "shared-output"
    monkeypatch.setenv("MUSE_OUTPUT_DIR", str(target))

    assert mcp_server._output_dir({}) == target
