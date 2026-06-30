"""Outcome classification for supervised llama-server finalists (T9).

Classifies the full lifecycle outcome from the T5 :class:`SupervisorResult`,
the :class:`LifecycleRecord` trace, and the parsed server artifacts. HTTP
transport/status/results are authoritative inputs to classification.
Startup/load failure, readiness timeout, request error, response-quality
failure, VRAM breach, telemetry loss, and cleanup failure each map to a
distinct non-scored outcome.

When the lifecycle dispatched HTTP workloads, classification is artifact-based
(readiness, metrics, responses, quality). When it did not, the exit code or
readiness state determines the failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from llama_optimizer.lifecycle import NonScoredOutcome
from llama_optimizer.server_parser import (
    parse_readiness,
    parse_responses,
    parse_server_metrics,
)
from llama_optimizer.server_schedule import interleave_requests
from llama_optimizer.server_types import (
    MetricsParseError,
    ReadinessTimeoutError,
    ServerIdentityMismatchError,
    ServerMetrics,
)

if TYPE_CHECKING:
    from pathlib import Path

    from llama_optimizer.server_http import WorkloadRecord
    from llama_optimizer.server_schedule import ScheduledRequest
    from llama_optimizer.server_types import FinalistRequest, LifecycleRecord
    from llama_optimizer.supervisor import ChildExit, SupervisorResult

_STDERR_FILENAME = "server.stderr.txt"


def classify_server_exit(exit_code: ChildExit, stderr: str) -> NonScoredOutcome:
    """Classify a nonzero llama-server exit into a closed outcome.

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


def percentile(values: tuple[float, ...], pct: int) -> float:
    """Return a deterministic nearest-rank percentile of ``values``."""
    if not values:
        return 0.0
    ranked = sorted(values)
    idx = max(0, min(len(ranked) - 1, round((pct / 100) * (len(ranked) - 1))))
    return ranked[idx]


def extract_metrics_map(metrics: ServerMetrics) -> dict[str, float]:
    """Flatten parsed server metrics into named metrics for the ledger."""
    return {
        "prompt_throughput": metrics.prompt_throughput,
        "generation_throughput": metrics.generation_throughput,
        "ttft_ms_p50": percentile(metrics.ttft_ms, 50),
        "ttft_ms_p95": percentile(metrics.ttft_ms, 95),
        "request_latency_ms_p50": percentile(metrics.request_latency_ms, 50),
        "request_latency_ms_p95": percentile(metrics.request_latency_ms, 95),
        "slots": float(metrics.slots),
    }


@dataclass(frozen=True, slots=True)
class ClassifiedOutcome:
    """Typed outcome of classifying one finalist attempt after completion."""

    outcome: NonScoredOutcome | None
    metrics: ServerMetrics | None
    reason: str
    raw_readiness: str
    raw_metrics: str
    raw_responses: str


@dataclass(frozen=True, slots=True)
class _RawArtifacts:
    """Raw artifact contents read from the finalist output directory."""

    readiness: str
    metrics: str
    responses: str
    stderr: str


def _read_artifact(path: Path) -> str:
    """Read a file if it exists, returning empty string otherwise."""
    return path.read_text() if path.exists() else ""


def _read_raw(output_dir: Path) -> _RawArtifacts:
    """Read readiness, metrics, responses, and stderr artifacts."""
    return _RawArtifacts(
        readiness=_read_artifact(output_dir / "readiness.json"),
        metrics=_read_artifact(output_dir / "metrics.json"),
        responses=_read_artifact(output_dir / "responses.jsonl"),
        stderr=_read_artifact(output_dir / _STDERR_FILENAME),
    )


def _outcome(
    raw: _RawArtifacts,
    outcome: NonScoredOutcome | None,
    metrics: ServerMetrics | None,
    reason: str,
) -> ClassifiedOutcome:
    """Build a ClassifiedOutcome from raw artifacts and the determined result."""
    return ClassifiedOutcome(
        outcome=outcome,
        metrics=metrics,
        reason=reason,
        raw_readiness=raw.readiness,
        raw_metrics=raw.metrics,
        raw_responses=raw.responses,
    )


def _classify_not_dispatched(
    raw: _RawArtifacts, lifecycle: LifecycleRecord, exit_code: ChildExit
) -> ClassifiedOutcome:
    """Classify a finalist where HTTP dispatch never started."""
    if not lifecycle.launched:
        return _outcome(raw, NonScoredOutcome.HANG, None, "supervisor thread failure")
    if lifecycle.ready:
        return _outcome(
            raw, NonScoredOutcome.MEASUREMENT_FAILURE, None, "ready but port unavailable"
        )
    failure = classify_server_exit(exit_code, raw.stderr)
    return _outcome(raw, failure, None, failure.value)


