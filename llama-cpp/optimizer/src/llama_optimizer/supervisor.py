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
from typing import Final, final

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


@dataclass
class _RunState:
    """Mutable accumulator for one supervised run (single-use per call)."""

    samples: list[HardChannel] = field(default_factory=list)
    diagnostics: list[Diagnostics] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    proc: subprocess.Popen[bytes] | None = None
    terminated_group: bool = False


@final
class ProcessSupervisor:
    """Launches a child in a dedicated session/group and supervises it fail-closed."""

    def run(
        self,
        command: list[str],
        *,
        provider: HardChannelProvider,
        config: SupervisorConfig,
    ) -> SupervisorResult:
        """Supervise ``command`` against the hard channel; never leaves an orphan."""
        state = _RunState()
        outcome: NonScoredOutcome | ChildExit
        try:
            block = self._preflight(provider, config)
            if block is not None:
                return self._finish(block, state)
            state.proc = subprocess.Popen(command, start_new_session=True)
            outcome = self._loop(state.proc, provider, config, state)
        except KeyboardInterrupt:
            outcome = NonScoredOutcome.CANCELLED

        if state.proc is not None and state.proc.poll() is None:
            self._terminate_group(state.proc, config.grace)
            state.terminated_group = True
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
    ) -> NonScoredOutcome | ChildExit:
        """Sample the hard channel until the child exits or a fail-closed condition fires."""
        deadline = time.monotonic() + config.deadline.total_seconds()
        while True:
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

    def _terminate_group(self, proc: subprocess.Popen[bytes], grace: timedelta) -> None:
        """SIGTERM the group, escalate to SIGKILL after ``grace``, then reap the child."""
        pgid = proc.pid
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            self._reap(proc)
            return
        deadline = time.monotonic() + grace.total_seconds()
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(_TERMINATE_POLL.total_seconds())
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pgid, signal.SIGKILL)
        self._reap(proc)

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
            process_group_pid=state.proc.pid if state.proc is not None else None,
        )
