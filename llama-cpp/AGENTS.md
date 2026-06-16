# Llama-CPP

This directory contains a declarative Nix setup for running local LLMs with `llama.cpp`. Models are declared in `flake.nix` as fixed-output derivations and symlinked into a single runtime directory.

## Layout

```
llama-cpp/
├── flake.nix             # Dev shell and model server packages
├── flake.lock            # Pinned inputs
├── templates/            # Jinja chat templates
├── .hipfire_kernels/     # Kernel cache/artifacts
└── README.md             # Project notes
```

## Entering the Environment

```bash
cd llama-cpp
nix develop          # ROCm shell
nix develop .#vulkan # Vulkan shell
```

## Running a Model Server

Models are exposed as Nix packages named after the model key in `flake.nix`.

```bash
# ROCm (default)
nix run .#tesslate-omnicoder-9b-q4_k_s

# Vulkan variant
nix run .#tesslate-omnicoder-9b-q4_k_s-vulkan
```

Each package starts `llama-server` with the model file, context size, and chat template already configured.

## Adding a New Model

Edit the `models` attribute set in `flake.nix`:

```nix
"My-New-Model-Q4_K_M" = pkgs.fetchurl {
  url = "https://huggingface.co/.../resolve/main/My-New-Model-Q4_K_M.gguf";
  sha256 = "sha256-...";
};
```

Then update the SHA256. The easiest way is to set `sha256 = pkgs.lib.fakeSha256;`, run `nix run .#my-new-model-q4_k_m`, and paste the expected hash from the error message.

## Chat Templates

Templates in `templates/` are Jinja files passed to `llama-server` via `--chat-template`. Place reusable templates here and reference them in the `flake.nix` server configuration.

## Common Gotchas

- Model downloads are fixed-output derivations; the URL and SHA256 must be exact.
- `.hipfire_kernels/` and `result` are generated artifacts and should not be committed.
- ROCm builds can take significant time and RAM on first evaluation.
- If a model fails to start, verify the chat template file path and the context size fit your VRAM.
- Prefer `nix run` for quick tests and `nix develop` when you need to inspect `llama-server` arguments or run related tools.
