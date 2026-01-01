#!/usr/bin/env python3
"""
ComfyUI Launcher with Aule Attention

This script MUST install the flash_attn shim BEFORE any ComfyUI imports,
because ComfyUI checks for flash_attn at module import time.
"""

import sys
import os

# === STEP 1: Install the shim BEFORE any other imports ===
# This must happen first, before importing anything from comfy

# Add scripts directory to path
scripts_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, scripts_dir)

# Install the shim
import flash_attn_shim
flash_attn_shim.install_shim()

# Verify it's installed
assert "flash_attn" in sys.modules, "flash_attn shim not installed!"
from flash_attn import flash_attn_func  # This should work now

print("Flash attention shim verified!")

# === STEP 2: Add --use-flash-attention to args if not present ===
if "--use-flash-attention" not in sys.argv:
    # Insert after script name
    sys.argv.insert(1, "--use-flash-attention")

# === STEP 3: Change to ComfyUI directory and run main.py ===
comfyui_dir = os.path.dirname(scripts_dir)  # Parent of scripts/
comfyui_main = os.path.join(comfyui_dir, "ComfyUI")

os.chdir(comfyui_main)
sys.path.insert(0, comfyui_main)

# Set __file__ for main.py compatibility
main_py_path = os.path.join(comfyui_main, "main.py")

# Update sys.argv[0] to be main.py
sys.argv[0] = main_py_path

# === STEP 4: Execute main.py with proper globals ===
# We use compile + exec with proper __file__ set
with open(main_py_path, 'r') as f:
    code = compile(f.read(), main_py_path, 'exec')

# Create globals with __file__ set correctly
globs = {
    '__name__': '__main__',
    '__file__': main_py_path,
    '__builtins__': __builtins__,
}

exec(code, globs)
