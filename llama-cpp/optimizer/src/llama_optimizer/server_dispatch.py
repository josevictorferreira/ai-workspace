"""IO helpers for server lifecycle: readiness, port, delay, dispatch log (T9).

Pure functions for reading/writing server lifecycle artifacts. Separated from
:mod:`server_lifecycle` so no single module exceeds the 250-pure-LOC ceiling.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path
    from threading import Thread

    from llama_optimizer.server_http import WorkloadRecord

_ARTIFACT_NAMES: Final[tuple[str, ...]] = (
    "readiness.json",
    "metrics.json",
    "responses.jsonl",
    "port.txt",
    "dispatch_log.jsonl",
)
_READY_POLL_SECONDS: Final[float] = 0.05


def clean_stale_artifacts(output_dir: Path) -> None:
    """Delete pre-existing server artifacts so a failed launch cannot claim them."""
    for name in _ARTIFACT_NAMES:
        target = output_dir / name
        if target.exists():
            target.unlink()


def wait_for_readiness(output_dir: Path, thread: Thread, readiness_timeout: int) -> bool:
    """Poll for ``readiness.json`` while the supervisor thread is alive."""
    deadline = time.monotonic() + readiness_timeout
    readiness_path = output_dir / "readiness.json"
    while thread.is_alive() and time.monotonic() < deadline:
        if readiness_path.exists():
            return True
        time.sleep(_READY_POLL_SECONDS)
    return readiness_path.exists()


def read_port(output_dir: Path) -> int | None:
    """Read the bound TCP port from ``port.txt``, or ``None`` if missing/invalid."""
    port_path = output_dir / "port.txt"
    if not port_path.exists():
        return None
    try:
        return int(port_path.read_text().strip())
    except ValueError:
        return None


def apply_sleep(seconds: int) -> bool:
    """Sleep for ``seconds`` if positive; return whether a sleep occurred."""
    if seconds > 0:
        time.sleep(seconds)
        return True
    return False


def write_dispatch_log(output_dir: Path, records: tuple[WorkloadRecord, ...]) -> None:
    """Write raw per-request HTTP dispatch records for evidence provenance."""
    lines = [
        json.dumps(
            {
                "sequence_index": r.sequence_index,
                "spec_name": r.spec_name,
                "kind": r.kind,
                "is_warmup": r.is_warmup,
                "repetition": r.repetition,
                "status": r.status,
                "response_body": r.response_body,
                "elapsed_ms": r.elapsed_ms,
                "error": r.error,
            }
        )
        for r in records
    ]
    _ = (output_dir / "dispatch_log.jsonl").write_text("".join(line + "\n" for line in lines))
