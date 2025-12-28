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
            transformers
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
      in
      {
        devShells.default = pkgs.mkShell {
          name = "comfyui-rocm";

          packages = [
            pythonEnv
            capGpu
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

            # Install additional packages
            pip install --quiet aule-attention huggingface_hub spandrel

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
            echo "ROCm: enabled | Python: ${python.version}"
            echo ""

            # Auto-install ComfyUI if not present
            if [ ! -d "ComfyUI" ]; then
              echo "First run detected. Installing ComfyUI..."
              comfy --here install --skip-manager
              comfy --here node install ComfyUI-Manager
            fi

            # Set this workspace as default
            comfy set-default "$PWD" 2>/dev/null || true
            echo ""
          '';
        };
      }
    );
}
