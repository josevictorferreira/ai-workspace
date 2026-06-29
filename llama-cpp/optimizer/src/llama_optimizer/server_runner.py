"""Supervised llama-server finalist runner with T5 routing and T4 ledger (T9).

Starts ``llama-server`` through the T5 :class:`ProcessSupervisor` with exact
``--ctx-size 32768`` and a matching model/backend/runtime identity. After the
supervised run, readiness/metrics/responses artifacts are parsed strictly and
the outcome is classified: startup/load failure, readiness timeout, request
error, response-quality failure, VRAM breach, telemetry loss, and cleanup are
each distinct non-scored outcomes. Metrics, raw artifacts, and telemetry are
recorded via the T4 ledger. Never converts a failure to a zero score.
"""

from __future__ import annotations

import hashlib
import os
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

from llama_optimizer.lifecycle import NonScoredOutcome
from llama_optimizer.server_command import build_server_command
from llama_optimizer.server_parser import (
    MetricsParseError,
    ReadinessTimeoutError,
    ServerIdentityMismatchError,
    parse_readiness,
    parse_responses,
    parse_server_metrics,
)
from llama_optimizer.server_types import FinalistRequest, FinalistResult, ServerMetrics

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from llama_optimizer.ledger import Ledger
    from llama_optimizer.supervisor import (
        ChildExit,
        ProcessSupervisor,
        SupervisorConfig,
    )
    from llama_optimizer.telemetry import HardChannelProvider


def classify_server_exit(exit_code: ChildExit, stderr: str) -> NonScoredOutcome:
    """Classify a nonzero llama-server exit into a closed T4 outcome.

    Exit 0 is never passed here. The classification distinguishes unsupported
    flag combinations, model-load errors, and confirmed crashes.
    """
    if exit_code.returncode == 0:
        return NonScoredOutcome.MEASUREMENT_FAILURE
    lower = stderr.lower()
    if "unsupported" in lower:
        return NonScoredOutcome.UNSUPPORTED
    if "failed to load" in lower or "error loading model" in lower:
        return NonScoredOutcome.DETERMINISTIC_LOAD_FAILURE
    return NonScoredOutcome.CRASH


# --- Stdio capture (mirrors bench_runner so the child inherits fd 1/2) ------


