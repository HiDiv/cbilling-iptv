#!/usr/bin/env bash
# Stop the reference Kodi container.
set -e
cd "$(dirname "$0")"
docker compose -f docker-compose.ref.yml down -v
echo "Reference container stopped."
