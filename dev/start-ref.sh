#!/usr/bin/env bash
# Start a REFERENCE Kodi container with stable v2.1.0 addon for visual comparison.
#
# Usage:
#   ./dev/start-ref.sh              — windowed (X11 window on desktop)
#   ./dev/start-ref.sh headless     — headless (access via noVNC)
#
# Access:
#   Windowed:  second Kodi window appears on desktop
#   noVNC:     http://localhost:28000/vnc.html
#   JSON-RPC:  http://localhost:28080/jsonrpc
#
# Stop:
#   ./dev/stop-ref.sh

set -e
cd "$(dirname "$0")"

MODE="${1:-windowed}"

# Load .env
ENV_FILE="../.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

ZIP_FILE="../dist/plugin.video.cbilling.iptv-2.1.0.zip"
if [ ! -f "$ZIP_FILE" ]; then
    echo "ERROR: Stable ZIP not found: $ZIP_FILE"
    echo "       Build it from tag v2.1.0 or check dist/ directory."
    exit 1
fi

# Verify X11 for windowed mode
if [ "$MODE" != "headless" ]; then
    if ! xhost 2>/dev/null | grep -q "LOCAL"; then
        echo "ERROR: X11 access not configured. Run: ./dev/setup-host.sh"
        exit 1
    fi
fi

# Create isolated kodi_data for reference
mkdir -p kodi_data_ref/userdata/addon_data/plugin.video.cbilling.iptv
mkdir -p kodi_data_ref/addons
mkdir -p kodi_data_ref/temp

# Provision settings
SETTINGS_FILE="kodi_data_ref/userdata/addon_data/plugin.video.cbilling.iptv/settings.xml"
if [ ! -f "$SETTINGS_FILE" ]; then
    if [ -z "$CBILLING_API_URL" ] || [ -z "$CBILLING_PUBLIC_KEY" ]; then
        echo "ERROR: CBILLING_API_URL and CBILLING_PUBLIC_KEY must be set in .env"
        exit 1
    fi
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
    echo "Settings provisioned."
fi

# Extract addon ZIP into kodi_data_ref/addons/
ADDON_DIR="kodi_data_ref/addons/plugin.video.cbilling.iptv"
if [ ! -d "$ADDON_DIR" ]; then
    echo "Installing addon v2.1.0 from ZIP..."
    cd kodi_data_ref/addons
    python3 -c "import zipfile; zipfile.ZipFile('../../$ZIP_FILE').extractall()"
    cd ../..
    echo "Addon installed to $ADDON_DIR"
fi

echo ""
echo "=== Starting REFERENCE Kodi (v2.1.0) ==="
echo "  Mode: $MODE"
echo ""

export KODI_MODE="$MODE"

if [ "$MODE" = "headless" ]; then
    docker compose -f docker-compose.ref.yml up -d
else
    docker compose -f docker-compose.ref.yml -f docker-compose.ref.gpu.yml up -d
fi

echo ""
echo "Reference Kodi (v2.1.0) started."
if [ "$MODE" = "headless" ]; then
    echo "  noVNC:    http://localhost:28000/vnc.html"
fi
echo "  JSON-RPC: http://localhost:28080/jsonrpc"
echo "  Logs:     ./dev/kodi_data_ref/temp/kodi.log"
echo "  Stop:     ./dev/stop-ref.sh"
echo ""

# Wait for healthcheck
echo "Waiting for Kodi to become ready..."
elapsed=0
timeout=60
while [ $elapsed -lt $timeout ]; do
    if curl -sf -X POST -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"JSONRPC.Ping","id":1}' \
        http://localhost:28080/jsonrpc > /dev/null 2>&1; then
        echo "Reference Kodi ready (${elapsed}s)."
        exit 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done

echo "WARNING: Healthcheck timeout after ${timeout}s"
exit 1
