"""HTTP workload dispatch for live llama-server finalists (T9).

Sends POST /v1/chat/completions requests to a running llama-server instance
using stdlib :mod:`http.client`. Each dispatch records the HTTP status, raw
response body, elapsed time, and any transport error so the runner observes
whether the live server is functional and retains full request provenance.
"""

from __future__ import annotations

import http.client
import json
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING

from llama_optimizer.server_schedule import ScheduledRequest, interleave_requests

if TYPE_CHECKING:
    from threading import Thread

    from llama_optimizer.server_types import FinalistRequest

_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class WorkloadRecord:
    """One HTTP workload dispatch result with full request provenance."""

    sequence_index: int
    spec_name: str
    kind: str
    is_warmup: bool
    repetition: int
    status: int
    response_body: str
    elapsed_ms: float
    error: str


@dataclass(frozen=True, slots=True)
class _RawHttp:
    """Raw HTTP response data for one request (no sequence context)."""

    status: int
    body: str
    elapsed_ms: float
    error: str


def _build_body(spec_name: str) -> bytes:
    """Build a minimal chat-completion request body for one workload spec."""
    body: dict[str, object] = {
        "messages": [{"role": "user", "content": spec_name}],
        "max_tokens": 100,
    }
    return json.dumps(body).encode()


def _send_raw(
    port: int,
    spec_name: str,
    *,
    host: str = _DEFAULT_HOST,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> _RawHttp:
    """Send one POST /v1/chat/completions and return raw HTTP data. Never raises."""
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    start = time.monotonic()
    try:
        conn.request(
            "POST",
            _CHAT_COMPLETIONS_PATH,
            _build_body(spec_name),
            {"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        body = resp.read().decode(errors="replace")
        elapsed = (time.monotonic() - start) * 1000.0
        return _RawHttp(status=resp.status, body=body, elapsed_ms=elapsed, error="")
    except (http.client.HTTPException, OSError) as exc:
        elapsed = (time.monotonic() - start) * 1000.0
        return _RawHttp(status=0, body="", elapsed_ms=elapsed, error=str(exc))
    finally:
        conn.close()


def dispatch_sequence(
    request: FinalistRequest,
    port: int,
    thread: Thread,
) -> tuple[WorkloadRecord, ...]:
    """Send interleaved HTTP requests concurrently, bounded by parallel, while thread is alive."""
    sequence = interleave_requests(request.config)
    records: list[WorkloadRecord | None] = [None] * len(sequence)

    def _task(index: int, scheduled: ScheduledRequest) -> WorkloadRecord:
        raw = _send_raw(port, scheduled.spec.name)
        return WorkloadRecord(
            sequence_index=index,
            spec_name=scheduled.spec.name,
            kind=scheduled.spec.kind.value,
            is_warmup=scheduled.is_warmup,
            repetition=scheduled.repetition,
            status=raw.status,
            response_body=raw.body,
            elapsed_ms=raw.elapsed_ms,
            error=raw.error,
        )

    with ThreadPoolExecutor(max_workers=request.config.parallel) as executor:
        futures: dict[Future[WorkloadRecord], int] = {}
        for index, scheduled in enumerate(sequence):
            if not thread.is_alive():
                break
            fut = executor.submit(_task, index, scheduled)
            futures[fut] = index
        for fut, idx in futures.items():
            exc = fut.exception()
            if exc is not None:
                sch = sequence[idx]
                records[idx] = WorkloadRecord(
                    sequence_index=idx,
                    spec_name=sch.spec.name,
                    kind=sch.spec.kind.value,
                    is_warmup=sch.is_warmup,
                    repetition=sch.repetition,
                    status=0,
                    response_body="",
                    elapsed_ms=0.0,
                    error=str(exc),
                )
            else:
                records[idx] = fut.result()
    valid_records = [r for r in records if r is not None]
    return tuple(valid_records)
