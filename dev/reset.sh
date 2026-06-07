#!/usr/bin/env bash
# Reset dev environment: remove all Kodi data and start fresh.
#
# Usage:
#   ./dev/reset.sh              — reset and re-provision settings
#   ./dev/reset.sh --confirm    — skip confirmation prompt
#
# This removes:
#   - kodi_data/ (EPG cache, watch history, settings, logs)
#
# After reset, run ./dev/start.sh to create a fresh environment.

set -e
cd "$(dirname "$0")"

if [ "$1" != "--confirm" ]; then
    echo "This will delete ALL Kodi data (settings, cache, EPG, logs)."
    echo "Press Enter to continue or Ctrl+C to cancel..."
    read -r
fi

# Stop container if running
echo "Stopping any running containers..."
docker compose --profile kodi19 --profile kodi20 --profile kodi21 down 2>/dev/null || true

# Remove kodi_data
if [ -d "kodi_data" ]; then
    echo "Removing kodi_data/..."
    sudo rm -rf kodi_data
    echo "Done."
else
    echo "kodi_data/ does not exist, nothing to remove."
fi

echo ""
echo "Environment reset complete."
echo "Run ./dev/start.sh to create a fresh Kodi instance."
