# Declarative Llama-CPP with Nix

This setup allows you to manage `llama-cpp` and your models entirely through Nix flakes.

## Features
- **Declarative Models**: Models are fetched by Nix and symlinked into a single directory.
- **Backend Switching**: Easily switch between `llama-cpp-rocm` and `llama-cpp-vulkan`.
- **Pre-configured Server**: Run the llama-server with a single command.

## Models available
- `qwopus-glm-18b`: Qwopus-GLM-18B-Merged-Q4_K_M (18B model, 10GB)
- `qwen-35b`: Qwen3.6-35B-A3B-UD-Q4_K_XL
- `gemma`: gemma-4-E4B-it-Q4_K_S
- `gemma-26b`: gemma-4-26B-A4B-it-UD-Q3_K_M
- `gemma-31b`: gemma-4-31b-jang-crack-Q4_K_M
- `qwopus-27b`: Qwopus3.5-27B-v3-TQ3_4S
- `qwen-27b`: Qwen3.5-27B-TQ3_1S
- `qwen36-27b`: Qwen3.6-27B (Q3_K_S)
- `qwen36-27b-speed`: Qwen3.6-27B (UD-IQ2_XXS, 50+ tok/s)
- `qwopus36-27b-mtp`: Qwopus3.6-27B-v2-MTP (Q3_K_S)
- `qwen35-9b-mtp`: Qwen3.5-9B-MTP (Q4_K_M)

## Usage

### Run the Server (Default: ROCm)
```bash
nix run .#qwopus-glm-18b
```

### Run the Server (Vulkan)
```bash
nix run .#qwopus-glm-18b-vulkan
```

### Enter a Development Shell
For ROCm:
```bash
nix develop
```

For Vulkan:
```bash
nix develop .#vulkan
```

In the shell, `LLAMA_MODELS_DIR` environment variable is set to the path containing your symlinked models.

### Adding New Models
1. Add the model URL and its SHA256 to `flake.nix` under the `models` set.
2. If you don't know the hash, use:
   ```bash
   nix-prefetch-url <URL>
   ```
3. Run `nix run .#server` and Nix will automatically download the new model.
