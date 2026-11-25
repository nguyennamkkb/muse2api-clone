"""Full-resolution media download from the Muse lightbox."""

from __future__ import annotations

import base64

from muse2api.drivers.browser import dom
from muse2api.drivers.browser.driver import BrowserDriver, _Tab


class _LightboxSession:
    def __init__(self) -> None:
        self.lightbox_states = [
            {"src": "blob:preview-in-lightbox", "w": 498, "h": 498},
            {"src": "blob:full", "w": 1600, "h": 1600},
        ]
        self.fetched: list[str] = []
        self.closed = False

    async def evaluate(self, expr, **_):
        if expr == dom.open_media_lightbox("blob:preview"):
            return True
        if expr == dom.MEDIA_LIGHTBOX_IMAGE:
            return self.lightbox_states.pop(0)
        if expr == dom.CLOSE_MEDIA_LIGHTBOX:
            self.closed = True
            return True
        if "blob:full" in expr:
            self.fetched.append("blob:full")
            return {
                "ok": True,
                "mime": "image/webp",
                "b64": base64.b64encode(b"full-image").decode(),
            }
        raise AssertionError(f"unexpected expression: {expr[:120]}")


async def test_download_waits_for_full_resolution_lightbox(monkeypatch):
    import asyncio

    import muse2api.drivers.browser.driver as mod

    real_sleep = asyncio.sleep
    monkeypatch.setattr(mod.asyncio, "sleep", lambda _: real_sleep(0))
    session = _LightboxSession()
    tab = _Tab("a0", "ctx", "t", session)

    result = await BrowserDriver._download(
        None,
        tab,
        {"src": "blob:preview", "w": 498, "h": 498, "kind": "image"},
        "image",
    )

    assert (result.width, result.height) == (1600, 1600)
    assert result.data == b"full-image"
    assert session.fetched == ["blob:full"]
    assert session.closed
