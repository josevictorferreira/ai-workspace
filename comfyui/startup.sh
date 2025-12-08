#!/bin/bash
# ComfyUI Startup Script

set -e

log() {
    echo "[ComfyUI] $1"
}

# Download models using Python script
python -u /workspace/download_models.py

# Start ComfyUI
log "Starting ComfyUI on port 8188..."
exec python main.py --listen 0.0.0.0 --port 8188 "$@"
