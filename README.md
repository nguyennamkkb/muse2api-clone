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

`setup` creates `.venv`, installs deps, starts the service (`http://127.0.0.1:18610`), and registers MCP for every supported agent CLI found on the machine.

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

## MCP (Claude, OpenCode, Pi, OMP, agy, Codex)

> **Recommended:** Install MCP at the **user/global level** so it is available in every project and you do not need to register it again for each repository.

The installer checks which tools are available before installing and registers `muse2api` at user level for: **Claude Code/Desktop, OpenCode, Pi, OMP, agy, and Codex**. Missing tools are skipped automatically.

After the service runs, `setup` already registers MCP for the installed agents. To (re)install manually:

```bash
# macOS/Linux
bash scripts/install_mcp.sh
# Windows
scripts\install_mcp.bat
```

Then restart or reload the installed agents. Available tools:
`muse_health`, `muse_list_models`, `muse_chat`, `muse_generate_image`, `muse_get_image_task`, `muse_generate_video`, `muse_get_video_task`.

Generated images are saved to `muse_output` in the **current project** by default. Pass `output_dir` to `muse_generate_image`, or set `MUSE_OUTPUT_DIR`, to override the location.

### Reference images

For local files, pass `image_paths` to `muse_generate_image` instead of putting base64 in the tool call:

```json
{
  "prompt": "Recreate this subject in a sunny garden",
  "image_paths": ["/Users/me/Pictures/reference.jpg"]
}
```

The MCP server reads up to 4 local images (20MB each) and sends them as multipart data to `/v1/images/edits`. URL and data URL references remain supported through `image`.

The same multipart endpoint can be called directly:

```bash
curl -sS http://127.0.0.1:18610/v1/images/edits \
  -H "Authorization: Bearer $(cat data/api_key)" \
  -F 'prompt=Recreate this subject in a sunny garden' \
  -F 'model=muse-image' \
  -F 'size=1:1' \
  -F 'async=true' \
  -F 'image=@/Users/me/Pictures/reference.jpg;type=image/jpeg'
```

## Test

```bash
KEY=$(cat data/api_key)
curl http://127.0.0.1:18610/v1/models -H "Authorization: Bearer $KEY"
```

## Project layout

`src/muse2api/` — api, services, accounts, drivers (mock/browser/http), upstream, core, web dashboard.

## License

MIT