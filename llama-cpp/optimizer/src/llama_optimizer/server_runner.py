"""Slim orchestrator for one supervised llama-server finalist (T9).

Coordinates the lifecycle (:mod:`server_lifecycle`), classification
(:mod:`server_classify`), and ledger recording (:mod:`server_recorder`) into a
single finalist attempt. This module owns only the orchestration sequence;
lifecycle, classification, and recording are each delegated to their module so
no single file exceeds the 250-pure-LOC responsibility ceiling.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from llama_optimizer.server_classify import classify_attempt
from llama_optimizer.server_dispatch import clean_stale_artifacts
from llama_optimizer.server_lifecycle import SupervisorJob, run_long_lived_server
from llama_optimizer.server_recorder import record_finalist_attempt
from llama_optimizer.server_schedule import schedule_finalists
from llama_optimizer.server_types import EligibilityStatus, FinalistRequest, FinalistResult

if TYPE_CHECKING:
    from pathlib import Path

    from llama_optimizer.ledger import Ledger
    from llama_optimizer.server_types import FinalistEntry, ServerConfig
    from llama_optimizer.supervisor import ProcessSupervisor, SupervisorConfig
    from llama_optimizer.telemetry import HardChannelProvider

_STDERR_FILENAME = "server.stderr.txt"
_STDOUT_FILENAME = "server.stdout.log"
_DISPATCH_FILENAME = "dispatch_log.jsonl"


def _read_dispatch(output_dir: Path) -> str:
    """Read the raw dispatch log written by the lifecycle, or empty string."""
    path = output_dir / _DISPATCH_FILENAME
    return path.read_text() if path.exists() else ""


def run_supervised_server(
    supervisor: ProcessSupervisor,
    provider: HardChannelProvider,
    sup_config: SupervisorConfig,
    ledger: Ledger,
    request: FinalistRequest,
) -> FinalistResult:
    """Run one supervised llama-server finalist and record everything to the ledger.

    Builds the command with exact 32768 context, cleans stale artifacts, runs
    the long-lived server lifecycle (probe, dispatch, explicit cancel, reap),
    classifies the outcome, records raw artifacts/metrics/telemetry via T4, and
    completes the attempt.
    """
    request.output_dir.mkdir(parents=True, exist_ok=True)
    clean_stale_artifacts(request.output_dir)
    attempt = ledger.start_attempt(request.trial_id)
    stdout_path = request.output_dir / _STDOUT_FILENAME
    stderr_path = request.output_dir / _STDERR_FILENAME

    lifecycle, sup_result, _dispatch = run_long_lived_server(
        SupervisorJob(supervisor, provider, sup_config),
        request,
        stdout_path,
        stderr_path,
    )
    classified = classify_attempt(request, sup_result, lifecycle, _dispatch)
    metrics_map = record_finalist_attempt(
        ledger, attempt.attempt_id, request, classified, sup_result
    )
    return FinalistResult(
        outcome=classified.outcome,
        metrics=classified.metrics,
        raw_readiness=classified.raw_readiness,
        raw_metrics=classified.raw_metrics,
        raw_responses=classified.raw_responses,
        raw_dispatch=_read_dispatch(request.output_dir),
        supervisor_result=sup_result,
        lifecycle=lifecycle,
        trial_id=request.trial_id,
        attempt_id=attempt.attempt_id,
        metrics_map=metrics_map,
        reason=classified.reason,
    )


@dataclass(frozen=True, slots=True)
class ValidationPlan:
    """Bundles inputs for multi-finalist seeded validation."""

    finalists: tuple[FinalistEntry, ...]
    seed: int
    binary: str
    output_base: Path
    config: ServerConfig


def validate_finalists(
    job: SupervisorJob, ledger: Ledger, plan: ValidationPlan
) -> tuple[FinalistResult, ...]:
    """Schedule and run only eligible finalists in seeded order.

    Ineligible finalists (failed feasibility/screening/quality) are rejected
    before launch. Each eligible finalist is run through
    :func:`run_supervised_server` with its own output directory. Cleanup of
    each process group is guaranteed before the next finalist starts.
    """
    eligible = tuple(f for f in plan.finalists if f.eligibility is EligibilityStatus.ELIGIBLE)
    scheduled = schedule_finalists(eligible, plan.seed)
    results: list[FinalistResult] = []
    for sched in scheduled:
        request = FinalistRequest(
            trial_id=sched.finalist.trial_id,
            identity=sched.finalist.identity,
            config=plan.config,
            binary=plan.binary,
            output_dir=plan.output_base / f"finalist-{sched.position}",
        )
        result = run_supervised_server(job.supervisor, job.provider, job.config, ledger, request)
        results.append(result)
        pgid = result.supervisor_result.process_group_pid
        if pgid is not None:
            cleanup_deadline = time.monotonic() + 2.0
            while time.monotonic() < cleanup_deadline:
                try:
                    os.killpg(pgid, 0)
                except ProcessLookupError:
                    break
                except PermissionError:
                    break
                time.sleep(0.05)
    return tuple(results)
