#!/usr/bin/env python3
"""FastAPI server for Inflect-Micro-v2 TTS — OpenAI-compatible /v1/audio/speech.

Serve:  nix run .#inflect-micro-v2-serve
Test:   curl -X POST http://localhost:8098/v1/audio/speech \
          -H "Content-Type: application/json" \
          -d '{"input":"Hello, how are you?","speed":1.0,"seed":7}' \
          --output hello.wav
"""

import argparse
import io
import sys
import json
from pathlib import Path
from contextlib import asynccontextmanager

import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
import torch

TTS = None
SAMPLE_RATE = 24000

class SpeechRequest(BaseModel):
    input: str | None = None
    text: str | None = None
    model: str | None = None
    voice: str | None = "default"
    speed: float = 1.0
    variation: float = 0.667
    seed: int = 0
    response_format: str = "wav"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global TTS
    args = app.state.args
    
    # Add model_dir and model_dir / "runtime" to sys.path so we can import inference classes
    model_dir = Path(args.model_dir).resolve()
    if str(model_dir) not in sys.path:
        sys.path.insert(0, str(model_dir))
    if str(model_dir / "runtime") not in sys.path:
        sys.path.insert(0, str(model_dir / "runtime"))
    
    print(f"Loading Inflect-Micro-v2 from {model_dir} on {args.device}...", flush=True)
    try:
        from inference import InflectTTS
        TTS = InflectTTS(model_dir=model_dir, device=args.device)
    except Exception as e:
        print(f"Error loading model: {e}", flush=True)
        raise e
    print("Inflect-Micro-v2 ready.", flush=True)
    yield

app = FastAPI(title="Inflect-Micro-v2 TTS Server", version="1.0", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok" if TTS is not None else "loading"}

@app.post("/v1/audio/speech")
async def speech(request: Request):
    if TTS is None:
        raise HTTPException(status_code=503, detail="model still loading")

    body_bytes = await request.body()
    try:
        data = json.loads(body_bytes.decode("utf-8"), strict=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    text_to_speak = data.get("input") or data.get("text")
    if not text_to_speak:
        raise HTTPException(status_code=400, detail="Missing parameter 'input' or 'text'")

    speed = float(data.get("speed", 1.0))
    variation = float(data.get("variation", 0.667))
    seed = int(data.get("seed", 0))
    response_format = str(data.get("response_format", "wav"))

    try:
        sample_rate, wav = TTS.synthesize(
            text_to_speak,
            speed=speed,
            variation=variation,
            seed=seed
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if response_format.lower() == "pcm":
        res_data = (wav * 32767).astype("int16").tobytes()
        return Response(content=res_data, media_type="audio/pcm",
                        headers={"x-sample-rate": str(sample_rate)})

    buf = io.BytesIO()
    sf.write(buf, wav, sample_rate, format="WAV", subtype="PCM_16")
    return Response(content=buf.getvalue(), media_type="audio/wav")

def main():
    p = argparse.ArgumentParser(description="Inflect-Micro-v2 TTS server")
    p.add_argument("--model-dir", required=True, help="Path to Inflect-Micro-v2 model directory")
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu",
                   help="Device to load the model on (cuda or cpu)")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8098)
    args = p.parse_args()
    app.state.args = args
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
