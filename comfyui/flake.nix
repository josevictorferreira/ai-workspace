{
  description = "ComfyUI with ROCm support using comfy-cli";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config = {
            allowUnfree = true;
            rocmSupport = true;
          };
        };
        python = pkgs.python312;

        # ROCm packages - 'clr' contains libamdhip64.so (CRITICAL for hip symbols)
        # NOTE: hipblaslt removed - gfx1030 (6900 XT) lacks Tensile library support
        rocmDependencies = with pkgs.rocmPackages; [
          rocm-runtime
          rocm-smi
          rocminfo
          hip-common
          # hipblas
          # hipblaslt # Provides libhipblaslt.so.0 (required by PyTorch); actual use disabled via env vars
          miopen
          rocblas
          rocsolver
          rocfft
          clr
        ];

        # Build tools for custom nodes that compile C++/CUDA code
        buildInputs = [
          pkgs.gcc
          pkgs.cmake
          pkgs.ninja
          pkgs.git
          pkgs.git-lfs
          pkgs.ffmpeg
          pkgs.uv
          pkgs.wget
        ];

        # Audio libraries needed by custom nodes (TTS, audio processing)
        audioLibs = [
          pkgs.portaudio
          pkgs.libsamplerate
        ];

        # Additional libraries required by pip-installed PyTorch ROCm
        torchLibs = [
          pkgs.zstd
          pkgs.libdrm  # Required for amdgpu.ids path resolution
        ];

        # Vulkan support for Aule Attention backend
        vulkanLibs = [
          pkgs.vulkan-loader
          pkgs.vulkan-headers
          pkgs.vulkan-tools
        ];

        pythonEnv = python.withPackages (
          ps: with ps; [
            torchWithRocm
            torchvision
            torchaudio
            pip
            virtualenv
            pyyaml
            numpy
            einops
            # transformers/huggingface_hub installed via pip for version compatibility
            tokenizers
            sentencepiece
            safetensors
            aiohttp
            yarl
            pillow
            scipy
            sounddevice
            tqdm
            psutil
            alembic
            sqlalchemy
            kornia
            av
            pydantic
            pydantic-settings
            torchsde
            soundfile
            gitpython
          ]
        );

        gpuCap = pkgs.writeShellScriptBin "gpu-cap" ''
          echo manual | sudo tee /sys/class/drm/card0/device/power_dpm_force_performance_level
          sudo rocm-smi --setpoweroverdrive 283
          sudo rocm-smi --setsrange 500 2400
          sudo rocm-smi --showclocks
          sudo rocm-smi --showpower
        '';

        # Helper script to save ComfyUI snapshots
        comfySave = pkgs.writeShellScriptBin "comfy-save" ''
          SNAPSHOT_DIR="$COMFYUI_WORKSPACE/snapshots"
          mkdir -p "$SNAPSHOT_DIR"
          TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
          SNAPSHOT_FILE="$SNAPSHOT_DIR/''${TIMESTAMP}_snapshot.json"
          
          echo "Saving snapshot to $SNAPSHOT_FILE..."
          comfy node save-snapshot
          
          # comfy-cli saves snapshots to ComfyUI/user/default/snapshots/
          LATEST=$(ls -t "$COMFYUI_WORKSPACE/ComfyUI/user/default/snapshots/"*.json 2>/dev/null | head -1)
          if [ -n "$LATEST" ]; then
            cp "$LATEST" "$SNAPSHOT_FILE"
            echo "Snapshot saved: $SNAPSHOT_FILE"
            echo "Don't forget to commit it to version control!"
          else
            echo "Error: Could not find generated snapshot"
            exit 1
          fi
        '';

        # Helper script to restore from latest versioned snapshot
        comfyRestore = pkgs.writeShellScriptBin "comfy-restore" ''
          SNAPSHOT_DIR="$COMFYUI_WORKSPACE/snapshots"
          
          if [ ! -d "$SNAPSHOT_DIR" ]; then
            echo "No snapshots directory found"
            exit 1
          fi
          
          LATEST=$(ls -t "$SNAPSHOT_DIR"/*.json 2>/dev/null | head -1)
          if [ -z "$LATEST" ]; then
            echo "No snapshots found in $SNAPSHOT_DIR"
            exit 1
          fi
          
          echo "Restoring from: $LATEST"
          
          # Copy snapshot to ComfyUI's snapshot directory
          COMFY_SNAP_DIR="$COMFYUI_WORKSPACE/ComfyUI/user/default/snapshots"
          mkdir -p "$COMFY_SNAP_DIR"
          cp "$LATEST" "$COMFY_SNAP_DIR/"
          
          # Use cm-cli directly with absolute path for reliability
          cd "$COMFYUI_WORKSPACE/ComfyUI"
          "$VENV_DIR/bin/python" "custom_nodes/ComfyUI-Manager/cm-cli.py" restore-snapshot "$COMFY_SNAP_DIR/$(basename "$LATEST")"
        '';

        # Wrapper to launch ComfyUI on 0.0.0.0 with relaxed security for Manager
        comfyLaunch = pkgs.writeShellScriptBin "comfy-launch" ''
          # Completely disable hipblaslt for gfx1030 (no Tensile library support)
          export TORCH_BLAS_PREFER_HIPBLASLT="0"
          export PYTORCH_TUNABLEOP_ENABLED="0"
          export PYTORCH_TUNABLEOP_HIPBLASLT_ENABLED="0"
          export CM_SECURITY_LEVEL="weak"
          comfy launch -- --auto-launch --listen 0.0.0.0 "$@"
        '';

        # Launch ComfyUI with Aule Attention (flash attention for RDNA2)
        comfyLaunchAule = pkgs.writeShellScriptBin "comfy-launch-aule" ''
          # Completely disable hipblaslt for gfx1030 (no Tensile library support)
          export TORCH_BLAS_PREFER_HIPBLASLT="0"
          export PYTORCH_TUNABLEOP_ENABLED="0"
          export PYTORCH_TUNABLEOP_HIPBLASLT_ENABLED="0"
          export CM_SECURITY_LEVEL="weak"
          
          echo "============================================"
          echo "  Launching ComfyUI with Aule Attention"
          echo "============================================"
          
          cd "$COMFYUI_WORKSPACE/ComfyUI"
          
          # Create a launcher script that installs shim before any imports
          exec python "$COMFYUI_WORKSPACE/scripts/comfy_aule_launcher.py" --listen 0.0.0.0 "$@"
        '';

        # Model downloader with automatic token injection
        comfyModel = pkgs.writeShellScriptBin "comfy-model" ''
          if [ -z "$1" ]; then
            echo "Usage: comfy-model <url> [extra-args...]"
            echo "Downloads a model with automatic HuggingFace/CivitAI token injection"
            exit 1
          fi

          URL="$1"
          shift

          if [[ "$URL" == *"huggingface.co"* ]] || [[ "$URL" == *"hf.co"* ]]; then
            HF_TOKEN=$(cat /run/secrets/hugging_face_api_key 2>/dev/null)
            if [ -n "$HF_TOKEN" ]; then
              comfy model download --set-hf-api-token "$HF_TOKEN" --url "$URL" "$@"
            else
              echo "Warning: HuggingFace token not found at /run/secrets/hugging_face_api_key"
              comfy model download --url "$URL" "$@"
            fi
          elif [[ "$URL" == *"civitai.com"* ]]; then
            CIVITAI_TOKEN=$(cat /run/secrets/civitai_api_key 2>/dev/null)
            if [ -n "$CIVITAI_TOKEN" ]; then
              comfy model download --set-civitai-api-token "$CIVITAI_TOKEN" --url "$URL" "$@"
            else
              echo "Warning: CivitAI token not found at /run/secrets/civitai_api_key"
              comfy model download --url "$URL" "$@"
            fi
          else
            comfy model download --url "$URL" "$@"
          fi
        '';

        # ROCm-safe node installer (excludes torch packages)
        comfyNodeInstall = pkgs.writeShellScriptBin "comfy-node-install" ''
          if [ -z "$1" ]; then
            echo "Usage: comfy-node-install <node-name-or-git-url>"
            echo "Installs a custom node with ROCm-compatible dependencies"
            exit 1
          fi

          NODE_ARG="$1"
          
          # Install the node (this may install CUDA torch)
          echo "Installing node: $NODE_ARG"
          comfy node install "$NODE_ARG"
          
          # Find the installed node directory
          if [[ "$NODE_ARG" == http* ]]; then
            # Git URL - extract repo name
            NODE_NAME=$(basename "$NODE_ARG" .git)
          else
            NODE_NAME="$NODE_ARG"
          fi
          
          # Search for the node in custom_nodes
          NODE_DIR=$(find "$COMFYUI_WORKSPACE/ComfyUI/custom_nodes" -maxdepth 1 -type d -iname "*$NODE_NAME*" | head -1)
          
          if [ -z "$NODE_DIR" ]; then
            echo "Warning: Could not find node directory for $NODE_NAME"
            echo "You may need to manually fix torch dependencies"
            exit 0
          fi
          
          # Fix ROCm: uninstall any CUDA torch and reinstall requirements without torch
          echo "Fixing ROCm compatibility..."
          pip uninstall -y torch torchvision torchaudio 2>/dev/null || true
          pip uninstall -y nvidia-cublas-cu12 nvidia-cuda-cupti-cu12 nvidia-cuda-nvrtc-cu12 \
            nvidia-cuda-runtime-cu12 nvidia-cudnn-cu12 nvidia-cufft-cu12 nvidia-cufile-cu12 \
            nvidia-curand-cu12 nvidia-cusolver-cu12 nvidia-cusparse-cu12 nvidia-cusparselt-cu12 \
            nvidia-nccl-cu12 nvidia-nvjitlink-cu12 nvidia-nvshmem-cu12 nvidia-nvtx-cu12 2>/dev/null || true
          
          # Reinstall requirements without torch lines
          if [ -f "$NODE_DIR/requirements.txt" ]; then
            echo "Reinstalling dependencies (excluding torch)..."
            grep -v "^torch" "$NODE_DIR/requirements.txt" | grep -v "^#" | grep -v "^$" | \
              pip install -r /dev/stdin 2>&1 || true
          fi
          
          # Run install.py if it exists (some nodes need this)
          if [ -f "$NODE_DIR/install.py" ]; then
            echo "Running install.py..."
            python "$NODE_DIR/install.py" 2>&1 || true
          fi
          
          echo "Done! Node installed with ROCm torch preserved."
        '';

        # Declarative model sync script wrapper
        comfyModelsSync = pkgs.writeShellScriptBin "comfy-models-sync" ''
          python "$COMFYUI_WORKSPACE/scripts/comfy-models-sync.py" "$@"
        '';

        # Fix for amdgpu.ids path (one-time setup, requires sudo)
        fixAmdgpuIds = pkgs.writeShellScriptBin "fix-amdgpu-ids" ''
          if [ -f /opt/amdgpu/share/libdrm/amdgpu.ids ]; then
            echo "amdgpu.ids symlink already exists at /opt/amdgpu/share/libdrm/amdgpu.ids"
            exit 0
          fi
          
          echo "Creating symlink for amdgpu.ids (fixes ROCm/Vulkan detection warnings)"
          echo "This requires sudo and only needs to be done once."
          echo ""
          
          sudo mkdir -p /opt/amdgpu/share/libdrm
          sudo ln -sf "${pkgs.libdrm}/share/libdrm/amdgpu.ids" /opt/amdgpu/share/libdrm/amdgpu.ids
          
          if [ -f /opt/amdgpu/share/libdrm/amdgpu.ids ]; then
            echo "Success! Symlink created."
            ls -la /opt/amdgpu/share/libdrm/amdgpu.ids
          else
            echo "Failed to create symlink"
            exit 1
          fi
        '';

        # Aule Attention - hardware-agnostic FlashAttention that works on RDNA2
        # Uses Triton for ROCm/CUDA or Vulkan for consumer AMD GPUs
        auleAttnInstall = pkgs.writeShellScriptBin "aule-attn-install" ''
          set -e
          
          # Check if already installed
          if python -c "import aule; print(f'Aule Attention already installed')" 2>/dev/null; then
            python -c "from aule import get_available_backends; print(f'Available backends: {get_available_backends()}')"
            exit 0
          fi
          
          echo "============================================"
          echo "  Installing Aule Attention"
          echo "  (Hardware-agnostic FlashAttention)"
          echo "============================================"
          echo ""
          echo "This works on AMD RDNA2 (6900 XT) via Triton/Vulkan backends"
          echo ""
          
          pip install --quiet aule-attention
          
          # Verify installation
          if python -c "import aule; from aule import get_available_backends; print(f'Aule Attention installed! Backends: {get_available_backends()}')" 2>/dev/null; then
            echo ""
            echo "============================================"
            echo "  Aule Attention installed successfully!"
            echo "============================================"
          else
            echo "Warning: Installation may have failed"
            echo "Try: pip install aule-attention"
          fi
        '';

        # Keep old name as alias for discoverability
        flashAttnInstall = pkgs.writeShellScriptBin "flash-attn-install" ''
          echo "NOTE: ROCm Flash Attention doesn't support RDNA2 (6900 XT)"
          echo "Use 'aule-attn-install' instead for a compatible alternative."
          echo ""
          exec ${pkgs.lib.getExe auleAttnInstall}
        '';

        comfyHelp = pkgs.writeShellScriptBin "comfy-help" ''
          echo "============================================"
          echo "  ComfyUI Environment (comfy-cli)"
          echo "============================================"
          echo ""
          echo "Commands:"
          echo "  comfy install              - Install ComfyUI"
          echo "  comfy-launch               - Start ComfyUI (0.0.0.0)"
          echo "  comfy-launch-aule          - Start with Aule Attention (RDNA2)"
          echo "  comfy stop                 - Stop background instance"
          echo "  comfy-node-install <name>  - Install node (ROCm-safe)"
          echo "  comfy node update all      - Update all nodes"
          echo "  comfy-model <url>          - Download model (auto-injects tokens)"
          echo "  comfy which                - Show current workspace"
          echo "  comfy env                  - Show environment info"
          echo ""
          echo "Model Management:"
          echo "  comfy-models-sync          - Sync models from models.yaml"
          echo "  comfy-models-sync list     - List configured models"
          echo "  comfy-models-sync add ...  - Add a model to models.yaml"
          echo "  comfy-models-sync --help   - Show model sync options"
          echo ""
          echo "Snapshot Management:"
          echo "  comfy-save                 - Save current config to snapshots/"
          echo "  comfy-restore              - Restore from latest snapshot"
          echo ""
          echo "Hardware Management:"
          echo "  gpu-cap                    - Downgrade GPU for stability"
          echo "  aule-attn-install          - Install Aule Attention (RDNA2 compatible)"
          echo "  fix-amdgpu-ids             - Fix amdgpu.ids path (one-time, sudo)"
          echo ""
          echo "Help:"
          echo "  comfy-help                 - Show this help"
          echo ""
          echo "ROCm: enabled | Python: ${python.version}"
          echo ""
        '';
      in
      {
        devShells.default = pkgs.mkShell {
          name = "comfyui-rocm";

          packages = [
            pythonEnv
            gpuCap
            comfySave
            comfyRestore
            comfyLaunch
            comfyLaunchAule
            comfyModel
            comfyNodeInstall
            comfyModelsSync
            auleAttnInstall
            flashAttnInstall
            fixAmdgpuIds
            comfyHelp
          ]
          ++ rocmDependencies
          ++ buildInputs
          ++ audioLibs
          ++ vulkanLibs;

          shellHook = ''
            # --- 6900 XT (gfx1030) STABILITY FIXES ---
            export HSA_OVERRIDE_GFX_VERSION="10.3.0"
            export HSA_ENABLE_SDMA="0"
            export PYTORCH_ALLOC_CONF="garbage_collection_threshold:0.8,max_split_size_mb:128"
            export HIP_VISIBLE_DEVICES="0"
            # Completely disable hipblaslt - gfx1030 lacks Tensile library support
            # TunableOp uses hipblaslt internally which causes errors on RDNA2
            export TORCH_BLAS_PREFER_HIPBLASLT="0"
            export PYTORCH_TUNABLEOP_ENABLED="0"
            export PYTORCH_TUNABLEOP_HIPBLASLT_ENABLED="0"
            
            # --- ROCm BUILD ENVIRONMENT ---
            export ROCM_PATH="${pkgs.rocmPackages.clr}"
            export HIP_PATH="${pkgs.rocmPackages.clr}"
            export PYTORCH_ROCM_ARCH="gfx1030"
            
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath (rocmDependencies ++ audioLibs ++ torchLibs ++ vulkanLibs)}:${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH"
            export PATH="${pkgs.rocmPackages.clr}/bin:$PATH"
            
            # --- FIX: libdrm amdgpu.ids path for Vulkan/ROCm detection ---
            export LIBDRM_AMDGPU_IDS_PATH="${pkgs.libdrm}/share/libdrm/amdgpu.ids"
            # Hint user about the symlink if not present
            if [ ! -f /opt/amdgpu/share/libdrm/amdgpu.ids ]; then
              export AMDGPU_IDS_MISSING=1
            fi

            # --- VENV SETUP ---
            VENV_DIR="$PWD/.venv"
            export VENV_DIR
            if [ ! -d "$VENV_DIR" ]; then
              echo "Creating virtual environment..."
              python -m venv "$VENV_DIR" --system-site-packages
            fi
            source "$VENV_DIR/bin/activate"

            # Install comfy-cli if not present
            if ! command -v comfy &> /dev/null; then
              echo "Installing comfy-cli..."
              pip install --quiet comfy-cli
            fi

            # Set workspace to current directory
            export COMFYUI_WORKSPACE="$PWD"

            ${pkgs.lib.getExe comfyHelp}

            # Auto-install ComfyUI if not present
            if [ ! -d "ComfyUI" ]; then
              echo "First run detected. Installing ComfyUI..."
              comfy --here install
              
              # Auto-restore from latest versioned snapshot if available
              if [ -d "snapshots" ] && ls snapshots/*.json &>/dev/null; then
                echo ""
                echo "Found versioned snapshots. Restoring configuration..."
                comfy-restore
              fi
              
              # Auto-sync models from models.yaml if present
              if [ -f "models.yaml" ]; then
                echo ""
                echo "Found models.yaml. Syncing models..."
                comfy-models-sync
              fi
            fi


            # --- DECLARATIVE OUTPUT & WORKFLOW DIRECTORIES ---
            OUTPUT_DIR="$HOME/Homelab/images/ai-generations"
            WORKFLOW_DIR="$HOME/Homelab/backups/workflows"
            COMFY_OUTPUT="$PWD/ComfyUI/output"
            COMFY_WORKFLOWS="$PWD/ComfyUI/user/default/workflows"

            # Ensure target directories exist
            mkdir -p "$OUTPUT_DIR"
            mkdir -p "$WORKFLOW_DIR"

            # Setup output symlink (only if ComfyUI is installed)
            if [ -d "$PWD/ComfyUI" ]; then
              if [ -d "$COMFY_OUTPUT" ] && [ ! -L "$COMFY_OUTPUT" ]; then
                # Move existing outputs to target dir and replace with symlink
                if [ "$(ls -A "$COMFY_OUTPUT" 2>/dev/null)" ]; then
                  mv "$COMFY_OUTPUT"/* "$OUTPUT_DIR/" 2>/dev/null || true
                fi
                rm -rf "$COMFY_OUTPUT"
                ln -sf "$OUTPUT_DIR" "$COMFY_OUTPUT"
                echo "Linked outputs -> $OUTPUT_DIR"
              elif [ ! -e "$COMFY_OUTPUT" ]; then
                ln -sf "$OUTPUT_DIR" "$COMFY_OUTPUT"
                echo "Linked outputs -> $OUTPUT_DIR"
              fi

              # Setup workflows symlink
              mkdir -p "$PWD/ComfyUI/user/default"
              if [ -d "$COMFY_WORKFLOWS" ] && [ ! -L "$COMFY_WORKFLOWS" ]; then
                # Move existing workflows to target dir and replace with symlink
                if [ "$(ls -A "$COMFY_WORKFLOWS" 2>/dev/null)" ]; then
                  mv "$COMFY_WORKFLOWS"/* "$WORKFLOW_DIR/" 2>/dev/null || true
                fi
                rm -rf "$COMFY_WORKFLOWS"
                ln -sf "$WORKFLOW_DIR" "$COMFY_WORKFLOWS"
                echo "Linked workflows -> $WORKFLOW_DIR"
              elif [ ! -e "$COMFY_WORKFLOWS" ]; then
                ln -sf "$WORKFLOW_DIR" "$COMFY_WORKFLOWS"
                echo "Linked workflows -> $WORKFLOW_DIR"
              fi
            fi

            # Set this workspace as default
            comfy set-default "$PWD" 2>/dev/null || true
            echo ""
          '';
        };
      }
    );
}
