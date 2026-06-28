"""Behavior tests for fail-closed process supervision (T5).

Drives the supervisor against REAL child subprocesses launched in dedicated
process sessions/groups, with a deterministic in-process telemetry provider.
Every failure class must terminate and reap the whole child group, leave no
surviving child/grandchild, and return the exact T4 outcome vocabulary:

  breach                        -> resource-infeasible
  missing/malformed/stale hard  -> telemetry-loss
  deadline                      -> hang
  parent interruption           -> cancelled
  nonzero child status          -> caller-classified ChildExit (not auto-scored)

An independent sentinel process (separate session, NOT launched by the
supervisor) must survive every cleanup. No GPU, model, or network is required.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, override

import pytest

from llama_optimizer.lifecycle import NonScoredOutcome
from llama_optimizer.supervisor import (
    ChildExit,
    ProcessSupervisor,
    SupervisorConfig,
)
from llama_optimizer.telemetry import (
    VRAM_CEILING_BYTES,
    Bytes,
    Diagnostics,
    HardChannel,
    HardChannelProvider,
    TelemetryLossError,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence
    from pathlib import Path
    from typing import Protocol

    class _HasPid(Protocol):
        pid: int


_CEILING = int(VRAM_CEILING_BYTES)
_FAST = SupervisorConfig(
    interval=timedelta(milliseconds=20),
    deadline=timedelta(seconds=30),
    grace=timedelta(milliseconds=400),
    provider_timeout=timedelta(seconds=2),
    max_staleness=timedelta(seconds=30),
)
_SHORT = SupervisorConfig(
    interval=timedelta(milliseconds=20),
    deadline=timedelta(milliseconds=400),
    grace=timedelta(milliseconds=400),
    provider_timeout=timedelta(seconds=2),
    max_staleness=timedelta(seconds=30),
)
_STALE_CFG = SupervisorConfig(
    interval=timedelta(milliseconds=20),
    deadline=timedelta(seconds=2),
    grace=timedelta(milliseconds=400),
    provider_timeout=timedelta(seconds=2),
    max_staleness=timedelta(milliseconds=50),
)


def _sample(used: int, *, collected_at: datetime | None = None) -> HardChannel:
    return HardChannel(
        total=Bytes(17_163_091_968),
        used=Bytes(used),
        collected_at=collected_at if collected_at is not None else datetime.now(UTC),
        raw="",
    )


@dataclass
class _ScriptedProvider(HardChannelProvider):
    """In-process provider returning scripted samples or raising.

    Call 1 is the preflight reading; calls >= 2 consume ``samples`` in order.
    ``raise_on_call`` (1-based) raises ``error`` instead of returning.
    """

    preflight: HardChannel = field(default_factory=lambda: _sample(1))
    samples: list[HardChannel] = field(default_factory=list)
    error: BaseException | None = None
    raise_on_call: int = 0
    _calls: int = field(default=0, init=False, repr=False)

    @override
    def sample(self) -> HardChannel:
        self._calls += 1
        if self.error is not None and self._calls == self.raise_on_call:
            raise self.error
        if self._calls == 1:
            return self.preflight
        idx = self._calls - 2
        if idx < len(self.samples):
            return self.samples[idx]
        return self.samples[-1] if self.samples else self.preflight

    @override
    def diagnostics(self) -> Diagnostics:
        return Diagnostics(
            temperature=None, power=None, gpu_use=None, clocks=None, pcie=None, raw=""
        )


_GRANDCHILD_SCRIPT = (
    "import os, signal, sys, time\n"
    "pid = os.fork()\n"
    "if pid == 0:\n"
    "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "    time.sleep(120)\n"
    "    sys.exit(0)\n"
    "with open(sys.argv[1], 'w') as f:\n"
    "    f.write(str(pid))\n"
    "os.waitpid(pid, 0)\n"
    "sys.exit(0)\n"
)


def _python(args: Sequence[str]) -> list[str]:
    return [sys.executable, *args]


@pytest.fixture
def sentinel() -> Generator[_HasPid]:
    """Given an independent sentinel process in its own session."""
    proc = subprocess.Popen(_python(["-c", "import time; time.sleep(30)"]), start_new_session=True)
    try:
        yield proc
    finally:
        proc.terminate()
        try:
            _ = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            _ = proc.wait(timeout=5)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_gone(pid: int, *, timeout: float = 5.0) -> None:
    """Bounded wait (not a fixed sleep) for ``pid`` to disappear."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _alive(pid):
            return
        time.sleep(0.01)
    pytest.fail(f"pid {pid} still alive after bounded wait")


