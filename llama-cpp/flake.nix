{
  description = "Declarative llama-cpp environment with ROCm and Vulkan support";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    llama-cpp.url = "github:ggerganov/llama.cpp";
    llama-cpp.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      llama-cpp,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };

        # --- Declarative Models ---
        # Add your models here. They will be downloaded by Nix and symlinked into a single directory.
        models = {
          "Tesslate_OmniCoder-9B-Q4_K_S" = pkgs.fetchurl {
            url = "https://huggingface.co/bartowski/Tesslate_OmniCoder-9B-GGUF/resolve/main/Tesslate_OmniCoder-9B-Q4_K_S.gguf";
            sha256 = "sha256-88POLoyURf3H06u0ZwwEJaZOzP3JNhOqCj1xkn/3U7w=";
          };
          "Qwen3.5-0.8B.Q4_K_S" = pkgs.fetchurl {
            url = "https://huggingface.co/Jackrong/Qwen3.5-0.8B-Claude-4.6-Opus-Reasoning-Distilled-GGUF/resolve/main/Qwen3.5-0.8B.Q4_K_S.gguf";
            sha256 = "sha256-k+UlZTXqpHKpcxfwDiGovg2FEYw6Dq7khbPsFj1Bo4g=";
          };
          "Qwen3.5-9b-Sushi-Coder-RL.Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/bigatuna/Qwen3.5-9b-Sushi-Coder-RL-GGUF/resolve/main/Qwen3.5-9b-Sushi-Coder-RL.Q4_K_M.gguf";
            sha256 = "sha256-q3STufp8IUQQROLldV+t3+jPEwZM4xnV/KoiE+Lkzsg=";
          };
          "Bonsai-8B" = pkgs.fetchurl {
            url = "https://huggingface.co/prism-ml/Bonsai-8B-gguf/resolve/main/Bonsai-8B.gguf";
            sha256 = "sha256-KEozWqP7LO07GwH8tAsIqng+O3CDJ2fw3S4/36E0vVQ=";
          };
          "nvidia_Nemotron-Cascade-2-30B-A3B-Q4_0" = pkgs.fetchurl {
            url = "https://huggingface.co/bartowski/nvidia_Nemotron-Cascade-2-30B-A3B-GGUF/resolve/main/nvidia_Nemotron-Cascade-2-30B-A3B-Q4_0.gguf";
            sha256 = "sha256-pJ/12kvlAjXVqmyLeVb/AMwjlo8oUxRa+EsDsdRMGnE=";
          };
          "Qwen3.5-27B-TQ3_1S" = pkgs.fetchurl {
            url = "https://huggingface.co/YTan2000/Qwen3.5-27B-TQ3_1S/resolve/main/Qwen3.5-27B-TQ3_1S.gguf";
            sha256 = "sha256-1fNaTk/3/Irj9aAq0Tw1wWRjcij6kk1ogbEF1YYRU8Q=";
          };
          "Qwopus3.5-27B-v3-TQ3_4S" = pkgs.fetchurl {
            url = "https://huggingface.co/YTan2000/Qwopus3.5-27B-v3-TQ3_4S/resolve/main/Qwopus3.5-27B-v3-TQ3_4S.gguf";
            sha256 = "sha256-tOA3h/NqFVqcvFnut7Jr6lmzxNKoAk1JvN6zgIyle30=";
          };
          "gemma-4-E4B-it-Q4_K_S" = pkgs.fetchurl {
            url = "https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_S.gguf";
            sha256 = "sha256-phdUsEKgWDyjaahQzDqtWcIAH62KIH3hi4i1sat87MM=";
          };
          "gemma-4-26B-A4B-it-UD-Q3_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/main/gemma-4-26B-A4B-it-UD-Q3_K_M.gguf";
            sha256 = "sha256-YpaznVgWaMS2VGF9bUnJ7coVY1+4A8PJ9tgTdx34XR4=";
          };
          "gemma-4-31b-jang-crack-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/douyamv/Gemma-4-31B-JANG_4M-CRACK-GGUF/resolve/main/gemma-4-31b-jang-crack-Q4_K_M.gguf";
            sha256 = "sha256-sfyO4Q+RbaAZ27HRd4VPo7ZCH76h6Tg5ogYYYTCOHec=";
          };
        };

        # Create a directory containing all defined models
        modelsDir = pkgs.linkFarm "llama-cpp-models" (
          pkgs.lib.mapAttrsToList (name: path: {
            name = "${name}.gguf";
            inherit path;
          }) models
        );

        # --- Backends ---
        llama-rocm = llama-cpp.packages.${system}.rocm;
        llama-vulkan = llama-cpp.packages.${system}.vulkan;

        # --- Helper to create server/cli apps ---
        mkServer = pkg: model: {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-server-wrapper" ''
            exec ${pkg}/bin/llama-server \
              --model "${model}" \
              --ctx-size "32768" \
              --n-gpu-layers "99" \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-server-wrapper";
        };

        mkSpeculativeServer = pkg: model: draftModel: ctxSize: {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-omnicoder-wrapper" ''
            exec ${pkg}/bin/llama-server \
              -m "${model}" \
              -md "${draftModel}" \
              --parallel 1 \
              --ctx-size "${ctxSize}" \
              --n-gpu-layers "99" \
              --n-gpu-layers-draft "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --cache-type-k-draft "q4_0" \
              --cache-type-v-draft "q4_0" \
              --draft-n 16 \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-omnicoder-wrapper";
        };

        mkCli = pkg: model: {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-cli-wrapper" ''
            exec ${pkg}/bin/llama-cli \
              -m "${model}" \
              -p "Hello, how are you today?" \
              -n "128" \
              --n-gpu-layers "99" \
              "$@"
          ''}/bin/llama-cli-wrapper";
        };

        mkGemma = pkg: model: {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-gemma-wrapper" ''
            exec ${pkg}/bin/llama-server \
              -m "${model}" \
              --parallel 1 \
              --ctx-size "98304" \
              --jinja \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-gemma-wrapper";
        };

        mkGemma26b = pkg: model: {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-gemma-26b-wrapper" ''
            exec ${pkg}/bin/llama-server \
              -m "${model}" \
              --ctx-size "16384" \
              --parallel 1 \
              --jinja \
              --n-gpu-layers "50" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-gemma-26b-wrapper";
        };

        mkGemma31b = pkg: model: {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-gemma-31b-wrapper" ''
            exec ${pkg}/bin/llama-server \
              -m "${model}" \
              --ctx-size "8192" \
              --parallel 1 \
              --jinja \
              --n-gpu-layers "45" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-gemma-31b-wrapper";
        };

      in
      {
        # Default package is ROCm version
        packages.default = llama-rocm;
        packages.vulkan = llama-vulkan;
        packages.models = modelsDir;

        # Apps for running the server easily
        # Usage: nix run .#omnicoder OR nix run .#omnicoder-vulkan
        apps.omnicoder = mkSpeculativeServer llama-rocm models."Tesslate_OmniCoder-9B-Q4_K_S" models."Qwen3.5-0.8B.Q4_K_S" "32768";
        apps.omnicoder-vulkan = mkSpeculativeServer llama-vulkan models."Tesslate_OmniCoder-9B-Q4_K_S" models."Qwen3.5-0.8B.Q4_K_S" "32768";

        apps.sushi-coder = mkSpeculativeServer llama-rocm models."Qwen3.5-9b-Sushi-Coder-RL.Q4_K_M" models."Qwen3.5-0.8B.Q4_K_S" "70000";
        apps.sushi-coder-vulkan = mkSpeculativeServer llama-vulkan models."Qwen3.5-9b-Sushi-Coder-RL.Q4_K_M" models."Qwen3.5-0.8B.Q4_K_S" "70000";

        apps.bonsai = mkSpeculativeServer llama-rocm models."Bonsai-8B" models."Qwen3.5-0.8B.Q4_K_S" "70000";
        apps.bonsai-vulkan = mkSpeculativeServer llama-vulkan models."Bonsai-8B" models."Qwen3.5-0.8B.Q4_K_S" "70000";

        apps.nemotron = mkSpeculativeServer llama-rocm models."nvidia_Nemotron-Cascade-2-30B-A3B-Q4_0" models."Qwen3.5-0.8B.Q4_K_S" "16384";
        apps.nemotron-vulkan = mkSpeculativeServer llama-vulkan models."nvidia_Nemotron-Cascade-2-30B-A3B-Q4_0" models."Qwen3.5-0.8B.Q4_K_S" "16384";

        apps.server = mkServer llama-rocm models."Tesslate_OmniCoder-9B-Q4_K_S";
        apps.server-vulkan = mkServer llama-vulkan models."Tesslate_OmniCoder-9B-Q4_K_S";

        apps.cli = mkCli llama-rocm models."Tesslate_OmniCoder-9B-Q4_K_S";
        apps.cli-vulkan = mkCli llama-vulkan models."Tesslate_OmniCoder-9B-Q4_K_S";

        apps.gemma = mkGemma llama-rocm models."gemma-4-E4B-it-Q4_K_S";
        apps.gemma-vulkan = mkGemma llama-vulkan models."gemma-4-E4B-it-Q4_K_S";

        apps.gemma-26b = mkGemma26b llama-rocm models."gemma-4-26B-A4B-it-UD-Q3_K_M";
        apps.gemma-26b-vulkan = mkGemma26b llama-vulkan models."gemma-4-26B-A4B-it-UD-Q3_K_M";

        apps.gemma-31b = mkGemma31b llama-rocm models."gemma-4-31b-jang-crack-Q4_K_M";
        apps.gemma-31b-vulkan = mkGemma31b llama-vulkan models."gemma-4-31b-jang-crack-Q4_K_M";

        apps.qwen-27b = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen-27b" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwen3.5-27B-TQ3_1S"}" \
              --parallel 1 \
              --ctx-size "98304" \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen-27b";
        };

        apps.qwen-27b-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen-27b-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwen3.5-27B-TQ3_1S"}" \
              --parallel 1 \
              --ctx-size "98304" \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen-27b-vulkan";
        };

        apps.qwopus-27b = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus-27b" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwopus3.5-27B-v3-TQ3_4S"}" \
              --parallel 1 \
              --ctx-size "98304" \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus-27b";
        };

        apps.qwopus-27b-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus-27b-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwopus3.5-27B-v3-TQ3_4S"}" \
              --parallel 1 \
              --ctx-size "98304" \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus-27b-vulkan";
        };

        # Development shell
        devShells.default = pkgs.mkShell {
          name = "llama-cpp-rocm-shell";
          buildInputs = [ llama-rocm ];
          shellHook = ''
            echo "--- Llama-cpp (ROCm) Development Environment ---"
            echo "To run gemma (4B active): nix run .#gemma"
            echo "To run gemma-26b (4B active, 256k ctx): nix run .#gemma-26b"
            echo "To run gemma-31b (Gemma 4 31B): nix run .#gemma-31b"
            echo "To run speculative server: nix run .#omnicoder"
          '';
        };

        devShells.vulkan = pkgs.mkShell {
          name = "llama-cpp-vulkan-shell";
          buildInputs = [ llama-vulkan ];
          shellHook = ''
            echo "--- Llama-cpp (Vulkan) Development Environment ---"
            echo "To run gemma (4B active): nix run .#gemma-vulkan"
            echo "To run gemma-26b (4B active, 256k ctx): nix run .#gemma-26b-vulkan"
            echo "To run gemma-31b (Gemma 4 31B): nix run .#gemma-31b-vulkan"
            echo "To run speculative server: nix run .#omnicoder-vulkan"
          '';
        };
      }
    );
}
