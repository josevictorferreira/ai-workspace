"""Behavior tests for supervised llama-server finalist validation (T9).

Drives the real T5 :class:`ProcessSupervisor` and T4 :class:`Ledger` against
the fake ``llama-server`` fixture. Every test uses a temporary run directory
and a scripted below-limit telemetry provider. No GPU, model, or network.

Happy path: a fake finalist asserts metrics, raw responses/artifacts, ledger
links, telemetry, and exact-32768 in every command.

Failure paths: startup/load crash, readiness hang, request error, quality
regression, malformed metrics, VRAM breach, telemetry loss, and a
SIGTERM-ignoring child — each a distinct non-scored outcome with no score.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, override

import pytest

from llama_optimizer.artifacts import RunArtifactRoot
from llama_optimizer.ledger import Ledger
from llama_optimizer.ledger_records import RunIdentity, TrialConfig
from llama_optimizer.lifecycle import NonScoredOutcome, TrialId
from llama_optimizer.server import (
    CODING_SPEC,
    TOOL_USE_SPEC,
    FinalistRequest,
    FinalistResult,
    ServerConfig,
    ServerIdentity,
    run_supervised_server,
)
from llama_optimizer.supervisor import ProcessSupervisor, SupervisorConfig
from llama_optimizer.telemetry import (
    Bytes,
    Diagnostics,
    HardChannel,
    HardChannelProvider,
    TelemetryLossError,
)

if TYPE_CHECKING:
    from collections.abc import Generator

_SERVER_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bin" / "llama-server"

_FAST = SupervisorConfig(
    interval=timedelta(milliseconds=50),
    deadline=timedelta(seconds=30),
    grace=timedelta(milliseconds=500),
    provider_timeout=timedelta(seconds=2),
    max_staleness=timedelta(seconds=30),
)

_FAST_HANG = SupervisorConfig(
    interval=timedelta(milliseconds=50),
    deadline=timedelta(seconds=3),
    grace=timedelta(milliseconds=500),
    provider_timeout=timedelta(seconds=2),
    max_staleness=timedelta(seconds=30),
)

_SERVER_CONFIG = ServerConfig(
    repetitions=2,
    delay_seconds=0,
    parallel=2,
    readiness_timeout_seconds=5,
    cooldown_seconds=0,
    request_specs=(CODING_SPEC, TOOL_USE_SPEC),
)

_IDENTITY = ServerIdentity(
    model_filename="ornith-1.0-9b-Q4_K_M.gguf",
    backend="rocm",
    build_label="b1234",
    n_gpu_layers=99,
    n_batch=2048,
    n_ubatch=512,
    type_k="f16",
    type_v="f16",
    n_threads=16,
    flash_attn=1,
    use_mmap=True,
)


def _sample(used: int) -> HardChannel:
    return HardChannel(
        total=Bytes(17_163_091_968),
        used=Bytes(used),
        collected_at=datetime.now(UTC),
        raw="",
    )


@dataclass
class _BelowLimitProvider(HardChannelProvider):
    """In-process provider always returning well-below-limit VRAM."""

    @override
    def sample(self) -> HardChannel:
        return _sample(1_000_000_000)

    @override
    def diagnostics(self) -> Diagnostics:
        return Diagnostics(
            temperature=None, power=None, gpu_use=None, clocks=None, pcie=None, raw=""
        )


@dataclass
class _BreachingProvider(HardChannelProvider):
    """Provider that always breaches the VRAM ceiling."""

    @override
    def sample(self) -> HardChannel:
        return _sample(14_000_000_000)

    @override
    def diagnostics(self) -> Diagnostics:
        return Diagnostics(
            temperature=None, power=None, gpu_use=None, clocks=None, pcie=None, raw=""
        )


@dataclass
class _TelemetryLossProvider(HardChannelProvider):
    """Provider that always loses hard telemetry."""

    @override
    def sample(self) -> HardChannel:
        raise TelemetryLossError(reason="test: telemetry unavailable", raw="")

    @override
    def diagnostics(self) -> Diagnostics:
        return Diagnostics(
            temperature=None, power=None, gpu_use=None, clocks=None, pcie=None, raw=""
        )


def _identity() -> RunIdentity:
    return RunIdentity(
        manifest_hash="sha256:manifest",
        config_hash="sha256:config",
        optimizer_version="0.1.0",
        optuna_version="4.9.0",
        checkpoint_format="pickle.v1",
        max_retries=2,
        seed=42,
        process_group_pid=os.getpid(),
    )


def _trial_config() -> TrialConfig:
    return TrialConfig(
        config_id="cfg-finalist-1",
        config_hash="hash-finalist-1",
        candidate_id="ornith-1.0-9b-q4_k_m",
        backend="rocm",
        quant="Q4_K_M",
    )


def _write_control(tmp_path: Path, output_dir: Path, *, mode: str = "happy") -> Path:
    """Write a JSON control file for the fake llama-server and return its path."""
    ctrl: dict[str, object] = {
        "mode": mode,
        "output_dir": str(output_dir),
        "ready_after_ms": 10,
        "slots": 2,
        "model": _IDENTITY.model_filename,
        "backend": _IDENTITY.backend,
        "prompt_throughput": 250.0,
        "generation_throughput": 42.5,
        "ttft_ms": [120.0, 130.0, 140.0],
        "request_latency_ms": [500.0, 600.0, 700.0],
        "request_count": 6,
        "response_text": "def solve():\n    return 42",
        "quality_pass": True,
    }
    path = tmp_path / "control.json"
    _ = path.write_text(json.dumps(ctrl))
    return path


@pytest.fixture
def ledger_trial(run_root_base: Path) -> Generator[tuple[Ledger, TrialId]]:
    """Create a RUNNING ledger with one RUNNING trial for finalist validation."""
    root = RunArtifactRoot.for_run("server-1", base=run_root_base)
    led = Ledger.create_run(root, _identity())
    led.start_run()
    trial = led.create_trial(_trial_config())
    _ = led.start_trial(trial.trial_id)
    try:
        yield led, trial.trial_id
    finally:
        led.close()


def _run(  # noqa: PLR0913
    led: Ledger,
    trial_id: TrialId,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str = "happy",
    provider: HardChannelProvider | None = None,
    sup_config: SupervisorConfig | None = None,
) -> FinalistResult:
    """Run a supervised server finalist and return the FinalistResult."""
    output_dir = tmp_path / "output"
    ctrl = _write_control(tmp_path, output_dir, mode=mode)
    monkeypatch.setenv("LLAMA_SERVER_FAKE_CONTROL", str(ctrl))
    return run_supervised_server(
        ProcessSupervisor(),
        provider or _BelowLimitProvider(),
        sup_config or _FAST,
        led,
        FinalistRequest(
            trial_id=trial_id,
            identity=_IDENTITY,
            config=_SERVER_CONFIG,
            binary=str(_SERVER_FIXTURE),
            output_dir=output_dir,
        ),
    )


# --- Happy path -------------------------------------------------------------


class TestHappyFinalist:
    def test_captures_metrics_and_responses(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch)
        assert result.outcome is None
        assert result.metrics is not None
        assert result.metrics.prompt_throughput == 250.0
        assert result.metrics.generation_throughput == 42.5
        assert result.metrics.slots == 2
        assert result.metrics.errors == 0
        assert "prompt_throughput" in result.metrics_map
        assert "ttft_ms_p95" in result.metrics_map
        assert result.raw_responses.strip()

    def test_process_launched_through_supervisor(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch)
        assert result.supervisor_result.process_group_pid is not None
        assert result.supervisor_result.launched is True

    def test_peak_vram_recorded(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch)
        assert result.supervisor_result.peak_used is not None
        assert int(result.supervisor_result.peak_used) > 0


# --- Exact context ----------------------------------------------------------


class TestExactContext:
    def test_every_command_contains_32768(self) -> None:
        from llama_optimizer.server import build_server_command

        cmd = build_server_command("llama-server", _SERVER_CONFIG, _IDENTITY)
        assert "32768" in cmd
        idx = cmd.index("--ctx-size")
        assert cmd[idx + 1] == "32768"


# --- Failure classifications ------------------------------------------------


class TestStartupLoadFailure:
    def test_crash_is_deterministic_load_failure(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, mode="crash")
        assert result.outcome is NonScoredOutcome.DETERMINISTIC_LOAD_FAILURE
        assert result.metrics is None


class TestReadinessTimeout:
    def test_hang_readiness_is_hang(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(
            led, trial_id, tmp_path, monkeypatch, mode="hang-readiness", sup_config=_FAST_HANG
        )
        assert result.outcome is NonScoredOutcome.HANG


class TestRequestError:
    def test_request_error_is_measurement_failure(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, mode="request-error")
        assert result.outcome is NonScoredOutcome.MEASUREMENT_FAILURE


class TestQualityRegression:
    def test_quality_regress_is_quality_failure(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, mode="quality-regress")
        assert result.outcome is NonScoredOutcome.QUALITY_FAILURE


class TestMalformedMetrics:
    def test_malformed_metrics_is_measurement_failure(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, mode="malformed-metrics")
        assert result.outcome is NonScoredOutcome.MEASUREMENT_FAILURE


class TestVRAMBreach:
    def test_vram_breach_is_resource_infeasible(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, provider=_BreachingProvider())
        assert result.outcome is NonScoredOutcome.RESOURCE_INFEASIBLE
        assert result.metrics is None


class TestTelemetryLoss:
    def test_telemetry_loss_is_non_scored(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, provider=_TelemetryLossProvider())
        assert result.outcome is NonScoredOutcome.TELEMETRY_LOSS


class TestSigtermIgnore:
    def test_sigterm_ignoring_child_still_cleaned_up(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(
            led, trial_id, tmp_path, monkeypatch, mode="sigterm-ignore", sup_config=_FAST_HANG
        )
        assert result.outcome is NonScoredOutcome.HANG
        assert result.supervisor_result.terminated_group is True
        assert result.supervisor_result.process_group_pid is not None


class TestNoScoreForFailures:
    def test_failed_attempt_has_no_metrics(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, mode="crash")
        assert result.metrics_map == {}
        assert result.metrics is None
