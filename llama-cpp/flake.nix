{
  description = "Declarative llama-cpp environment with ROCm and Vulkan support";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    llama-cpp.url = "github:am17an/llama.cpp/mtp-clean";
    llama-cpp.inputs.nixpkgs.follows = "nixpkgs";
    supertonic-py-src = {
      url = "github:supertone-inc/supertonic-py/v1.3.1";
      flake = false;
    };
    gepard-inference-src = {
      url = "git+https://github.com/nineninesix-ai/gepard-inference";
      flake = false;
    };
    fish-speech-src = {
      url = "github:fishaudio/fish-speech";
      flake = false;
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      llama-cpp,
      supertonic-py-src,
      gepard-inference-src,
      fish-speech-src,
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
            sha256 = "sha256-D9vW30TlBUgaBjb+MWDSMNbeLs8PiiDwalxkre8MrgA=";
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

          "gemma-4-26B-A4B-it-qat-UD-Q4_K_XL" = pkgs.fetchurl {
            url = "https://huggingface.co/unsloth/gemma-4-26B-A4B-it-qat-GGUF/resolve/main/gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf";
            sha256 = "sha256-3PF5qRFT46fs55LkjvhyGA2dbvm3Z38KC9PoPP5iTV4=";
          };
          "Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/HauhauCS/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-MTP/resolve/main/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf";
            sha256 = "sha256-PBMTNGnkMTEv/7ix2cha5CGZ5rtXRuodqE6N3yCX1zw=";
          };
          "gemma-4-31b-jang-crack-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/douyamv/Gemma-4-31B-JANG_4M-CRACK-GGUF/resolve/main/gemma-4-31b-jang-crack-Q4_K_M.gguf";
            sha256 = "sha256-sfyO4Q+RbaAZ27HRd4VPo7ZCH76h6Tg5ogYYYTCOHec=";
          };
          "gemma-4-12b-coder-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF/resolve/main/gemma4-coding-Q4_K_M.gguf";
            sha256 = "0lfp7hc5sxzf0ar9v9ggbcwxhbja64klkdakln1pfn1aay3bn4a0";
          };
          "Ornith-1.0-9B-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/deepreinforce-ai/Ornith-1.0-9B-GGUF/resolve/3296bc7a404871a72ac3f1903f561459c09b5c17/ornith-1.0-9b-Q4_K_M.gguf";
            sha256 = "sha256-VyDR9nG0mWSBJ0//4Bhow8Nuh8E1zIU4RxzHvWCHsQY=";
          };
          "Ornith-1.0-9B-Q5_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/deepreinforce-ai/Ornith-1.0-9B-GGUF/resolve/3296bc7a404871a72ac3f1903f561459c09b5c17/ornith-1.0-9b-Q5_K_M.gguf";
            sha256 = "sha256-0bNglWNsCWsE6gnnmKejeJVvL6kJk0C9VK3RlUqvFJw=";
          };
          "Ornith-1.0-9B-Q6_K" = pkgs.fetchurl {
            url = "https://huggingface.co/deepreinforce-ai/Ornith-1.0-9B-GGUF/resolve/3296bc7a404871a72ac3f1903f561459c09b5c17/ornith-1.0-9b-Q6_K.gguf";
            sha256 = "sha256-M7b2o+PwUHhDjhLfiktVyKz3jOrcxjnSrxzzWgJug4c=";
          };
          "Ornith-1.0-9B-Q8_0" = pkgs.fetchurl {
            url = "https://huggingface.co/deepreinforce-ai/Ornith-1.0-9B-GGUF/resolve/3296bc7a404871a72ac3f1903f561459c09b5c17/ornith-1.0-9b-Q8_0.gguf";
            sha256 = "sha256-0OS+uqizRQxiCQ3xQI8u5cyyCU+cYQ/95WSmVEg9Tzc=";
          };

          "Ornith-1.5-9B-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/ornith-ai/Ornith-1.5-9B-GGUF/resolve/85bf2b98cdcbad4291cb4f46943526cc089f75a0/Ornith-1.5-9B-Q4_K_M.gguf";
            sha256 = "sha256-fXka/LMYEqzIjNWq/GdTkd8oxvw9jq4AK7TmzD2M/Y0=";
          };

          # 11.27 GB: largest quant of Ornith-1.5-35B that fits in the ~13 GB
          # VRAM budget (Hipfire daemon reserves ~3 GB of the 16 GB card).
          "Ornith-1.5-35B-A3B-IQ2_XS" = pkgs.fetchurl {
            url = "https://huggingface.co/bartowski/Ornith-1.5-35B-A3B-GGUF/resolve/main/Ornith-1.5-35B-A3B-IQ2_XS.gguf";
            sha256 = "sha256-K8gHwTl5jNKY6pNx0eJO+FHCfsihlk52HVWuAV3hNzc=";
          };

          "Ornith-1.0-35B-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/deepreinforce-ai/Ornith-1.0-35B-GGUF/resolve/main/ornith-1.0-35b-Q4_K_M.gguf";
            sha256 = "sha256-/yUpGyWZ+5J6g15iTSs1QBBq9hdhw/pXrEJkBG2+wAI=";
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
          "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF/resolve/main/Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M.gguf";
            sha256 = "sha256-DeQf9Wq07/JnZEN7J28L1dIPRCMq3TThTE9ZP6GusI8=";
          };
          "Qwopus3.5-9B-coder-Exp-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/Jackrong/Qwopus3.5-9B-Coder-GGUF/resolve/main/Qwopus3.5-9B-coder-Exp-Q4_K_M.gguf";
            sha256 = "0la0ava76rdwlc52mj4frm1s5qhmvm6l6ccr5azyj0gy99n873sf";
          };
          "Qwen3.6-12B-IQ-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/KevinJK51/Qwen3.6-12B-IQ-Ultra-Heretic-Uncensored-Thinking-V2-Hightop-GGUF/resolve/main/Qwen3.6-12B-IQ-Q4_K_M.gguf";
            sha256 = "09b7krzhf1shrkp7sj76jb9wycwzj46rwrazz9mwy680x6a3a6mh";
          };

          "VibeThinker-3B-Q8_0" = pkgs.fetchurl {
            url = "https://huggingface.co/prithivMLmods/VibeThinker-3B-GGUF/resolve/main/VibeThinker-3B.Q8_0.gguf";
            sha256 = "03jjckmfvfir895vsf91rvx9sgig0mnjyp50vzrpvpgycglbr04f";
          };
          "NeuTTS-2E-Q8_0" = pkgs.fetchurl {
            url = "https://huggingface.co/neuphonic/neutts-2e-q8-gguf/resolve/main/neutts-2e-Q8_0.gguf";
            sha256 = "sha256-ChFi7HHbgiOoGIGuPX66IuSlQTErKg7pv/FB6v2TDNA=";
          };
          "NuExtract3-Q4_K_M" = pkgs.fetchurl {
            url = "https://huggingface.co/numind/NuExtract3-GGUF/resolve/main/NuExtract3-Q4_K_M.gguf";
            sha256 = "sha256-Ejq6y87Ef1dPX+2GQKZQwgkr19cgfQQxSLEQVr1bdx8=";
          };
          "mmproj-NuExtract3-BF16" = pkgs.fetchurl {
            url = "https://huggingface.co/numind/NuExtract3-GGUF/resolve/main/mmproj-NuExtract3-BF16.gguf";
            sha256 = "sha256-mlBs5DVEaR9PVvFTN2j0PhiH72m4zXSy56RsTZoVWgE=";
          };
        };

        # Create a directory containing all defined models
        modelsDir = pkgs.linkFarm "llama-cpp-models" (
          pkgs.lib.mapAttrsToList (name: path: {
            name = "${name}.gguf";
            inherit path;
          }) models
        );

        # Immutable copy of the optimizer project for the deterministic wrapper.
        # Excludes Python caches and the local virtualenv so the store path is
        # reproducible and minimal.
        optimizer-src = pkgs.lib.cleanSourceWith {
          src = ./optimizer;
          filter =
            path: type:
            baseNameOf path != ".venv"
            && baseNameOf path != ".pytest_cache"
            && baseNameOf path != ".ruff_cache"
            && baseNameOf path != "__pycache__";
        };

        # Minimal deterministic wrapper that runs the locked optimizer project
        # without realizing any model derivation. Forwards arguments unchanged.
        llama-cpp-optimizer = pkgs.writeShellApplication {
          name = "llama-cpp-optimizer";
          runtimeInputs = [
            pkgs.python313
            pkgs.uv
          ];
          text = ''
            # Keep the project source immutable in the store; place the
            # virtualenv in a writable per-user cache so --help (and any
            # command) works without realizing a model derivation.
            export UV_PROJECT_ENVIRONMENT="''${UV_PROJECT_ENVIRONMENT:-''${XDG_CACHE_HOME:-$HOME/.cache}/llama-cpp-optimizer/.venv}"
            exec uv run --frozen --project "${optimizer-src}" llama-cpp-opt "$@"
          '';
        };

        # --- Backends ---

        # llama-server reports the --model path as the API model id, which under
        # Nix is a store-hashed name like "ds90...-Ornith-1.5-9B-Q4_K_M.gguf".
        # Wrap the binary so it derives a stable id ("Ornith-1.5-9B-Q4_K_M")
        # from the model file, unless the caller passed --alias explicitly.
        llamaServerAliasWrapper =
          pkg:
          pkgs.writeShellScript "llama-server-alias" ''
            model=
            prev=
            hasAlias=
            for arg in "$@"; do
              case "$prev" in
                -m | --model) model=$arg ;;
              esac
              case "$arg" in
                -a | --alias | --alias=*) hasAlias=1 ;;
                -m=* | --model=*) model=''${arg#*=} ;;
              esac
              prev=$arg
            done
            if [ -z "$hasAlias" ] && [ -n "$model" ]; then
              modelAlias=''${model##*/}
              modelAlias=''${modelAlias%.gguf}
              case "$model" in
                /nix/store/*) modelAlias=''${modelAlias#*-} ;;
              esac
              set -- --alias "$modelAlias" "$@"
            fi
            exec ${pkg}/bin/llama-server "$@"
          '';

        withModelAlias =
          pkg:
          pkgs.symlinkJoin {
            name = "${pkg.name}-aliased";
            paths = [ pkg ];
            postBuild = ''
              rm "$out/bin/llama-server"
              ln -s ${llamaServerAliasWrapper pkg} "$out/bin/llama-server"
            '';
          };

        llama-rocm-unwrapped = llama-cpp.packages.${system}.rocm.overrideAttrs (oldAttrs: {
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
        llama-rocm = withModelAlias llama-rocm-unwrapped;
        llama-vulkan = withModelAlias llama-cpp.packages.${system}.vulkan;

        # --- Hipfire Integration ---
        hipfire-src = pkgs.fetchFromGitHub {
          owner = "Kaden-Schutt";
          repo = "hipfire";
          rev = "5ca8ed83da5372ffc559f5603206869a758226c4";
          hash = "sha256-gEg6XV9pBKctefVD2wM8bPZA9LN/SEsNOxkYbRPq7Xc=";
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
              --port "11434" \
              "$@"
          ''}/bin/llama-server-wrapper";
        };

        mkServerWithCtx =
          {
            pkg,
            model,
            ctxSize ? "32768",
            nGpuLayers ? "99",
            cacheTypeK ? "q8_0",
            cacheTypeV ? "q8_0",
            batchSize ? "512",
            ubatchSize ? "512",
            flashAttn ? "on",
            fit ? "on",
          }:
          {
            type = "app";
            program = "${pkgs.writeShellScriptBin "llama-server-wrapper" ''
              exec ${pkg}/bin/llama-server \
                --model "${model}" \
                --ctx-size "${ctxSize}" \
                --n-gpu-layers "${nGpuLayers}" \
                --fit "${fit}" \
                --cache-type-k "${cacheTypeK}" \
                --cache-type-v "${cacheTypeV}" \
                --flash-attn "${flashAttn}" \
                --batch-size "${batchSize}" \
                --ubatch-size "${ubatchSize}" \
                --host "0.0.0.0" \
                --port "11434" \
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
              --spec-draft-n-max 16 \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "11434" \
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
                --port "11434" \
                --temp "0" \
                "''$@"
            ''}/bin/llama-gemma-wrapper";
          };

        mkGemma26b = pkg: model: cacheType: ctxSize: {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-gemma-26b-wrapper" ''
              exec ${pkg}/bin/llama-server \
                -m "${model}" \
                --ctx-size "${ctxSize}" \
                --parallel 1 \
                --jinja \
                --n-gpu-layers "50" \
            --cache-type-k "${cacheType}" \
            --cache-type-v "${cacheType}" \
                --flash-attn on \
                --host "0.0.0.0" \
                --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
              "$@"
          ''}/bin/llama-lfm-wrapper";
        };

        mkQwythos =
          pkg: model:
          let
            chatTemplate = pkgs.writeText "qwythos-9b-chat-template" (
              builtins.readFile ./templates/qwythos-9b-chat.jinja
            );
          in
          {
            type = "app";
            program = "${pkgs.writeShellScriptBin "llama-qwythos-9b-wrapper" ''
                          exec ${pkg}/bin/llama-server \
                      --model "${model}" \
                            --parallel 1 \
              --ctx-size "65536" \
                            --jinja \
                            --chat-template "''$(cat "${chatTemplate}")" \
                            --n-gpu-layers "99" \
                            --cache-type-k "q4_0" \
                            --cache-type-v "q4_0" \
                  --flash-attn on \
                            --host "0.0.0.0" \
                            --port "11434" \
                            "$@"
            ''}/bin/llama-qwythos-9b-wrapper";
          };

        # --- Supertonic 3 TTS ---

        supertonic-py = pkgs.python313Packages.buildPythonPackage rec {
          pname = "supertonic";
          version = "1.3.1";
          format = "pyproject";

          src = supertonic-py-src;

          nativeBuildInputs = with pkgs.python313Packages; [
            setuptools
            wheel
          ];

          propagatedBuildInputs = with pkgs.python313Packages; [
            onnxruntime
            numpy
            soundfile
            sounddevice
            huggingface-hub
            fastapi
            python-multipart
            uvicorn
          ];

          meta = {
            description = "Lightning-fast on-device multilingual TTS with ONNX Runtime";
            homepage = "https://github.com/supertone-inc/supertonic-py";
            license = pkgs.lib.licenses.mit;
          };
        };

        # --- Gepard TTS (ROCm hybrid: Nix torch + uv venv for NeMo/transformers) ---

        pkgs-rocm = import nixpkgs {
          inherit system;
          config = {
            allowUnfree = true;
            rocmSupport = true;
          };
        };

        rocmDependencies = with pkgs-rocm.rocmPackages; [
          rocm-runtime
          rocm-smi
          rocminfo
          hip-common
          miopen
          rocblas
          rocsolver
          rocfft
          clr
        ];

        # Nix-managed Python: torchWithRocm + base libs.
        # NeMo + transformers==5.3.0 + gepard go in a uv venv (--system-site-packages).
        gepard-python = pkgs-rocm.python312.withPackages (
          ps: with ps; [
            torchWithRocm
            torchaudio
            pip
            uv
            numpy
            scipy
            librosa
            soundfile
            safetensors
            huggingface-hub
            hydra-core
            omegaconf
            rich
            pyyaml
            fastapi
            uvicorn
            pydantic
          ]
        );

        # Shared ROCm env vars for Gepard apps (gfx1030 / 6900 XT stability)
        gepard-rocm-env = ''
          export HSA_OVERRIDE_GFX_VERSION="''${HSA_OVERRIDE_GFX_VERSION:-10.3.0}"
          export PYTORCH_ROCM_ARCH="''${PYTORCH_ROCM_ARCH:-gfx1030}"
          export PYTORCH_ALLOC_CONF="garbage_collection_threshold:0.8,max_split_size_mb:128"
          export TORCH_BLAS_PREFER_HIPBLASLT="0"
          export PYTORCH_TUNABLEOP_ENABLED="0"
          export PYTORCH_TUNABLEOP_HIPBLASLT_ENABLED="0"
          export LD_LIBRARY_PATH="${
            pkgs.lib.makeLibraryPath (rocmDependencies ++ [ pkgs.zlib ])
          }:${pkgs.stdenv.cc.cc.lib}/lib''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        '';

        # Shared venv setup: creates a uv venv with --system-site-packages,
        # then pip-installs nemo-toolkit + transformers==5.3.0.
        # Gepard itself is NOT installed (its source is read-only in the Nix store;
        # it runs directly via PYTHONPATH/GEPARD_SRC).
        # Cached at $XDG_CACHE_HOME/gepard-venv; first run takes ~3 min.
        gepard-venv-setup = ''
              VENV="''${GEPARD_VENV:-''${XDG_CACHE_HOME:-$HOME/.cache}/gepard-venv}"
              # Validate sentinel: qwen3_5 importable AND torch is the ROCm build
              # (nemo-toolkit pulls a CUDA torch wheel that shadows torchWithRocm;
              # we uninstall it so the Nix ROCm torch shows through system-site-packages).
              VENV_OK=0
              if [ -f "$VENV/.gepard-ready" ]; then
                "$VENV/bin/python" -c "
          from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5DynamicCache
          import torch; assert torch.version.hip
                " 2>/dev/null && VENV_OK=1
              fi
              if [ "$VENV_OK" != "1" ]; then
                echo "Setting up Gepard venv at $VENV..." >&2
                ${gepard-python}/bin/uv venv --python ${gepard-python}/bin/python --system-site-packages "$VENV"
                echo "Installing nemo-toolkit[tts]==2.4.0..." >&2
                "$VENV/bin/python" -m uv pip install "nemo-toolkit[tts]==2.4.0"
                echo "Re-pinning transformers==5.3.0 (NeMo pulls an older version)..." >&2
                "$VENV/bin/python" -m uv pip install "transformers==5.3.0"
                echo "Removing CUDA torch/torchaudio/torchcodec wheels (shadow Nix ROCm builds)..." >&2
                "$VENV/bin/python" -m uv pip uninstall torch torchaudio torchcodec >/dev/null 2>&1 || true
                touch "$VENV/.gepard-ready"
                echo "Gepard venv ready (ROCm torch "$("$VENV/bin/python" -c 'import torch;print(torch.__version__)')")." >&2
              fi
        '';

        # --- Fish Speech S2 Pro TTS (ROCm hybrid: Nix torch + uv venv) ---

        fish-speech-python = pkgs-rocm.python312.withPackages (
          ps: with ps; [
            torchWithRocm
            torchaudio
            pip
            uv
            huggingface-hub
            pyaudio
          ]
        );

        # S2 Pro defaults to a 32k-token KV cache and a FP32 codec, which do not
        # fit beside the model on a 16 GB GPU. Keep 4k tokens and use FP16 codec.
        fish-speech-low-vram-src = pkgs.runCommand "fish-speech-low-vram-src" { } ''
          cp -r ${fish-speech-src} "$out"
          chmod -R u+w "$out"
          substituteInPlace "$out/fish_speech/models/text2semantic/inference.py" \
            --replace-fail \
              'DualARTransformer.from_pretrained(checkpoint_path, load_weights=True)' \
              'DualARTransformer.from_pretrained(checkpoint_path, load_weights=True, max_length=4096)'
          substituteInPlace "$out/fish_speech/models/dac/inference.py" \
            --replace-fail \
              'def load_model(config_name, checkpoint_path, device="cuda"):' \
              'def load_model(config_name, checkpoint_path, device="cuda", precision=torch.float16):' \
            --replace-fail 'model.to(device)' 'model.to(device=device, dtype=precision)'
        '';

        # Cached at $XDG_CACHE_HOME/fish-speech-venv; model weights are cached
        # separately at $XDG_CACHE_HOME/fish-speech/checkpoints/s2-pro.
        fish-speech-venv-setup = ''
                        FISH_SPEECH_VENV="''${FISH_SPEECH_VENV:-''${XDG_CACHE_HOME:-$HOME/.cache}/fish-speech-venv}"
                        FISH_SPEECH_CHECKPOINTS="''${FISH_SPEECH_CHECKPOINTS:-''${XDG_CACHE_HOME:-$HOME/.cache}/fish-speech/checkpoints}"
                        set -e
                        GCROOT="''${HOME}/.local/share/nix-gcroots/fish-speech-venv"
                        export PYTHONPATH="${fish-speech-low-vram-src}''${PYTHONPATH:+:$PYTHONPATH}"

                        VENV_OK=0
                        if [ -f "$FISH_SPEECH_VENV/.fish-speech-ready" ] && [ -e "$FISH_SPEECH_VENV/bin/python" ]; then
                          "$FISH_SPEECH_VENV/bin/python" -c 'import torch; assert torch.version.hip; import fish_speech; import pyrootutils; import numba' 2>/dev/null && VENV_OK=1
                        fi

                        if [ "$VENV_OK" != "1" ]; then
                          echo "Setting up Fish Speech venv at $FISH_SPEECH_VENV..." >&2
                          rm -rf "$FISH_SPEECH_VENV"
                          ${fish-speech-python}/bin/uv venv --python ${fish-speech-python}/bin/python --system-site-packages "$FISH_SPEECH_VENV"
                          "$FISH_SPEECH_VENV/bin/python" -m uv pip install \
                            numpy "transformers<=4.57.3" datasets lightning hydra-core natsort einops \
                            librosa rich "gradio>5.0.0" wandb grpcio kui uvicorn loguru loralib \
                            pyrootutils resampy "numba>=0.60" "einx[torch]==0.2.2" zstandard pydub \
                            "modelscope==1.17.1" "opencc-python-reimplemented==0.1.7" silero-vad \
                            ormsgpack tiktoken "pydantic==2.9.2" cachetools safetensors soundfile \
                            vector-quantize-pytorch argbind flatten-dict pyloudnorm importlib-resources julius \
                            ffmpy ipython pystoi torch-stoi markdown2 randomname tensorboard
                          "$FISH_SPEECH_VENV/bin/python" -m uv pip install --no-deps descript-audiotools descript-audio-codec
                          "$FISH_SPEECH_VENV/bin/python" -m uv pip uninstall torch torchaudio torchcodec >/dev/null 2>&1 || true
                          "$FISH_SPEECH_VENV/bin/python" -c 'import audiotools; import dac; import pyrootutils; import torch; assert torch.version.hip'
                          mkdir -p "$(dirname "$GCROOT")"
                          nix-store --add-root "$GCROOT" --indirect -r ${fish-speech-python} >/dev/null 2>&1 || true
                          touch "$FISH_SPEECH_VENV/.fish-speech-ready"
                        fi

                        if [ ! -f "$FISH_SPEECH_CHECKPOINTS/s2-pro/codec.pth" ]; then
                          echo "Downloading fishaudio/s2-pro model weights to $FISH_SPEECH_CHECKPOINTS/s2-pro..." >&2
                          export FISH_SPEECH_CHECKPOINTS
                          "$FISH_SPEECH_VENV/bin/python" -c '
          from huggingface_hub import snapshot_download
          import os
          snapshot_download("fishaudio/s2-pro", local_dir=os.path.join(os.environ["FISH_SPEECH_CHECKPOINTS"], "s2-pro"))
                          '
                        fi
        '';

        # --- OmniVoice TTS (ROCm hybrid: Nix torch + uv venv) ---

        omnivoice-python = pkgs-rocm.python312.withPackages (
          ps: with ps; [
            torchWithRocm
            torchaudio
            pip
            uv
            numpy
            librosa
            soundfile
            huggingface-hub
          ]
        );

        # Cached at $XDG_CACHE_HOME/omnivoice-venv; first run takes ~3 min.
        omnivoice-venv-setup = ''
          OMNIVOICE_PYTHON="${omnivoice-python}/bin/python"
          VENV="''${OMNIVOICE_VENV:-''${XDG_CACHE_HOME:-$HOME/.cache}/omnivoice-venv}"
          GCROOT="''${HOME}/.local/share/nix-gcroots/omnivoice-venv"

          # Validate sentinel: venv exists, interpreter symlinks resolve,
          # store paths are still present, and omnivoice+ROCm torch are importable.
          VENV_OK=0
          if [ -f "$VENV/.omnivoice-ready" ] && [ -e "$VENV/bin/python" ]; then
            VENV_PYTHON_REAL="$(readlink -f "$VENV/bin/python" 2>/dev/null || true)"
            case "$VENV_PYTHON_REAL" in
              /nix/store/*)
                if [ -e "$VENV_PYTHON_REAL" ]; then
                  "$VENV/bin/python" -c "
                    import omnivoice
                    import torch; assert torch.version.hip
                  " 2>/dev/null && VENV_OK=1
                fi
                ;;
            esac
          fi

          if [ "$VENV_OK" != "1" ]; then
            echo "Setting up OmniVoice venv at $VENV..." >&2
            rm -rf "''$VENV"
            ${omnivoice-python}/bin/uv venv --python "$OMNIVOICE_PYTHON" --system-site-packages "$VENV"
            echo "Installing omnivoice..." >&2
            "$VENV/bin/python" -m uv pip install "omnivoice"
            echo "Removing CUDA torch/torchaudio/torchcodec wheels (shadow Nix ROCm builds)..." >&2
            "$VENV/bin/python" -m uv pip uninstall torch torchaudio torchcodec >/dev/null 2>&1 || true

            # Pin the whole Python environment (with torchWithRocm) in the Nix store
            # so GC does not delete the interpreter/ROCm libs that the venv symlinks to.
            mkdir -p "$(dirname "$GCROOT")"
            nix-store --add-root "$GCROOT" --indirect -r ${omnivoice-python} >/dev/null 2>&1 || true

            touch "''$VENV/.omnivoice-ready"
            echo "OmniVoice venv ready (ROCm torch "$('$VENV/bin/python' -c 'import torch;print(torch.__version__)')")." >&2
          fi
        '';

        # --- Qwen3-TTS (ROCm hybrid: Nix torch + uv venv) ---

        qwen-tts-python = pkgs-rocm.python312.withPackages (
          ps: with ps; [
            torchWithRocm
            torchaudio
            pip
            uv
            numpy
            librosa
            soundfile
            huggingface-hub
          ]
        );

        # Cached at $XDG_CACHE_HOME/qwen-tts-venv; first run takes ~3 min.
        qwen-tts-venv-setup = ''
          QWEN_TTS_PYTHON="${qwen-tts-python}/bin/python"
          VENV="''${QWEN_TTS_VENV:-''${XDG_CACHE_HOME:-$HOME/.cache}/qwen-tts-venv}"
          GCROOT="''${HOME}/.local/share/nix-gcroots/qwen-tts-venv"

          # Validate sentinel: venv exists, interpreter symlinks resolve,
          # store paths are still present, and qwen-tts+ROCm torch are importable.
          VENV_OK=0
          if [ -f "$VENV/.qwen-tts-ready" ] && [ -e "$VENV/bin/python" ]; then
            VENV_PYTHON_REAL="$(readlink -f "$VENV/bin/python" 2>/dev/null || true)"
            case "$VENV_PYTHON_REAL" in
              /nix/store/*)
                if [ -e "$VENV_PYTHON_REAL" ]; then
                  "$VENV/bin/python" -c "
                    from qwen_tts import Qwen3TTSModel
                    import torch; assert torch.version.hip
                  " 2>/dev/null && VENV_OK=1
                fi
                ;;
            esac
          fi

          if [ "$VENV_OK" != "1" ]; then
            echo "Setting up Qwen3-TTS venv at $VENV..." >&2
            rm -rf "$VENV"
            ${qwen-tts-python}/bin/uv venv --python "$QWEN_TTS_PYTHON" --system-site-packages "$VENV"
            echo "Installing qwen-tts..." >&2
            "$VENV/bin/python" -m uv pip install "qwen-tts"
            echo "Removing CUDA torch/torchaudio/torchcodec wheels (shadow Nix ROCm builds)..." >&2
            "$VENV/bin/python" -m uv pip uninstall torch torchaudio torchcodec >/dev/null 2>&1 || true

            # Pin the whole Python environment (with torchWithRocm) in the Nix store
            # so GC does not delete the interpreter/ROCm libs that the venv symlinks to.
            mkdir -p "$(dirname "$GCROOT")"
            nix-store --add-root "$GCROOT" --indirect -r ${qwen-tts-python} >/dev/null 2>&1 || true

            touch "$VENV/.qwen-tts-ready"
            echo "Qwen3-TTS venv ready." >&2
          fi
        '';

        # --- Dia2 TTS (ROCm hybrid: Nix torch + uv venv) ---

        dia2-python = pkgs-rocm.python312.withPackages (
          ps: with ps; [
            torchWithRocm
            torchaudio
            pip
            uv
            numpy
            soundfile
            huggingface-hub
          ]
        );

        # Cached at $XDG_CACHE_HOME/dia2-venv; first run takes ~2 min.
        dia2-venv-setup = ''
          DIA2_PYTHON="${dia2-python}/bin/python"
          VENV="''${DIA2_VENV:-''${XDG_CACHE_HOME:-$HOME/.cache}/dia2-venv}"
          GCROOT="''${HOME}/.local/share/nix-gcroots/dia2-venv"

          # Validate sentinel
          VENV_OK=0
          if [ -f "$VENV/.dia2-ready" ] && [ -e "$VENV/bin/python" ]; then
            VENV_PYTHON_REAL="$(readlink -f "$VENV/bin/python" 2>/dev/null || true)"
            case "$VENV_PYTHON_REAL" in
              /nix/store/*)
                if [ -e "$VENV_PYTHON_REAL" ]; then
                  "$VENV/bin/python" -c "import torch; assert torch.version.hip; import dia2" 2>/dev/null && VENV_OK=1
                fi
                ;;
            esac
          fi

          if [ "$VENV_OK" != "1" ]; then
            echo "Setting up Dia2 venv at $VENV..." >&2
            rm -rf "$VENV"
            ${dia2-python}/bin/uv venv --python "$DIA2_PYTHON" --system-site-packages "$VENV"
            echo "Cloning dia2..." >&2
            mkdir -p "$VENV/src"
            git clone --depth 1 https://github.com/nari-labs/dia2.git "$VENV/src/dia2"
            echo "Installing dia2..." >&2
            "$VENV/bin/python" -m uv pip install --no-deps -e "$VENV/src/dia2"
            "$VENV/bin/python" -m uv pip install "numpy>=2.1.0,<3.0" "transformers>=4.45.0" "safetensors" "huggingface-hub>=0.24.7" "sphn>=0.2.0" "soundfile>=0.12.1" "whisper-timestamped>=1.14.2" "gradio>=4.44.1" "numba>=0.60" fastapi uvicorn
            echo "Removing CUDA torch/torchaudio/torchcodec wheels (shadow Nix ROCm builds)..." >&2
            "$VENV/bin/python" -m uv pip uninstall torch torchaudio torchcodec >/dev/null 2>&1 || true

            mkdir -p "$(dirname "$GCROOT")"
            nix-store --add-root "$GCROOT" --indirect -r ${dia2-python} >/dev/null 2>&1 || true

            touch "$VENV/.dia2-ready"
            echo "Dia2 venv ready." >&2
          fi
        '';

        # --- Higgs Audio v3 TTS (ROCm hybrid: Nix torch + uv venv) ---
        # bosonai/higgs-tts-3-4b has no native transformers class; we load the
        # multimodalart trust_remote_code port (identical Boson weights) which
        # rides plain torch+transformers on top of Nix torchWithRocm (gfx1030).
        # bf16 backbone + fp32 codec, ~11 GB VRAM on a 16 GB card.

        higgs-tts-python = pkgs-rocm.python312.withPackages (
          ps: with ps; [
            torchWithRocm
            torchaudio
            pip
            uv
            numpy
            soundfile
            huggingface-hub
          ]
        );

        # Cached at $XDG_CACHE_HOME/higgs-tts-venv; first run takes ~2 min.
        higgs-tts-venv-setup = ''
          HIGGS_TTS_PYTHON="${higgs-tts-python}/bin/python"
          VENV="''${HIGGS_TTS_VENV:-''${XDG_CACHE_HOME:-$HOME/.cache}/higgs-tts-venv}"
          GCROOT="''${HOME}/.local/share/nix-gcroots/higgs-tts-venv"

          VENV_OK=0
          if [ -f "$VENV/.higgs-tts-ready" ] && [ -e "$VENV/bin/python" ]; then
            VENV_PYTHON_REAL="$(readlink -f "$VENV/bin/python" 2>/dev/null || true)"
            case "$VENV_PYTHON_REAL" in
              /nix/store/*)
                if [ -e "$VENV_PYTHON_REAL" ]; then
                  "$VENV/bin/python" -c "
                    import torch; assert torch.version.hip
                    import transformers, fastapi, uvicorn
                  " 2>/dev/null && VENV_OK=1
                fi
                ;;
            esac
          fi

          if [ "$VENV_OK" != "1" ]; then
            echo "Setting up Higgs TTS venv at $VENV..." >&2
            rm -rf "$VENV"
            ${higgs-tts-python}/bin/uv venv --python "$HIGGS_TTS_PYTHON" --system-site-packages "$VENV"
            echo "Installing transformers>=5.5 + server deps..." >&2
            "$VENV/bin/python" -m uv pip install "transformers>=5.5" fastapi uvicorn requests soundfile
            echo "Removing CUDA torch/torchaudio/torchcodec wheels (shadow Nix ROCm builds)..." >&2
            "$VENV/bin/python" -m uv pip uninstall torch torchaudio torchcodec >/dev/null 2>&1 || true

            mkdir -p "$(dirname "$GCROOT")"
            nix-store --add-root "$GCROOT" --indirect -r ${higgs-tts-python} >/dev/null 2>&1 || true

            touch "$VENV/.higgs-tts-ready"
            echo "Higgs TTS venv ready." >&2
          fi
        '';

        # --- NeuTTS-2E TTS (CPU: neutts + llama-cpp-python) ---

        neutts-tts-python = pkgs.python312.withPackages (
          ps: with ps; [
            pip
            uv
          ]
        );

        # Cached at $XDG_CACHE_HOME/neutts-tts-venv; first run ~2 min.
        neutts-tts-venv-setup = ''
          NEUTTS_TTS_PYTHON="${neutts-tts-python}/bin/python"
          VENV="''${NEUTTS_TTS_VENV:-''${XDG_CACHE_HOME:-$HOME/.cache}/neutts-tts-venv}"

          VENV_OK=0
          if [ -f "$VENV/.neutts-ready" ] && [ -e "$VENV/bin/python" ]; then
            "$VENV/bin/python" -c "from neutts import NeuTTS2E; import fastapi, uvicorn, soundfile" 2>/dev/null && VENV_OK=1
          fi

          if [ "$VENV_OK" != "1" ]; then
            echo "Setting up NeuTTS venv at $VENV..." >&2
            rm -rf "$VENV"
            ${neutts-tts-python}/bin/uv venv --python "$NEUTTS_TTS_PYTHON" "$VENV"
            echo "Installing neutts + server deps..." >&2
            ${neutts-tts-python}/bin/uv pip install --python "$VENV/bin/python" "neutts[llama]" fastapi uvicorn soundfile
            touch "$VENV/.neutts-ready"
            echo "NeuTTS venv ready." >&2
          fi
        '';

        # --- Inflect-Micro-v2 TTS (ROCm hybrid: Nix torch + uv venv) ---

        inflect-micro-v2-python = pkgs-rocm.python312.withPackages (
          ps: with ps; [
            torchWithRocm
            torchaudio
            pip
            uv
            numpy
            scipy
            soundfile
            huggingface-hub
          ]
        );

        # Cached at $XDG_CACHE_HOME/inflect-micro-v2-venv; first run ~2 min.
        inflect-micro-v2-venv-setup = ''
          INFLECT_PYTHON="${inflect-micro-v2-python}/bin/python"
          VENV="''${INFLECT_VENV:-''${XDG_CACHE_HOME:-$HOME/.cache}/inflect-micro-v2-venv}"
          MODEL_DIR="''${INFLECT_MODEL_DIR:-''${XDG_CACHE_HOME:-$HOME/.cache}/inflect-micro-v2}"
          GCROOT="''${HOME}/.local/share/nix-gcroots/inflect-micro-v2-venv"

          VENV_OK=0
          if [ -f "$VENV/.inflect-ready" ] && [ -e "$VENV/bin/python" ]; then
            VENV_PYTHON_REAL="$(readlink -f "$VENV/bin/python" 2>/dev/null || true)"
            case "$VENV_PYTHON_REAL" in
              /nix/store/*)
                if [ -e "$VENV_PYTHON_REAL" ]; then
                  "$VENV/bin/python" -c "
                    import torch; assert torch.version.hip
                    import fastapi, uvicorn
                  " 2>/dev/null && VENV_OK=1
                fi
                ;;
            esac
          fi

          if [ "$VENV_OK" != "1" ]; then
            echo "Setting up Inflect Micro v2 venv at $VENV..." >&2
            rm -rf "$VENV"
            ${inflect-micro-v2-python}/bin/uv venv --python "$INFLECT_PYTHON" --system-site-packages "$VENV"
            echo "Installing dependencies..." >&2
            "$VENV/bin/python" -m uv pip install "fastapi" "uvicorn" "phonemizer" "espeakng-loader" "num2words" "Unidecode"
            echo "Removing CUDA torch/torchaudio/torchcodec wheels (shadow Nix ROCm builds)..." >&2
            "$VENV/bin/python" -m uv pip uninstall torch torchaudio torchcodec >/dev/null 2>&1 || true

            mkdir -p "$(dirname "$GCROOT")"
            nix-store --add-root "$GCROOT" --indirect -r ${inflect-micro-v2-python} >/dev/null 2>&1 || true

            touch "$VENV/.inflect-ready"
            echo "Inflect Micro v2 venv ready." >&2
          fi

          if [ ! -f "$MODEL_DIR/model.pth" ]; then
            echo "Downloading owensong/Inflect-Micro-v2 weights to $MODEL_DIR..." >&2
            "$VENV/bin/python" -c "
          from huggingface_hub import snapshot_download
          import os
          snapshot_download('owensong/Inflect-Micro-v2', local_dir='$MODEL_DIR')
            "
          fi
        '';

      in
      {
        # Default package is ROCm version
        packages.default = llama-rocm;
        packages.vulkan = llama-vulkan;
        packages.models = modelsDir;

        # Separately-buildable Ornith 1.0 9B optimizer candidate packages.
        packages."Ornith-1.0-9B-Q4_K_M" = models."Ornith-1.0-9B-Q4_K_M";
        packages."Ornith-1.0-9B-Q5_K_M" = models."Ornith-1.0-9B-Q5_K_M";
        packages."Ornith-1.0-9B-Q6_K" = models."Ornith-1.0-9B-Q6_K";
        packages."Ornith-1.0-9B-Q8_0" = models."Ornith-1.0-9B-Q8_0";

        packages.llama-cpp-optimizer = llama-cpp-optimizer;

        packages.supertonic-py = supertonic-py;

        # --- Help listing all commands ---
        apps.help = {
          type = "app";
          program =
            let
              script = pkgs.writeShellScriptBin "flake-help" ''
                printf '%s\n' \
                  "=== Available Commands (nix run .#<command>) ===" \
                  "" \
                  "  nix run .#help              Show this help" \
                  "  nix run .#cli                CLI chat" \
                  "  nix run .#server             Start default LLM server" \
                  "  nix run .#optimizer          Model optimizer" \
                  "" \
                  "  nix run .#supertonic-serve   Start TTS server" \
                  "  nix run .#supertonic-say      Speak text via TTS" \
                  "" \
                  "  nix run .#gepard-serve     Gepard TTS server (FastAPI, ROCm)" \
                  "  nix run .#gepard-say        Gepard voice cloning TTS (ROCm)" \
                  "" \
                  "  nix run .#omnivoice-serve  OmniVoice TTS server (Gradio demo, ROCm)" \
                  "  nix run .#fish-speech-serve Fish Speech S2 Pro API server (ROCm)" \
                  "  nix run .#qwen-tts-serve   Qwen3-TTS server (Gradio demo, ROCm)" \
                  "  nix run .#higgs-tts-serve  Higgs Audio v3 TTS server (ROCm, ~11 GB VRAM)" \
                  "  nix run .#neutts-2e-serve  NeuTTS-2E emotional TTS server (CPU, ~236 MB)" \
                  "  nix run .#dia2-serve       Dia2-2B dialogue TTS server (Gradio demo, ROCm)" \
                  "  nix run .#inflect-micro-v2-serve Inflect-Micro-v2 TTS server (ROCm, 0.0.0.0, ~37 MB)" \
                  "" \
                  "  nix run .#omnicoder          OmniCoder 9B" \
                  "  nix run .#omnicoder          OmniCoder 9B" \
                  "  nix run .#sushi-coder        Sushi Coder 9B" \
                  "  nix run .#bonsai             Bonsai 8B" \
                  "  nix run .#nemotron           Nemotron 30B" \
                  "  nix run .#gemma              Gemma 4B" \
                  "  nix run .#gemma-12b          Gemma 12B" \
                  "  nix run .#gemma-26b          Gemma 26B" \
                  "  nix run .#gemma-12b-coder    Gemma 12B Coder" \
                  "  nix run .#ornith-9b          Ornith 9B" \
                  "  nix run .#ornith-15-35b      Ornith 1.5 35B A3B IQ2_XS (13 GB VRAM cap)" \
                  "  nix run .#ornith-35b         Ornith 35B" \
                  "  nix run .#qwythos-9b         Qwythos 9B" \
                  "  nix run .#qwen-*             Qwen variants" \
                  "  nix run .#qwopus-*           Qwopus variants" \
                  "  nix run .#qwopus36-27b-mtp   Qwopus 3.6 27B MTP" \
                  "  nix run .#qwen36-12b-heretic Qwen 3.6 12B Heretic" \
                  "  nix run .#granite-4-1-8b     Granite 4.1 8B" \
                  "  nix run .#vibe-thinker       Vibe Thinker" \
                  "  nix run .#neutts-2e          NeuTTS-2E emotional TTS" \
                  "  nix run .#lfm-8b             LFM 2.5 8B" \
                  "  nix run .#nuextract3         NuExtract3 4B (document extraction VLM)" \
                  "" \
                  "=== Backend variants ===" \
                  "" \
                  "  Append -vulkan to any model for Vulkan backend" \
                  "  (e.g. nix run .#omnicoder-vulkan)" \
                  "" \
                  "=== HIP Kernel Tools ===" \
                  "" \
                  "  nix run .#hipfire            HIP kernel fire" \
                  "  nix run .#hipfire-setup       Setup HIP environment" \
                  "  nix run .#hipfire-qwen        HIP + Qwen server" \
                  "  nix run .#hipfire-server      HIP persistent server"
              '';
            in
            "${script}/bin/flake-help";
        };

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
        apps.gemma-26b = mkGemma26b llama-rocm models."gemma-4-26B-A4B-it-UD-Q3_K_M" "q4_0" "32768";
        apps.gemma-26b-vulkan =
          mkGemma26b llama-vulkan models."gemma-4-26B-A4B-it-UD-Q3_K_M" "q4_0"
            "32768";

        apps.gemma-26b-qat =
          mkGemma26b llama-rocm models."gemma-4-26B-A4B-it-qat-UD-Q4_K_XL" "q8_0"
            "32768";
        apps.gemma-26b-qat-vulkan =
          mkGemma26b llama-vulkan models."gemma-4-26B-A4B-it-qat-UD-Q4_K_XL" "q8_0"
            "32768";
        apps.gemma-26b-hauhaucs-qat =
          mkGemma26b llama-rocm models."Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M" "q4_0"
            "65536";
        apps.gemma-26b-hauhaucs-qat-vulkan =
          mkGemma26b llama-vulkan models."Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M" "q4_0"
            "65536";

        apps.ornith-9b = mkServerWithCtx {
          pkg = llama-rocm;
          model = models."Ornith-1.0-9B-Q4_K_M";
          ctxSize = "32768";
          nGpuLayers = "99";
        };
        apps.ornith-9b-vulkan = mkServerWithCtx {
          pkg = llama-vulkan;
          model = models."Ornith-1.0-9B-Q4_K_M";
          ctxSize = "32768";
          nGpuLayers = "99";
        };

        apps.ornith-15-9b = mkServerWithCtx {
          pkg = llama-rocm;
          model = models."Ornith-1.5-9B-Q4_K_M";
          ctxSize = "65536";
          nGpuLayers = "99";
          cacheTypeK = "q8_0";
          cacheTypeV = "q8_0";
          batchSize = "2048";
          ubatchSize = "512";
        };
        apps.ornith-15-9b-vulkan = mkServerWithCtx {
          pkg = llama-vulkan;
          model = models."Ornith-1.5-9B-Q4_K_M";
          ctxSize = "65536";
          nGpuLayers = "99";
          cacheTypeK = "q8_0";
          cacheTypeV = "q8_0";
          batchSize = "2048";
          ubatchSize = "512";
        };

        apps.ornith-15-35b = mkServerWithCtx {
          pkg = llama-rocm;
          model = models."Ornith-1.5-35B-A3B-IQ2_XS";
          ctxSize = "65536";
          nGpuLayers = "99";
          cacheTypeK = "q4_0";
          cacheTypeV = "q4_0";
          batchSize = "2048";
          ubatchSize = "512";
        };
        apps.ornith-15-35b-vulkan = mkServerWithCtx {
          pkg = llama-vulkan;
          model = models."Ornith-1.5-35B-A3B-IQ2_XS";
          ctxSize = "65536";
          nGpuLayers = "99";
          cacheTypeK = "q4_0";
          cacheTypeV = "q4_0";
          batchSize = "2048";
          ubatchSize = "512";
        };

        apps.ornith-35b = mkServerWithCtx {
          pkg = llama-rocm;
          model = models."Ornith-1.0-35B-Q4_K_M";
          ctxSize = "16384";
          nGpuLayers = "60";
          cacheTypeK = "q4_0";
          cacheTypeV = "q4_0";
          batchSize = "1024";
          ubatchSize = "512";
        };
        apps.ornith-35b-vulkan = mkServerWithCtx {
          pkg = llama-vulkan;
          model = models."Ornith-1.0-35B-Q4_K_M";
          ctxSize = "16384";
          nGpuLayers = "60";
          cacheTypeK = "q4_0";
          cacheTypeV = "q4_0";
          batchSize = "1024";
          ubatchSize = "512";
        };

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
              --port "11434" \
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
              --port "11434" \
              "$@"
          ''}/bin/llama-qwen-27b-vulkan";
        };

        apps.qwythos-9b = mkQwythos llama-rocm models."Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M";
        apps.qwythos-9b-vulkan = mkQwythos llama-vulkan models."Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M";

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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
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
              --port "11434" \
              "$@"
          ''}/bin/llama-granite-4.1-8b-vulkan";
        };

        apps.nuextract3 = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-nuextract3" ''
            exec ${llama-rocm}/bin/llama-server \
              -m "${models."NuExtract3-Q4_K_M"}" \
              --mmproj "${models."mmproj-NuExtract3-BF16"}" \
              --parallel 1 \
              --ctx-size "32768" \
              --jinja \
              --n-gpu-layers "99" \
              --cache-type-k "q8_0" \
              --cache-type-v "q8_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "11434" \
              "$@"
          ''}/bin/llama-nuextract3";
        };

        apps.nuextract3-vulkan = {
          type = "app";
          program = "${pkgs.writeShellScriptBin "llama-nuextract3-vulkan" ''
            exec ${llama-vulkan}/bin/llama-server \
              -m "${models."NuExtract3-Q4_K_M"}" \
              --mmproj "${models."mmproj-NuExtract3-BF16"}" \
              --parallel 1 \
              --ctx-size "32768" \
              --jinja \
              --n-gpu-layers "99" \
              --cache-type-k "q8_0" \
              --cache-type-v "q8_0" \
              --flash-attn on \
              --host "0.0.0.0" \
              --port "11434" \
              "$@"
          ''}/bin/llama-nuextract3-vulkan";
        };

        apps.vibe-thinker =
          let
            chatTemplate = pkgs.writeText "qwen2-chat-template" (
              builtins.readFile ./templates/qwen2-chat.jinja
            );
          in
          {
            type = "app";
            program = "${pkgs.writeShellScriptBin "llama-vibe-thinker" ''
              exec ${llama-rocm}/bin/llama-server \
              --model "${models."VibeThinker-3B-Q8_0"}" \
              --parallel 1 \
              --ctx-size "32768" \
              --jinja \
              --chat-template "''$(cat "${chatTemplate}")" \
              --n-gpu-layers "99" \
              --cache-type-k "q8_0" \
              --cache-type-v "q8_0" \
              --flash-attn on \
              --no-context-shift \
              --host "0.0.0.0" \
              --port "11434" \
              "$@"
            ''}/bin/llama-vibe-thinker";
          };

        apps.vibe-thinker-vulkan =
          let
            chatTemplate = pkgs.writeText "qwen2-chat-template-vulkan" (
              builtins.readFile ./templates/qwen2-chat.jinja
            );
          in
          {
            type = "app";
            program = "${pkgs.writeShellScriptBin "llama-vibe-thinker-vulkan" ''
              exec ${llama-vulkan}/bin/llama-server \
              --model "${models."VibeThinker-3B-Q8_0"}" \
              --parallel 1 \
              --ctx-size "32768" \
              --jinja \
              --chat-template "''$(cat "${chatTemplate}")" \
              --n-gpu-layers "99" \
              --cache-type-k "q8_0" \
              --cache-type-v "q8_0" \
              --flash-attn on \
              --no-context-shift \
              --host "0.0.0.0" \
              --port "11434" \
              "$@"
            ''}/bin/llama-vibe-thinker-vulkan";
          };

        apps.neutts-2e =
          let
            chatTemplate = pkgs.writeText "neutts-2e-chat-template" (
              builtins.readFile ./templates/neutts-2e-chat.jinja
            );
          in
          {
            type = "app";
            program = "${pkgs.writeShellScriptBin "llama-neutts-2e" ''
              exec ${llama-rocm}/bin/llama-server \
                -m "${models."NeuTTS-2E-Q8_0"}" \
                --parallel 1 \
                --ctx-size "32768" \
                --jinja \
                --chat-template "''$(cat "${chatTemplate}")" \
                --n-gpu-layers "99" \
                --host "0.0.0.0" \
                --port "11434" \
                "$@"
            ''}/bin/llama-neutts-2e";
          };

        apps.neutts-2e-vulkan =
          let
            chatTemplate = pkgs.writeText "neutts-2e-chat-template-vulkan" (
              builtins.readFile ./templates/neutts-2e-chat.jinja
            );
          in
          {
            type = "app";
            program = "${pkgs.writeShellScriptBin "llama-neutts-2e-vulkan" ''
              exec ${llama-vulkan}/bin/llama-server \
                -m "${models."NeuTTS-2E-Q8_0"}" \
                --parallel 1 \
                --ctx-size "32768" \
                --jinja \
                --chat-template "''$(cat "${chatTemplate}")" \
                --n-gpu-layers "99" \
                --host "0.0.0.0" \
                --port "11434" \
                "$@"
            ''}/bin/llama-neutts-2e-vulkan";
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

        apps.optimizer = {
          type = "app";
          program = "${llama-cpp-optimizer}/bin/llama-cpp-optimizer";
        };

        # --- Supertonic 3 TTS Apps ---
        apps.supertonic-serve = {
          type = "app";
          program =
            let
              script = pkgs.writeShellScriptBin "supertonic-serve" ''
                exec ${supertonic-py}/bin/supertonic serve --host 0.0.0.0 "$@"
              '';
            in
            "${script}/bin/supertonic-serve";
        };

        apps.supertonic-say = {
          type = "app";
          program =
            let
              script = pkgs.writeShellScriptBin "supertonic-say" ''
                exec ${supertonic-py}/bin/supertonic say "$@"
              '';
            in
            "${script}/bin/supertonic-say";
        };

        # --- Gepard TTS Apps (ROCm) ---
        apps.gepard-serve = {
          type = "app";
          program =
            let
              script = pkgs.writeShellScriptBin "gepard-serve" ''
                ${gepard-rocm-env}
                ${gepard-venv-setup}
                export GEPARD_SRC="${gepard-inference-src}"
                export GEPARD_SRC="${gepard-inference-src}"
                # serve.py defaults --config to relative "config.yaml";
                # pass absolute path if user didn't override.
                if [[ " $* " != *" --config "* ]]; then
                  set -- --config "${gepard-inference-src}/config.yaml" "$@"
                fi
                exec "$VENV/bin/python" "${gepard-inference-src}/serve.py" "$@"
              '';
            in
            "${script}/bin/gepard-serve";
        };

        apps.gepard-say = {
          type = "app";
          program =
            let
              script = pkgs.writeShellScriptBin "gepard-say" ''
                ${gepard-rocm-env}
                ${gepard-venv-setup}
                export GEPARD_SRC="${gepard-inference-src}"
                exec "$VENV/bin/python" ${./scripts/gepard_say.py} "$@"
              '';
            in
            "${script}/bin/gepard-say";
        };

        apps.omnivoice-serve = {
          type = "app";
          program =
            let
              script = pkgs.writeShellScriptBin "omnivoice-serve" ''
                ${gepard-rocm-env}
                ${omnivoice-venv-setup}
                if [ -f "''${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token" ]; then
                    export HF_TOKEN="$(cat "''${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token")"
                fi
                if [[ " $* " != *" --ip "* ]]; then
                  set -- --ip 0.0.0.0 "$@"
                fi
                if [[ " $* " != *" --port "* ]]; then
                  set -- --port 8001 "$@"
                fi
                exec "$VENV/bin/omnivoice-demo" "$@"
              '';
            in
            "${script}/bin/omnivoice-serve";
        };

        apps.fish-speech-serve = {
          type = "app";
          program =
            let
              script = pkgs.writeShellScriptBin "fish-speech-serve" ''
                ${gepard-rocm-env}
                ${fish-speech-venv-setup}
                export FISH_SPEECH_CHECKPOINTS
                export PYTHONPATH="${fish-speech-low-vram-src}''${PYTHONPATH:+:$PYTHONPATH}"
                exec "$FISH_SPEECH_VENV/bin/python" "${fish-speech-low-vram-src}/tools/api_server.py" \
                  --listen 0.0.0.0:8080 \
                  --llama-checkpoint-path "$FISH_SPEECH_CHECKPOINTS/s2-pro" \
                  --decoder-checkpoint-path "$FISH_SPEECH_CHECKPOINTS/s2-pro/codec.pth" \
                  --decoder-config-name modded_dac_vq \
                  --half \
                  "$@"
              '';
            in
            "${script}/bin/fish-speech-serve";
        };

        apps.qwen-tts-serve = {
          type = "app";
          program =
            let
              script = pkgs.writeShellScriptBin "qwen-tts-serve" ''
                ${gepard-rocm-env}
                ${qwen-tts-venv-setup}
                export PATH="${pkgs.lib.makeBinPath [ pkgs.sox pkgs.ffmpeg ]}:''$PATH"
                if [ -f "''${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token" ]; then
                    export HF_TOKEN="$(cat "''${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token")"
                fi
                if [[ " $* " != *" --ip "* ]]; then
                  set -- --ip 0.0.0.0 "$@"
                fi
                if [[ " $* " != *" --port "* ]]; then
                  set -- --port 8000 "$@"
                fi
                if [[ " $* " != *" --flash-attn "* && " $* " != *" --no-flash-attn "* ]]; then
                  set -- --no-flash-attn "$@"
                fi
                exec "$VENV/bin/qwen-tts-demo" Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice "$@"
              '';
            in
            "${script}/bin/qwen-tts-serve";
        };

        apps.higgs-tts-serve = {
          type = "app";
          program =
            let
              script = pkgs.writeShellScriptBin "higgs-tts-serve" ''
                ${gepard-rocm-env}
                ${higgs-tts-venv-setup}
                if [ -f "''${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token" ]; then
                    export HF_TOKEN="$(cat "''${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token")"
                fi
                exec "$VENV/bin/python" ${./scripts/higgs_tts_serve.py} --host 0.0.0.0 --port 8095 "$@"
              '';
            in
            "${script}/bin/higgs-tts-serve";
        };

        apps.neutts-2e-serve = {
          type = "app";
          program =
            let
              script = pkgs.writeShellScriptBin "neutts-2e-serve" ''
                export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH"
                ${neutts-tts-venv-setup}
                if [ -f "''${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token" ]; then
                    export HF_TOKEN="$(cat "''${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token")"
                fi
                exec "$VENV/bin/python" ${./scripts/neutts_2e_serve.py} --host 0.0.0.0 --port 8096 "$@"
              '';
            in
            "${script}/bin/neutts-2e-serve";
        };

        apps.dia2-serve = {
          type = "app";
          program =
            let
              script = pkgs.writeShellScriptBin "dia2-serve" ''
                ${gepard-rocm-env}
                ${dia2-venv-setup}
                if [ -f "''${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token" ]; then
                    export HF_TOKEN="$(cat "''${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token")"
                fi
                exec "$VENV/bin/python" ${./scripts/dia2_serve.py} --host 0.0.0.0 --port 8097 "$@"
              '';
            in
            "${script}/bin/dia2-serve";
        };

        apps.inflect-micro-v2-serve = {
          type = "app";
          program =
            let
              script = pkgs.writeShellScriptBin "inflect-micro-v2-serve" ''
                ${gepard-rocm-env}
                ${inflect-micro-v2-venv-setup}
                if [ -f "''${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token" ]; then
                    export HF_TOKEN="$(cat "''${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token")"
                fi
                exec "$VENV/bin/python" ${./scripts/inflect_micro_v2_serve.py} --model-dir "$MODEL_DIR" --host 0.0.0.0 --port 8098 "$@"
              '';
            in
            "${script}/bin/inflect-micro-v2-serve";
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
                                  echo "To run neutts-2e (NeuTTS-2E emotional TTS, 0.7B): nix run .#neutts-2e"
                                  echo "To run nuextract3 (NuExtract3 4B document extraction VLM): nix run .#nuextract3"
                                  echo "To run speculative server: nix run .#omnicoder"
            echo "--- Supertonic 3 TTS ---"
            echo "To start TTS server: nix run .#supertonic-serve"
            echo "To speak text: nix run .#supertonic-say -- "Hello world""
            echo
            echo ""
            echo "--- Gepard TTS (ROCm) ---"
            echo "To start Gepard server: nix run .#gepard-serve"
            echo "To speak with Gepard: nix run .#gepard-say -- 'Hello world'"
            echo ""
            echo "--- OmniVoice TTS (ROCm) ---"
            echo "To start OmniVoice server: nix run .#omnivoice-serve"
            echo ""
            echo "--- Fish Speech S2 Pro TTS (ROCm) ---"
            echo "To start Fish Speech API server: nix run .#fish-speech-serve"
            echo ""
            echo "--- Qwen3-TTS (ROCm) ---"
            echo "To start Qwen3-TTS server: nix run .#qwen-tts-serve"
            echo ""
            echo "--- Higgs Audio v3 TTS (ROCm) ---"
            echo "To start Higgs TTS server: nix run .#higgs-tts-serve"
            echo ""
            echo "--- NeuTTS 2E TTS ---"
            echo "To start NeuTTS-2E server: nix run .#neutts-2e-serve"
            echo ""
            echo "--- Dia2 TTS (ROCm) ---"
            echo "To start Dia2 server: nix run .#dia2-serve"
            echo ""
            echo "--- Inflect-Micro-v2 TTS (ROCm) ---"
            echo "To start Inflect-Micro-v2 server: nix run .#inflect-micro-v2-serve"
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
                                  echo "To run neutts-2e (NeuTTS-2E emotional TTS, 0.7B): nix run .#neutts-2e-vulkan"
                                  echo "To run nuextract3 (NuExtract3 4B document extraction VLM): nix run .#nuextract3-vulkan"
                                  echo "To run speculative server: nix run .#omnicoder-vulkan"
            echo "--- Supertonic 3 TTS ---"
            echo "To start TTS server: nix run .#supertonic-serve"
            echo "To speak text: nix run .#supertonic-say -- "Hello world""
            echo
            echo ""
            echo "--- NeuTTS 2E TTS ---"
            echo "To start NeuTTS-2E server: nix run .#neutts-2e-serve"
            echo ""
            echo "--- Inflect-Micro-v2 TTS ---"
            echo "To start Inflect-Micro-v2 server: nix run .#inflect-micro-v2-serve --device cpu"
            echo ""
            echo "--- Hipfire (RDNA Native) ---"
                                  echo "To setup Qwen 3.5 9B: nix run .#hipfire-setup"
                                  echo "To run Qwen 3.5 9B (CLI): nix run .#hipfire-qwen"
                                  echo "To run Qwen 3.5 9B (Server): nix run .#hipfire-server"
                                  echo "General hipfire usage: hipfire --help"
          '';
        };

        devShells.optimizer = pkgs.mkShell {
          name = "llama-cpp-optimizer-shell";
          buildInputs = [
            pkgs.python313
            pkgs.uv
          ];
          shellHook = ''
            export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH"
            echo "--- Llama-cpp Optimizer (Python 3.13 Development Environment) ---"
            echo "Run optimizer CLI: uv run --project optimizer llama-cpp-opt --help"
            echo "Run test suite: uv run --project optimizer --frozen pytest optimizer/tests"
          '';
        };
      }
    );
}
