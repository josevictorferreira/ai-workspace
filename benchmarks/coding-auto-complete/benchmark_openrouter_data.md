# Artificial Analysis Coding Benchmark - OpenRouter Model Data

This document contains the complete OpenRouter data for all models from the Artificial Analysis Coding Benchmark.

---

## 1. Gemini 3 Flash (Score: 53.12)

**OpenRouter Data:**
- **Name:** Google: Gemini 3 Flash Preview
- **Short Name:** Gemini 3 Flash Preview  
- **Slug:** google/gemini-3-flash-preview
- **Provider:** Google Vertex
- **Description:** Gemini 3 Flash Preview is a high speed, high value thinking model designed for agentic workflows, multi turn chat, and coding assistance. It delivers near Pro level reasoning and tool use performance with substantially lower latency than larger Gemini variants, making it well suited for interactive development, long running agent loops, and collaborative coding tasks. Compared to Gemini 2.5 Flash, it provides broad quality improvements across reasoning, multimodal understanding, and reliability.

The model supports a 1M token context window and multimodal inputs including text, images, audio, video, and PDFs, with text output. It includes configurable reasoning via thinking levels (minimal, low, medium, high), structured output, tool use, and automatic context caching. Gemini 3 Flash Preview is optimized for users who want strong reasoning and agentic behavior without the cost or latency of full scale frontier models.

- **Context Length:** 1,048,576 tokens
- **Input Modalities:** text, image, file, audio, video
- **Output Modalities:** text
- **Supports Reasoning:** Yes
- **Reasoning Config:** Configurable thinking levels (minimal, low, medium, high)
- **Pricing:** Prompt: $0.0000005/completion, $0.000003/completion
- **Provider:** Google Vertex

---

## 2. Seed-OSS-36B-Instruct (Score: 39.78)

**OpenRouter Data:**
- **Name:** ByteDance Seed: Seed-OSS-36B-Instruct
- **Short Name:** Seed-OSS-36B-Instruct
- **Slug:** bytedance-seed/seed-oss-36b-instruct
- **Provider:** Seed (BytePlus)
- **Description:** Seed-OSS-36B-Instruct is a 36B-parameter instruction-tuned reasoning language model from ByteDance's Seed team, released under Apache-2.0. The model is optimized for general instruction following with strong performance in reasoning, mathematics, coding, tool use/agentic workflows, and multilingual tasks, and is intended for international (i18n) use cases. It is not currently possible to control the reasoning effort.

- **Context Length:** 262,144 tokens
- **Input Modalities:** text
- **Output Modalities:** text
- **Supports Reasoning:** Yes
- **Reasoning Config:** Thinking tokens (start_token: "<think>", end_token: "</think>")

---

## 3. Grok CodeFast 1 (Score: 39.42)

**OpenRouter Data:**
- **Name:** xAI: Grok Code Fast 1
- **Short Name:** Grok Code Fast 1
- **Slug:** x-ai/grok-code-fast-1
- **Provider:** xAI
- **Description:** Grok Code Fast 1 is a speedy and economical reasoning model that excels at agentic coding. With reasoning traces visible in the response, developers can steer Grok Code for high-quality work flows.

- **Context Length:** 256,000 tokens
- **Input Modalities:** text
- **Output Modalities:** text
- **Supports Reasoning:** Yes
- **Max Completion Tokens:** 10,000
- **Pricing:** 
  - Prompt: $0.0000002 per token
  - Completion: $0.0000015 per token
  - Cache Read: $0.00000002 per token
- **Features:** 
  - Supports tool parameters
  - Supports reasoning and include_reasoning
  - Structured outputs support
  - Tool choice (none, auto, required, function)
  - Implicit caching
  - Abortable requests
- **Data Policy:** 
  - Retains prompts for 30 days
  - Requires user IDs
  - Terms: https://x.ai/legal/terms-of-service-enterprise
  - Privacy: https://x.ai/legal/privacy-policy

---

## 4. GLM-4.5-Air (Score: 39.35)

**OpenRouter Data:**
- **Name:** Z.AI: GLM 4.5 Air (free)
- **Short Name:** GLM 4.5 Air (free)
- **Slug:** z-ai/glm-4.5-air
- **Provider:** GMICloud (FP8)
- **Description:** GLM-4.5-Air is the lightweight variant of our latest flagship model family, also purpose-built for agent-centric applications. Like GLM-4.5, it adopts the Mixture-of-Experts (MoE) architecture but with a more compact parameter size. GLM-4.5-Air also supports hybrid inference modes, offering a "thinking mode" for advanced reasoning and tool use, and a "non-thinking mode" for real-time interaction. Users can control the reasoning behaviour with the `reasoning` `enabled` boolean.

