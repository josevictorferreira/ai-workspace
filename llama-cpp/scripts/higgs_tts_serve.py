#!/usr/bin/env python3
"""FastAPI server for Higgs Audio v3 TTS (4B) — OpenAI-compatible /v1/audio/speech.

The official bosonai/higgs-tts-3-4b checkpoint ships no native transformers code;
its only documented inference paths (SGLang-Omni / vLLM-Omni) target gfx942
datacenter GPUs. To run on ROCm consumer hardware (gfx1030) on top of Nix's
torchWithRocm, we load the HF-staff trust_remote_code port
`multimodalart/higgs-audio-v3-tts-4b-transformers`, which is the identical Boson
weights with a thin modeling_*.py wrapper added. It uses the transformers-native
`bosonai/higgs-audio-v2-tokenizer` codec.

VRAM: bf16 backbone (~8 GB) + fp32 codec, measured ~11 GB on a 16 GB card.

Usage:
    nix run .#higgs-tts-serve
    nix run .#higgs-tts-serve -- --host 0.0.0.0 --port 8095 --dtype float16

Then:
    curl -X POST http://localhost:8095/v1/audio/speech \
      -H "Content-Type: application/json" \
      -d '{"input": "Hello, how are you?"}' --output out.wav
"""

import argparse
import io
import os
import tempfile

import requests
import torch
import torchaudio
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

# Identical Boson weights + a trust_remote_code modeling wrapper (no native
# transformers class exists in the upstream repo). Override with --model-id.
DEFAULT_MODEL_ID = "multimodalart/higgs-audio-v3-tts-4b-transformers"
FALLBACK_CODEC = "bosonai/higgs-audio-v2-tokenizer"
DEFAULT_SAMPLE_RATE = 24000

app = FastAPI(title="Higgs Audio v3 TTS", version="1.0")
MODEL = None
TOKENIZER = None


class Reference(BaseModel):
    audio_path: str
    text: str | None = None


class SpeechRequest(BaseModel):
    input: str
    # Accepted for OpenAI compatibility; this model uses smart/cloned voices.
    voice: str | None = "default"
    references: list[Reference] | None = None
    ref_audio: str | None = None
    ref_text: str | None = None
    temperature: float = 1.0
    top_p: float | None = None
    top_k: int | None = None
    max_new_tokens: int = 2048
    response_format: str = "wav"


def load_reference(path: str):
    """Load an audio file or URL into a [C, L] tensor + sample rate."""
    if path.startswith("http://") or path.startswith("https://"):
        resp = requests.get(path, timeout=120)
        resp.raise_for_status()
        suffix = os.path.splitext(path.split("?")[0])[1] or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(resp.content)
            tmp = f.name
        try:
            wav, sr = torchaudio.load(tmp)
        finally:
            os.unlink(tmp)
    else:
        wav, sr = torchaudio.load(path)
    return wav, sr


def to_wav_bytes(wav: torch.Tensor, sample_rate: int) -> bytes:
    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, wav.clamp(-1, 1).cpu().numpy(), sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


@app.on_event("startup")
def _load():
    global MODEL, TOKENIZER
    from transformers import AutoModelForCausalLM, AutoTokenizer

    args = app.state.args
    print(f"Loading {args.model_id} (dtype={args.dtype}) ...", flush=True)
    TOKENIZER = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
    MODEL = AutoModelForCausalLM.from_pretrained(
        args.model_id, trust_remote_code=True, dtype=args.dtype
    ).to("cuda").eval()
    if not getattr(MODEL.config, "audio_tokenizer_id", None):
        MODEL.config.audio_tokenizer_id = FALLBACK_CODEC
    print("Model ready on", next(MODEL.parameters()).device, flush=True)


@app.get("/health")
def health():
    return {"status": "ok" if MODEL is not None else "loading"}


@app.post("/v1/audio/speech")
def speech(req: SpeechRequest):
    if MODEL is None:
        raise HTTPException(status_code=503, detail="model still loading")

    ref_kwargs = {}
    try:
        if req.references:
            wav, sr = load_reference(req.references[0].audio_path)
            ref_kwargs = dict(
                reference_audio=wav, reference_sample_rate=sr,
                reference_text=req.references[0].text,
            )
        elif req.ref_audio:
            wav, sr = load_reference(req.ref_audio)
            ref_kwargs = dict(
                reference_audio=wav, reference_sample_rate=sr, reference_text=req.ref_text,
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"could not load reference audio: {e}")

    try:
        with torch.inference_mode():
            out = MODEL.generate_speech(
                req.input, TOKENIZER,
                max_new_tokens=req.max_new_tokens,
                temperature=req.temperature, top_p=req.top_p, top_k=req.top_k,
                **ref_kwargs,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if out.numel() == 0:
        return JSONResponse(status_code=500, content={"error": "model produced no audio"})

    sr = getattr(MODEL.config, "sample_rate", DEFAULT_SAMPLE_RATE)
    fmt = req.response_format.lower()
    if fmt == "pcm":
        # Raw 16-bit mono PCM.
        data = (out.clamp(-1, 1).to(torch.float32) * 32767).to(torch.int16).cpu().numpy().tobytes()
        return Response(content=data, media_type="audio/pcm",
                        headers={"x-sample-rate": str(sr)})
    # Default: WAV.
    return Response(content=to_wav_bytes(out, sr), media_type="audio/wav")


def main():
    p = argparse.ArgumentParser(description="Higgs Audio v3 TTS server")
    p.add_argument("--model-id", default=DEFAULT_MODEL_ID,
                   help=f"HF model id (default: {DEFAULT_MODEL_ID})")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8095)
    p.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16", "float32"],
                   help="backbone dtype; float16 may be faster on RDNA2 (gfx1030)")
    args = p.parse_args()

    dtype_map = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
    args.dtype = dtype_map[args.dtype]
    app.state.args = args
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
