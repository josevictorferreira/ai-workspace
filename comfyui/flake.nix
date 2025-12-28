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
        rocmDependencies = with pkgs.rocmPackages; [
          rocm-runtime
          rocm-smi
          rocminfo
          hip-common
          hipblas
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
          pkgs.portaudio
          pkgs.uv
          pkgs.wget
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

        capGpu = pkgs.writeShellScriptBin "cap-gpu" ''
          echo manual | sudo tee /sys/class/drm/card0/device/power_dpm_force_performance_level
          sudo rocm-smi --setpoweroverdrive 281
          sudo rocm-smi --setsrange 500 1800
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
      in
      {
        devShells.default = pkgs.mkShell {
          name = "comfyui-rocm";

          packages = [
            pythonEnv
            capGpu
            comfySave
            comfyRestore
          ]
          ++ rocmDependencies
          ++ buildInputs;

          shellHook = ''
            # --- 6900 XT STABILITY FIXES ---
            export HSA_OVERRIDE_GFX_VERSION="10.3.0"
            export HSA_ENABLE_SDMA="0"
            export PYTORCH_ALLOC_CONF="garbage_collection_threshold:0.8,max_split_size_mb:128"
            export HIP_VISIBLE_DEVICES="0"
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath rocmDependencies}:$LD_LIBRARY_PATH"

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

            # Install additional packages (transformers needs compatible huggingface_hub<1.0)
            pip install --quiet "huggingface_hub>=0.34.0,<1.0" "transformers>=4.40.0" aule-attention spandrel

            # Set workspace to current directory
            export COMFYUI_WORKSPACE="$PWD"

            echo "============================================"
            echo "  ComfyUI Environment (comfy-cli)"
            echo "============================================"
            echo ""
            echo "Commands:"
            echo "  comfy install              - Install ComfyUI"
            echo "  comfy launch               - Start ComfyUI"
            echo "  comfy launch --background  - Start in background"
            echo "  comfy stop                 - Stop background instance"
            echo "  comfy node install <name>  - Install custom node"
            echo "  comfy node update all      - Update all nodes"
            echo "  comfy model download --url <url>  - Download model"
            echo "  comfy which                - Show current workspace"
            echo "  comfy env                  - Show environment info"
            echo "  cap-gpu                    - Downgrade GPU for stability"
            echo ""
            echo "Snapshot Management:"
            echo "  comfy-save                 - Save current config to snapshots/"
            echo "  comfy-restore              - Restore from latest snapshot"
            echo ""
            echo "ROCm: enabled | Python: ${python.version}"
            echo ""

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
            fi

            # Set this workspace as default
            comfy set-default "$PWD" 2>/dev/null || true
            echo ""
          '';
        };
      }
    );
}
