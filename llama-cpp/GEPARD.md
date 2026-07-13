# Gepard TTS

Open-source expressive text-to-speech with zero-shot voice cloning. ~555M
parameter autoregressive model (Qwen3.5 backbone + NVIDIA NeMo NanoCodec,
22.05 kHz). Runs on AMD ROCm via Nix-managed `torchWithRocm`.

## Quick start

```bash
# Start the server (first run: ~3 min venv build + model download)
nix run .#gepard-serve

# In another terminal, synthesize:
curl -X POST http://127.0.0.1:8000/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world."}' \
  -o speech.wav
```

Or use the one-shot CLI (no server needed):

```bash
nix run .#gepard-say -- "Hello world." -o speech.wav
```

## Two ways to run

| Command | What it does |
|---|---|
| `nix run .#gepard-serve` | FastAPI server at `http://127.0.0.1:8000`. Load model once, synthesize many times. |
| `nix run .#gepard-say -- "<text>"` | One-shot CLI. Loads model, generates one clip, exits. Slower per-call (model reload) but no server to manage. |

## API reference

### `GET /` — server status

```bash
curl http://127.0.0.1:8000/
```

```json
{
  "status": "ready",
  "checkpoint": "nineninesix/gepard-1.0",
  "device": "cuda",
  "default_voice": "ref_audio/audio_ru.wav",
  "defaults": {
    "temperature": 0.3,
    "top_k": 0,
    "cfg_scale": 1.0,
    "cfg_frames": 0,
    "stop_threshold": 0.5,
    "max_frames": 2000,
    "repetition_penalty": 1.0,
    "repetition_window": 32
  }
}
```

Interactive API docs: <http://127.0.0.1:8000/docs>

### `POST /synthesize` — generate speech

**Request body** (only `text` is required; everything else falls back to the
server defaults shown above):

| Field | Type | Default | Notes |
|---|---|---|---|
| `text` | string | *(required)* | Text to speak. Empty string → 422. |
| `reference` | string\|null | config default | Path to a voice clip to clone (5–10 s works best). |
| `temperature` | float\|null | `0.3` | Sampling temperature. Higher = more expressive/varied. |
| `top_k` | int\|null | `0` | Top-k sampling. `0` = off. |
| `cfg_scale` | float\|null | `1.0` | Classifier-free guidance weight. `1.0` = off. `3.0` = strong adherence to text. |
| `cfg_frames` | int\|null | `0` | Apply CFG only to the first N frames. `0` = all frames. |
| `stop_threshold` | float\|null | `0.5` | End-of-speech detection threshold. |
| `max_frames` | int\|null | `2000` | Hard cap on generated frames (~93 s at 21.5 fps). |
| `repetition_penalty` | float\|null | `1.0` | Penalize repeated tokens. `1.0` = off. |
| `repetition_window` | int\|null | `32` | Window (in tokens) for repetition penalty. |

**Response:** `audio/wav` (22050 Hz, mono, 16-bit PCM).

### Examples

**Basic synthesis (default voice):**

```bash
curl -X POST http://127.0.0.1:8000/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"The quick brown fox jumps over the lazy dog."}' \
  -o fox.wav
```

**Voice cloning (custom reference clip):**

```bash
curl -X POST http://127.0.0.1:8000/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is my cloned voice speaking new words.",
    "reference": "/path/to/reference_clip.wav"
  }' \
  -o cloned.wav
```

**Stronger text adherence (CFG):**

```bash
curl -X POST http://127.0.0.1:8000/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "WHISPERING: do not wake the baby.",
    "cfg_scale": 3.0,
    "temperature": 0.5
  }' \
  -o expressive.wav
```

## CLI usage (`gepard-say`)

```bash
nix run .#gepard-say -- "Hello world." [options]
```

| Flag | Default | Description |
|---|---|---|
| `-o, --output` | `tts_output.wav` | Output WAV path. |
| `-r, --reference` | config default | Reference voice clip to clone. |
| `--config` | `<gepard-src>/config.yaml` | Config YAML. |
| `--device` | auto (`cuda` if available) | `cuda`, `cpu`, or omit. |
| `--checkpoint` | `nineninesix/gepard-1.0` | Override checkpoint. |
| `--temperature` | `0.3` | Sampling temperature. |
| `--top-k` | `0` | Top-k sampling. |
| `--cfg-scale` | `1.0` | CFG weight. |
| `--cfg-frames` | `0` | CFG frame limit. |
| `--stop-threshold` | `0.5` | End-of-speech threshold. |
| `--max-frames` | `2000` | Max frames. |
| `--repetition-penalty` | `1.0` | Repetition penalty. |
| `--repetition-window` | `32` | Repetition window. |

Example:

```bash
nix run .#gepard-say -- \
  "Voice cloning test." \
  -o cloned.wav \
  -r /path/to/ref.wav \
  --cfg-scale 3.0
```

## Server flags

```bash
nix run .#gepard-serve -- [flags]
```

