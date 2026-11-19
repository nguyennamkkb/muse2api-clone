# muse2api

OpenAI-compatible gateway for [muse.ai](https://muse.ai) (chat, image, video). Works with any OpenAI SDK/client by changing `base_url`.

## Quick start

**macOS / Linux**
```bash
git clone https://github.com/nguyennamkkb/muse2api-clone.git
cd muse2api-clone
chmod +x setup.sh
./setup.sh
```

**Windows**
```bat
git clone https://github.com/nguyennamkkb/muse2api-clone.git
cd muse2api-clone
setup.bat
```

`setup` creates `.venv`, installs deps, starts the service (`http://127.0.0.1:18610`), and registers MCP for OpenCode/Claude Desktop.

Requirements: Python 3.10+, Google Chrome, Git.

## Run manually

```bash
# macOS/Linux
./run.sh
# Windows
run.bat
```

## Configure

Edit `.env` (auto-created from `.env.example`):
- `MUSE2API_DRIVER`: `browser` (real) or `mock` (offline)
- `MUSE2API_API_KEY` / `MUSE2API_ADMIN_KEY`
- `MUSE2API_PUBLIC_BASE`: public URL (Cloudflare Tunnel) for media links
- Chrome path, account pool, timeouts, keepalive...

To expose to the internet:
```bash
cloudflared tunnel --url http://127.0.0.1:18610
# put the printed URL into MUSE2API_PUBLIC_BASE, restart service
```

## MCP (OpenCode / Claude Desktop)

After the service runs, `setup` already registers MCP. To (re)install manually:

```bash
# macOS/Linux
bash scripts/install_mcp.sh
# Windows
scripts\install_mcp.bat
```

Then restart OpenCode / Claude Desktop. Available tools:
`muse_health`, `muse_list_models`, `muse_chat`, `muse_generate_image`, `muse_get_image_task`, `muse_generate_video`, `muse_get_video_task`.

## Test

```bash
KEY=$(cat data/api_key)
curl http://127.0.0.1:18610/v1/models -H "Authorization: Bearer $KEY"
```

## Project layout

`src/muse2api/` — api, services, accounts, drivers (mock/browser/http), upstream, core, web dashboard.

## License

MIT