- **Context Length:** 131,072 tokens
- **Input Modalities:** text
- **Output Modalities:** text
- **Supports Reasoning:** Yes
- **Reasoning Config:** Thinking tokens (start_token: "<think>", end_token: "</think>")
- **Default Parameters:** temperature: 0.75

---

## 5. NVIDIA Nemotron 3Nano (Score: 38.82)

**OpenRouter Data:**
- **Name:** NVIDIA: Nemotron 3 Nano 30B A3B (free)
- **Short Name:** Nemotron 3 Nano 30B A3B (free)
- **Slug:** nvidia/nemotron-3-nano-30b-a3b
- **Provider:** Multiple (DeepInfra, etc.)
- **Description:** NVIDIA Nemotron 3 Nano 30B A3B is a small language MoE model with highest compute efficiency and accuracy for developers to build specialized agentic AI systems. The model is fully open with open-weights, datasets and recipes so developers can easily customize, optimize, and deploy the model on their infrastructure for maximum privacy and security.

Note: For the free endpoint, all prompts and output are logged to improve the provider's model and its product and services. Please do not upload any personal, confidential, or otherwise sensitive information. This is a trial use only. Do not use for production or business-critical systems.

- **Context Length:** 256,000 tokens
- **Input Modalities:** text
- **Output Modalities:** text
- **Supports Reasoning:** Yes
- **Reasoning Config:** Thinking tokens (start_token: "<think>", end_token: "</think>")
- **HF Model:** nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16

---

## 6. Gemini 2.5Flash (Sep) (Score: 37.84)

**OpenRouter Data:**
- **Name:** Google: Gemini 2.5 Flash Preview 09-2025
- **Short Name:** Gemini 2.5 Flash Preview 09-2025
- **Slug:** google/gemini-2.5-flash-preview-09-2025
- **Provider:** Google AI Studio, Google Vertex
- **Description:** Gemini 2.5 Flash Preview September 2025 Checkpoint is Google's state-of-the-art workhorse model, specifically designed for advanced reasoning, coding, mathematics, and scientific tasks. It includes built-in "thinking" capabilities, enabling it to provide responses with greater accuracy and nuanced context handling.

Additionally, Gemini 2.5 Flash is configurable through the "max tokens for reasoning" parameter, as described in the documentation.

- **Context Length:** 1,048,576 tokens
- **Input Modalities:** text, image, file, audio, video
- **Output Modalities:** text
- **Supports Reasoning:** Yes

---

## 7. LlamaNemotronSuper 49B v1.5 (Score: 37.82)

**OpenRouter Data:**
- **Name:** NVIDIA: Llama 3.3 Nemotron Super 49B V1.5
- **Short Name:** Llama 3.3 Nemotron Super 49B V1.5
- **Slug:** nvidia/llama-3.3-nemotron-super-49b-v1.5
- **Provider:** DeepInfra, GMICloud
- **Description:** Llama-3.3-Nemotron-Super-49B-v1.5 is a 49B-parameter, English-centric reasoning/chat model derived from Meta's Llama-3.3-70B-Instruct with a 128K context. It's post-trained for agentic workflows (RAG, tool calling) via SFT across math, code, science, and multi-turn chat, followed by multiple RL stages; Reward-aware Preference Optimization (RPO) for alignment, RL with Verifiable Rewards (RLVR) for step-wise reasoning, and iterative DPO to refine tool-use behavior. A distillation-driven Neural Architecture Search ("Puzzle") replaces some attention blocks and varies FFN widths to shrink memory footprint and improve throughput, enabling single-GPU (H100/H200) deployment while preserving instruction following and CoT quality.

In internal evaluations (NeMo-Skills, up to 16 runs, temp = 0.6, top_p = 0.95), the model reports strong reasoning/coding results, e.g., MATH500 pass@1 = 97.4, AIME-2024 = 87.5, AIME-2025 = 82.71, GPQA = 71.97, LiveCodeBench (24.10–25.02) = 73.58, and MMLU-Pro (CoT) = 79.53.

- **Context Length:** 131,072 tokens
- **Input Modalities:** text
- **Output Modalities:** text
- **Supports Reasoning:** Yes
- **Reasoning Config:** Thinking tokens (start_token: "<think>", end_token: "</think>")
- **HF Model:** nvidia/Llama-3_3-Nemotron-Super-49B-v1_5

---

## 8. MagistralSmall 1.2 (Score: 37.24)

**OpenRouter Data:**
- **Name:** Mistral: Magistral Small 2506
- **Short Name:** Magistral Small 2506
- **Slug:** mistralai/magistral-small-2506
- **Provider:** Mistral
- **Description:** Magistral Small is a 24B parameter instruction-tuned model based on Mistral-Small-3.1 (2503), enhanced through supervised fine-tuning on traces from Magistral Medium and further refined via reinforcement learning. It is optimized for reasoning and supports a wide multilingual range, including over 20 languages.

