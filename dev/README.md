# Dev Environment — Manual Addon Testing

Run the addon in a real Kodi instance (Docker) for manual testing. No need to build ZIP packages — source code is mounted directly and changes are picked up on each addon navigation.

## Requirements

- Docker 23.0+ with Compose v2
- X11 (Linux) for windowed/fullscreen modes
- NVIDIA Container Toolkit (optional, for GPU acceleration)
- `.env` file with API credentials (see `.env.example`)

## Quick Start

```bash
# 1. One-time host setup (X11 access, audio check)
./dev/setup-host.sh

# 2. Start Kodi in a window
./dev/start.sh
```

That's it. Kodi opens in a window with the addon pre-configured and ready to use.

## Usage

### Start Kodi

```bash
./dev/start.sh                     # Kodi 20, windowed (default)
./dev/start.sh headless            # Kodi 20, headless (access via noVNC)
./dev/start.sh gui                 # Kodi 20, fullscreen
./dev/start.sh windowed kodi21     # Kodi 21, windowed
```

### View Logs

```bash
./dev/logs.sh                      # Last 50 lines
./dev/logs.sh -f                   # Follow in real-time
./dev/logs.sh addon                # Only [Cbilling] entries
./dev/logs.sh all                  # Full log
```

### Stop Kodi

```bash
./dev/stop.sh                      # Stop Kodi 20 (default)
./dev/stop.sh kodi21               # Stop Kodi 21
```

### Reset (clean slate)

```bash
./dev/reset.sh                     # Remove all Kodi data, start fresh
```

## How It Works

- **Addon source** is mounted read-only at `/root/.kodi/addons/plugin.video.cbilling.iptv/`
- **Addon data** (settings, EPG cache, watch history) stored in `dev/kodi_data/userdata/addon_data/plugin.video.cbilling.iptv/` (read-write, persists between runs)
- **Kodi logs** available at `dev/kodi_data/temp/kodi.log`
- **Settings** auto-provisioned from `.env` on first run

Since Kodi starts a fresh Python process for each `plugin://` URL, code changes take effect immediately — just navigate back and re-enter the addon.

## Headless Mode (noVNC)

When running headless, access Kodi via browser:

```
http://localhost:18000/vnc.html
```

Or VNC client: `localhost:15900`

## Configuration

Environment variables (set in `.env` or export before running):

| Variable | Default | Description |
|----------|---------|-------------|
| `KODI20_IMAGE` | `ghcr.io/hidiv/kodi-docker:kodi20-v0.1.0` | Docker image for Kodi 20 |
| `KODI21_IMAGE` | `ghcr.io/hidiv/kodi-docker:kodi21-v0.1.0` | Docker image for Kodi 21 |
| `KODI19_IMAGE` | `ghcr.io/hidiv/kodi-docker:kodi19-v0.1.0` | Docker image for Kodi 19 |
| `HTTP_PORT` | `18080` | JSON-RPC HTTP port |
| `WS_PORT` | `19090` | JSON-RPC WebSocket port |
| `VNC_PORT` | `15900` | VNC port |
| `NOVNC_PORT` | `18000` | noVNC web port |
| `KODI_RESOLUTION` | `1280x720` | Screen resolution |
| `TZ` | `Europe/Moscow` | Container timezone |

## Troubleshooting

### "X11 access not configured"

Run `./dev/setup-host.sh` once after reboot.

### Addon not visible in Kodi

First run takes ~30s for Kodi to generate initial config. If the addon doesn't appear, restart Kodi (`./dev/stop.sh && ./dev/start.sh`).

### Settings lost after reset

`./dev/reset.sh` removes all data. Settings are re-provisioned from `.env` on next `./dev/start.sh`.

### Port conflicts

Change ports via environment variables:
```bash
HTTP_PORT=28080 VNC_PORT=25900 ./dev/start.sh
```
