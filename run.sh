#!/usr/bin/env bash
# Khởi chạy muse2api trên macOS / Linux. Lần đầu sẽ tự tạo môi trường và cài thư viện.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Không tìm thấy python3. Cài Python 3.10+ rồi chạy lại." >&2
  exit 1
fi
if ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
  echo "Cần Python 3.10 trở lên (hiện có: $("$PY" --version))." >&2
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo ">> Tạo môi trường ảo .venv"
  "$PY" -m venv .venv
fi
if ! .venv/bin/python -c 'import muse2api' 2>/dev/null; then
  echo ">> Cài thư viện (chỉ lần đầu)"
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -e .
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo ">> Đã tạo .env từ .env.example (driver=mock). Sửa .env rồi chạy lại nếu cần."
fi

exec .venv/bin/python -m muse2api