@contextmanager
def _capture_stdio(stdout_path: Path, stderr_path: Path) -> Generator[None]:
    """Redirect fd 1 and 2 to files so the supervised child inherits them."""
    _ = sys.stdout.flush()
    _ = sys.stderr.flush()
    saved_out = os.dup(1)
    saved_err = os.dup(2)
    out_fd = os.open(str(stdout_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    err_fd = os.open(str(stderr_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    try:
        _ = os.dup2(out_fd, 1)
        _ = os.dup2(err_fd, 2)
        _ = os.close(out_fd)
        _ = os.close(err_fd)
        yield
    finally:
        _ = sys.stdout.flush()
        _ = sys.stderr.flush()
        _ = os.dup2(saved_out, 1)
        _ = os.dup2(saved_err, 2)
        _ = os.close(saved_out)
        _ = os.close(saved_err)


def _percentile(values: tuple[float, ...], pct: int) -> float:
    """Return a deterministic nearest-rank percentile of ``values``."""
    if not values:
        return 0.0
    ranked = sorted(values)
    idx = max(0, min(len(ranked) - 1, round((pct / 100) * (len(ranked) - 1))))
    return ranked[idx]


def _extract_metrics_map(metrics: ServerMetrics) -> dict[str, float]:
    """Flatten parsed server metrics into named metrics for the ledger."""
    return {
        "prompt_throughput": metrics.prompt_throughput,
        "generation_throughput": metrics.generation_throughput,
        "ttft_ms_p50": _percentile(metrics.ttft_ms, 50),
        "ttft_ms_p95": _percentile(metrics.ttft_ms, 95),
        "request_latency_ms_p50": _percentile(metrics.request_latency_ms, 50),
        "request_latency_ms_p95": _percentile(metrics.request_latency_ms, 95),
        "slots": float(metrics.slots),
    }


def _classify_exit0(
    request: FinalistRequest,
) -> tuple[NonScoredOutcome | None, ServerMetrics | None, str]:
    """Classify a clean (exit-0) server run by parsing its artifacts."""
    readiness_path = request.output_dir / "readiness.json"
    metrics_path = request.output_dir / "metrics.json"
    responses_path = request.output_dir / "responses.jsonl"
    raw_readiness = readiness_path.read_text() if readiness_path.exists() else ""
    raw_metrics = metrics_path.read_text() if metrics_path.exists() else ""
    raw_responses = responses_path.read_text() if responses_path.exists() else ""

    try:
        parse_readiness(raw_readiness)
    except ReadinessTimeoutError as exc:
        return NonScoredOutcome.HANG, None, str(exc)

    try:
        metrics = parse_server_metrics(raw_metrics, request.identity)
        responses = parse_responses(raw_responses)
    except (MetricsParseError, ServerIdentityMismatchError) as exc:
        return NonScoredOutcome.MEASUREMENT_FAILURE, None, str(exc)

    if metrics.errors > 0:
        return NonScoredOutcome.MEASUREMENT_FAILURE, metrics, f"{metrics.errors} request errors"
    if not metrics.quality_pass or any(not r.quality_pass for r in responses):
        return NonScoredOutcome.QUALITY_FAILURE, metrics, "response quality regression"
    return None, metrics, "all gates passed"


def run_supervised_server(
    supervisor: ProcessSupervisor,
    provider: HardChannelProvider,
    sup_config: SupervisorConfig,
    ledger: Ledger,
    request: FinalistRequest,
) -> FinalistResult:
    """Run one supervised llama-server finalist and record everything to the ledger.

    Builds the command with exact 32768 context, captures stdio, routes the
    process through the T5 supervisor, classifies the outcome, parses
    metrics/responses/telemetry, records raw artifacts via T4, and completes
    the attempt. Never converts a failure to throughput zero.
    """
    request.output_dir.mkdir(parents=True, exist_ok=True)
    command = build_server_command(request.binary, request.config, request.identity)
    attempt = ledger.start_attempt(request.trial_id)
    stdout_path = request.output_dir / f"server-{attempt.attempt_id}.stdout.log"
    stderr_path = request.output_dir / f"server-{attempt.attempt_id}.stderr.txt"

    with _capture_stdio(stdout_path, stderr_path):
        sup_result = supervisor.run(command, provider=provider, config=sup_config)

    raw_stderr = stderr_path.read_text() if stderr_path.exists() else ""
    outcome: NonScoredOutcome | None = None
    metrics: ServerMetrics | None = None
    reason = ""

    if isinstance(sup_result.outcome, NonScoredOutcome):
        outcome = sup_result.outcome
        reason = sup_result.outcome.value
    elif sup_result.outcome.returncode != 0:
        outcome = classify_server_exit(sup_result.outcome, raw_stderr)
        reason = raw_stderr.strip() or outcome.value
    else:
        outcome, metrics, reason = _classify_exit0(request)

    raw_readiness = (
        (request.output_dir / "readiness.json").read_text()
        if (request.output_dir / "readiness.json").exists()
        else ""
    )
    raw_metrics_text = (
        (request.output_dir / "metrics.json").read_text()
        if (request.output_dir / "metrics.json").exists()
        else ""
    )
    raw_responses = (
        (request.output_dir / "responses.jsonl").read_text()
        if (request.output_dir / "responses.jsonl").exists()
        else ""
    )

    metrics_map = _extract_metrics_map(metrics) if metrics is not None else {}
    content_hash = hashlib.sha256(raw_metrics_text.encode()).hexdigest()
    ledger.record_artifact(
        attempt_id=attempt.attempt_id,
        kind="server-metrics",
        relative_path=str(request.output_dir / "metrics.json"),
        content_hash=content_hash,
    )
    ledger.record_artifact(
        attempt_id=attempt.attempt_id,
        kind="server-responses",
        relative_path=str(request.output_dir / "responses.jsonl"),
        content_hash=hashlib.sha256(raw_responses.encode()).hexdigest(),
    )
    if metrics_map:
        ledger.record_metrics(attempt.attempt_id, metrics_map)
    if sup_result.peak_used is not None:
        breached = outcome is NonScoredOutcome.RESOURCE_INFEASIBLE
        ledger.record_telemetry(
            attempt_id=attempt.attempt_id,
            vram_used_bytes=int(sup_result.peak_used),
            peak_vram_bytes=int(sup_result.peak_used),
            breached=breached,
        )

    if outcome is None:
        ledger.succeed_attempt(attempt.attempt_id)
    else:
        ledger.end_attempt_nonscored(
            attempt.attempt_id, outcome=outcome, reason=reason.strip() or outcome.value
        )

    return FinalistResult(
        outcome=outcome,
        metrics=metrics,
        raw_readiness=raw_readiness,
        raw_metrics=raw_metrics_text,
        raw_responses=raw_responses,
        supervisor_result=sup_result,
        trial_id=request.trial_id,
        attempt_id=attempt.attempt_id,
        metrics_map=metrics_map,
        reason=reason,
    )
