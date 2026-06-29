"""Supervised llama-bench runner with T5 routing and T4 ledger writing."""

from __future__ import annotations

import hashlib
import os
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

from llama_optimizer.bench_command import build_bench_command
from llama_optimizer.bench_parser import parse_bench_jsonl
from llama_optimizer.bench_types import (
    BenchResult,
    BenchScreenRequest,
    BenchScreenResult,
    MeasurementFailureError,
)
from llama_optimizer.lifecycle import NonScoredOutcome

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


def classify_child_exit(
    exit_code: ChildExit,
    stderr: str,
) -> NonScoredOutcome:
    """Classify a nonzero llama-bench exit into a closed T4 outcome.

    Exit 0 is never passed here (the caller parses output instead). The
    classification distinguishes unsupported flag combinations, model-load
    errors, and confirmed temporary launch errors.
    """
    if exit_code.returncode == 0:
        # Exit 0 means success; the caller parses output, not classifies exit.
        return NonScoredOutcome.MEASUREMENT_FAILURE
    lower = stderr.lower()
    if "unsupported" in lower:
        return NonScoredOutcome.UNSUPPORTED
    if "failed to load" in lower or "error loading model" in lower:
        return NonScoredOutcome.DETERMINISTIC_LOAD_FAILURE
    return NonScoredOutcome.TRANSIENT_FAILURE


# --- Stdio capture ----------------------------------------------------------


@contextmanager
def _capture_stdio(stdout_path: Path, stderr_path: Path) -> Generator[None]:
    """Redirect fd 1 and 2 to files so the supervised child inherits them.

    The supervisor launches the child with ``start_new_session=True`` and no
    explicit ``stdout=`` / ``stderr=`` redirection, so the child inherits the
    parent's file descriptors. Redirecting fd 1/2 before calling the supervisor
    captures the child's output without modifying the supervisor.
    """
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


# --- Screening orchestrator -------------------------------------------------


def _extract_metrics(result: BenchResult) -> dict[str, float]:
    """Flatten parsed measurements into named metrics for the ledger."""
    metrics: dict[str, float] = {}
    for m in result.measurements:
        metrics[f"{m.workload_name}_avg_ts"] = m.avg_ts
        metrics[f"{m.workload_name}_stddev_ts"] = m.stddev_ts
    return metrics


def run_supervised_bench(
    supervisor: ProcessSupervisor,
    provider: HardChannelProvider,
    sup_config: SupervisorConfig,
    ledger: Ledger,
    request: BenchScreenRequest,
) -> BenchScreenResult:
    """Run one supervised llama-bench attempt and record everything to the ledger.

    Starts the attempt, builds the command from ``request``, captures stdio,
    routes the process through the T5 supervisor, classifies the outcome, parses
    JSONL, records metrics/artifacts/telemetry via T4, and completes the attempt.
    Never converts a failure to throughput zero.
    """
    request.output_dir.mkdir(parents=True, exist_ok=True)
    command = build_bench_command(request.binary, request.bench_config, request.identity)
    attempt = ledger.start_attempt(request.trial_id)
    stdout_path = request.output_dir / f"bench-{attempt.attempt_id}.stdout.jsonl"
    stderr_path = request.output_dir / f"bench-{attempt.attempt_id}.stderr.txt"

    with _capture_stdio(stdout_path, stderr_path):
        sup_result = supervisor.run(command, provider=provider, config=sup_config)

    raw_jsonl = stdout_path.read_text() if stdout_path.exists() else ""
    raw_stderr = stderr_path.read_text() if stderr_path.exists() else ""
    outcome: NonScoredOutcome | None = None
    parsed: BenchResult | None = None
    metrics: dict[str, float] = {}

    if isinstance(sup_result.outcome, NonScoredOutcome):
        outcome = sup_result.outcome
    elif sup_result.outcome.returncode != 0:
        outcome = classify_child_exit(sup_result.outcome, raw_stderr)
    else:
        try:
            parsed = parse_bench_jsonl(
                raw_jsonl,
                expected=request.identity,
                expected_workload_names=tuple(w.name for w in request.bench_config.workloads),
            )
            metrics = _extract_metrics(parsed)
        except MeasurementFailureError as exc:
            outcome = NonScoredOutcome.MEASUREMENT_FAILURE
            raw_stderr = f"{raw_stderr}\n{exc}"

    # Record raw artifact (always, even on failure for evidence).
    content_hash = hashlib.sha256(raw_jsonl.encode()).hexdigest()
    ledger.record_artifact(
        attempt_id=attempt.attempt_id,
        kind="bench-jsonl",
        relative_path=str(stdout_path),
        content_hash=content_hash,
    )
    if metrics:
        ledger.record_metrics(attempt.attempt_id, metrics)
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
            attempt.attempt_id, outcome=outcome, reason=raw_stderr.strip() or outcome.value
        )

    return BenchScreenResult(
        outcome=outcome,
        result=parsed,
        raw_jsonl=raw_jsonl,
        supervisor_result=sup_result,
        trial_id=request.trial_id,
        attempt_id=attempt.attempt_id,
        metrics=metrics,
    )
