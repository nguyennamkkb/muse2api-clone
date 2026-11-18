# Hướng dẫn chạy muse2api trên máy khác

muse2api biến tài khoản muse.ai thành API chuẩn OpenAI (chat, tạo ảnh, tạo video).
Máy chạy server cần **luôn bật** trong lúc sử dụng.

## Gói gồm những gì

| File | Nội dung |
|---|---|
| `muse2api-src.zip` | Mã nguồn + `run.sh` / `run.bat` + hướng dẫn này. Chia sẻ được. |
| `muse2api-secrets.zip` | `.env` và `data/accounts.json` (cookie muse.ai, API key). **Bí mật — ai có file này dùng được tài khoản của bạn.** |
| `client/muse_image.py` | Script tạo ảnh cho người dùng. Bản trong gói mã nguồn để trống key; bản trong gói secrets đã điền sẵn link + key và sẽ ghi đè khi giải nén. |

## Yêu cầu

- **Python 3.10 trở lên** — kiểm tra: `python3 --version` (Windows: `python --version`)
- **Google Chrome** (hoặc Chromium) đã cài — server dùng nó để nói chuyện với muse.ai
- Internet truy cập được `https://muse.ai`

## Cách 1 — Chạy trực tiếp (macOS / Linux)

```bash
unzip muse2api-src.zip -d muse2api
cd muse2api
unzip ../muse2api-secrets.zip        # bỏ qua nếu muốn nhập tài khoản mới
chmod +x run.sh
./run.sh
```

Lần đầu mất 1–2 phút để cài thư viện. Thấy dòng
`muse2api 0.3.0 ready (driver=browser)` là xong. Server nghe tại `http://127.0.0.1:18610`.

Chạy nền, không bị tắt khi đóng Terminal:
```bash
nohup ./run.sh > server.log 2>&1 &
```
Dừng: `pkill -f "python -m muse2api"`

## Cách 2 — Windows

1. Cài Python từ python.org, **tick "Add python.exe to PATH"**.
2. Giải nén `muse2api-src.zip`, rồi giải nén `muse2api-secrets.zip` vào **cùng thư mục**.
3. Nhấp đúp `run.bat`.

`run.bat` tự tìm Chrome. Nếu báo không thấy Chrome, mở `.env` và điền:
```
MUSE2API_CHROMIUM_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
```
> Ghi chú: dự án được phát triển và kiểm thử trên macOS/Linux; Windows chưa được thử.

## Cách 3 — Docker (khuyên dùng cho VPS Linux)

Không cần cài Python hay Chrome; Docker image đã có sẵn Chromium.
```bash
unzip muse2api-src.zip -d muse2api && cd muse2api
unzip ../muse2api-secrets.zip
docker compose up -d --build
docker compose logs -f              # xem log
```
Trong Docker server nghe ở `0.0.0.0:18610`.

## Nhập tài khoản muse.ai (nếu không dùng gói secrets)

1. Mở `.env`, đặt `MUSE2API_DRIVER=browser`, rồi chạy server.
2. Lấy cookie: đăng nhập https://muse.ai → `F12` → tab **Application** → **Cookies** → `https://muse.ai`.
   Bắt buộc: `hatch_sess`, `hatch_native_auth_device`. Nên lấy thêm: `hatch_vml`, `hatch_gw`, `__Host-hatch_one_tap`.
   Hoặc dùng extension có sẵn trong `src/muse2api/web/extension` (Chrome → `chrome://extensions` → Developer mode → Load unpacked).
3. Nhập vào server:
   ```bash
   curl -X POST http://127.0.0.1:18610/admin/accounts \
     -H "Authorization: Bearer <MUSE2API_ADMIN_KEY>" \
     -H "Content-Type: application/json" \
     -d '{"label":"acc1","cookies":{"hatch_sess":"...","hatch_native_auth_device":"...","hatch_vml":"..."}}'
   ```
   Hoặc dán vào **Dashboard → Accounts → Import hàng loạt** tại `http://127.0.0.1:18610/dashboard`.

Cookie `hatch_vml` hết hạn sau vài ngày. Khi API báo lỗi xác thực, lấy cookie mới và nhập lại.

## Cấu hình chính trong `.env`

| Biến | Ý nghĩa |
|---|---|
| `MUSE2API_DRIVER` | `browser` = dùng muse.ai thật, `mock` = dữ liệu giả để thử |
| `MUSE2API_API_KEY` | Key cho người dùng API (`/v1/*`) |
| `MUSE2API_ADMIN_KEY` | Key quản trị (`/admin`, dashboard) — giữ riêng |
| `MUSE2API_PUBLIC_BASE` | Link công khai của server (để link ảnh/video trả về mở được từ ngoài) |
| `MUSE2API_HOST` / `MUSE2API_PORT` | Địa chỉ nghe, mặc định `127.0.0.1:18610` |
| `MUSE2API_ACCOUNT_MAX_CONCURRENCY` | Số yêu cầu song song mỗi tài khoản (mặc định 4) |

Sửa `.env` xong phải khởi động lại server.

## Đưa lên Internet (Cloudflare Tunnel)

Không cần mở port router.
```bash
# macOS:  brew install cloudflared
# Linux:  xem https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
cloudflared tunnel --url http://127.0.0.1:18610
```
Lệnh in ra link dạng `https://xxxx.trycloudflare.com`. Điền link đó vào
`MUSE2API_PUBLIC_BASE` trong `.env` và khởi động lại server.

Link `trycloudflare` **đổi mỗi lần chạy lại**. Muốn link cố định: dùng named tunnel của
Cloudflare với domain riêng, hoặc chạy Docker trên VPS và trỏ domain vào.

## Kiểm tra

```bash
KEY=<MUSE2API_API_KEY>
curl http://127.0.0.1:18610/v1/models -H "Authorization: Bearer $KEY"
curl http://127.0.0.1:18610/v1/chat/completions -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"muse-chat","messages":[{"role":"user","content":"Xin chào"}]}'
```

## Tạo ảnh bằng script `client/muse_image.py`

Chỉ cần Python 3.8+, không cài thêm gì. Copy file này sang máy người dùng:
```bash
export MUSE_BASE_URL=https://xxxx.trycloudflare.com   # hoặc http://IP:18610
export MUSE_API_KEY=<API key>
python3 muse_image.py                                  # hỏi tỷ lệ → prompt → ảnh tham chiếu
python3 muse_image.py --ratio 16:9 --prompt "..." --ref anh.png
```
Tỷ lệ hỗ trợ: `1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3`. Ảnh lưu vào `muse_output/`.

## Lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `Chromium/Chrome not found` | Cài Chrome hoặc điền `MUSE2API_CHROMIUM_PATH` trong `.env` |
| `401` khi gọi API | Sai API key / dùng API key cho `/admin` (phải dùng admin key) |
| `503` / không có tài khoản khả dụng | Cookie hết hạn → lấy cookie mới, nhập lại |
| `429` | Tài khoản muse.ai hết hạn mức → chờ reset hoặc thêm tài khoản |
| Port 18610 bị chiếm | Đổi `MUSE2API_PORT` trong `.env` |
| Ảnh lâu (20–70s) | Bình thường — thời gian do muse.ai tạo ảnh |

**Lưu ý:** dùng cùng một bộ cookie trên hai máy cùng lúc có thể khiến muse.ai đăng xuất phiên.
Khi chuyển server sang máy mới, hãy tắt server ở máy cũ.