| Flag | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Bind host. Use `0.0.0.0` for LAN access. |
| `--port` | `8000` | Bind port. |
| `--device` | auto | `cuda`, `cpu`, or omit for auto-detect. |
| `--config` | `<gepard-src>/config.yaml` | Config YAML with defaults. |
| `--checkpoint` | `nineninesix/gepard-1.0` | Override checkpoint. |
| `--reference` | `ref_audio/audio_ru.wav` | Override default voice clip. |

Example: LAN-accessible server with a custom default voice:

```bash
nix run .#gepard-serve -- \
  --host 0.0.0.0 \
  --port 9000 \
  --reference /path/to/my_voice.wav
```

## Bundled reference voices

The gepard-inference source ships these under `ref_audio/` (use the full
Nix store path, or clone from your own file):

| File | Language |
|---|---|
| `ref_audio/audio_en.wav` | English |
| `ref_audio/audio_ru.wav` | Russian (config default) |
| `ref_audio/nurisa_en.wav` | English |
| `ref_audio/ulan_emo.wav` | English (emotional) |

Find the store path with:

```bash
nix eval --raw '.#gepard-serve.program' | xargs dirname | xargs dirname
# → /nix/store/...-source/ref_audio/
```

## First run

The first `nix run .#gepard-serve` (or `gepard-say`) does three things:

1. **Builds the Nix env** — `torchWithRocm` + base libs. Cached by Nix after
   the first build. Can take a while on the first evaluation.
2. **Creates a uv venv** at `~/.cache/gepard-venv/` — installs
   `nemo-toolkit[tts]==2.4.0` and `transformers==5.3.0`, then removes the
   CUDA torch wheel that NeMo pulls in (so the Nix ROCm torch shows
   through). Takes ~3 minutes. A `.gepard-ready` sentinel skips this on
   subsequent runs; the sentinel is **validated** (imports `qwen3_5` +
   checks `torch.version.hip`) — a broken venv auto-rebuilds.
3. **Downloads the model** — `nineninesix/gepard-1.0` from HuggingFace
   (~555M params) + `nvidia/nemo-nano-codec-22khz-1.89kbps-21.5fps`. Cached
   in `~/.cache/huggingface/`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `GEPARD_VENV` | `~/.cache/gepard-venv` | Override venv location. |
| `HSA_OVERRIDE_GFX_VERSION` | `10.3.0` | ROCm GPU arch (gfx1030 = 6900 XT). |
| `PYTORCH_ROCM_ARCH` | `gfx1030` | ROCm compile target. |

## Troubleshooting

### `device: cpu` in server info (should be `cuda`)

The venv has a stale CUDA torch wheel shadowing the Nix ROCm torch. Delete
the venv and restart:

```bash
rm -rf ~/.cache/gepard-venv
nix run .#gepard-serve
```

After the rebuild, `GET /` should report `"device": "cuda"`.

### `ModuleNotFoundError: No module named 'transformers.models.qwen3_5'`

Stale transformers in the venv. Same fix — delete `~/.cache/gepard-venv` and
restart. The sentinel now validates this import and auto-rebuilds.

### `FileNotFoundError: config.yaml`

Fixed in the current wrapper — `--config` is auto-injected with the absolute
Nix store path. If you see this, you're on an older wrapper build; re-run
`nix run .#gepard-serve`.

### Model download fails

The checkpoint comes from
<https://huggingface.co/nineninesix/gepard-1.0> (Apache 2.0, not gated). If
the download stalls, check your HF cache:

```bash
ls ~/.cache/huggingface/hub/models--nineninesix--gepard-1.0/
```

## Architecture notes

- **Model**: ~555M params. Qwen3.5 14-layer full-attention backbone (hidden
  1024, 8 heads) + audio interface + voice-cloning compressor. Single
  autoregressive decoder-only model — text and speech learned jointly.
- **Codec**: NVIDIA NeMo NanoCodec (FSQ, 22.05 kHz, 21.5 fps, 1.89 kbps).
- **Languages**: English (US/UK), Spanish (MX), Portuguese (BR), Dutch.
- **License**: Apache 2.0 (codec: NVIDIA Open Model License).

## How the Nix integration works

Gepard needs three things Nix can't cleanly provide:

1. `nemo-toolkit[tts]==2.4.0` — not in nixpkgs.
2. `transformers==5.3.0` — nixpkgs has 5.5.4; gepard pins exact 5.3.0 for its
   custom `qwen3_5` module.
3. A torch matched to the model — Nix provides `torchWithRocm` (ROCm 7.2).

The wrapper creates a uv venv with `--system-site-packages` so the venv sees
Nix's ROCm torch, then installs only NeMo + transformers into the venv.
NeMo drags in a CUDA torch wheel, which the setup script uninstalls so the
ROCm torch shows through. The gepard source itself runs directly from the
Nix store via `PYTHONPATH`/`GEPARD_SRC` — it's not pip-installed (the store
is read-only).