# --- Successful below-limit run --------------------------------------------


class TestSuccessfulBelowLimit:
    def test_records_series_peak_and_succeeded(self) -> None:
        # Given a child that exits 0 and a below-limit provider.
        supervisor = ProcessSupervisor()
        provider = _ScriptedProvider(
            preflight=_sample(100),
            samples=[_sample(200), _sample(150)],
        )
        command = _python(["-c", "import sys; sys.exit(0)"])
        # When supervising.
        result = supervisor.run(command, provider=provider, config=_FAST)
        # Then the outcome is a clean ChildExit(0) (caller confirms success).
        assert isinstance(result.outcome, ChildExit)
        assert result.outcome.returncode == 0
        assert result.launched is True
        assert result.terminated_group is False
        assert result.samples  # timestamped series recorded
        assert result.peak_used is not None
        assert int(result.peak_used) <= _CEILING
        for sample in result.samples:
            assert sample.collected_at.tzinfo is not None


# --- Preflight blocking -----------------------------------------------------


class TestPreflightBlocking:
    def test_exact_limit_blocks_launch(self) -> None:
        # Given a preflight sample exactly at the ceiling.
        supervisor = ProcessSupervisor()
        provider = _ScriptedProvider(preflight=_sample(_CEILING))
        command = _python(["-c", "import sys; sys.exit(0)"])
        # When supervising.
        result = supervisor.run(command, provider=provider, config=_FAST)
        # Then no child launches and the outcome is resource-infeasible.
        assert result.outcome is NonScoredOutcome.RESOURCE_INFEASIBLE
        assert result.launched is False
        assert result.terminated_group is False

    def test_one_byte_over_blocks_launch(self) -> None:
        # Given a preflight sample one byte over the ceiling.
        supervisor = ProcessSupervisor()
        provider = _ScriptedProvider(preflight=_sample(_CEILING + 1))
        command = _python(["-c", "import sys; sys.exit(0)"])
        # When supervising.
        result = supervisor.run(command, provider=provider, config=_FAST)
        # Then launch is blocked as resource-infeasible.
        assert result.outcome is NonScoredOutcome.RESOURCE_INFEASIBLE
        assert result.launched is False


# --- Sampled breach mid-run ------------------------------------------------


class TestSampledBreach:
    def test_kills_group_and_reaps_on_breach(self, sentinel: _HasPid) -> None:
        # Given a long-running child and a provider that breaches mid-run.
        supervisor = ProcessSupervisor()
        provider = _ScriptedProvider(
            preflight=_sample(100),
            samples=[_sample(100), _sample(_CEILING + 1)],
        )
        command = _python(["-c", "import time; time.sleep(120)"])
        # When supervising.
        result = supervisor.run(command, provider=provider, config=_FAST)
        # Then the outcome is resource-infeasible and the group was terminated+reaped.
        assert result.outcome is NonScoredOutcome.RESOURCE_INFEASIBLE
        assert result.launched is True
        assert result.terminated_group is True
        # And the unrelated sentinel survives.
        assert _alive(sentinel.pid)


# --- Telemetry loss classes ------------------------------------------------


class TestTelemetryLoss:
    def test_provider_malformed_raises_is_telemetry_loss(self, sentinel: _HasPid) -> None:
        # Given a provider that raises telemetry-loss mid-run.
        supervisor = ProcessSupervisor()
        provider = _ScriptedProvider(
            preflight=_sample(100),
            samples=[_sample(100)],
            raise_on_call=2,
            error=TelemetryLossError(reason="malformed", raw="bad"),
        )
        command = _python(["-c", "import time; time.sleep(120)"])
        # When supervising.
        result = supervisor.run(command, provider=provider, config=_FAST)
        # Then the outcome is telemetry-loss and the group was reaped.
        assert result.outcome is NonScoredOutcome.TELEMETRY_LOSS
        assert result.terminated_group is True
        assert _alive(sentinel.pid)

    def test_stale_sample_is_telemetry_loss(self, sentinel: _HasPid) -> None:
        # Given a provider returning a sample older than max_staleness.
        supervisor = ProcessSupervisor()
        stale_at = datetime.now(UTC) - timedelta(seconds=1)
        provider = _ScriptedProvider(
            preflight=_sample(100),
            samples=[_sample(100, collected_at=stale_at)],
        )
        command = _python(["-c", "import time; time.sleep(120)"])
        # When supervising with a tight max_staleness.
        result = supervisor.run(command, provider=provider, config=_STALE_CFG)
        # Then the outcome is telemetry-loss.
        assert result.outcome is NonScoredOutcome.TELEMETRY_LOSS
        assert result.terminated_group is True
        assert _alive(sentinel.pid)


