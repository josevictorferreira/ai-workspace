#!/usr/bin/env bash
echo "=== Available Commands (nix run .#<command>) ===="
echo
echo "  nix run .#help              Show this help"
echo "  nix run .#cli                CLI chat"
echo "  nix run .#server             Start default LLM server"
echo "  nix run .#optimizer          Model optimizer"
echo
echo "  nix run .#supertonic-serve   Start TTS server"
echo "  nix run .#supertonic-say      Speak text via TTS"
echo
echo "  nix run .#omnicoder          OmniCoder 9B"
echo "  nix run .#sushi-coder        Sushi Coder 9B"
echo "  nix run .#bonsai             Bonsai 8B"
echo "  nix run .#nemotron           Nemotron 30B"
echo "  nix run .#gemma              Gemma 4B"
echo "  nix run .#gemma-12b          Gemma 12B"
echo "  nix run .#gemma-26b          Gemma 26B"
echo "  nix run .#gemma-12b-coder    Gemma 12B Coder"
echo "  nix run .#ornith-9b          Ornith 9B"
echo "  nix run .#ornith-35b         Ornith 35B"
echo "  nix run .#qwythos-9b         Qwythos 9B"
echo "  nix run .#qwen-*             Qwen variants"
echo "  nix run .#qwopus-*           Qwopus variants"
echo "  nix run .#qwopus36-27b-mtp   Qwopus 3.6 27B MTP"
echo "  nix run .#qwen36-12b-heretic Qwen 3.6 12B Heretic"
echo "  nix run .#granite-4-1-8b     Granite 4.1 8B"
echo "  nix run .#vibe-thinker       Vibe Thinker"
echo "  nix run .#lfm-8b             LFM 2.5 8B"
echo
echo "=== Backend variants ==="
echo
echo "  Append -vulkan to any model for Vulkan backend"
echo "  (e.g. nix run .#omnicoder-vulkan)"
echo
echo "=== HIP Kernel Tools ==="
echo
echo "  nix run .#hipfire            HIP kernel fire"
echo "  nix run .#hipfire-setup       Setup HIP environment"
echo "  nix run .#hipfire-qwen        HIP + Qwen server"
echo "  nix run .#hipfire-server      HIP persistent server"
