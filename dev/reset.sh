#!/usr/bin/env bash
# Reset dev environment.
#
# Usage:
#   ./dev/reset.sh              — soft reset (clear cache, EPG, logs; keep settings)
#   ./dev/reset.sh --full       — full reset (delete everything, start from scratch)
#   ./dev/reset.sh --confirm    — soft reset without confirmation prompt
#
# Soft reset removes:
#   - EPG database, VOD cache, temp/logs
#   - Does NOT touch: settings.xml, guisettings.xml, Database/
#
# Full reset removes:
#   - ALL kodi_data/ (settings, cache, EPG, logs, databases)
#   - After full reset, config overlay (dev/config/) restores base settings on next start

set -e
cd "$(dirname "$0")"

MODE="soft"
CONFIRM="yes"

for arg in "$@"; do
    case "$arg" in
        --full) MODE="full" ;;
        --confirm) CONFIRM="no" ;;
    esac
done

# Stop container if running
echo "Stopping any running containers..."
docker compose --profile kodi19 --profile kodi20 --profile kodi21 down 2>/dev/null || true

if [ "$MODE" = "full" ]; then
    if [ "$CONFIRM" = "yes" ]; then
        echo ""
        echo "FULL RESET: This will delete ALL Kodi data (settings, cache, EPG, logs)."
        echo "Base settings (language, timezone) will be restored from config overlay on next start."
        echo "Press Enter to continue or Ctrl+C to cancel..."
        read -r
    fi

    if [ -d "kodi_data" ]; then
        echo "Removing ALL kodi_data/..."
        sudo rm -rf kodi_data
        echo "Done."
    else
        echo "kodi_data/ does not exist, nothing to remove."
    fi

    echo ""
    echo "Full reset complete. Run ./dev/start.sh to create a fresh Kodi instance."
    echo "Language and timezone will be auto-configured from dev/config/."
else
    # Soft reset: clear only cache/logs, preserve settings
    if [ "$CONFIRM" = "yes" ]; then
        echo ""
        echo "SOFT RESET: This will clear EPG cache, VOD cache, logs, and temp files."
        echo "Settings and Kodi configuration will be preserved."
        echo "Press Enter to continue or Ctrl+C to cancel..."
        read -r
    fi

    if [ ! -d "kodi_data" ]; then
        echo "kodi_data/ does not exist, nothing to reset."
        exit 0
    fi

    echo "Clearing cache and logs..."

    # Remove EPG database
    ADDON_DATA="kodi_data/userdata/addon_data/plugin.video.cbilling.iptv"
    if [ -d "$ADDON_DATA" ]; then
        rm -f "$ADDON_DATA/epg.db" "$ADDON_DATA/epg.db-wal" "$ADDON_DATA/epg.db-shm"
        rm -f "$ADDON_DATA/vod_cache.db" "$ADDON_DATA/vod_cache.db-wal" "$ADDON_DATA/vod_cache.db-shm"
        echo "  ✓ EPG and VOD cache cleared"
    fi

    # Remove Kodi temp/logs
    if [ -d "kodi_data/temp" ]; then
        sudo rm -rf kodi_data/temp/*
        echo "  ✓ Logs cleared"
    fi

    # Remove Kodi thumbnails cache
    if [ -d "kodi_data/userdata/Thumbnails" ]; then
        sudo rm -rf kodi_data/userdata/Thumbnails
        echo "  ✓ Thumbnails cache cleared"
    fi

    echo ""
    echo "Soft reset complete. Settings preserved."
    echo "Run ./dev/start.sh to restart Kodi."
fi