# --- Deadline hang ----------------------------------------------------------


class TestDeadlineHang:
    def test_deadline_expiry_is_hang_and_reaps(self, sentinel: _HasPid) -> None:
        # Given a child that never exits and a short deadline.
        supervisor = ProcessSupervisor()
        provider = _ScriptedProvider(preflight=_sample(100), samples=[_sample(100)])
        command = _python(["-c", "import time; time.sleep(120)"])
        # When supervising with a short deadline.
        result = supervisor.run(command, provider=provider, config=_SHORT)
        # Then the outcome is hang and the group was terminated+reaped.
        assert result.outcome is NonScoredOutcome.HANG
        assert result.terminated_group is True
        assert _alive(sentinel.pid)


# --- Cancellation -----------------------------------------------------------


class TestCancellation:
    def test_keyboard_interrupt_is_cancelled_and_reaps(self, sentinel: _HasPid) -> None:
        # Given a provider that interrupts the parent during sampling.
        supervisor = ProcessSupervisor()
        provider = _ScriptedProvider(
            preflight=_sample(100),
            samples=[_sample(100)],
            raise_on_call=2,
            error=KeyboardInterrupt(),
        )
        command = _python(["-c", "import time; time.sleep(120)"])
        # When supervising.
        result = supervisor.run(command, provider=provider, config=_FAST)
        # Then the outcome is cancelled and the group was reaped.
        assert result.outcome is NonScoredOutcome.CANCELLED
        assert result.terminated_group is True
        assert _alive(sentinel.pid)


# --- Grandchild ignoring SIGTERM -------------------------------------------


class TestGrandchildEscalation:
    def test_sigterm_ignoring_grandchild_killed_and_reaped(
        self, tmp_path: Path, sentinel: _HasPid
    ) -> None:
        # Given a child that forks a SIGTERM-ignoring grandchild in the same group.
        grandchild_pid_file = tmp_path / "grandchild.pid"
        script = tmp_path / "tree.py"
        _ = script.write_text(_GRANDCHILD_SCRIPT)
        supervisor = ProcessSupervisor()
        provider = _ScriptedProvider(preflight=_sample(100), samples=[_sample(100)])
        command = _python([str(script), str(grandchild_pid_file)])
        # When the deadline fires and SIGTERM is ignored, SIGKILL escalates.
        result = supervisor.run(command, provider=provider, config=_SHORT)
        # Then the outcome is hang and both child and grandchild are gone.
        assert result.outcome is NonScoredOutcome.HANG
        assert result.terminated_group is True
        grandchild_pid = int(grandchild_pid_file.read_text())
        _wait_gone(grandchild_pid)
        assert _alive(sentinel.pid)


# --- Nonzero child status (caller classifies) ------------------------------


class TestNonzeroChild:
    def test_nonzero_child_returns_childexit_for_caller(self, sentinel: _HasPid) -> None:
        # Given a child that exits nonzero under the limit.
        supervisor = ProcessSupervisor()
        provider = _ScriptedProvider(preflight=_sample(100), samples=[_sample(100)])
        command = _python(["-c", "import sys; sys.exit(7)"])
        # When supervising.
        result = supervisor.run(command, provider=provider, config=_FAST)
        # Then the supervisor returns the raw ChildExit (caller classifies transient/deterministic).  # noqa: E501
        assert isinstance(result.outcome, ChildExit)
        assert result.outcome.returncode == 7
        assert result.terminated_group is False  # exited naturally
        assert _alive(sentinel.pid)


# --- Cleanup invariant ------------------------------------------------------


class TestCleanupInvariant:
    def test_no_surviving_child_after_failure(self, sentinel: _HasPid) -> None:
        # Given a long-running child that the supervisor must terminate.
        supervisor = ProcessSupervisor()
        provider = _ScriptedProvider(preflight=_sample(100), samples=[_sample(100)])
        command = _python(["-c", "import time; time.sleep(120)"])
        # When the deadline fires.
        result = supervisor.run(command, provider=provider, config=_SHORT)
        # Then the child process group is fully reaped (no orphan).
        assert result.terminated_group is True
        child_pid = result.process_group_pid
        assert child_pid is not None
        _wait_gone(child_pid)
        assert _alive(sentinel.pid)
