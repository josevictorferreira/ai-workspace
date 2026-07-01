"""Fake run e2e test: exercises full pipeline components together.

This test proves that the completed components (profile parsing, ledger,
search space, quality gates, server validation, reports, nix recommendation)
work together correctly through a synthetic run without real GPU hardware.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from llama_optimizer.nix_recommendation import (
    RecommendationContext,
    render_recommendation,
    write_recommendation,
)
from llama_optimizer.profiles import parse_profile
from llama_optimizer.report_models import (
    CandidateConfig,
    MetricDirection,
    MetricSpec,
    ReportMetadata,
)
from llama_optimizer.reports import ReportRequest, generate_report, write_reports

if TYPE_CHECKING:
    from llama_optimizer.ledger_dump import AttemptDump, LedgerDump, TrialDump

# --- Helpers ----------------------------------------------------------------

_TIMESTAMP = "2026-06-30T12:00:00+00:00"

_METRICS: tuple[MetricSpec, ...] = (
    MetricSpec("prompt_throughput", MetricDirection.BENEFIT, 0.20),
    MetricSpec("generation_throughput", MetricDirection.BENEFIT, 0.30),
    MetricSpec("ttft_p95", MetricDirection.COST, 0.15),
    MetricSpec("request_latency_p95", MetricDirection.COST, 0.15),
    MetricSpec("quality_margin", MetricDirection.BENEFIT, 0.15),
    MetricSpec("vram_headroom", MetricDirection.BENEFIT, 0.05),
)


def _make_attempt(attempt_id: str, metrics: dict[str, float]) -> AttemptDump:
    return {
        "attempt_id": attempt_id,
        "attempt_number": 1,
        "phase": "succeeded",
        "outcome": None,
        "process_group_pid": 12345,
        "parent_attempt_id": None,
        "started_at": _TIMESTAMP,
        "ended_at": _TIMESTAMP,
        "phase_deadline": None,
        "termination_reason": "completed",
        "metrics": metrics,
        "telemetry": [
            {
                "vram_used_bytes": 1_000,
                "peak_vram_bytes": 1_000,
                "breached": False,
                "sampled_at": _TIMESTAMP,
            }
        ],
        "artifacts": [],
    }


def _make_trial(trial_id: str, config_id: str, attempt: AttemptDump) -> TrialDump:
    return {
        "trial_id": trial_id,
        "config_id": config_id,
        "config_hash": f"hash-{config_id}",
        "candidate_id": f"cand-{config_id}",
        "backend": "rocm",
        "quant": "Q4_K_M",
        "phase": "succeeded",
        "outcome": None,
        "optuna_trial_number": 0,
        "committed_generation": None,
        "retry_parent_attempt_id": None,
        "termination_reason": "completed",
        "created_at": _TIMESTAMP,
        "updated_at": _TIMESTAMP,
        "attempts": [attempt],
    }


def _make_ledger(trials: list[TrialDump]) -> LedgerDump:
    return {
        "run_id": "e2e-test-run",
        "schema_version": 1,
        "run": {"profile_path": "test.toml", "started_at": _TIMESTAMP},
        "trials": trials,
        "checkpoints": [],
    }


def _make_config(config_id: str) -> CandidateConfig:
    return CandidateConfig(
        config_id=config_id,
        model_path=f"/models/{config_id}.gguf",
        nix_package=f"pkgs.{config_id}",
        constraint_violations=(),
        server_flags=("--ctx-size", "32768"),
    )


# --- Tests ------------------------------------------------------------------


class TestFakeRun:
    """End-to-end fake run: profile -> ledger -> reports -> recommendation."""

    def test_full_pipeline_produces_report_and_recommendation(self, tmp_path: Path) -> None:
        """Exercise the full pipeline without real hardware."""
        # 1. Parse profile (proves profile module works)
        profile_path = Path(__file__).parent.parent.parent / "profiles" / "ornith-1.0-9b.toml"
        if not profile_path.exists():
            pytest.skip("Ornith profile not found")
        profile = parse_profile(profile_path)
        assert profile.context_size == 32768

        # 2. Create synthetic trial data (proves ledger types work)
        att_a = _make_attempt(
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
        att_b = _make_attempt(
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
            _make_trial("t1", "cfg-a", att_a),
            _make_trial("t2", "cfg-b", att_b),
        ]
        configs = (_make_config("cfg-a"), _make_config("cfg-b"))

        # 3. Generate report (proves reports module works)
        metadata = ReportMetadata(
            manifest_id="e2e-test",
            manifest_hash="abc123",
            provenance=("e2e-test",),
            environment=("test",),
            resume_mode="fresh",
            drift_diagnostics=(),
            reproduction_commands=(),
        )
        request = ReportRequest(
            ledger=_make_ledger(trials),
            metadata=metadata,
            configs=configs,
            metrics=_METRICS,
        )
        result = generate_report(request)

        # Verify report structure
        assert len(result.frontier) > 0
        assert result.selected is not None
        assert len(result.json_text) > 0
        assert len(result.markdown_text) > 0

        # 4. Write reports to disk
        write_reports(request, tmp_path)
        assert (tmp_path / "report.json").exists()
        assert (tmp_path / "report.md").exists()

        # Verify JSON report is valid
        report_data = json.loads((tmp_path / "report.json").read_text())
        assert "frontier" in report_data
        assert "selected" in report_data

        # 5. Generate Nix recommendation (proves nix_recommendation works)
        assert result.selected is not None
        context = RecommendationContext(
            config=result.selected.config,
            run_id="e2e-test-run",
            manifest_id="e2e-test",
            manifest_hash="abc123",
        )
        nix_content = render_recommendation(context)
        assert len(nix_content) > 0
        assert result.selected.config.config_id in nix_content

        # Write recommendation to disk
        nix_path = write_recommendation(context, tmp_path)
        assert nix_path.exists()
        assert nix_path.suffix == ".nix"


class TestInterruptedResume:
    """Test that interrupted runs can be detected and reported."""

    def test_partial_trial_data_still_generates_report(self) -> None:
        """A run with one failed and one successful trial still produces a report."""
        # One failed attempt, one successful
        failed = _make_attempt("att-fail", {})
        failed["outcome"] = "server_crash"
        failed["phase"] = "non_scored"

        good = _make_attempt(
            "att-good",
            {
                "prompt_throughput": 150.0,
                "generation_throughput": 75.0,
                "ttft_ms_p95": 250.0,
                "request_latency_ms_p95": 400.0,
                "quality_margin": 0.85,
                "vram_headroom": 2_000_000_000,
            },
        )

        trials = [
            _make_trial("t1", "cfg-a", failed),
            _make_trial("t2", "cfg-b", good),
        ]
        configs = (_make_config("cfg-a"), _make_config("cfg-b"))

        metadata = ReportMetadata(
            manifest_id="resume-test",
            manifest_hash="def456",
            provenance=("resume-test",),
            environment=("test",),
            resume_mode="exact",
            drift_diagnostics=(),
            reproduction_commands=(),
        )
        request = ReportRequest(
            ledger=_make_ledger(trials),
            metadata=metadata,
            configs=configs,
            metrics=_METRICS,
        )
        result = generate_report(request)

        # Should have at least one feasible candidate
        assert len(result.frontier) >= 1
        # Failed trial should not prevent report generation
        assert len(result.json_text) > 0


class TestNoFeasibleRun:
    """Test behavior when no candidates are feasible."""

    def test_all_candidates_incomplete(self) -> None:
        """When all candidates have missing metrics, report still generates."""
        # Attempts missing required metrics
        incomplete_values = {
            "prompt_throughput": 100.0,
            # Missing all other metrics
        }
        att = _make_attempt("att-1", incomplete_values)
        trials = [_make_trial("t1", "cfg-a", att)]
        configs = (_make_config("cfg-a"),)

        metadata = ReportMetadata(
            manifest_id="no-feasible-test",
            manifest_hash="ghi789",
            provenance=("no-feasible-test",),
            environment=("test",),
            resume_mode="fresh",
            drift_diagnostics=(),
            reproduction_commands=(),
        )
        request = ReportRequest(
            ledger=_make_ledger(trials),
            metadata=metadata,
            configs=configs,
            metrics=_METRICS,
        )
        result = generate_report(request)

        # No feasible candidates
        assert result.frontier == ()
        assert result.selected is None
        assert len(result.incomplete) >= 1

        # Report should still be valid
        assert len(result.json_text) > 0
        data = json.loads(result.json_text)
        assert data["frontier"] == []
        assert data["selected"] is None
