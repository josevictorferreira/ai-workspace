{
  description = "ComfyUI with ROCm support - Declarative Setup";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config = {
            allowUnfree = true;
            rocmSupport = true;
          };
        };

        python = pkgs.python312;

        # Python packages available in nixpkgs
        pythonEnv = python.withPackages (ps: with ps; [
          # PyTorch with ROCm
          torchWithRocm
          torchvision
          torchaudio

          # Core dependencies
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
        ]);

        # ROCm runtime libraries
        rocmPackages = with pkgs.rocmPackages; [
          rocm-runtime
          rocm-smi
          hip-common
          hipblas
          miopen
          rocblas
          rocsolver
          rocfft
        ];

        # Setup script wrapper
        setupScript = pkgs.writeShellScriptBin "comfyui-setup" ''
          cd "''${COMFYUI_ROOT:-$PWD}"
          exec python setup.py "$@"
        '';

        # Start script
        startScript = pkgs.writeShellScriptBin "comfyui-start" ''
          COMFYUI_DIR="''${COMFYUI_ROOT:-$PWD}/ComfyUI"

          if [ ! -d "$COMFYUI_DIR" ]; then
            echo "ComfyUI not found. Running setup first..."
            comfyui-setup
          fi

          cd "$COMFYUI_DIR"
          exec python main.py --listen 0.0.0.0 --port 8188 "$@"
        '';

      in {
        packages = {
          default = setupScript;
          setup = setupScript;
          start = startScript;
        };

        devShells.default = pkgs.mkShell {
          name = "comfyui-dev";

          packages = [
            pythonEnv
            pkgs.git
            pkgs.git-lfs
            pkgs.wget
            pkgs.curl
            pkgs.ffmpeg
            pkgs.portaudio
            setupScript
            startScript
          ] ++ rocmPackages;

          shellHook = ''
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath rocmPackages}:$LD_LIBRARY_PATH"

            # AMD GPU environment variables
            export HSA_OVERRIDE_GFX_VERSION="11.0.0"
            export PYTORCH_HIP_ALLOC_CONF="expandable_segments:True"
            export HIP_VISIBLE_DEVICES="0"

            # Setup virtual environment for pip packages not in nixpkgs
            VENV_DIR="$PWD/.venv"
            export VENV_DIR
            if [ ! -d "$VENV_DIR" ]; then
              echo "Creating virtual environment for additional pip packages..."
              python -m venv "$VENV_DIR" --system-site-packages
            fi
            source "$VENV_DIR/bin/activate"

            export COMFYUI_ROOT="$PWD"

            echo ""
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
          '';
        };

        # App for direct execution
        apps = {
          default = {
            type = "app";
            program = "${startScript}/bin/comfyui-start";
          };
          setup = {
            type = "app";
            program = "${setupScript}/bin/comfyui-setup";
          };
        };
      }
    );
}
