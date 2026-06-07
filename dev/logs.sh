#!/usr/bin/env bash
# View Kodi log file (addon debug messages).
#
# Usage:
#   ./dev/logs.sh              — tail last 50 lines of kodi.log
#   ./dev/logs.sh -f           — follow log in real-time
#   ./dev/logs.sh all          — show full log
#   ./dev/logs.sh addon        — show only [Cbilling] lines

set -e
cd "$(dirname "$0")"

LOG_FILE="kodi_data/temp/kodi.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found: $LOG_FILE"
    echo "Start Kodi first: ./dev/start.sh"
    exit 1
fi

case "${1:-}" in
    -f|--follow)
        tail -f "$LOG_FILE"
        ;;
    all)
        cat "$LOG_FILE"
        ;;
    addon)
        grep -i "\[Cbilling\]" "$LOG_FILE" || echo "No [Cbilling] entries found."
        ;;
    *)
        tail -50 "$LOG_FILE"
        ;;
esac
