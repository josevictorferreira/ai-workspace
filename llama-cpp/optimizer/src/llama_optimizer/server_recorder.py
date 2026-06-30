"""Ledger recording for supervised llama-server finalist attempts (T9).

Records raw artifacts (readiness, metrics, responses, dispatch log), parsed
metrics, telemetry, and finalizes the attempt in the T4 ledger. Failed
attempts never receive metrics, a numeric score, winner eligibility, or
successful metric-ledger rows.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from llama_optimizer.lifecycle import NonScoredOutcome
from llama_optimizer.server_classify import ClassifiedOutcome, extract_metrics_map

if TYPE_CHECKING:
    from pathlib import Path

    from llama_optimizer.ledger import Ledger
    from llama_optimizer.lifecycle import AttemptId
    from llama_optimizer.server_types import FinalistRequest
    from llama_optimizer.supervisor import SupervisorResult
_READINESS_KIND = "server-readiness"
_METRICS_KIND = "server-metrics"
_RESPONSES_KIND = "server-responses"
_DISPATCH_KIND = "server-dispatch"


def _record_artifact(ledger: Ledger, attempt_id: AttemptId, kind: str, path: Path) -> None:
    """Record an artifact only if it exists on disk (never links absent files)."""
    if path.exists():
        ledger.record_artifact(
            attempt_id=attempt_id,
            kind=kind,
            relative_path=str(path),
            content_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
        )


def record_finalist_attempt(
    ledger: Ledger,
    attempt_id: AttemptId,
    request: FinalistRequest,
    classified: ClassifiedOutcome,
    sup_result: SupervisorResult,
) -> dict[str, float]:
    """Record artifacts, metrics, telemetry, and finalize the attempt.

    Returns the metrics map (empty for failed attempts). Failed attempts never
    receive metrics or winner eligibility.
    """
    out = request.output_dir
    _record_artifact(ledger, attempt_id, _READINESS_KIND, out / "readiness.json")
    _record_artifact(ledger, attempt_id, _METRICS_KIND, out / "metrics.json")
    _record_artifact(ledger, attempt_id, _RESPONSES_KIND, out / "responses.jsonl")
    _record_artifact(ledger, attempt_id, _DISPATCH_KIND, out / "dispatch_log.jsonl")

    metrics_map = extract_metrics_map(classified.metrics) if classified.metrics else {}
    if classified.metrics:
        ledger.record_metrics(attempt_id, metrics_map)

    if sup_result.peak_used is not None:
        breached = classified.outcome is NonScoredOutcome.RESOURCE_INFEASIBLE
        ledger.record_telemetry(
            attempt_id=attempt_id,
            vram_used_bytes=int(sup_result.peak_used),
            peak_vram_bytes=int(sup_result.peak_used),
            breached=breached,
        )

    if classified.outcome is None:
        ledger.succeed_attempt(attempt_id)
    else:
        ledger.end_attempt_nonscored(
            attempt_id,
            outcome=classified.outcome,
            reason=classified.reason.strip() or classified.outcome.value,
        )
    return metrics_map
