#!/usr/bin/env bash
# Host setup for running Kodi in Docker with GPU and audio.
# Run once after system reboot.
#
# Usage: ./dev/setup-host.sh

set -e
echo "=== Host setup for Kodi dev environment ==="

# 1. Allow Docker access to X11
echo "[1/3] Allowing Docker access to X11..."
xhost +local:docker

# 2. Check PulseAudio socket
PULSE_SOCKET="/run/user/$(id -u)/pulse/native"
if [ -S "$PULSE_SOCKET" ]; then
    echo "[2/3] PulseAudio socket found: $PULSE_SOCKET"
else
    echo "[2/3] WARNING: PulseAudio socket not found: $PULSE_SOCKET"
    echo "       Audio will not work. Ensure PulseAudio is running (pulseaudio --check)"
fi

# 3. Check NVIDIA Container Toolkit
if command -v nvidia-ctk &>/dev/null; then
    echo "[3/3] NVIDIA Container Toolkit: OK"
    nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null || true
else
    echo "[3/3] WARNING: nvidia-ctk not found. GPU acceleration unavailable."
    echo "       Kodi will still work but with software rendering."
fi

echo ""
echo "=== Done! Ready to start Kodi ==="
echo "  ./dev/start.sh              — Kodi 20 windowed (GPU + audio)"
echo "  ./dev/start.sh headless     — Kodi 20 headless (VNC/noVNC)"
echo "  ./dev/stop.sh               — stop Kodi"
