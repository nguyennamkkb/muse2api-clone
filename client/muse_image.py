#!/usr/bin/env python3
"""Tạo ảnh qua muse2api — chỉ dùng thư viện chuẩn của Python (3.8+), không cần pip.

Chạy tương tác:
    python3 muse_image.py

Hoặc truyền tham số (bỏ qua bước hỏi):
    python3 muse_image.py --ratio 16:9 --prompt "a red fox" --ref fox.png --ref https://x/y.jpg

Cấu hình máy chủ: sửa BASE_URL / API_KEY bên dưới, hoặc đặt biến môi trường
MUSE_BASE_URL và MUSE_API_KEY (biến môi trường được ưu tiên).
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import struct
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get("MUSE_BASE_URL", "http://127.0.0.1:18610")
API_KEY = os.environ.get("MUSE_API_KEY", "m2a-0Ac5ryeFHnZj2lyxgz7_T_KBsRANqAVY")


def _apply_overrides(base_url: str | None, api_key: str | None) -> None:
    global BASE_URL, API_KEY
    if base_url:
        BASE_URL = base_url
    if api_key:
        API_KEY = api_key
MODEL = "muse-image"
OUTPUT_DIR = Path(os.environ.get("MUSE_OUTPUT_DIR", "muse_output"))
POLL_INTERVAL = 3      # giây giữa hai lần hỏi trạng thái
MAX_WAIT = 600         # giây tối đa chờ một ảnh
MAX_REFS = 4

RATIOS = {
    "1": ("1:1", "Vuông"),
    "2": ("16:9", "Ngang rộng (YouTube, banner)"),
    "3": ("9:16", "Dọc (Story, TikTok, Reels)"),
    "4": ("4:3", "Ngang cổ điển"),
    "5": ("3:4", "Dọc cổ điển"),
    "6": ("3:2", "Ngang ảnh chụp"),
    "7": ("2:3", "Dọc ảnh chụp (poster)"),
}


# ---------------------------------------------------------------- HTTP
def _request(method: str, path: str, body: dict | None = None, timeout: float = 90):
    url = path if path.startswith("http") else BASE_URL.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "muse-image-client/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        try:
            detail = json.loads(detail)["error"]["message"]
        except Exception:
            pass
        raise SystemExit(f"Lỗi HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise SystemExit(f"Không kết nối được tới {url}: {exc.reason}") from None


def _json(method: str, path: str, body: dict | None = None) -> dict:
    return json.loads(_request(method, path, body))


# ---------------------------------------------------------------- input
def ref_to_payload(ref: str) -> str:
    """URL giữ nguyên; file trên máy được chuyển thành data URL base64."""
    ref = ref.strip().strip('"').strip("'")
    if ref.startswith(("http://", "https://", "data:")):
        return ref
    path = Path(ref).expanduser()
    if not path.is_file():
        raise SystemExit(f"Không tìm thấy file tham chiếu: {path}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def ask_ratio() -> str:
    print("\nChọn tỷ lệ ảnh:")
    for key, (ratio, label) in RATIOS.items():
        print(f"  {key}. {ratio:<5} {label}")
    while True:
        choice = input("Nhập số [1]: ").strip() or "1"
        if choice in RATIOS:
            return RATIOS[choice][0]
        if choice in {r for r, _ in RATIOS.values()}:
            return choice
        print("  Lựa chọn không hợp lệ.")


def ask_prompt() -> str:
    print("\nNhập prompt (Enter 2 lần để kết thúc):")
    lines = []
    while True:
        line = input()
        if not line and lines:
            break
        if line:
            lines.append(line)
    return " ".join(lines).strip()


def ask_refs() -> list[str]:
    print(f"\nẢnh tham chiếu (tùy chọn, tối đa {MAX_REFS}). "
          "Nhập đường dẫn file hoặc URL, mỗi dòng một ảnh; Enter trống để bỏ qua/kết thúc:")
    refs = []
    while len(refs) < MAX_REFS:
        line = input(f"  Ảnh {len(refs) + 1}: ").strip()
        if not line:
            break
        refs.append(line)
    return refs


# ---------------------------------------------------------------- output
def image_size(data: bytes) -> tuple[int, int] | None:
    """Đọc kích thước PNG / JPEG / WebP mà không cần Pillow."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if chunk == b"VP8L":
            b = data[21:25]
            return 1 + (((b[1] & 0x3F) << 8) | b[0]), 1 + (((b[3] & 0xF) << 10) | (b[2] << 2) | (b[1] >> 6))
        if chunk == b"VP8X":
            return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def save(url: str, ratio: str, scale: int = 1) -> Path:
    data = _request("GET", url, timeout=120)
    ext = Path(url.split("?")[0]).suffix or ".webp"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{time.strftime('%Y%m%d_%H%M%S')}_{ratio.replace(':', 'x')}{ext}"
    path = OUTPUT_DIR / name
    path.write_bytes(data)

    # Optional upscale (Lanczos). Use --upscale N (e.g. 4 -> ~1992x1992 from 498).
    if scale and scale > 1:
        try:
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(data))
            new_size = (im.width * scale, im.height * scale)
            im = im.resize(new_size, Image.LANCZOS)
            # Slight sharpen to recover perceived detail after upscaling.
            from PIL import ImageFilter
            im = im.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
            im.save(path, dpi=(300, 300))
            data = path.read_bytes()
            print(f"  Upscaled {scale}x -> {new_size[0]}x{new_size[1]}")
        except Exception as e:
            print(f"  Upscale failed: {e}")

    size = image_size(data)
    print(f"Đã lưu: {path.resolve()}" + (f"  ({size[0]}x{size[1]})" if size else ""))
    return path