def _validate_record(rec: WorkloadRecord, expected: ScheduledRequest, index: int) -> str | None:
    """Return a mismatch reason when a dispatch record violates its schedule."""
    http_ok = 200
    transport_reason = rec.error or "transport error"
    checks: list[tuple[bool, str]] = [
        (rec.sequence_index != index, f"reordered or duplicate sequence index at {index}"),
        (
            rec.spec_name != expected.spec.name,
            "mismatched spec name at index "
            + f"{index}: expected {expected.spec.name}, got {rec.spec_name}",
        ),
        (rec.is_warmup != expected.is_warmup, f"mismatched is_warmup flag at index {index}"),
        (rec.repetition != expected.repetition, f"mismatched repetition index at index {index}"),
        (rec.kind != expected.spec.kind.value, f"mismatched request kind at index {index}"),
        (rec.status != http_ok, f"HTTP status error {rec.status} on request {index}"),
        (
            rec.status <= 0 or bool(rec.error),
            f"HTTP transport error on request {index}: {transport_reason}",
        ),
    ]
    for failed, msg in checks:
        if failed:
            return msg
    return None


def _classify_dispatched(
    request: FinalistRequest,
    raw: _RawArtifacts,
    dispatch_records: tuple[WorkloadRecord, ...],
) -> ClassifiedOutcome:
    """Classify a finalist where HTTP dispatch completed, using artifacts and records."""
    expected_seq = interleave_requests(request.config)
    failure = _measurement_failure(request, raw, dispatch_records, expected_seq)
    if failure is not None:
        return failure
    metrics = parse_server_metrics(raw.metrics, request.identity)
    responses = parse_responses(raw.responses)
    if not metrics.quality_pass or any(not r.quality_pass for r in responses):
        return _outcome(raw, NonScoredOutcome.QUALITY_FAILURE, None, "response quality regression")
    return _outcome(raw, None, metrics, "all gates passed")


def _measurement_failure(
    request: FinalistRequest,
    raw: _RawArtifacts,
    dispatch_records: tuple[WorkloadRecord, ...],
    expected_seq: tuple[ScheduledRequest, ...],
) -> ClassifiedOutcome | None:
    """Return a MEASUREMENT_FAILURE/HANG outcome when dispatch artifacts are invalid."""
    if len(dispatch_records) != len(expected_seq):
        reason = (
            f"incomplete dispatch schedule: expected {len(expected_seq)} "
            + f"requests, got {len(dispatch_records)}"
        )
        return _outcome(raw, NonScoredOutcome.MEASUREMENT_FAILURE, None, reason)
    for index, rec in enumerate(dispatch_records):
        reason = _validate_record(rec, expected_seq[index], index)
        if reason is not None:
            return _outcome(raw, NonScoredOutcome.MEASUREMENT_FAILURE, None, reason)
    try:
        _ = parse_readiness(raw.readiness)
    except ReadinessTimeoutError as exc:
        return _outcome(raw, NonScoredOutcome.HANG, None, str(exc))
    try:
        _ = parse_server_metrics(raw.metrics, request.identity)
        _ = parse_responses(raw.responses)
    except (MetricsParseError, ServerIdentityMismatchError) as exc:
        return _outcome(raw, NonScoredOutcome.MEASUREMENT_FAILURE, None, str(exc))
    return None


def classify_attempt(
    request: FinalistRequest,
    sup_result: SupervisorResult,
    lifecycle: LifecycleRecord,
    dispatch_records: tuple[WorkloadRecord, ...],
) -> ClassifiedOutcome:
    """Classify the full outcome from supervisor result, lifecycle, and artifacts."""
    raw = _read_raw(request.output_dir)
    if isinstance(sup_result.outcome, NonScoredOutcome):
        return _outcome(raw, sup_result.outcome, None, sup_result.outcome.value)
    if sup_result.escalated_to_sigkill:
        return _outcome(raw, NonScoredOutcome.HANG, None, "SIGTERM ignored; SIGKILL required")
    if lifecycle.dispatched:
        return _classify_dispatched(request, raw, dispatch_records)
    return _classify_not_dispatched(raw, lifecycle, sup_result.outcome)
