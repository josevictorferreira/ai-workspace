"""Deterministic report, Pareto, and balanced-selection tests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from llama_optimizer.reports import (
    CandidateConfig,
    MetricDirection,
    MetricSpec,
    ReportMetadata,
    ReportRequest,
    ReportWeightError,
    generate_report,
    write_reports,
)

if TYPE_CHECKING:
    from pathlib import Path

    from llama_optimizer.ledger_dump import AttemptDump, LedgerDump, TelemetrySample, TrialDump
    from llama_optimizer.report_models import ReportCandidate, ReportResult

_METRICS: tuple[MetricSpec, ...] = (
    MetricSpec("prompt_throughput", MetricDirection.BENEFIT, 0.20),
    MetricSpec("generation_throughput", MetricDirection.BENEFIT, 0.30),
    MetricSpec("ttft_p95", MetricDirection.COST, 0.15),
    MetricSpec("request_latency_p95", MetricDirection.COST, 0.15),
    MetricSpec("quality_margin", MetricDirection.BENEFIT, 0.15),
    MetricSpec("vram_headroom", MetricDirection.BENEFIT, 0.05),
)

# The _KEYS mapping in reports.py translates metric names to attempt dict keys.
# ttft_p95 -> ttft_ms_p95, request_latency_p95 -> request_latency_ms_p95
_METRIC_VALUES_FULL: dict[str, float] = {
    "prompt_throughput": 100.0,
    "generation_throughput": 50.0,
    "ttft_ms_p95": 200.0,
    "request_latency_ms_p95": 500.0,
    "quality_margin": 0.95,
    "vram_headroom": 2_000_000_000,
}

_TIMESTAMP = "2026-06-30T12:00:00+00:00"


def _attempt(
    attempt_id: str,
    metrics: dict[str, float],
    *,
    outcome: str | None = None,
    breached: bool = False,
) -> AttemptDump:
    phase = "succeeded" if outcome is None else "non_scored"
    telemetry: list[TelemetrySample] = [
        {
            "vram_used_bytes": 1_000,
            "peak_vram_bytes": 1_000,
            "breached": breached,
            "sampled_at": _TIMESTAMP,
        },
    ]
    return {
        "attempt_id": attempt_id,
        "attempt_number": 1,
        "phase": phase,
        "outcome": outcome,
        "process_group_pid": 12345,
        "parent_attempt_id": None,
        "started_at": _TIMESTAMP,
        "ended_at": _TIMESTAMP,
        "phase_deadline": None,
        "termination_reason": "completed",
        "metrics": metrics,
        "telemetry": telemetry,
        "artifacts": [],
    }


def _trial(
    trial_id: str,
    config_id: str,
    attempts: list[AttemptDump],
    *,
    outcome: str | None = None,
) -> TrialDump:
    return {
        "trial_id": trial_id,
        "config_id": config_id,
        "config_hash": f"hash-{config_id}",
        "candidate_id": f"cand-{config_id}",
        "backend": "rocm",
        "quant": "Q4_K_M",
        "phase": "succeeded",
        "outcome": outcome,
        "optuna_trial_number": 0,
        "committed_generation": None,
        "retry_parent_attempt_id": None,
        "termination_reason": "completed",
        "created_at": _TIMESTAMP,
        "updated_at": _TIMESTAMP,
        "attempts": attempts,
    }


def _ledger(trials: list[TrialDump]) -> LedgerDump:
    return {
        "run_id": "test-run",
        "schema_version": 1,
        "run": {"profile_path": "test.toml", "started_at": _TIMESTAMP},
        "trials": trials,
        "checkpoints": [],
    }


def _metadata() -> ReportMetadata:
    return ReportMetadata(
        manifest_id="test-manifest",
        manifest_hash="abc123",
        provenance=("test",),
        environment=("test",),
        resume_mode="fresh",
        drift_diagnostics=(),
        reproduction_commands=(),
    )


def _config(config_id: str, **overrides: object) -> CandidateConfig:
    defaults: dict[str, object] = {
        "config_id": config_id,
        "constraint_violations": (),
        "model_path": f"/models/{config_id}.gguf",
        "nix_package": f"pkgs.{config_id}",
        "server_flags": ("--ctx-size", "32768"),
    }
    defaults.update(overrides)
    return CandidateConfig(**defaults)  # pyright: ignore[reportArgumentType]


def _request(
    trials: list[TrialDump],
    configs: tuple[CandidateConfig, ...],
    *,
    metrics: tuple[MetricSpec, ...] = _METRICS,
) -> ReportRequest:
    return ReportRequest(
        ledger=_ledger(trials),
        metadata=_metadata(),
        configs=configs,
        metrics=metrics,
    )


def _generate_report(
    trials: list[TrialDump],
    configs: tuple[CandidateConfig, ...],
    *,
    metrics: tuple[MetricSpec, ...] = _METRICS,
) -> ReportResult:
    return generate_report(_request(trials, configs, metrics=metrics))


def _by_id(result: ReportResult) -> dict[str, ReportCandidate]:
    """Index frontier candidates by config_id."""
    return {c.config.config_id: c for c in result.frontier}


# --- Tests ------------------------------------------------------------------


class TestEmptyLedger:
    def test_no_trials_returns_empty_frontier(self) -> None:
        result = _generate_report([], (_config("a"),))
        assert result.frontier == ()
        assert result.selected is None

    def test_no_trials_emits_json_with_empty_frontier(self) -> None:
        result = _generate_report([], (_config("a"),))
        data = json.loads(result.json_text)
        assert data["frontier"] == []
        assert data["selected"] is None


class TestSingleCandidate:
    def test_single_feasible_candidate_is_selected(self) -> None:
        attempt = _attempt("att-1", _METRIC_VALUES_FULL)
        trial = _trial("t1", "cfg-a", [attempt])
        result = _generate_report([trial], (_config("cfg-a"),))

        assert len(result.frontier) == 1
        assert result.selected is not None
        assert result.selected.config.config_id == "cfg-a"

    def test_single_candidate_perfect_score(self) -> None:
        """A single candidate with only one data point gets normalized to 1.0."""
        attempt = _attempt("att-1", _METRIC_VALUES_FULL)
        trial = _trial("t1", "cfg-a", [attempt])
        result = _generate_report([trial], (_config("cfg-a"),))

        assert result.selected is not None
        assert result.selected.score == pytest.approx(1.0)


class TestParetoFrontier:
    def _two_candidates(self) -> tuple[list[TrialDump], tuple[CandidateConfig, ...]]:
        """Return two trials: A better throughput, B better latency."""
        att_a = _attempt(
            "att-a",
            {
                "prompt_throughput": 200.0,
                "generation_throughput": 100.0,
                "ttft_ms_p95": 300.0,
                "request_latency_ms_p95": 600.0,
                "quality_margin": 0.90,
                "vram_headroom": 1_000_000_000,
            },
        )
        att_b = _attempt(
            "att-b",
            {
                "prompt_throughput": 100.0,
                "generation_throughput": 50.0,
                "ttft_ms_p95": 100.0,
                "request_latency_ms_p95": 200.0,
                "quality_margin": 0.95,
                "vram_headroom": 3_000_000_000,
            },
        )
        trials = [
            _trial("t1", "cfg-a", [att_a]),
            _trial("t2", "cfg-b", [att_b]),
        ]
        configs = (_config("cfg-a"), _config("cfg-b"))
        return trials, configs

    def test_both_nondominated_candidates_on_frontier(self) -> None:
        trials, configs = self._two_candidates()
        result = _generate_report(trials, configs)
        frontier_ids = {c.config.config_id for c in result.frontier}
        assert frontier_ids == {"cfg-a", "cfg-b"}

    def test_balanced_score_selects_winner(self) -> None:
        trials, configs = self._two_candidates()
        result = _generate_report(trials, configs)
        assert result.selected is not None
        winner = result.selected
        assert winner.score is not None
        for other in result.frontier:
            if other.config.config_id != winner.config.config_id:
                assert winner.score >= other.score

    def test_dominated_candidate_excluded(self) -> None:
        """C is dominated by A on all metrics, should be excluded."""
        att_a = _attempt(
            "att-a",
            {
                "prompt_throughput": 200.0,
                "generation_throughput": 100.0,
                "ttft_ms_p95": 100.0,
                "request_latency_ms_p95": 200.0,
                "quality_margin": 0.95,
                "vram_headroom": 3_000_000_000,
            },
        )
        att_c = _attempt(
            "att-c",
            {
                "prompt_throughput": 50.0,
                "generation_throughput": 25.0,
                "ttft_ms_p95": 400.0,
                "request_latency_ms_p95": 800.0,
                "quality_margin": 0.80,
                "vram_headroom": 500_000_000,
            },
        )
        trials = [
            _trial("t1", "cfg-a", [att_a]),
            _trial("t3", "cfg-c", [att_c]),
        ]
        configs = (_config("cfg-a"), _config("cfg-c"))
        result = _generate_report(trials, configs)
        frontier_ids = {c.config.config_id for c in result.frontier}
        assert frontier_ids == {"cfg-a"}


class TestBalancedScoring:
    def test_contributions_sum_to_score(self) -> None:
        attempt = _attempt("att-1", _METRIC_VALUES_FULL)
        trial = _trial("t1", "cfg-a", [attempt])
        result = _generate_report([trial], (_config("cfg-a"),))

        assert result.selected is not None
        contributions = result.selected.contributions
        total = sum(c.contribution for c in contributions)
        assert total == pytest.approx(result.selected.score, abs=1e-9)

    def test_weights_sum_to_one(self) -> None:
        attempt = _attempt("att-1", _METRIC_VALUES_FULL)
        trial = _trial("t1", "cfg-a", [attempt])
        result = _generate_report([trial], (_config("cfg-a"),))

        assert result.selected is not None
        weights = [c.weight for c in result.selected.contributions]
        assert sum(weights) == pytest.approx(1.0, abs=1e-9)

    def test_normalized_values_between_zero_and_one(self) -> None:
        att_a = _attempt(
            "att-a",
            {
                "prompt_throughput": 100.0,
                "generation_throughput": 50.0,
                "ttft_ms_p95": 200.0,
                "request_latency_ms_p95": 500.0,
                "quality_margin": 0.95,
                "vram_headroom": 2_000_000_000,
            },
        )
        att_b = _attempt(
            "att-b",
            {
                "prompt_throughput": 200.0,
                "generation_throughput": 100.0,
                "ttft_ms_p95": 100.0,
                "request_latency_ms_p95": 200.0,
                "quality_margin": 0.80,
                "vram_headroom": 3_000_000_000,
            },
        )
        trials = [
            _trial("t1", "cfg-a", [att_a]),
            _trial("t2", "cfg-b", [att_b]),
        ]
        configs = (_config("cfg-a"), _config("cfg-b"))
        result = _generate_report(trials, configs)

        for candidate in result.frontier:
            for item in candidate.contributions:
                assert 0.0 <= item.normalized <= 1.0

    def test_benefit_metrics_higher_is_better(self) -> None:
        """For benefit metrics, higher raw value should get higher normalized."""
        att_a = _attempt(
            "att-a",
            {
                "prompt_throughput": 100.0,
                "generation_throughput": 50.0,
                "ttft_ms_p95": 200.0,
                "request_latency_ms_p95": 500.0,
                "quality_margin": 0.95,
                "vram_headroom": 2_000_000_000,
            },
        )
        att_b = _attempt(
            "att-b",
            {
                "prompt_throughput": 200.0,
                "generation_throughput": 100.0,
                "ttft_ms_p95": 100.0,
                "request_latency_ms_p95": 200.0,
                "quality_margin": 0.80,
                "vram_headroom": 3_000_000_000,
            },
        )
        trials = [
            _trial("t1", "cfg-a", [att_a]),
            _trial("t2", "cfg-b", [att_b]),
        ]
        configs = (_config("cfg-a"), _config("cfg-b"))
        result = _generate_report(trials, configs)
        by_id = _by_id(result)

        a_pt = next(
            iter([c for c in by_id["cfg-a"].contributions if c.name == "prompt_throughput"])
        )
        b_pt = next(
            iter([c for c in by_id["cfg-b"].contributions if c.name == "prompt_throughput"])
        )
        # B has higher raw throughput -> should have higher normalized
        assert b_pt.normalized >= a_pt.normalized

    def test_cost_metrics_lower_is_better(self) -> None:
        """For cost metrics, lower raw value should get higher normalized."""
        att_a = _attempt(
            "att-a",
            {
                "prompt_throughput": 100.0,
                "generation_throughput": 50.0,
                "ttft_ms_p95": 100.0,
                "request_latency_ms_p95": 200.0,
                "quality_margin": 0.95,
                "vram_headroom": 2_000_000_000,
            },
        )
        att_b = _attempt(
            "att-b",
            {
                "prompt_throughput": 200.0,
                "generation_throughput": 100.0,
                "ttft_ms_p95": 300.0,
                "request_latency_ms_p95": 600.0,
                "quality_margin": 0.80,
                "vram_headroom": 1_000_000_000,
            },
        )
        trials = [
            _trial("t1", "cfg-a", [att_a]),
            _trial("t2", "cfg-b", [att_b]),
        ]
        configs = (_config("cfg-a"), _config("cfg-b"))
        result = _generate_report(trials, configs)
        by_id = _by_id(result)

        a_ttft = next(iter([c for c in by_id["cfg-a"].contributions if c.name == "ttft_p95"]))
        b_ttft = next(iter([c for c in by_id["cfg-b"].contributions if c.name == "ttft_p95"]))
        # A has lower ttft (better for cost metric) -> should have higher normalized
        assert a_ttft.normalized >= b_ttft.normalized


class TestWeightValidation:
    def test_duplicate_metric_names_raise(self) -> None:
        malformed = (*_METRICS[:-1], MetricSpec("quality_margin", MetricDirection.BENEFIT, 0.05))
        with pytest.raises(ReportWeightError):
            _generate_report([], (), metrics=malformed)


class TestIncompleteCandidate:
    def test_candidate_missing_metrics_is_incomplete(self) -> None:
        # Attempt missing quality_margin and vram_headroom
        incomplete_values = {
            "prompt_throughput": 100.0,
            "generation_throughput": 50.0,
            "ttft_ms_p95": 200.0,
            "request_latency_ms_p95": 500.0,
        }
        attempt = _attempt("att-1", incomplete_values)
        trial = _trial("t1", "cfg-a", [attempt])
        result = _generate_report([trial], (_config("cfg-a"),))

        # Incomplete candidates appear in incomplete list, not frontier
        assert result.frontier == ()
        assert len(result.incomplete) >= 1


class TestFailedAttempt:
    def test_failed_attempt_excluded_from_scoring(self) -> None:
        failed = _attempt("att-fail", {}, outcome="server_crash")
        good = _attempt("att-good", _METRIC_VALUES_FULL)
        trial = _trial("t1", "cfg-a", [failed, good])
        result = _generate_report([trial], (_config("cfg-a"),))

        assert len(result.frontier) == 1
        assert result.selected is not None

    def test_breached_telemetry_excludes_attempt(self) -> None:
        """An attempt with breached=True in telemetry should be excluded."""
        breached = _attempt("att-breached", _METRIC_VALUES_FULL, breached=True)
        good = _attempt("att-good", _METRIC_VALUES_FULL)
        trial = _trial("t1", "cfg-a", [breached, good])
        result = _generate_report([trial], (_config("cfg-a"),))

        assert len(result.frontier) == 1
        assert result.selected is not None


class TestDeterministicOutput:
    def test_json_is_deterministic_across_calls(self) -> None:
        attempt = _attempt("att-1", _METRIC_VALUES_FULL)
        trial = _trial("t1", "cfg-a", [attempt])
        configs = (_config("cfg-a"),)

        r1 = _generate_report([trial], configs)
        r2 = _generate_report([trial], configs)
        assert r1.json_text == r2.json_text

    def test_json_is_valid_and_contains_expected_keys(self) -> None:
        attempt = _attempt("att-1", _METRIC_VALUES_FULL)
        trial = _trial("t1", "cfg-a", [attempt])
        result = _generate_report([trial], (_config("cfg-a"),))

        data = json.loads(result.json_text)
        assert "frontier" in data
        assert "selected" in data
        assert "metadata" in data

    def test_markdown_is_nonempty(self) -> None:
        attempt = _attempt("att-1", _METRIC_VALUES_FULL)
        trial = _trial("t1", "cfg-a", [attempt])
        result = _generate_report([trial], (_config("cfg-a"),))
        assert len(result.markdown_text) > 0


class TestWriteReports:
    def test_writes_json_and_markdown_files(self, tmp_path: Path) -> None:
        attempt = _attempt("att-1", _METRIC_VALUES_FULL)
        trial = _trial("t1", "cfg-a", [attempt])
        req = _request([trial], (_config("cfg-a"),))

        result = write_reports(req, tmp_path)

        json_path = tmp_path / "report.json"
        md_path = tmp_path / "report.md"
        assert json_path.exists()
        assert md_path.exists()

        data = json.loads(json_path.read_text())
        assert "frontier" in data

        md_content = md_path.read_text()
        assert len(md_content) > 0

        # Result should have the frontier
        assert len(result.frontier) == 1
        assert result.selected is not None
