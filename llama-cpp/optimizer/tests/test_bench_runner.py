"""Behavior tests for supervised llama-bench screening (T6).

Drives the real T5 :class:`ProcessSupervisor` and T4 :class:`Ledger` against
the fake ``llama-bench`` fixture. Every test uses a temporary run directory and
a scripted below-limit telemetry provider. No GPU, model, or network required.

Happy path: a fake sweep with three repetitions asserts commands, sample
counts, means, ledger links, telemetry, and no score for failed cases.

Failure paths: malformed JSONL, wrong identity, missing samples, unsupported
flags, deterministic load failure, and transient failure (retry-eligible).
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
from llama_optimizer.bench import (
    DEFAULT_BENCH_CONFIG,
    BenchIdentity,
    BenchScreenRequest,
    BenchScreenResult,
    run_supervised_bench,
)
from llama_optimizer.ledger import Ledger
from llama_optimizer.ledger_records import RunIdentity, TrialConfig
from llama_optimizer.lifecycle import (
    RETRY_ELIGIBLE_OUTCOMES,
    NonScoredOutcome,
    TrialId,
    is_retry_eligible,
)
from llama_optimizer.supervisor import ProcessSupervisor, SupervisorConfig
from llama_optimizer.telemetry import (
    Bytes,
    Diagnostics,
    HardChannel,
    HardChannelProvider,
)

if TYPE_CHECKING:
    from collections.abc import Generator

_BENCH_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bin" / "llama-bench"

_FAST = SupervisorConfig(
    interval=timedelta(milliseconds=50),
    deadline=timedelta(seconds=30),
    grace=timedelta(milliseconds=500),
    provider_timeout=timedelta(seconds=2),
    max_staleness=timedelta(seconds=30),
)

_IDENTITY = BenchIdentity(
    model_filename="ornith-1.0-9b-Q4_K_M.gguf",
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
    """Provider that breaches after the first loop sample."""

    @override
    def sample(self) -> HardChannel:
        return _sample(14_000_000_000)

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
        config_id="cfg-screen-1",
        config_hash="hash-screen-1",
        candidate_id="ornith-1.0-9b-q4_k_m",
        backend="rocm",
        quant="Q4_K_M",
    )


def _write_control(tmp_path: Path, *, mode: str = "happy", transient_fail_count: int = 0) -> Path:
    """Write a JSON control file for the fake llama-bench and return its path."""
    ctrl: dict[str, object] = {
        "mode": mode,
        "model": _IDENTITY.model_filename,
        "n_gpu_layers": _IDENTITY.n_gpu_layers,
        "n_batch": _IDENTITY.n_batch,
        "n_ubatch": _IDENTITY.n_ubatch,
        "type_k": _IDENTITY.type_k,
        "type_v": _IDENTITY.type_v,
        "n_threads": _IDENTITY.n_threads,
        "flash_attn": _IDENTITY.flash_attn,
        "use_mmap": 1,
        "build": 1234,
        "pp_avg_ts": 250.0,
        "tg_avg_ts": 42.5,
        "pp_samples_ts": [248.0, 250.0, 252.0],
        "tg_samples_ts": [41.5, 42.5, 43.5],
        "pp_samples_ns": [4_000_000, 4_032_000, 4_000_000],
        "tg_samples_ns": [3_000_000, 3_000_000, 2_990_000],
    }
    if transient_fail_count:
        ctrl["transient_fail_count"] = transient_fail_count
    path = tmp_path / "control.json"
    _ = path.write_text(json.dumps(ctrl))
    return path


@pytest.fixture
def ledger_trial(run_root_base: Path) -> Generator[tuple[Ledger, TrialId]]:
    """Create a RUNNING ledger with one RUNNING trial for bench screening."""
    root = RunArtifactRoot.for_run("bench-1", base=run_root_base)
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
    transient_fail_count: int = 0,
) -> BenchScreenResult:
    """Run a supervised bench and return the BenchScreenResult."""
    ctrl = _write_control(tmp_path, mode=mode, transient_fail_count=transient_fail_count)
    monkeypatch.setenv("LLAMA_BENCH_FAKE_CONTROL", str(ctrl))
    if transient_fail_count:
        monkeypatch.setenv("LLAMA_BENCH_FAKE_STATE", str(tmp_path / "state.txt"))
    return run_supervised_bench(
        ProcessSupervisor(),
        provider or _BelowLimitProvider(),
        _FAST,
        led,
        BenchScreenRequest(
            trial_id=trial_id,
            bench_config=DEFAULT_BENCH_CONFIG,
            identity=_IDENTITY,
            binary=str(_BENCH_FIXTURE),
            output_dir=tmp_path / "output",
        ),
    )


# --- Happy path -------------------------------------------------------------


class TestHappyScreening:
    def test_records_metrics_artifacts_and_raw_samples(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch)
        assert result.outcome is None
        assert result.result is not None
        parsed = result.result
        assert len(parsed.measurements) == 2
        pp = next(m for m in parsed.measurements if m.workload_name == "pp512")
        assert pp.avg_ts == 250.0
        assert len(pp.samples) == 3
        assert pp.samples[0].ns == 4_000_000
        tg = next(m for m in parsed.measurements if m.workload_name == "tg128")
        assert tg.avg_ts == 42.5
        assert "pp512_avg_ts" in result.metrics
        assert "tg128_avg_ts" in result.metrics
        assert result.raw_jsonl.strip()


class TestSupervisorRouting:
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


class TestTelemetryRecording:
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


class TestResourceBreach:
    def test_vram_breach_is_resource_infeasible(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, provider=_BreachingProvider())
        assert result.outcome is NonScoredOutcome.RESOURCE_INFEASIBLE
        assert result.result is None


# --- Failure classifications ------------------------------------------------


class TestUnsupportedConfig:
    def test_unsupported_is_not_scored(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, mode="unsupported")
        assert result.outcome is NonScoredOutcome.UNSUPPORTED
        assert result.result is None
        assert result.metrics == {}


class TestDeterministicLoadFailure:
    def test_load_fail_is_deterministic(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, mode="load-fail")
        assert result.outcome is NonScoredOutcome.DETERMINISTIC_LOAD_FAILURE
        assert result.result is None


class TestTransientFailure:
    def test_transient_is_retry_eligible(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(
            led, trial_id, tmp_path, monkeypatch, mode="transient", transient_fail_count=1
        )
        assert result.outcome is NonScoredOutcome.TRANSIENT_FAILURE
        assert is_retry_eligible(NonScoredOutcome.TRANSIENT_FAILURE)
        assert NonScoredOutcome.TRANSIENT_FAILURE in RETRY_ELIGIBLE_OUTCOMES


class TestMeasurementFailure:
    def test_malformed_jsonl(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, mode="malformed")
        assert result.outcome is NonScoredOutcome.MEASUREMENT_FAILURE
        assert result.result is None

    def test_wrong_identity(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, mode="wrong-identity")
        assert result.outcome is NonScoredOutcome.MEASUREMENT_FAILURE
        assert result.result is None

    def test_missing_samples(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, mode="missing-samples")
        assert result.outcome is NonScoredOutcome.MEASUREMENT_FAILURE


class TestNoScoreForFailures:
    def test_failed_attempt_has_no_metrics(
        self,
        ledger_trial: tuple[Ledger, TrialId],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        led, trial_id = ledger_trial
        result = _run(led, trial_id, tmp_path, monkeypatch, mode="unsupported")
        assert result.metrics == {}
        assert result.result is None
