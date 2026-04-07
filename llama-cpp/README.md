# Declarative Llama-CPP with Nix

This setup allows you to manage `llama-cpp` and your models entirely through Nix flakes.

## Features
- **Declarative Models**: Models are fetched by Nix and symlinked into a single directory.
- **Backend Switching**: Easily switch between `llama-cpp-rocm` and `llama-cpp-vulkan`.
- **Pre-configured Server**: Run the llama-server with a single command.

## Usage

### Run the Server (Default: ROCm)
```bash
nix run .#server
```

### Run the Server (Vulkan)
```bash
nix run .#server-vulkan
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
