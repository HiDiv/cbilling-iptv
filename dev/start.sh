#!/usr/bin/env bash
# Start Kodi for manual addon testing.
#
# Usage:
#   ./dev/start.sh                    — Kodi 20, windowed, GPU, audio
#   ./dev/start.sh headless           — Kodi 20, headless (VNC/noVNC)
#   ./dev/start.sh gui                — Kodi 20, fullscreen, GPU, audio
#   ./dev/start.sh headless kodi19    — Kodi 19, headless
#   ./dev/start.sh windowed kodi21    — Kodi 21, windowed
#
# Modes:
#   windowed  — window on desktop (default)
#   gui       — fullscreen
#   headless  — no GUI, access via VNC/noVNC

set -e
cd "$(dirname "$0")"

MODE="${1:-windowed}"
VERSION="${2:-kodi20}"
RESOLUTION="${3:-1280x720}"

# Load project .env if exists
ENV_FILE="../.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Verify X11 for GUI modes
if [ "$MODE" != "headless" ]; then
    if ! xhost 2>/dev/null | grep -q "LOCAL"; then
        echo "ERROR: X11 access not configured. Run: ./dev/setup-host.sh"
        exit 1
    fi
fi

# Create kodi_data directories
mkdir -p kodi_data/userdata/addon_data/plugin.video.cbilling.iptv
mkdir -p kodi_data/addons
mkdir -p kodi_data/temp

# Provision addon settings from .env (if not already present)
SETTINGS_FILE="kodi_data/userdata/addon_data/plugin.video.cbilling.iptv/settings.xml"
if [ ! -f "$SETTINGS_FILE" ]; then
    if [ -z "$CBILLING_API_URL" ] || [ -z "$CBILLING_PUBLIC_KEY" ]; then
        echo "ERROR: CBILLING_API_URL and CBILLING_PUBLIC_KEY must be set in .env"
        echo "       Copy .env.example to .env and fill in your credentials."
        exit 1
    fi
    echo "Provisioning addon settings from .env..."
    cat > "$SETTINGS_FILE" << EOF
<settings version="2">
    <setting id="api_url">${CBILLING_API_URL}</setting>
    <setting id="user_login">${CBILLING_PUBLIC_KEY}</setting>
    <setting id="debug">true</setting>
    <setting id="stb_timezone">Europe/Moscow</setting>
    <setting id="viewmode">0</setting>
    <setting id="vod_preload_metadata">true</setting>
    <setting id="vod_cache_ttl_days">7</setting>
    <setting id="watch_history_size">5</setting>
</settings>
EOF
    echo "Settings created: $SETTINGS_FILE"
fi

echo ""
echo "=== Starting Kodi ==="
echo "  Version:    $VERSION"
echo "  Mode:       $MODE"
echo "  Resolution: $RESOLUTION"
echo ""

export KODI_MODE="$MODE"
export KODI_RESOLUTION="$RESOLUTION"

if [ "$MODE" = "headless" ]; then
    docker compose --profile "$VERSION" up -d
    echo ""
    echo "Kodi started in headless mode."
    echo "  JSON-RPC: http://localhost:${HTTP_PORT:-18080}/jsonrpc"
    echo "  noVNC:    http://localhost:${NOVNC_PORT:-18000}/vnc.html"
    echo "  VNC:      localhost:${VNC_PORT:-15900}"
else
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile "$VERSION" up -d
    echo ""
    echo "Kodi started in $MODE mode."
    echo "  JSON-RPC: http://localhost:${HTTP_PORT:-18080}/jsonrpc"
fi

echo ""
echo "  Logs:     ./dev/kodi_data/temp/kodi.log"
echo "  Stop:     ./dev/stop.sh"
echo ""

# Wait for healthcheck
echo "Waiting for Kodi to become ready..."
elapsed=0
timeout=60
while [ $elapsed -lt $timeout ]; do
    if curl -sf -X POST -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"JSONRPC.Ping","id":1}' \
        "http://localhost:${HTTP_PORT:-18080}/jsonrpc" > /dev/null 2>&1; then
        echo "Kodi is ready! (took ${elapsed}s)"

        # Enable addon if disabled
        ADDON_ENABLED=$(curl -sf -X POST -H "Content-Type: application/json" \
            -d '{"jsonrpc":"2.0","method":"Addons.GetAddonDetails","params":{"addonid":"plugin.video.cbilling.iptv","properties":["enabled"]},"id":9}' \
            "http://localhost:${HTTP_PORT:-18080}/jsonrpc" 2>/dev/null | grep -o '"enabled":[a-z]*' | cut -d: -f2)

        if [ "$ADDON_ENABLED" = "false" ]; then
            echo "Enabling addon..."
            curl -sf -X POST -H "Content-Type: application/json" \
                -d '{"jsonrpc":"2.0","method":"Addons.SetAddonEnabled","params":{"addonid":"plugin.video.cbilling.iptv","enabled":true},"id":10}' \
                "http://localhost:${HTTP_PORT:-18080}/jsonrpc" > /dev/null 2>&1
            sleep 2
            echo "Addon enabled."
        fi

        # Auto-configure locale on first run (if not already Russian)
        CURRENT_LANG=$(curl -sf -X POST -H "Content-Type: application/json" \
            -d '{"jsonrpc":"2.0","method":"Settings.GetSettingValue","params":{"setting":"locale.language"},"id":11}' \
            "http://localhost:${HTTP_PORT:-18080}/jsonrpc" 2>/dev/null | grep -o '"value":"[^"]*"' | cut -d'"' -f4)

        if [ "$CURRENT_LANG" != "resource.language.ru_ru" ]; then
            echo "Configuring Russian locale..."
            sleep 3
            curl -sf -X POST -H "Content-Type: application/json" \
                -d '{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"locale.language","value":"resource.language.ru_ru"},"id":12}' \
                "http://localhost:${HTTP_PORT:-18080}/jsonrpc" > /dev/null 2>&1
            sleep 5
            curl -sf -X POST -H "Content-Type: application/json" \
                -d '{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"locale.timezone","value":"Europe/Moscow"},"id":13}' \
                "http://localhost:${HTTP_PORT:-18080}/jsonrpc" > /dev/null 2>&1
            curl -sf -X POST -H "Content-Type: application/json" \
                -d '{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"locale.country","value":"Russia"},"id":14}' \
                "http://localhost:${HTTP_PORT:-18080}/jsonrpc" > /dev/null 2>&1
            echo "Locale configured (ru_RU, Europe/Moscow)."
        fi

        exit 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done

echo "WARNING: Kodi did not respond within ${timeout}s. It may still be starting."
echo "Check logs: cat ./dev/kodi_data/temp/kodi.log | tail -50"
