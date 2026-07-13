#!/usr/bin/env python3
"""Gepard TTS one-shot generation.

Loads the model, synthesizes text, saves WAV. No server needed.

Usage:
    gepard-say "Hello world"
    gepard-say "Hello" -o out.wav --reference ref_audio/audio_en.wav --cfg-scale 3
"""

import argparse
import os
import sys

GEPARD_SRC = os.environ.get("GEPARD_SRC", ".")
sys.path.insert(0, GEPARD_SRC)

from gepard_inference import GepardSession


def main():
    p = argparse.ArgumentParser(
        prog="gepard-say",
        description="Gepard TTS — one-shot speech generation (no server).",
    )
    p.add_argument("text", help="Text to synthesize.")
    p.add_argument(
        "-o",
        "--output",
        default="tts_output.wav",
        help="Output WAV path (default: tts_output.wav).",
    )
    p.add_argument(
        "-r",
        "--reference",
        default=None,
        help="Reference voice clip to clone. Omit for the config default voice.",
    )
    p.add_argument(
        "--config",
        default=os.path.join(GEPARD_SRC, "config.yaml"),
        help="Config YAML (default: <gepard-src>/config.yaml).",
    )
    p.add_argument("--device", default=None, help="'cuda', 'cpu', or auto-detect.")
    p.add_argument("--checkpoint", default=None, help="Override checkpoint.")

    g = p.add_argument_group("generation (override config defaults)")
    g.add_argument("--temperature", type=float)
    g.add_argument("--top-k", type=int)
    g.add_argument("--cfg-scale", type=float, help="Text CFG weight; 1.0 = off.")
    g.add_argument("--cfg-frames", type=int, help="Guide only the first N frames.")
    g.add_argument("--stop-threshold", type=float)
    g.add_argument("--max-frames", type=int)
    g.add_argument("--repetition-penalty", type=float)
    g.add_argument("--repetition-window", type=int)

    args = p.parse_args()

    from gepard_inference import SessionConfig

    cfg = SessionConfig.from_yaml(args.config)
    if args.checkpoint:
        cfg.checkpoint = args.checkpoint

    session = GepardSession(cfg, device=args.device).load()

    overrides = {
        k: v
        for k, v in {
            "temperature": args.temperature,
            "top_k": args.top_k,
            "cfg_scale": args.cfg_scale,
            "cfg_frames": args.cfg_frames,
            "stop_threshold": args.stop_threshold,
            "max_frames": args.max_frames,
            "repetition_penalty": args.repetition_penalty,
            "repetition_window": args.repetition_window,
        }.items()
        if v is not None
    }

    import soundfile as sf

    sr, wave = session.synthesize(args.text, reference=args.reference, **overrides)
    sf.write(args.output, wave, sr)
    print(f"Saved: {args.output} ({len(wave) / sr:.1f}s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