- **Context Length:** 40,000 tokens
- **Input Modalities:** text
- **Output Modalities:** text
- **Supports Reasoning:** Yes
- **Reasoning Config:** Thinking tokens with specific system prompt
- **Default Parameters:** temperature: 0.3
- **HF Model:** mistralai/Magistral-Small-2506

---

## 9. gpt-oss-120B(low) (Score: 37.22)

**OpenRouter Data:**
- **Name:** OpenAI: gpt-oss-120b (free)
- **Short Name:** gpt-oss-120b (free)
- **Slug:** openai/gpt-oss-120b
- **Provider:** OpenInference, GMICloud, DeepInfra
- **Description:** gpt-oss-120b is an open-weight, 117B-parameter Mixture-of-Experts (MoE) language model from OpenAI designed for high-reasoning, agentic, and general-purpose production use cases. It activates 5.1B parameters per forward pass and is optimized to run on a single H100 GPU with native MXFP4 quantization. The model supports configurable reasoning depth, full chain-of-thought access, and native tool use, including function calling, browsing, and structured output generation.

- **Context Length:** 131,072 tokens
- **Input Modalities:** text
- **Output Modalities:** text
- **Supports Reasoning:** Yes
- **Reasoning Config:** Thinking tokens with mandatory reasoning, configurable reasoning effort (low, medium, high), default: medium
- **HF Model:** openai/gpt-oss-120b

---

## 10. Qwen3 Next 80BA3B (Score: 35.3)

**OpenRouter Data:**
- **Name:** Qwen: Qwen3 Next 80B A3B Thinking
- **Short Name:** Qwen3 Next 80B A3B Thinking
- **Slug:** qwen/qwen3-next-80b-a3b-thinking
- **Provider:** Multiple
- **Description:** Qwen3-Next-80B-A3B-Thinking is a reasoning-first chat model in the Qwen3-Next line that outputs structured "thinking" traces by default. It's designed for hard multi-step problems; math proofs, code synthesis/debugging, logic, and agentic planning, and reports strong results across knowledge, reasoning, coding, alignment, and multilingual evaluations. Compared with prior Qwen3 variants, it emphasizes stability under long chains of thought and efficient scaling during inference, and it is tuned to follow complex instructions while reducing repetitive or off-task behavior.

The model is suitable for agent frameworks and tool use (function calling), retrieval-heavy workflows, and standardized benchmarking where step-by-step solutions are required. It supports long, detailed completions and leverages throughput-oriented techniques (e.g., multi-token prediction) for faster generation. Note that it operates in thinking-only mode.

- **Context Length:** 262,144 tokens
- **Input Modalities:** text
- **Output Modalities:** text
- **Supports Reasoning:** Yes (Mandatory)
- **Reasoning Config:** Thinking tokens (start_token: "<think>", end_token: "</think>")
- **HF Model:** Qwen/Qwen3-Next-80B-A3B-Thinking

---

## 11. Kimi K2 (Score: 34.98)

**OpenRouter Data:**
- **Name:** MoonshotAI: Kimi K2 Thinking
- **Short Name:** Kimi K2 Thinking
- **Slug:** moonshotai/kimi-k2-thinking
- **Provider:** Multiple
- **Description:** Kimi K2 Thinking is Moonshot AI's most advanced open reasoning model to date, extending the K2 series into agentic, long-horizon reasoning. Built on the trillion-parameter Mixture-of-Experts (MoE) architecture introduced in Kimi K2, it activates 32 billion parameters per forward pass and supports 256 k-token context windows. The model is optimized for persistent step-by-step thought, dynamic tool invocation, and complex reasoning workflows that span hundreds of turns. It interleaves step-by-step reasoning with tool use, enabling autonomous research, coding, and writing that can persist for hundreds of sequential actions without drift.

It sets new open-source benchmarks on HLE, BrowseComp, SWE-Multilingual, and LiveCodeBench, while maintaining stable multi-agent behavior through 200–300 tool calls. Built on a large-scale MoE architecture with MuonClip optimization, it combines strong reasoning depth with high inference efficiency for demanding agentic and analytical tasks.

- **Context Length:** 262,144 tokens
- **Input Modalities:** text
- **Output Modalities:** text
- **Supports Reasoning:** Yes (Mandatory)
- **Reasoning Config:** Thinking tokens (start_token: "<think>", end_token: "</think>"), is_mandatory_reasoning: true
- **HF Model:** moonshotai/Kimi-K2-Thinking

---

## 12. gpt-oss-20B(low) (Score: 34.49)

