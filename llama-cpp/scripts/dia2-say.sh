#!/usr/bin/env bash
# Generate speech with the Dia2 TTS server and save it to a WAV file.
#
# Usage:
#   dia2-say.sh [output.wav] ["speaker 1 line"] ["speaker 2 line"]
#
# The server must be running first:
#   nix run ./llama-cpp#dia2-serve
set -euo pipefail

HOST="${DIA2_HOST:-127.0.0.1}"
PORT="${DIA2_PORT:-8097}"
BASE="http://${HOST}:${PORT}"
OUT="${1:-dia2.wav}"
S1="${2:-Hello there, this is a test of the Dia2 dialogue model.}"
S2="${3:-How exciting! It really works.}"

# 1. Is the server reachable?
if ! curl -s -o /dev/null --max-time 5 "${BASE}/config"; then
  echo "ERROR: Dia2 server not reachable at ${BASE}." >&2
  echo "       Start it first:  nix run ./llama-cpp#dia2-serve" >&2
  exit 1
fi

# 2. Build request payload (JSON-safe strings).
PAYLOAD=$(python3 - "$S1" "$S2" <<'PY'
import json, sys
s1, s2 = sys.argv[1], sys.argv[2]
turns = [s1, s2] + [""] * 8            # 10 turn slots
data = [2, *turns, None, None, 6.0, 0.6, 0.8, 50, 50, False]
print(json.dumps({"data": data}))
PY
)

# 3. Submit the job.
RESP=$(curl -s -X POST "${BASE}/gradio_api/call/generate_audio" \
  -H "Content-Type: application/json" -d "$PAYLOAD")

EVENT=$(printf '%s' "$RESP" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.stderr.write("server did not return JSON: " + sys.stdin.read()[:200] + "\n"); sys.exit(2)
if "event_id" not in d:
    sys.stderr.write("no event_id in response: " + json.dumps(d)[:200] + "\n"); sys.exit(3)
print(d["event_id"])
') || {
  echo "ERROR: could not submit job. Raw server response was:" >&2
  echo "  $RESP" >&2
  echo "(If the server is busy with another generation, wait for it to finish and retry.)" >&2
  exit 1
}

echo "Submitted (event=$EVENT). Generating..." >&2

# 4. Read the SSE result stream, extract the audio URL or surface the error.
URL=$(curl -s -N --max-time 600 "${BASE}/gradio_api/call/generate_audio/${EVENT}" \
  | python3 -c '
import sys, json
event = None
for line in sys.stdin:
    line = line.rstrip("\n")
    if line.startswith("event:"):
        event = line.split(":",1)[1].strip()
    elif line.startswith("data:") and event == "complete":
        payload = line.split(":",1)[1].strip()
        print(json.loads(payload)[0]["url"]); sys.exit(0)
    elif line.startswith("data:") and event == "error":
        sys.stderr.write("server reported a generation error (check the server terminal for a traceback)\n")
        sys.exit(4)
sys.stderr.write("stream ended without a completion event\n")
sys.exit(5)
') || {
  echo "ERROR: generation did not complete. See the server terminal for details." >&2
  exit 1
}

# 5. Download the WAV.
curl -s "$URL" -o "$OUT"
echo "Saved $OUT"
