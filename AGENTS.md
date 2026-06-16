# AI Workspace

This repository is a collection of isolated AI/ML projects, tools, and benchmarks. Every subproject that needs dependencies is managed through its own Nix flake, so reproducible environments are the default.

## Repository Layout

```
.
├── comfyui/                  # Declarative ComfyUI setup with ROCm support
├── llama-cpp/                # Declarative local LLM servers via llama.cpp
├── benchmarks/               # LLM evaluation suites
│   ├── coding-auto-complete/
│   ├── rails-inventory-system/
│   ├── real-estate-normalizer/
│   ├── real-estate-normalizer-v2/
│   └── real-estate-page-design/
├── AGENTS.md                 # This file
└── README.md                 # Very short top-level notes
```

There is **no root `flake.nix`**. Enter the Nix shell of the specific subproject you are working on.

## Cross-Cutting Conventions

- **Nix-first development**: If a directory contains a `flake.nix`, use `nix develop` before running tests, scripts, or builds.
- **Subproject autonomy**: Each directory owns its dependencies, lock file, and scripts. Do not add global package manifests at the workspace root unless the change truly spans every project.
- **Environment variables**: API keys and provider credentials live in the environment or in per-user config files (e.g., `~/benchmark-providers.json`). Never commit secrets. `.env.dist` exists only as documentation for optional container variables.
- **Git hygiene**: `git status` before you edit. Several generated artifacts (`.sisyphus/`, `outputs/`, `__pycache__/`, `ComfyUI/` vendored checkout) are ignored, but some may still appear as untracked files.
- **Documentation locality**: Prefer adding guidance to the `AGENTS.md` closest to the code it describes. Read the sub-`AGENTS.md` before making non-trivial changes in that directory.

## Domain Quick Reference

### ComfyUI (`comfyui/`)

- Enter environment: `cd comfyui && nix develop`
- Launch: `comfy-launch` or `comfy-launch-aule`
- Sync models: `comfy-models-sync` (driven by `models.yaml`)
- Install a custom node safely: `comfy-node-install <name>`

See [`comfyui/AGENTS.md`](comfyui/AGENTS.md) for ROCm/venv details.

### Llama-CPP (`llama-cpp/`)

- Run a model server (ROCm): `nix run .#<model_name>`
- Run a model server (Vulkan): `nix run .#<model_name>-vulkan`
- Enter dev shell: `nix develop` (ROCm) or `nix develop .#vulkan`
- Add models by editing `flake.nix` with the URL and SHA256.

See [`llama-cpp/AGENTS.md`](llama-cpp/AGENTS.md) for model declaration conventions.

### Benchmarks (`benchmarks/`)

- Rails inventory benchmark: `make benchmark MODEL=<model>` or `make benchmark-manual`
- Python benchmarks: `python run_benchmarks.py --model <model> [--openrouter]`
- Input data comes from `PROMPT.md` and `data.json`; outputs land in `outputs/`.

See [`benchmarks/AGENTS.md`](benchmarks/AGENTS.md) and the Rails-specific `AGENTS.md` for details.

## Development Guidelines

1. **Start in the right shell**: If a `flake.nix` exists in the directory, run `nix develop` before anything else.
2. **Read local `AGENTS.md`**: Subdirectories such as `benchmarks/rails-inventory-system/` have specialized instructions.
3. **Do not leak secrets**: API keys are loaded from environment variables or external config files.
4. **Keep changes subproject-scoped**: Avoid cross-subproject refactorings unless the change is explicitly workspace-wide.
5. **Verify with the actual command**: After editing Nix code, run `nix flake check` or the relevant `nix run`/`nix develop` command. After editing benchmark runners, run a small test with a cheap model before a full benchmark.

## Common Gotchas

- `comfyui/ComfyUI/` is a vendored/upstream checkout. Do not treat it as source code you own.
- ROCm support depends on `rocmSupport = true` and specific `rocmPackages`. GPU-related Nix builds can be slow and memory-intensive.
- Benchmark results and worktrees are generated under `.sisyphus/` and `worktrees-*`; know whether you are cleaning artifacts or deleting valuable results.
- Some Python benchmarks write to `outputs/` and `__pycache__/`. These are ignored by Git but can clutter `git status`.
