#!/bin/bash
# ComfyUI Startup Script

set -e

log() {
    echo "[ComfyUI] $1"
}

# Download models using Python script
python -u /workspace/download_models.py

# Install Python dependencies for custom nodes
log "Installing dependencies for custom nodes..."
if [ -d "/workspace/custom_nodes" ]; then
    for dir in /workspace/custom_nodes/*/; do
        if [ -f "$dir/requirements.txt" ]; then
            log "Installing requirements for $(basename "$dir")..."
            (cd "$dir" && pip install -r requirements.txt 2>/dev/null) || log "Failed to install requirements for $(basename "$dir"), continuing..."
        fi
    done
fi

# Start ComfyUI
log "Starting ComfyUI on port 8188..."
exec python main.py --listen 0.0.0.0 --port 8188 "$@"
