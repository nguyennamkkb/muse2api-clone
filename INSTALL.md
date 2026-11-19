# Cài đặt & chạy muse2api từ GitHub (macOS / Windows)

## 1. Yêu cầu
- Python 3.10+ (Windows: tick "Add Python to PATH" khi cài)
- Google Chrome (driver browser)
- Git

## 2. Clone & chạy service

### macOS / Linux
```bash
git clone https://github.com/nguyennamkkb/muse2api-clone.git
cd muse2api-clone
chmod +x run.sh
./run.sh
```
Lần đầu tự tạo `.venv` và cài thư viện. Service chạy tại `http://127.0.0.1:18610`.

### Windows
```bat
git clone https://github.com/nguyennamkkb/muse2api-clone.git
cd muse2api-clone
run.bat
```
Tương tự, tự tạo `.venv` và cài thư viện. Service chạy tại `http://127.0.0.1:18610`.

## 3. Cấu hình (.env)
- File `.env` tự tạo từ `.env.example` lần đầu. Sửa nếu cần (API key, driver, Chrome path...).
- Driver mặc định `browser` cần đăng nhập muse.ai → import cookie qua dashboard `/dashboard` hoặc file `data/accounts.json`.
- Để đưa ra Internet: chạy `cloudflared tunnel --url http://127.0.0.1:18610`, lấy URL điền vào `MUSE2API_PUBLIC_BASE` trong `.env`, restart service.

## 4. Tích hợp MCP (OpenCode / Claude Desktop)

Sau khi service chạy:

### macOS / Linux
```bash
bash scripts/install_mcp.sh
```
Ghi cấu hình vào `~/.config/opencode/opencode.json` và `~/Library/Application Support/Claude/claude_desktop_config.json`.

### Windows
```bat
scripts\install_mcp.bat
```
Ghi cấu hình vào `%APPDATA%\Claude\claude_desktop_config.json`.

Sau đó **restart** OpenCode / Claude Desktop. MCP server cung cấp các tool: `muse_health`, `muse_list_models`, `muse_chat`, `muse_generate_image`, `muse_get_image_task`, `muse_generate_video`, `muse_get_video_task`.

## 5. Chỉ cài MCP client (không chạy service) qua pipx
```bash
pipx install "git+https://github.com/nguyennamkkb/muse2api-clone.git"
```
MCP command: `muse2api-mcp` (cần env `PYTHONPATH`, `MUSE_BASE_URL`, `MUSE_API_KEY`). Lưu ý MCP chỉ là client; vẫn cần service muse2api chạy ở đâu đó.

## 6. Kiểm tra
```bash
KEY=$(cat data/api_key)   # macOS/Linux
curl http://127.0.0.1:18610/v1/models -H "Authorization: Bearer $KEY"
```
Windows: `set /p KEY=<data\api_key` rồi curl tương tự.