**OpenRouter Data:**
- **Name:** OpenAI: gpt-oss-20b (free)
- **Short Name:** gpt-oss-20b (free)
- **Slug:** openai/gpt-oss-20b
- **Provider:** OpenInference, GMICloud
- **Description:** gpt-oss-20b is an open-weight 21B parameter model released by OpenAI under the Apache 2.0 license. It uses a Mixture-of-Experts (MoE) architecture with 3.6B active parameters per forward pass, optimized for lower-latency inference and deployability on consumer or single-GPU hardware. The model is trained in OpenAI's Harmony response format and supports reasoning level configuration, fine-tuning, and agentic capabilities including function calling, tool use, and structured outputs.

- **Context Length:** 131,072 tokens
- **Input Modalities:** text
- **Output Modalities:** text
- **Supports Reasoning:** Yes
- **Reasoning Config:** Configurable reasoning effort (low, medium, high), default: medium
- **HF Model:** openai/gpt-oss-20b

---

## 13. Gemini 2.5Flash-Lite(Sep) (Score: 33.23)

**OpenRouter Data:**
- **Name:** Google: Gemini 2.5 Flash Lite Preview 09-2025
- **Short Name:** Gemini 2.5 Flash Lite Preview 09-2025
- **Slug:** google/gemini-2.5-flash-lite-preview-09-2025
- **Provider:** Google AI Studio
- **Description:** Gemini 2.5 Flash-Lite is a lightweight reasoning model in the Gemini 2.5 family, optimized for ultra-low latency and cost efficiency. It offers improved throughput, faster token generation, and better performance across common benchmarks compared to earlier Flash models. By default, "thinking" (i.e. multi-pass reasoning) is disabled to prioritize speed, but developers can enable it via the Reasoning API parameter to selectively trade off cost for intelligence.

- **Context Length:** 1,048,576 tokens
- **Input Modalities:** text, image, file, audio, video
- **Output Modalities:** text
- **Supports Reasoning:** Yes

---

## 14. Devstral 2 (Score: 31.86)

**OpenRouter Data:**
- **Name:** Mistral: Devstral 2 2512 (free)
- **Short Name:** Devstral 2 2512 (free)
- **Slug:** mistralai/devstral-2512
- **Provider:** Mistral
- **Description:** Devstral 2 is a state-of-the-art open-source model by Mistral AI specializing in agentic coding. It is a 123B-parameter dense transformer model supporting a 256K context window.

Devstral 2 supports exploring codebases and orchestrating changes across multiple files while maintaining architecture-level context. It tracks framework dependencies, detects failures, and retries with corrections—solving challenges like bug fixing and modernizing legacy systems. The model can be fine-tuned to prioritize specific languages or optimize for large enterprise codebases. It is available under a modified MIT license.

- **Context Length:** 262,144 tokens
- **Input Modalities:** text
- **Output Modalities:** text
- **Supports Reasoning:** No
- **Default Parameters:** temperature: 0.3
- **HF Model:** mistralai/Devstral-2-123B-Instruct-2512

---

## 15. Nova 2.0 Lite (Score: 21.65)

**OpenRouter Data:**
- **Name:** Amazon: Nova 2 Lite
- **Short Name:** Nova 2 Lite
- **Slug:** amazon/nova-2-lite-v1
- **Provider:** Amazon Bedrock
- **Description:** Nova 2 Lite is a fast, cost-effective reasoning model for everyday workloads that can process text, images, and videos to generate text.

Nova 2 Lite demonstrates standout capabilities in processing documents, extracting information from videos, generating code, providing accurate grounded answers, and automating multi-step agentic workflows.

- **Context Length:** 1,000,000 tokens
- **Input Modalities:** text, image, video, file
- **Output Modalities:** text
- **Supports Reasoning:** Yes
- **Quick Start Example Type:** reasoning

---

## Summary Statistics

**Models Found in OpenRouter:** 15/15 (100%)
**Models Not Found:** 0/15 (0%)

**Reasoning Support:**
- Supports Reasoning: 14/15 (93.3%)
- Does Not Support Reasoning: 1/15 (6.7%) - Devstral 2

**Context Lengths:**
- 1M+ tokens: 4 models (Gemini 3 Flash, Gemini 2.5 Flash, Gemini 2.5 Flash Lite, Nova 2 Lite)
- 256K-262K tokens: 5 models (Nemotron 3 Nano, Qwen3 Next, Kimi K2, Devstral 2, Seed-OSS)
- 128K-131K tokens: 4 models (GLM-4.5-Air, LlamaNemotron Super, gpt-oss models)
- 40K tokens: 1 model (Magistral Small)

**MoE Models:**
- gpt-oss-120b (117B total, 5.1B active)
- gpt-oss-20b (21B total, 3.6B active)
- Kimi K2 (1T total, 32B active)
- GLM-4.5-Air (MoE architecture)
- Nemotron 3 Nano (MoE architecture)

**Free Models:**
- Nemotron 3 Nano 30B A3B (free)
- GLM-4.5-Air (free)
- gpt-oss-120b (free)
- gpt-oss-20b (free)
- Devstral 2 2512 (free)
