"""MCP reference images from local files use the multipart edit endpoint."""

from __future__ import annotations

from PIL import Image

from muse2api import mcp_server


class _Response:
    def raise_for_status(self):
        pass

    def json(self):
        return {"id": "task_test", "status": "queued"}


class _Client:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def post(self, path, **kwargs):
        files = kwargs.get("files")
        if files:
            kwargs["file_bytes"] = [handle.read() for _, (_, handle, _) in files]
        self.calls.append((path, kwargs))
        return _Response()


def test_local_image_paths_use_multipart_endpoint(tmp_path, monkeypatch):
    ref = tmp_path / "reference.png"
    Image.new("RGB", (3, 2), "orange").save(ref)
    calls = []
    monkeypatch.setattr(mcp_server, "_client", lambda: _Client(calls))

    task = mcp_server._submit_image_task(
        {"prompt": "use this reference", "async": True},
        {"image_paths": [str(ref)]},
    )

    assert task["id"] == "task_test"
    path, kwargs = calls[0]
    assert path == "/v1/images/edits"
    assert kwargs["data"] == {"prompt": "use this reference", "async": True}
    assert kwargs["files"][0][0] == "image"
    assert kwargs["files"][0][1][0] == "reference.png"
    assert kwargs["files"][0][1][2] == "image/png"
    assert kwargs["file_bytes"][0].startswith(b"\x89PNG")


def test_mixed_image_and_image_paths_are_rejected(tmp_path, monkeypatch):
    ref = tmp_path / "reference.png"
    Image.new("RGB", (2, 2)).save(ref)
    calls = []
    monkeypatch.setattr(mcp_server, "_client", lambda: _Client(calls))

    try:
        mcp_server._submit_image_task(
            {"prompt": "x", "async": True},
            {"image": ["https://example.com/ref.png"], "image_paths": [str(ref)]},
        )
    except ValueError as exc:
        assert "either image or image_paths" in str(exc)
    else:
        raise AssertionError("expected mixed reference modes to be rejected")
    assert calls == []
