"""Fail-closed process supervision for trial children (T5).

Every child is launched in a dedicated process session/group. The hard
channel is sampled at the configured interval through startup, measurement,
cooldown, and shutdown. On a sampled breach, missing/malformed/stale hard
telemetry, deadline expiry, parent interruption, or a child crash, the whole
group is terminated (SIGTERM), escalated to SIGKILL after a bounded grace,
reaped, and a typed result is returned only after cleanup.

Outcome vocabulary (exact T4 lifecycle terms):

* breach (preflight or sampled)          -> ``resource-infeasible``
* missing/malformed/stale hard telemetry -> ``telemetry-loss``
* deadline expiry                        -> ``hang``
* parent interruption (SIGINT)           -> ``cancelled``
* nonzero child status                   -> raw :class:`ChildExit` (caller classifies
                                           transient-vs-deterministic)

Only the group this supervisor launched is ever signalled; unrelated processes
and independent sentinel sessions are untouched.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, final

from llama_optimizer.lifecycle import NonScoredOutcome
from llama_optimizer.telemetry import (
    Bytes,
    Diagnostics,
    HardChannel,
    HardChannelProvider,
    TelemetryLossError,
    is_breach,
    is_stale,
)

if TYPE_CHECKING:
    import threading
__all__ = ("ChildExit", "ProcessSupervisor", "SupervisorConfig", "SupervisorResult")

_TERMINATE_POLL: Final[timedelta] = timedelta(milliseconds=20)


@dataclass(frozen=True, slots=True)
class ChildExit:
    """Raw child termination status; the caller classifies nonzero as transient/deterministic."""

    returncode: int


@dataclass(frozen=True, slots=True)
class SupervisorConfig:
    """Bounded timing knobs for supervision."""

    interval: timedelta
    deadline: timedelta
    grace: timedelta
    provider_timeout: timedelta
    max_staleness: timedelta


@dataclass(frozen=True, slots=True)
class SupervisorResult:
    """Typed outcome of one supervised run, available only after cleanup."""

    outcome: NonScoredOutcome | ChildExit
    samples: tuple[HardChannel, ...]
    diagnostics_series: tuple[Diagnostics, ...]
    peak_used: Bytes | None
    started_at: datetime
    ended_at: datetime
    launched: bool
    terminated_group: bool
    process_group_pid: int | None = None
    escalated_to_sigkill: bool = False


@dataclass
class _RunState:
    """Mutable accumulator for one supervised run (single-use per call)."""

    samples: list[HardChannel] = field(default_factory=list)
    diagnostics: list[Diagnostics] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    proc: subprocess.Popen[bytes] | None = None
    terminated_group: bool = False
    escalated_to_sigkill: bool = False


@final
class ProcessSupervisor:
    """Launches a child in a dedicated session/group and supervises it fail-closed."""

    def run(
        self,
        command: list[str],
        *,
        provider: HardChannelProvider,
        config: SupervisorConfig,
        cancel: threading.Event | None = None,
    ) -> SupervisorResult:
        """Supervise ``command`` against the hard channel; never leaves an orphan.

        When ``cancel`` is provided and set by the caller, the supervisor terminates
        the process group (SIGTERM -> bounded grace -> SIGKILL -> reap) and returns
        a :class:`ChildExit` with the signal exit code, letting a long-lived server
        be explicitly stopped after successful workloads.
        """
        state = _RunState()
        outcome: NonScoredOutcome | ChildExit
        try:
            block = self._preflight(provider, config)
            if block is not None:
                return self._finish(block, state)
            state.proc = subprocess.Popen(command, start_new_session=True)
            outcome = self._loop(state.proc, provider, config, state, cancel)
        except KeyboardInterrupt:
            outcome = NonScoredOutcome.CANCELLED

        if state.proc is not None:
            if state.proc.poll() is None:
                state.escalated_to_sigkill = self._terminate_group(state.proc, config.grace)
                state.terminated_group = True
            else:
                self._reap(state.proc)
            pgid = state.proc.pid
            group_gone = False
            cleanup_deadline = time.monotonic() + 2.0
            while time.monotonic() < cleanup_deadline:
                try:
                    os.killpg(pgid, 0)
                except ProcessLookupError:
                    group_gone = True
                    break
                except PermissionError:
                    break
                time.sleep(0.05)
            if not group_gone:
                outcome = NonScoredOutcome.CLEANUP_FAILURE
        return self._finish(outcome, state)

    def _preflight(
        self, provider: HardChannelProvider, config: SupervisorConfig
    ) -> NonScoredOutcome | None:
        """Block launch on breach/stale/missing hard telemetry; ``None`` means proceed."""
        try:
            sample = provider.sample()
        except TelemetryLossError:
            return NonScoredOutcome.TELEMETRY_LOSS
        if is_breach(sample):
            return NonScoredOutcome.RESOURCE_INFEASIBLE
        if is_stale(sample, now=datetime.now(UTC), max_staleness=config.max_staleness):
            return NonScoredOutcome.TELEMETRY_LOSS
        return None

    def _loop(
        self,
        proc: subprocess.Popen[bytes],
        provider: HardChannelProvider,
        config: SupervisorConfig,
        state: _RunState,
        cancel: threading.Event | None = None,
    ) -> NonScoredOutcome | ChildExit:
        """Sample until the child exits, a fail-closed condition fires, or cancel is set."""
        deadline = time.monotonic() + config.deadline.total_seconds()
        while True:
            if cancel is not None and cancel.is_set():
                state.escalated_to_sigkill = self._terminate_group(proc, config.grace)
                state.terminated_group = True
                return ChildExit(proc.returncode)
            try:
                sample = provider.sample()
            except TelemetryLossError:
                return NonScoredOutcome.TELEMETRY_LOSS
            if is_breach(sample):
                state.samples.append(sample)
                state.diagnostics.append(provider.diagnostics())
                return NonScoredOutcome.RESOURCE_INFEASIBLE
            if is_stale(sample, now=datetime.now(UTC), max_staleness=config.max_staleness):
                state.samples.append(sample)
                state.diagnostics.append(provider.diagnostics())
                return NonScoredOutcome.TELEMETRY_LOSS
            state.samples.append(sample)
            state.diagnostics.append(provider.diagnostics())
            if proc.poll() is not None:
                return ChildExit(proc.returncode)
            if time.monotonic() >= deadline:
                return NonScoredOutcome.HANG
            time.sleep(config.interval.total_seconds())

    def _terminate_group(self, proc: subprocess.Popen[bytes], grace: timedelta) -> bool:
        """SIGTERM the group; escalate to SIGKILL after ``grace`` if still alive."""
        pgid = proc.pid
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            self._reap(proc)
            return False
        deadline = time.monotonic() + grace.total_seconds()
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(_TERMINATE_POLL.total_seconds())
        sigkill_needed = proc.poll() is None
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pgid, signal.SIGKILL)
        self._reap(proc)
        return sigkill_needed

    @staticmethod
    def _reap(proc: subprocess.Popen[bytes]) -> None:
        """Block until the child is reaped (it is already dead)."""
        _ = proc.wait()

    def _finish(self, outcome: NonScoredOutcome | ChildExit, state: _RunState) -> SupervisorResult:
        """Build the immutable typed result after cleanup."""
        peak: Bytes | None = None
        if state.samples:
            peak = Bytes(max(int(s.used) for s in state.samples))
        launched = state.proc is not None
        return SupervisorResult(
            outcome=outcome,
            samples=tuple(state.samples),
            diagnostics_series=tuple(state.diagnostics),
            peak_used=peak,
            started_at=state.started_at,
            ended_at=datetime.now(UTC),
            launched=launched,
            terminated_group=state.terminated_group if launched else False,
            escalated_to_sigkill=state.escalated_to_sigkill,
            process_group_pid=state.proc.pid if state.proc is not None else None,
        )
