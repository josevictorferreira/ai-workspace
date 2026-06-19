{
  description = "Declarative llama-cpp environment with ROCm and Vulkan support";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    llama-cpp.url = "github:am17an/llama.cpp/mtp-clean";
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
          "lfm2-5-8b-a1b-ud-q4-k-s" = pkgs.fetchurl {
            url = "https://huggingface.co/unsloth/LFM2.5-8B-A1B-GGUF/resolve/main/LFM2.5-8B-A1B-UD-Q4_K_S.gguf";
            sha256 = "0cj0kxymh9h1yf9yjn1z864swgsxjpiwqksjg17yxdn9bqgxx5pz";
          };
          "gemma-4-E4B-it-Q4_K_S" = pkgs.fetchurl {
            url = "https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_S.gguf";
            sha256 = "sha256-phdUsEKgWDyjaahQzDqtWcIAH62KIH3hi4i1sat87MM=";
          };
          "gemma-4-12b-it-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/unsloth/gemma-4-12b-it-GGUF/resolve/main/gemma-4-12b-it-Q4_K_M.gguf";
            sha256 = "sha256-Xmz0WuzWYPwTUsO4bQx/w05dfRfbJGbtekDRmtmmJiY=";
          };
          "gemma-4-12b-it-Q8_0" = pkgs.fetchurl {
            url = "https://huggingface.co/unsloth/gemma-4-12b-it-GGUF/resolve/main/gemma-4-12b-it-Q8_0.gguf";
            sha256 = "sha256-441AYLVioXcstDZ/9md6RtZBdj0AafUCSuW2LRcvtTU=";
          };
          "gemma-4-26B-A4B-it-UD-Q3_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/main/gemma-4-26B-A4B-it-UD-Q3_K_M.gguf";
            sha256 = "sha256-YpaznVgWaMS2VGF9bUnJ7coVY1+4A8PJ9tgTdx34XR4=";
          };
          "gemma-4-31b-jang-crack-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/douyamv/Gemma-4-31B-JANG_4M-CRACK-GGUF/resolve/main/gemma-4-31b-jang-crack-Q4_K_M.gguf";
            sha256 = "sha256-sfyO4Q+RbaAZ27HRd4VPo7ZCH76h6Tg5ogYYYTCOHec=";
          };
          "gemma-4-12b-coder-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF/resolve/main/gemma4-coding-Q4_K_M.gguf";
            sha256 = "0lfp7hc5sxzf0ar9v9ggbcwxhbja64klkdakln1pfn1aay3bn4a0";
          };
          "Qwen3.6-35B-A3B-UD-Q4_K_XL" = pkgs.fetchurl {
            url = "https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/resolve/main/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf";
            sha256 = "sha256-cHpVqKQ5fs3kTeDEmdPmjBrR0kDR2mWCa0lJ0QQ/RFA=";
          };
          "Qwopus-GLM-18B-Merged-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/Jackrong/Qwopus-GLM-18B-Merged-GGUF/resolve/main/Qwopus-GLM-18B-Healed-Q4_K_M.gguf";
            sha256 = "sha256-E70Dn5XJ6kbvHXWQX6p75spOR6WvnUz2LimKc4pbGV8=";
          };
          "Qwopus-GLM-18B-Healed-Q3_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/KyleHessling1/Qwopus-GLM-18B-Merged-GGUF/resolve/main/Qwopus-GLM-18B-Healed-Q3_K_M.gguf";
            sha256 = "sha256-oRHruJXIl+308eHcd60uE7bCyXpWLFM5ux+VXNIX0hQ=";
          };
          "Qwen3.5-9B-GLM5.1-Distill-v1-Q6_K" = pkgs.fetchurl {
            url = "https://huggingface.co/Jackrong/Qwen3.5-9B-GLM5.1-Distill-v1-GGUF/resolve/main/Qwen3.5-9B-GLM5.1-Distill-v1-Q6_K.gguf";
            sha256 = "09441ra4n7gfbf2bkrqianp3glcjs6ixzqgjsa5lfv8sbi333qcc";
          };
          "Qwopus3.5-9B-Coder-MTP-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/Jackrong/Qwopus3.5-9B-Coder-MTP-GGUF/resolve/main/Qwopus3.5-9B-Coder-MTP-Q4_K_M.gguf";
            sha256 = "148r6fwq52wnq7sw74q5yx9mzrbzh87w9jvh32g6sya560cmvz7n";
          };
          "Qwen3.6-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/hesamation/Qwen3.6-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled-GGUF/resolve/main/Qwen3.6-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled.Q4_K_M.gguf";
            sha256 = "0r97w24r4z9532acvwzrxhga68dj1z1mg4yn20khm2alcdcgffzx";
          };
          "Qwen3.6-27B-Q3_K_S" = pkgs.fetchurl {
            url = "https://huggingface.co/unsloth/Qwen3.6-27B-GGUF/resolve/main/Qwen3.6-27B-Q3_K_S.gguf";
            sha256 = "sha256-SvtKvPAgekhLDX6SwEIbdOjOHHpyULudgkt5KI2mjyA=";
          };
          "Qwopus3.6-27B-v2-MTP-Q3_K_S" = pkgs.fetchurl {
            url = "https://huggingface.co/Jackrong/Qwopus3.6-27B-v2-MTP-GGUF/resolve/main/Qwopus3.6-27B-v2-MTP-Q3_K_S.gguf";
            sha256 = "1zkpjk9j479sb9irywq42wrm8afbn97l4v5zyam69kdcks9rsh2y";
          };
          "Qwen3.6-27B-UD-IQ2_XXS" = pkgs.fetchurl {
            url = "https://huggingface.co/unsloth/Qwen3.6-27B-GGUF/resolve/main/Qwen3.6-27B-UD-IQ2_XXS.gguf";
            sha256 = "sha256-lov8cSgyAxr+vsM52jrmHGgiq5oRjh1ytr4qd4GpbjA=";
          };
          "Granite-4.1-8B-Q8_0" = pkgs.fetchurl {
            url = "https://huggingface.co/bartowski/ibm-granite_granite-4.1-8b-GGUF/resolve/main/ibm-granite_granite-4.1-8b-Q8_0.gguf";
            sha256 = "1pln8w81jv6ah2pdryn5sdjhr7jrz039kskfyjjmgwqvbdcc9dc2";
          };
          "Qwen3.5-9B-MTP-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/unsloth/Qwen3.5-9B-MTP-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf";
            sha256 = "1zj150imw8r68xn624vv6xw9j9hqhh39s102j69w1mlmgs0r9pg8";
          };
          "Qwopus3.5-9B-coder-Exp-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/Jackrong/Qwopus3.5-9B-Coder-GGUF/resolve/main/Qwopus3.5-9B-coder-Exp-Q4_K_M.gguf";
            sha256 = "0la0ava76rdwlc52mj4frm1s5qhmvm6l6ccr5azyj0gy99n873sf";
          };
          "Qwen3.6-12B-IQ-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/KevinJK51/Qwen3.6-12B-IQ-Ultra-Heretic-Uncensored-Thinking-V2-Hightop-GGUF/resolve/main/Qwen3.6-12B-IQ-Q4_K_M.gguf";
            sha256 = "09b7krzhf1shrkp7sj76jb9wycwzj46rwrazz9mwy680x6a3a6mh";
          };

          "VibeThinker-3B-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/prithivMLmods/VibeThinker-3B-GGUF/resolve/main/VibeThinker-3B.Q4_K_M.gguf";
            sha256 = "0y8dr13s6dymqvknrdbgv3jjgq1sbkjf66z2b4fvh3r2rhcbk0lp";
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
        llama-rocm = llama-cpp.packages.${system}.rocm.overrideAttrs (oldAttrs: {
          cmakeFlags =
            builtins.map (
              flag:
              if pkgs.lib.hasPrefix "-DCMAKE_HIP_ARCHITECTURES:STRING=" flag then
                "-DCMAKE_HIP_ARCHITECTURES:STRING=gfx1030"
              else if flag == "-DLLAMA_BUILD_WEBUI:BOOL=TRUE" then
                "-DLLAMA_BUILD_WEBUI:BOOL=FALSE"
              else
                flag
            ) oldAttrs.cmakeFlags
            ++ [ "-DLLAMA_BUILD_UI:BOOL=FALSE" ];
        });
        llama-vulkan = llama-cpp.packages.${system}.vulkan;

        # --- Hipfire Integration ---
        hipfire-src = pkgs.fetchFromGitHub {
          owner = "Kaden-Schutt";
          repo = "hipfire";
          rev = "master";
          hash = "sha256-pcKKft5KhXWQNkwB+KvTxaW3A/sXN3aHcDPGz6gz1aA=";
        };

        hipfire-engine = pkgs.rustPlatform.buildRustPackage {
          pname = "hipfire-engine";
          version = "0.1.8-alpha";
          src = hipfire-src;
          cargoLock = {
            lockFile = "${hipfire-src}/Cargo.lock";
            allowBuiltinFetchGit = true;
          };
          nativeBuildInputs = [
            pkgs.pkg-config
            pkgs.clang
          ];
          buildInputs = [
            pkgs.rocmPackages.clr
          ];
          buildFeatures = [ "deltanet" ];
          cargoBuildFlags = [
            "--example"
            "daemon"
          ];
          doCheck = false;
          installPhase = ''
            mkdir -p $out/bin
            find target -name daemon -type f -executable -exec cp {} $out/bin/hipfire-daemon \;
          '';
          # Hipfire needs to find ROCm
          ROCM_PATH = "${pkgs.rocmPackages.clr}";
        };

        hipfire-cli = pkgs.stdenv.mkDerivation {
          pname = "hipfire-cli";
          version = "0.1.8-alpha";
          src = hipfire-src;
          nativeBuildInputs = [ pkgs.makeWrapper ];
          buildInputs = [ pkgs.bun ];
          installPhase = ''
            mkdir -p $out/lib/hipfire-cli
            cp -r cli/* $out/lib/hipfire-cli/

            # Patch the binary path in cli/index.ts
            # It normally looks in ../target/release/examples/daemon
            substituteInPlace $out/lib/hipfire-cli/index.ts \
              --replace 'resolve(__dirname, `../target/release/examples/daemon''${exe}`)' '"${hipfire-engine}/bin/hipfire-daemon"' \
              --replace 'join(HIPFIRE_DIR, "bin", `daemon''${exe}`)' '"${hipfire-engine}/bin/hipfire-daemon"'

            makeWrapper ${pkgs.bun}/bin/bun $out/bin/hipfire \
              --add-flags "run $out/lib/hipfire-cli/index.ts" \
              --set PATH "${
                pkgs.lib.makeBinPath [
                  pkgs.rocmPackages.clr
                  pkgs.git
                  pkgs.python3Packages.huggingface-hub
                  pkgs.rocmPackages.hipcc
                  pkgs.rocmPackages.rocm-device-libs
                ]
              }" \
              --set HIP_PATH "${pkgs.rocmPackages.clr}" \
              --set ROCM_PATH "${pkgs.rocmPackages.clr}" \
              --set HIP_DEVICE_LIB_PATH "${pkgs.rocmPackages.rocm-device-libs}/amdgcn/bitcode" \
              --set LD_LIBRARY_PATH "${
                pkgs.lib.makeLibraryPath [
                  pkgs.rocmPackages.clr
                  pkgs.stdenv.cc.cc.lib
                  pkgs.rocmPackages.rocm-device-libs
                ]
              }"
          '';
        };

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

        mkGemma =
          pkg: model:
          let
            chatTemplate = pkgs.writeText "gemma4-coder-chat-template" (
              builtins.readFile ./templates/gemma4-coder-chat.jinja
            );
          in
          {
            type = "app";
            program = "${pkgs.writeShellScriptBin "llama-gemma-wrapper" ''
              exec ${pkg}/bin/llama-server \
                -m "${model}" \
                --parallel 1 \
                --ctx-size "16384" \
                --jinja \
                --chat-template "''$(cat "${chatTemplate}")" \
                --n-gpu-layers "99" \
                --batch-size 2048 \
                --ubatch-size 512 \
                --cache-type-k "q4_0" \
                --cache-type-v "q4_0" \
                --flash-attn on \
                --no-context-shift \
                --cache-reuse 256 \
                --host "0.0.0.0" \
                --port "8080" \
                --temp "0" \
                "''$@"
            ''}/bin/llama-gemma-wrapper";
          };

        mkGemma26b = pkg: model: {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-gemma-26b-wrapper" ''
            exec ${pkg}/bin/llama-server \
              -m "${model}" \
              --ctx-size "32768" \
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

        mkLfm = pkg: model: {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-lfm-wrapper" ''
            exec ${pkg}/bin/llama-server \
              -m "${model}" \
              --parallel 1 \
              --ctx-size "65536" \
              --jinja \
              --reasoning-format deepseek \
              --n-gpu-layers "99" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --no-context-shift \
              --cache-reuse 256 \
              --threads "$(nproc)" \
              --threads-batch "$(nproc)" \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-lfm-wrapper";
        };

      in
      {
        # Default package is ROCm version
        packages.default = llama-rocm;
        packages.vulkan = llama-vulkan;
        packages.models = modelsDir;

        # Apps for running the server easily
        # Usage: nix run .#omnicoder OR nix run .#omnicoder-vulkan
        apps.omnicoder =
          mkSpeculativeServer llama-rocm models."Tesslate_OmniCoder-9B-Q4_K_S" models."Qwen3.5-0.8B.Q4_K_S"
            "32768";
        apps.omnicoder-vulkan =
          mkSpeculativeServer llama-vulkan models."Tesslate_OmniCoder-9B-Q4_K_S" models."Qwen3.5-0.8B.Q4_K_S"
            "32768";

        apps.sushi-coder =
          mkSpeculativeServer llama-rocm models."Qwen3.5-9b-Sushi-Coder-RL.Q4_K_M"
            models."Qwen3.5-0.8B.Q4_K_S"
            "70000";
        apps.sushi-coder-vulkan =
          mkSpeculativeServer llama-vulkan models."Qwen3.5-9b-Sushi-Coder-RL.Q4_K_M"
            models."Qwen3.5-0.8B.Q4_K_S"
            "70000";

        apps.bonsai =
          mkSpeculativeServer llama-rocm models."Bonsai-8B" models."Qwen3.5-0.8B.Q4_K_S"
            "70000";
        apps.bonsai-vulkan =
          mkSpeculativeServer llama-vulkan models."Bonsai-8B" models."Qwen3.5-0.8B.Q4_K_S"
            "70000";

        apps.nemotron =
          mkSpeculativeServer llama-rocm models."nvidia_Nemotron-Cascade-2-30B-A3B-Q4_0"
            models."Qwen3.5-0.8B.Q4_K_S"
            "16384";
        apps.nemotron-vulkan =
          mkSpeculativeServer llama-vulkan models."nvidia_Nemotron-Cascade-2-30B-A3B-Q4_0"
            models."Qwen3.5-0.8B.Q4_K_S"
            "16384";

        apps.server = mkServer llama-rocm models."Tesslate_OmniCoder-9B-Q4_K_S";
        apps.server-vulkan = mkServer llama-vulkan models."Tesslate_OmniCoder-9B-Q4_K_S";

        apps.cli = mkCli llama-rocm models."Tesslate_OmniCoder-9B-Q4_K_S";
        apps.cli-vulkan = mkCli llama-vulkan models."Tesslate_OmniCoder-9B-Q4_K_S";

        apps.gemma = mkGemma llama-rocm models."gemma-4-E4B-it-Q4_K_S";
        apps.gemma-vulkan = mkGemma llama-vulkan models."gemma-4-E4B-it-Q4_K_S";

        apps.gemma-12b = mkGemma llama-rocm models."gemma-4-12b-it-Q4_K_M";
        apps.gemma-12b-vulkan = mkGemma llama-vulkan models."gemma-4-12b-it-Q4_K_M";

        apps.gemma-12b-q8 = mkGemma llama-rocm models."gemma-4-12b-it-Q8_0";
        apps.gemma-12b-q8-vulkan = mkGemma llama-vulkan models."gemma-4-12b-it-Q8_0";

        apps.gemma-12b-coder = mkGemma llama-rocm models."gemma-4-12b-coder-Q4_K_M";
        apps.gemma-12b-coder-vulkan = mkGemma llama-vulkan models."gemma-4-12b-coder-Q4_K_M";
        apps.gemma-26b = mkGemma26b llama-rocm models."gemma-4-26B-A4B-it-UD-Q3_K_M";
        apps.gemma-26b-vulkan = mkGemma26b llama-vulkan models."gemma-4-26B-A4B-it-UD-Q3_K_M";

        apps.gemma-31b = mkGemma31b llama-rocm models."gemma-4-31b-jang-crack-Q4_K_M";
        apps.gemma-31b-vulkan = mkGemma31b llama-vulkan models."gemma-4-31b-jang-crack-Q4_K_M";

        apps.lfm2-5 = mkLfm llama-rocm models."lfm2-5-8b-a1b-ud-q4-k-s";
        apps.lfm2-5-vulkan = mkLfm llama-vulkan models."lfm2-5-8b-a1b-ud-q4-k-s";

        apps.qwen-27b = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen-27b" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwen3.5-27B-TQ3_1S"}" \
              --parallel 1 \
              --ctx-size "81920" \
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
              --ctx-size "81920" \
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
              --ctx-size "81920" \
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
              --ctx-size "81920" \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus-27b-vulkan";
        };

        apps.qwen-35b = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen-35b" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwen3.6-35B-A3B-UD-Q4_K_XL"}" \
              --port 8002 \
              --alias qwen3.6-35b-a3b \
              --ctx-size 131072 \
              --n-predict 32768 \
              --no-context-shift \
              --temp 0.6 \
              --top-p 0.95 \
              --top-k 20 \
              --repeat-penalty 1.00 \
              --presence-penalty 0.00 \
              --fit on \
              --flash-attn on \
              --cache-type-k q8_0 \
              --cache-type-v q8_0 \
              --chat-template-kwargs '{"preserve_thinking": true}' \
              --host "0.0.0.0" \
              --n-gpu-layers 20 \
              "$@"
          ''}/bin/llama-qwen-35b";
        };

        apps.qwen-35b-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen-35b-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwen3.6-35B-A3B-UD-Q4_K_XL"}" \
              --port 8002 \
              --alias qwen3.6-35b-a3b \
              --ctx-size 131072 \
              --n-predict 32768 \
              --no-context-shift \
              --temp 0.6 \
              --top-p 0.95 \
              --top-k 20 \
              --repeat-penalty 1.00 \
              --presence-penalty 0.00 \
              --fit on \
              --flash-attn on \
              --cache-type-k q8_0 \
              --cache-type-v q8_0 \
              --chat-template-kwargs '{"preserve_thinking": true}' \
              --host "0.0.0.0" \
              --n-gpu-layers 20 \
              "$@"
          ''}/bin/llama-qwen-35b-vulkan";
        };

        apps.qwopus-glm-18b = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus-glm-18b" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwopus-GLM-18B-Merged-Q4_K_M"}" \
              --parallel 1 \
              --ctx-size "32768" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --no-context-shift \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus-glm-18b";
        };

        apps.qwopus-glm-18b-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus-glm-18b-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwopus-GLM-18B-Merged-Q4_K_M"}" \
              --parallel 1 \
              --ctx-size "32768" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --no-context-shift \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus-glm-18b-vulkan";
        };

        apps.qwopus-glm-18b-healed = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus-glm-18b-healed" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwopus-GLM-18B-Healed-Q3_K_M"}" \
              --parallel 1 \
              --ctx-size "98304" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --no-context-shift \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus-glm-18b-healed";
        };

        apps.qwopus-glm-18b-healed-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus-glm-18b-healed-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwopus-GLM-18B-Healed-Q3_K_M"}" \
              --parallel 1 \
              --ctx-size "98304" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --no-context-shift \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus-glm-18b-healed-vulkan";
        };

        apps.qwen-9b-glm = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen-9b-glm" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwen3.5-9B-GLM5.1-Distill-v1-Q6_K"}" \
              --parallel 1 \
              --ctx-size "81920" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q8_0" \
              --cache-type-v "q8_0" \
              --flash-attn on \
              --no-context-shift \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen-9b-glm";
        };

        apps.qwen-9b-glm-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen-9b-glm-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwen3.5-9B-GLM5.1-Distill-v1-Q6_K"}" \
              --parallel 1 \
              --ctx-size "81920" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q8_0" \
              --cache-type-v "q8_0" \
              --flash-attn on \
              --no-context-shift \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen-9b-glm-vulkan";
        };

        apps.qwen-9b-glm-120k = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen-9b-glm-120k" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwen3.5-9B-GLM5.1-Distill-v1-Q6_K"}" \
              --parallel 1 \
              --ctx-size "120000" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --no-context-shift \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen-9b-glm-120k";
        };

        apps.qwen-9b-glm-120k-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen-9b-glm-120k-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwen3.5-9B-GLM5.1-Distill-v1-Q6_K"}" \
              --parallel 1 \
              --ctx-size "120000" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --no-context-shift \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen-9b-glm-120k-vulkan";
        };

        apps.qwopus-35b = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus-35b" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwen3.6-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled-Q4_K_M"}" \
              --parallel 1 \
              --ctx-size "32768" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "20" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --no-context-shift \
              --reasoning-budget -1 \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus-35b";
        };

        apps.qwopus-35b-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus-35b-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwen3.6-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled-Q4_K_M"}" \
              --parallel 1 \
              --ctx-size "32768" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "20" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --no-context-shift \
              --reasoning-budget -1 \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus-35b-vulkan";
        };

        apps.qwen36-27b = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen36-27b" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwen3.6-27B-Q3_K_S"}" \
              --parallel 1 \
              --ctx-size "8192" \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen36-27b";
        };

        apps.qwen36-27b-speed = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen36-27b-speed" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwen3.6-27B-UD-IQ2_XXS"}" \
              --parallel 1 \
              --ctx-size "49152" \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen36-27b-speed";
        };

        apps.qwopus36-27b-mtp = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus36-27b-mtp" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwopus3.6-27B-v2-MTP-Q3_K_S"}" \
              --parallel 1 \
              --ctx-size "8192" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --spec-type draft-mtp \
              --spec-draft-n-max 2 \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus36-27b-mtp";
        };

        apps.qwen36-27b-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen36-27b-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwen3.6-27B-Q3_K_S"}" \
              --parallel 1 \
              --ctx-size "8192" \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen36-27b-vulkan";
        };

        apps.qwen36-27b-speed-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen36-27b-speed-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwen3.6-27B-UD-IQ2_XXS"}" \
              --parallel 1 \
              --ctx-size "49152" \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen36-27b-speed-vulkan";
        };

        apps.qwopus36-27b-mtp-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus36-27b-mtp-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwopus3.6-27B-v2-MTP-Q3_K_S"}" \
              --parallel 1 \
              --ctx-size "8192" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --spec-type draft-mtp \
              --spec-draft-n-max 2 \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus36-27b-mtp-vulkan";
        };
        apps.qwopus35-9b-coder-mtp = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus35-9b-coder-mtp" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwopus3.5-9B-Coder-MTP-Q4_K_M"}" \
              --parallel 1 \
              --ctx-size "32768" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --spec-type draft-mtp \
              --spec-draft-n-max 2 \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus35-9b-coder-mtp";
        };

        apps.qwopus35-9b-coder-mtp-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus35-9b-coder-mtp-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwopus3.5-9B-Coder-MTP-Q4_K_M"}" \
              --parallel 1 \
              --ctx-size "32768" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --spec-type draft-mtp \
              --spec-draft-n-max 2 \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus35-9b-coder-mtp-vulkan";
        };

        apps.qwopus35-9b-coder = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus35-9b-coder" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwopus3.5-9B-coder-Exp-Q4_K_M"}" \
              --parallel 1 \
              --ctx-size "65536" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --reasoning-budget -1 \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus35-9b-coder";
        };

        apps.qwopus35-9b-coder-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwopus35-9b-coder-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwopus3.5-9B-coder-Exp-Q4_K_M"}" \
              --parallel 1 \
              --ctx-size "65536" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --reasoning-budget -1 \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwopus35-9b-coder-vulkan";
        };

        apps.qwen36-12b-heretic = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen36-12b-heretic" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwen3.6-12B-IQ-Q4_K_M"}" \
              --parallel 1 \
              --ctx-size "65536" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --reasoning-budget -1 \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen36-12b-heretic";
        };

        apps.qwen36-12b-heretic-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen36-12b-heretic-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwen3.6-12B-IQ-Q4_K_M"}" \
              --parallel 1 \
              --ctx-size "65536" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --reasoning-budget -1 \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen36-12b-heretic-vulkan";
        };

        apps.qwen35-9b-mtp = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen35-9b-mtp" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Qwen3.5-9B-MTP-Q4_K_M"}" \
              --parallel 1 \
              --ctx-size "32768" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --spec-type draft-mtp \
              --spec-draft-n-max 6 \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen35-9b-mtp";
        };

        apps.qwen35-9b-mtp-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-qwen35-9b-mtp-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Qwen3.5-9B-MTP-Q4_K_M"}" \
              --parallel 1 \
              --ctx-size "32768" \
              --batch-size 2048 \
              --ubatch-size 512 \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --spec-type draft-mtp \
              --spec-draft-n-max 6 \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-qwen35-9b-mtp-vulkan";
        };

        apps.granite-4-1-8b = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-granite-4.1-8b" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."Granite-4.1-8B-Q8_0"}" \
              --parallel 1 \
              --ctx-size "81920" \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-granite-4.1-8b";
        };

        apps.granite-4-1-8b-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-granite-4.1-8b-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."Granite-4.1-8B-Q8_0"}" \
              --parallel 1 \
              --ctx-size "81920" \
              --n-gpu-layers "99" \
              --cache-type-k "q4_0" \
              --cache-type-v "q4_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "8080" \
              "$@"
          ''}/bin/llama-granite-4.1-8b-vulkan";
    };

          apps.vibe-thinker = {
            type = "app";
            program = "${pkgs.writeShellScriptBin "llama-vibe-thinker" ''
              exec ${llama-rocm}/bin/llama-server \
                --model "${models."VibeThinker-3B-Q4_K_M"}" \
                --parallel 1 \
                --ctx-size "8192" \
                --n-gpu-layers "99" \
                --cache-type-k "q4_0" \
                --cache-type-v "q4_0" \
                --flash-attn \
                --no-context-shift \
                --host "0.0.0.0" \
                --port "8080" \
                "$@"
            ''}/bin/llama-vibe-thinker";
          };

          apps.vibe-thinker-vulkan = {
            type = "app";
            program = "${pkgs.writeShellScriptBin "llama-vibe-thinker-vulkan" ''
              exec ${llama-vulkan}/bin/llama-server \
                --model "${models."VibeThinker-3B-Q4_K_M"}" \
                --parallel 1 \
                --ctx-size "8192" \
                --n-gpu-layers "99" \
                --cache-type-k "q4_0" \
                --cache-type-v "q4_0" \
                --flash-attn \
                --no-context-shift \
                --host "0.0.0.0" \
                --port "8080" \
                "$@"
            ''}/bin/llama-vibe-thinker-vulkan";
          };
        };

        # --- Hipfire Apps ---
        apps.hipfire = {
          type = "app";
          program = "${hipfire-cli}/bin/hipfire";
        };

        apps.hipfire-setup = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "hipfire-setup" ''
            echo "--- Hipfire Setup ---"
            echo "Pulling Qwen 3.5 9B..."
            ${hipfire-cli}/bin/hipfire pull qwen3.5:9b
            echo "Setup complete. Run with: nix run .#hipfire-qwen"
          ''}/bin/hipfire-setup";
        };

        apps.hipfire-qwen = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "hipfire-qwen" ''
            exec ${hipfire-cli}/bin/hipfire run qwen3.5:9b "$@"
          ''}/bin/hipfire-qwen";
        };

        apps.hipfire-server = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "hipfire-server" ''
            export HIPFIRE_MODEL="qwen3.5:9b"
            echo "Starting Hipfire OpenAI-compatible server on port 8080..."
            echo "Default Model: qwen3.5:9b"
            echo "Endpoint: http://localhost:8080/v1/chat/completions"
            exec ${hipfire-cli}/bin/hipfire serve 8080 "$@"
          ''}/bin/hipfire-server";
        };

        # Development shell
        devShells.default = pkgs.mkShell {
          name = "llama-cpp-rocm-shell";
          buildInputs = [
            llama-rocm
            hipfire-cli
          ];
          shellHook = ''
                        echo "--- Llama-cpp (ROCm) Development Environment ---"
                        echo "To run gemma (4B active): nix run .#gemma"
                        echo "To run gemma-12b (Gemma 4 12B): nix run .#gemma-12b"
                        echo "To run gemma-12b-q8 (Gemma 4 12B Q8): nix run .#gemma-12b-q8"
                        echo "To run gemma-12b-coder (Gemma 4 12B Coder, Q4_K_M, velocity): nix run .#gemma-12b-coder"
                        echo "To run gemma-26b (4B active, 256k ctx): nix run .#gemma-26b"
                        echo "To run gemma-31b (Gemma 4 31B): nix run .#gemma-31b"
                        echo "To run lfm2-5 (LFM2.5 8B-A1B MoE, 64k ctx): nix run .#lfm2-5"
                        echo "To run qwen-9b-glm (120k context, 12GB VRAM): nix run .#qwen-9b-glm-120k"
                        echo "To run qwopus-35b (Qwen3.6 35B Distilled): nix run .#qwopus-35b"
                        echo "To run qwen36-27b (Quality, ~41 tok/s): nix run .#qwen36-27b"
                        echo "To run qwen36-27b-speed (Speed, 50+ tok/s): nix run .#qwen36-27b-speed"
                        echo "To run qwopus36-27b-mtp (Qwopus 3.6 27B MTP): nix run .#qwopus36-27b-mtp"
                        echo "To run granite-4.1-8b (IBM Granite 4.1 8B, 80k context): nix run .#granite-4-1-8b"
                        echo "To run qwopus35-9b-coder (Qwopus 3.5 9B Coder): nix run .#qwopus35-9b-coder"
                        echo "To run qwen36-12b-heretic (Qwen3.6 12B Heretic Uncensored): nix run .#qwen36-12b-heretic"
                        echo "To run qwen35-9b-mtp (Qwen3.5 9B MTP): nix run .#qwen35-9b-mtp"
            echo "To run vibe-thinker (VibeThinker 3B, fastest): nix run .#vibe-thinker"
                        echo "To run speculative server: nix run .#omnicoder"
                        echo ""
                        echo "--- Hipfire (RDNA Native) ---"
                        echo "To setup Qwen 3.5 9B: nix run .#hipfire-setup"
                        echo "To run Qwen 3.5 9B (CLI): nix run .#hipfire-qwen"
                        echo "To run Qwen 3.5 9B (Server): nix run .#hipfire-server"
                        echo "General hipfire usage: hipfire --help"
          '';
        };

        devShells.vulkan = pkgs.mkShell {
          name = "llama-cpp-vulkan-shell";
          buildInputs = [
            llama-vulkan
            hipfire-cli
          ];
          shellHook = ''
                        echo "--- Llama-cpp (Vulkan) Development Environment ---"
                        echo "To run gemma (4B active): nix run .#gemma-vulkan"
                        echo "To run gemma-12b (Gemma 4 12B): nix run .#gemma-12b-vulkan"
                        echo "To run gemma-12b-q8 (Gemma 4 12B Q8): nix run .#gemma-12b-q8-vulkan"
                        echo "To run gemma-12b-coder (Gemma 4 12B Coder, Q4_K_M, velocity): nix run .#gemma-12b-coder-vulkan"
                        echo "To run gemma-26b (4B active, 256k ctx): nix run .#gemma-26b-vulkan"
                        echo "To run gemma-31b (Gemma 4 31B): nix run .#gemma-31b-vulkan"
                        echo "To run lfm2-5 (LFM2.5 8B-A1B MoE, 64k ctx): nix run .#lfm2-5-vulkan"
                        echo "To run qwen-9b-glm (120k context, 12GB VRAM): nix run .#qwen-9b-glm-120k-vulkan"
                        echo "To run qwopus-35b (Qwen3.6 35B Distilled): nix run .#qwopus-35b-vulkan"
                        echo "To run qwen36-27b (Quality, ~41 tok/s): nix run .#qwen36-27b-vulkan"
                        echo "To run qwen36-27b-speed (Speed, 50+ tok/s): nix run .#qwen36-27b-speed-vulkan"
                        echo "To run qwopus36-27b-mtp (Qwopus 3.6 27B MTP): nix run .#qwopus36-27b-mtp-vulkan"
                        echo "To run granite-4.1-8b (IBM Granite 4.1 8B, 80k context): nix run .#granite-4-1-8b-vulkan"
                        echo "To run qwopus35-9b-coder (Qwopus 3.5 9B Coder): nix run .#qwopus35-9b-coder-vulkan"
                        echo "To run qwen36-12b-heretic (Qwen3.6 12B Heretic Uncensored): nix run .#qwen36-12b-heretic-vulkan"
                        echo "To run qwen35-9b-mtp (Qwen3.5 9B MTP): nix run .#qwen35-9b-mtp-vulkan"
            echo "To run vibe-thinker (VibeThinker 3B, fastest): nix run .#vibe-thinker-vulkan"
                        echo "To run speculative server: nix run .#omnicoder-vulkan"
                        echo ""
                        echo "--- Hipfire (RDNA Native) ---"
                        echo "To setup Qwen 3.5 9B: nix run .#hipfire-setup"
                        echo "To run Qwen 3.5 9B (CLI): nix run .#hipfire-qwen"
                        echo "To run Qwen 3.5 9B (Server): nix run .#hipfire-server"
                        echo "General hipfire usage: hipfire --help"
          '';
        };
      }
    );
}