# ---------------------------------------------------------------- main flow
def generate(ratio: str, prompt: str, refs: list[str], scale: int = 1) -> Path:
    body = {"model": MODEL, "prompt": prompt, "size": ratio, "n": 1, "async": True}
    if refs:
        body["image"] = [ref_to_payload(r) for r in refs]

    print(f"\nĐang gửi yêu cầu (tỷ lệ {ratio}, {len(refs)} ảnh tham chiếu)...")
    started = time.time()
    task = _json("POST", "/v1/images/generations", body)

    while task.get("status") in ("queued", "running"):
        if time.time() - started > MAX_WAIT:
            raise SystemExit(f"Quá {MAX_WAIT}s mà chưa xong (task {task['id']}).")
        print(f"\r  {task['status']}... {time.time() - started:4.0f}s", end="", flush=True)
        time.sleep(POLL_INTERVAL)
        task = _json("GET", f"/v1/images/generations/{task['id']}")
    print()

    if task.get("status") != "succeeded":
        raise SystemExit(f"Tạo ảnh thất bại: {task.get('error') or task.get('status')}")
    print(f"Hoàn tất sau {time.time() - started:.1f}s")
    return save(task["result"]["data"][0]["url"], ratio, scale)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo ảnh qua muse2api")
    parser.add_argument("--base-url", help="URL máy chủ muse2api (ghi đè MUSE_BASE_URL)")
    parser.add_argument("--api-key", help="API key (ghi đè MUSE_API_KEY)")
    parser.add_argument("--ratio", help="Tỷ lệ, ví dụ 1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3")
    parser.add_argument("--prompt", help="Mô tả ảnh")
    parser.add_argument("--ref", action="append", default=None,
                        help="Ảnh tham chiếu (file hoặc URL), lặp lại tối đa 4 lần")
    parser.add_argument("--upscale", type=int, default=1,
                        help="Hệ số phóng to ảnh (Lanczos), ví dụ 4 -> ~1992x1992")
    args = parser.parse_args()
    _apply_overrides(args.base_url, args.api_key)

    print(f"Máy chủ: {BASE_URL}")
    ratio = args.ratio or ask_ratio()
    prompt = args.prompt or ask_prompt()
    if not prompt:
        raise SystemExit("Prompt không được để trống.")
    refs = args.ref if args.ref is not None else ([] if args.prompt else ask_refs())
    if len(refs) > MAX_REFS:
        raise SystemExit(f"Tối đa {MAX_REFS} ảnh tham chiếu.")
    generate(ratio, prompt, refs, args.upscale)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nĐã hủy.")
