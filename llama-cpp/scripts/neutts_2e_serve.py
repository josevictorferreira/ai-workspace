#!/usr/bin/env python3
"""FastAPI server for NeuTTS-2E emotional TTS (6 emotions × 4 speakers).

Uses the neutts library which wraps the GGUF backbone (llama-cpp-python)
and neucodec for audio decoding.

Serve:  nix run .#neutts-2e-serve
Test:   curl -X POST http://localhost:8096/v1/audio/speech \
          -H "Content-Type: application/json" \
          -d '{"input":"Hello!","speaker":"emily","emotion":"happy"}' \
          --output hello.wav
"""

import argparse
import io
from contextlib import asynccontextmanager

import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

TTS = None

SPEAKERS = ["emily", "paul", "sophie", "steven"]
EMOTIONS = ["angry", "disgusted", "fearful", "happy", "neutral", "sad", "surprised"]
SAMPLE_RATE = 24000


class SpeechRequest(BaseModel):
    input: str
    speaker: str = "emily"
    emotion: str = "neutral"
    temperature: float = 1.0
    top_k: int = 50
    response_format: str = "wav"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global TTS
    from neutts import NeuTTS2E

    args = app.state.args
    print(f"Loading NeuTTS-2E (backbone={args.backbone_repo}) ...", flush=True)
    TTS = NeuTTS2E(
        backbone_repo=args.backbone_repo,
        backbone_device=args.backbone_device,
        seed=args.seed,
    )
    print("NeuTTS-2E ready.", flush=True)
    yield


app = FastAPI(title="NeuTTS-2E Emotional TTS", version="1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok" if TTS is not None else "loading"}


@app.get("/v1/audio/voices")
def list_voices():
    return {
        "speakers": [
            {"id": s, "emotions": EMOTIONS}
            for s in SPEAKERS
        ]
    }


@app.post("/v1/audio/speech")
def speech(req: SpeechRequest):
    if TTS is None:
        raise HTTPException(status_code=503, detail="model still loading")

    if req.speaker not in SPEAKERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown speaker '{req.speaker}'. Available: {SPEAKERS}",
        )
    if req.emotion not in EMOTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown emotion '{req.emotion}'. Available: {EMOTIONS}",
        )

    try:
        wav = TTS.infer(
            req.input,
            speaker=req.speaker,
            emotion=req.emotion,
            temperature=req.temperature,
            top_k=req.top_k,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if req.response_format.lower() == "pcm":
        data = (wav * 32767).astype("int16").tobytes()
        return Response(content=data, media_type="audio/pcm",
                        headers={"x-sample-rate": str(SAMPLE_RATE)})

    buf = io.BytesIO()
    sf.write(buf, wav, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return Response(content=buf.getvalue(), media_type="audio/wav")


def main():
    p = argparse.ArgumentParser(description="NeuTTS-2E TTS server")
    p.add_argument("--backbone-repo", default="neuphonic/neutts-2e-q8-gguf",
                   help="HF repo or local .gguf path for the backbone")
    p.add_argument("--backbone-device", default="cpu",
                   choices=["cpu", "cuda"],
                   help="Device for the GGUF backbone")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8096)
    p.add_argument("--seed", type=int, default=None,
                   help="Random seed for reproducibility")
    args = p.parse_args()
    app.state.args = args
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
