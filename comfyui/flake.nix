{
  description = "ComfyUI with ROCm support";

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

        # ComfyUI source
        comfyui-src = pkgs.fetchFromGitHub {
          owner = "comfyanonymous";
          repo = "ComfyUI";
          rev = "v0.5.1";
          hash = "sha256-mJf8p6ga9jQHXmHrQjeGs4fgAlRFnREQIPskNM0vwXQ=";
        };

        # Python packages available in nixpkgs
        pythonEnv = python.withPackages (ps: with ps; [
          # PyTorch with ROCm
          torchWithRocm
          torchvision
          torchaudio

          # Core dependencies from requirements_rocm.txt
          pip
          virtualenv
          numpy
          einops
          transformers
          tokenizers
          sentencepiece
          safetensors
          aiohttp
          yarl
          pyyaml
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

        # Packages not in nixpkgs - will be installed via pip
        pipPackages = [
          "spandrel"
          "comfyui-frontend-package"
          "comfyui-workflow-templates"
          "comfyui-embedded-docs"
        ];

      in {
        packages.default = pkgs.stdenv.mkDerivation {
          pname = "comfyui";
          version = "0.5.1";
          src = comfyui-src;

          nativeBuildInputs = [ pkgs.makeWrapper ];
          buildInputs = [ pythonEnv ] ++ rocmPackages;

          installPhase = ''
            mkdir -p $out/lib/comfyui
            cp -r . $out/lib/comfyui/

            mkdir -p $out/bin
            makeWrapper ${pythonEnv}/bin/python $out/bin/comfyui \
              --add-flags "$out/lib/comfyui/main.py" \
              --prefix LD_LIBRARY_PATH : "${pkgs.lib.makeLibraryPath rocmPackages}" \
              --set HSA_OVERRIDE_GFX_VERSION "11.0.0" \
              --set PYTORCH_HIP_ALLOC_CONF "expandable_segments:True"
          '';
        };

        devShells.default = pkgs.mkShell {
          name = "comfyui-dev";

          packages = [
            pythonEnv
            pkgs.git
            pkgs.wget
            pkgs.curl
            pkgs.ffmpeg
            pkgs.portaudio
          ] ++ rocmPackages;

          shellHook = ''
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath rocmPackages}:$LD_LIBRARY_PATH"

            # AMD GPU environment variables
            export HSA_OVERRIDE_GFX_VERSION="11.0.0"
            export PYTORCH_HIP_ALLOC_CONF="expandable_segments:True"
            export HIP_VISIBLE_DEVICES="0"

            # Setup virtual environment for pip packages not in nixpkgs
            VENV_DIR="$PWD/.venv"
            if [ ! -d "$VENV_DIR" ]; then
              echo "Creating virtual environment for additional pip packages..."
              python -m venv "$VENV_DIR" --system-site-packages
              source "$VENV_DIR/bin/activate"
              pip install --quiet ${builtins.concatStringsSep " " pipPackages}
            else
              source "$VENV_DIR/bin/activate"
            fi

            export COMFYUI_PATH="$PWD"

            echo ""
            echo "ComfyUI development shell with ROCm support"
            echo "============================================"
            echo ""
            echo "To start ComfyUI:"
            echo "  1. Clone if needed: git clone https://github.com/comfyanonymous/ComfyUI.git"
            echo "  2. cd ComfyUI && git checkout v0.5.1"
            echo "  3. python main.py --listen 0.0.0.0 --port 8188"
            echo ""
            echo "ROCm: enabled"
            echo "Python: ${python.version}"
            echo ""
          '';
        };

        # App for direct execution
        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/comfyui";
        };
      }
    );
}
