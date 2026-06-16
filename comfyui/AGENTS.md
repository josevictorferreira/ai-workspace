# ComfyUI

This directory contains a declarative Nix-based ComfyUI setup with ROCm support. It uses a Python virtual environment layered on top of Nix-provided PyTorch to avoid breaking GPU support when installing custom nodes.

## Layout

```
comfyui/
├── ComfyUI/              # Vendored upstream checkout (do not edit as your own)
├── scripts/              # Helper scripts (model sync, launchers, ROCm shims)
├── snapshots/            # Custom-node configuration snapshots
├── flake.nix             # Dev shell and launcher packages
├── flake.lock            # Pinned inputs
├── models.yaml           # Declarative model catalog
└── .venv/                # Python virtual environment (created by the shell)
```

## Entering the Environment

```bash
cd comfyui
nix develop
```

The shell links models, sets `PYTHONPATH`, and patches pip behavior so that `torch` and other ROCm-sensitive packages are not overwritten by naive `pip install` calls from custom nodes.

## Core Commands

- `comfy-launch` — Start ComfyUI on `0.0.0.0`.
- `comfy-launch-aule` — Start Aule Attention variant (RDNA2).
- `comfy-save` — Save current custom-node state to `snapshots/`.
- `comfy-restore` — Restore a saved custom-node snapshot.
- `comfy-models-sync` — Download/install all models declared in `models.yaml`.
- `comfy-model <url>` — Download a single model with automatic token injection.
- `comfy-node-install <name>` — Install a custom node while preserving the ROCm-safe torch setup.

## Declarative Models (`models.yaml`)

`models.yaml` is the single source of truth for models. Supported sources:

- `huggingface:` HuggingFace files (gated models need `HF_TOKEN` or `/run/secrets/hugging_face_api_key`)
- `civitai:` CivitAI files (needs `CIVITAI_API_TOKEN` or `/run/secrets/civitai_api_key`)
- `github:` Direct release/raw file downloads
- `git:` Clone entire repositories
- `url:` Direct HTTP/HTTPS links

Supported destination folders include `checkpoints`, `loras`, `vae`, `controlnet`, `clip`, `clip_vision`, `embeddings`, `upscale_models`, `diffusion_models`, `text_encoders`, `unet`, `audio`, `TTS`, and others.

Use the `tags` field to sync only a subset: `comfy-models-sync --tags audio,tts`.

## ROCm Notes

- `rocmSupport = true` is set in `flake.nix`.
- Required ROCm packages (`clr`, `rocblas`, `hipblas`, etc.) are brought in as runtime dependencies.
- `hipblaslt` is included for `libhipblaslt.so.0`, but its use may be disabled at runtime via environment variables for GPUs that lack Tensile support (e.g., gfx1030 / RX 6900 XT).
- The `flash_attn_shim.py` script helps custom nodes that expect Flash Attention without breaking the Nix torch build.

## Custom Nodes

Use `comfy-node-install <name>` instead of raw `git clone` into `ComfyUI/custom_nodes/`. It:

1. Installs the node into the managed location.
2. Installs declared `requirements.txt` into the venv.
3. Blocks reinstalls of Nix-provided PyTorch/ROCm wheels.

If a node absolutely needs a different torch build, document the override in this file and the command history.

## Common Gotchas

- `ComfyUI/` is a vendored upstream checkout. Do not commit changes to it unless you are intentionally upgrading the vendored version.
- GPU-related Nix builds are slow and memory-intensive; plan builds ahead of benchmark runs.
- If custom nodes fail to import, check that they are not trying to replace the Nix `torch` wheel.
- Models are linked, not copied, so `models.yaml` changes require a `comfy-models-sync` rerun.
