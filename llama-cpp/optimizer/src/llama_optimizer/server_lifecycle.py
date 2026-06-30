"""Long-lived llama-server lifecycle: launch, readiness, dispatch, termination (T9).

Runs the T5 supervisor in a background thread (process-group + telemetry
management) while the main thread actively probes readiness, applies the
configured delay/cooldown, and dispatches HTTP workloads. After dispatch (or
on readiness/port failure) the server is explicitly cancelled via a shared
:class:`threading.Event` so the supervisor reaps the process group through its
SIGTERM -> bounded grace -> SIGKILL -> wait sequence.

The fake ``llama-server`` must stay alive until the runner explicitly stops it;
this module never relies on fake self-exit or the overall supervisor deadline.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from llama_optimizer.lifecycle import NonScoredOutcome
from llama_optimizer.server_command import build_server_command
from llama_optimizer.server_dispatch import (
    apply_sleep,
    read_port,
    wait_for_readiness,
    write_dispatch_log,
)
from llama_optimizer.server_http import dispatch_sequence
from llama_optimizer.server_types import LifecycleRecord
from llama_optimizer.supervisor import SupervisorResult
from llama_optimizer.telemetry import Bytes

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from llama_optimizer.server_http import WorkloadRecord
    from llama_optimizer.server_types import FinalistRequest
    from llama_optimizer.supervisor import ProcessSupervisor, SupervisorConfig
    from llama_optimizer.telemetry import HardChannelProvider

_POST_DISPATCH_SETTLE_SECONDS: Final[float] = 0.15
_JOIN_EXTRA_SECONDS: Final[float] = 5.0


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


@dataclass(frozen=True, slots=True)
class SupervisorJob:
    """Bundles the supervisor, telemetry provider, and config for one finalist."""

    supervisor: ProcessSupervisor
    provider: HardChannelProvider
    config: SupervisorConfig


def _run_supervisor_thread(
    job: SupervisorJob,
    command: list[str],
    cancel: threading.Event,
    holder: list[object],
) -> None:
    """Target for the background supervisor thread."""
    try:
        result = job.supervisor.run(
            command, provider=job.provider, config=job.config, cancel=cancel
        )
    except OSError as exc:
        holder.append(exc)
        return
    holder.append(result)


def _hang_result() -> SupervisorResult:
    """Build a fail-closed SupervisorResult when the thread fails to produce one."""
    now = datetime.now(UTC)
    return SupervisorResult(
        outcome=NonScoredOutcome.HANG,
        samples=(),
        diagnostics_series=(),
        peak_used=Bytes(0),
        started_at=now,
        ended_at=now,
        launched=False,
        terminated_group=False,
    )


def _extract_result(holder: list[object]) -> SupervisorResult:
    """Extract the result, building a fail-closed HANG fallback on failure."""
    if not holder:
        return _hang_result()
    raw = holder[0]
    if isinstance(raw, OSError):
        return _hang_result()
    if isinstance(raw, SupervisorResult):
        return raw
    return _hang_result()


def run_long_lived_server(
    job: SupervisorJob,
    request: FinalistRequest,
    stdout_path: Path,
    stderr_path: Path,
) -> tuple[LifecycleRecord, SupervisorResult, tuple[WorkloadRecord, ...]]:
    """Run one long-lived server lifecycle: probe, dispatch, cancel, reap.

    Returns a :class:`LifecycleRecord` trace, the :class:`SupervisorResult`,
    and the raw HTTP dispatch records. The server is explicitly cancelled via
    ``cancel`` after dispatch (or on readiness/port failure) so the supervisor
    reaps the process group promptly.
    """
    command = build_server_command(request.binary, request.config, request.identity)
    cancel = threading.Event()
    holder: list[object] = []
    thread = threading.Thread(
        target=_run_supervisor_thread,
        args=(SupervisorJob(job.supervisor, job.provider, job.config), command, cancel, holder),
        daemon=True,
    )
    delay_applied = False
    cooldown_applied = False
    dispatch_records: tuple[WorkloadRecord, ...] = ()

    with _capture_stdio(stdout_path, stderr_path):
        thread.start()
        ready = wait_for_readiness(
            request.output_dir, thread, request.config.readiness_timeout_seconds
        )
        port: int | None = None
        if ready and thread.is_alive():
            port = read_port(request.output_dir)
            if port is not None:
                delay_applied = apply_sleep(request.config.delay_seconds)
                dispatch_records = dispatch_sequence(request, port, thread)
                cooldown_applied = apply_sleep(request.config.cooldown_seconds)
                time.sleep(_POST_DISPATCH_SETTLE_SECONDS)
                cancel.set()
            else:
                cancel.set()
        else:
            cancel.set()
        thread.join(
            timeout=job.config.deadline.total_seconds()
            + job.config.grace.total_seconds()
            + _JOIN_EXTRA_SECONDS
        )

    sup_result = _extract_result(holder)
    failure = ""
    if sup_result.escalated_to_sigkill:
        failure = "server ignored SIGTERM; SIGKILL required"
    record = LifecycleRecord(
        launched=sup_result.launched,
        ready=ready,
        dispatched=port is not None,
        port=port,
        request_count=len(dispatch_records),
        delay_applied=delay_applied,
        cooldown_applied=cooldown_applied,
        terminated=cancel.is_set(),
        failure=failure,
    )
    if dispatch_records:
        write_dispatch_log(request.output_dir, dispatch_records)
    return record, sup_result, dispatch_records
