#!/usr/bin/env bash
# Stop Kodi dev container.
#
# Usage:
#   ./dev/stop.sh              — stop Kodi 20 (default)
#   ./dev/stop.sh kodi21       — stop Kodi 21

set -e
cd "$(dirname "$0")"

VERSION="${1:-kodi20}"

echo "Stopping $VERSION container..."
docker compose --profile "$VERSION" down
echo "Container stopped."
echo ""
echo "Kodi data preserved in: ./dev/kodi_data/"
echo "Logs: ./dev/kodi_data/temp/kodi.log"
echo "View logs: ./dev/logs.sh"
