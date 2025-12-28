{
  description = "ComfyUI with ROCm support - Stable Setup for 6900 XT";
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

        # 1. Define the ROCm packages explicitly so we can use them in LD_LIBRARY_PATH
        # 'clr' is CRITICAL: It contains libamdhip64.so and the hip symbols you were missing.
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
          clr # <--- THIS FIXES THE 'hipGetErrorString' ERROR
        ];

        # 2. Build Tooling
        # Required for "Custom Nodes" that try to compile C++/CUDA code via pip
        buildInputs = [
          pkgs.gcc
          pkgs.cmake
          pkgs.ninja
          pkgs.git
          pkgs.git-lfs
          pkgs.ffmpeg
          pkgs.portaudio
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

        # Setup script wrapper
        setupScript = pkgs.writeShellScriptBin "comfyui-setup" ''
          cd "''${COMFYUI_ROOT:-$PWD}"
          if [ -f "setup.py" ]; then
             exec python setup.py "$@"
          else
             echo "No setup.py found. Usage: Ensure you are in the ComfyUI folder."
          fi
        '';

        # Start script
        startScript = pkgs.writeShellScriptBin "comfyui-start" ''
          COMFYUI_DIR="''${COMFYUI_ROOT:-$PWD}/ComfyUI"
          if [ ! -d "$COMFYUI_DIR" ]; then
            echo "ComfyUI directory not found at $COMFYUI_DIR"
            exit 1
          fi
          cd "$COMFYUI_DIR"
          echo "Starting ComfyUI..."
          exec python main.py --listen 0.0.0.0 --port 8188 "$@"
        '';
      in
      {
        packages = {
          default = setupScript;
          setup = setupScript;
          start = startScript;
        };

        devShells.default = pkgs.mkShell {
          name = "comfyui-rocm-stable";

          # Include both Python env and the system libs
          packages = [
            pythonEnv
            setupScript
            startScript
          ]
          ++ rocmDependencies
          ++ buildInputs;

          shellHook = ''
            # --- 6900 XT STABILITY FIXES ---
            # 1. Force RDNA2 Architecture
            export HSA_OVERRIDE_GFX_VERSION="10.3.0"

            # 2. Disable SDMA to prevent "Ring Hang" / System freeze
            export HSA_ENABLE_SDMA="0"

            # 3. Memory Allocation fix for PyTorch on consumer cards
            export PYTORCH_HIP_ALLOC_CONF="expandable_segments:True"

            # 4. Device Visibility
            export HIP_VISIBLE_DEVICES="0"

            # 5. THE LINKING FIX
            # We explicitly construct the library path from the rocmDependencies list above.
            # This ensures 'clr' (libamdhip64.so) is found by Python extensions.
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath rocmDependencies}:$LD_LIBRARY_PATH"
            # Remove the bad /opt/rocm path that confuses Nix

            # --- VENV SETUP ---
            VENV_DIR="$PWD/.venv"
            export VENV_DIR
            if [ ! -d "$VENV_DIR" ]; then
              echo "Creating virtual environment..."
              # We use --system-site-packages so it sees the Nix-installed Torch
              python -m venv "$VENV_DIR" --system-site-packages
            fi
            source "$VENV_DIR/bin/activate"
            export COMFYUI_ROOT="$PWD"

            echo "============================================"
            echo "  ComfyUI Declarative Environment"
            echo "============================================"
            echo ""
            echo "Commands:"
            echo "  comfyui-setup         - Install/update ComfyUI, nodes, and models"
            echo "  comfyui-setup --all   - Include optional models"
            echo "  comfyui-start         - Start ComfyUI server"
            echo ""
            echo "Configuration: Edit comfyui.yaml"
            echo ""
            echo "ROCm: enabled | Python: ${python.version}"
            echo ""
            # Auto-run setup if ComfyUI not installed
            if [ ! -d "ComfyUI" ]; then
              echo "First run detected. Running setup..."
              comfyui-setup
            fi
            echo ""
          '';
        };
      }
    );
}
