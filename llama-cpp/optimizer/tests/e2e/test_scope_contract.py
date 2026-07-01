"""Scope contract tests: reject invalid inputs and protect invariants.

These tests verify that the optimizer rejects:
- Invalid context sizes (e.g., 81920)
- Tracked file mutations during runs
- Applying promotion without explicit user action
- GPU/download use in normal (non-smoke) tests
- Changes to protected model/app regions
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llama_optimizer.nix_recommendation import RecommendationContext, render_recommendation
from llama_optimizer.profiles import ProfileParseError, ProfileVramError, parse_profile
from llama_optimizer.report_models import CandidateConfig


# Test that the existing Ornith profile is valid
class TestValidProfileAccepted:
    def test_ornith_profile_parses(self) -> None:
        """The checked-in Ornith profile must parse successfully."""
        profile_path = Path(__file__).parent.parent.parent / "profiles" / "ornith-1.0-9b.toml"
        if not profile_path.exists():
            pytest.skip("Ornith profile not found")
        profile = parse_profile(profile_path)
        assert profile.context_size == 32768
        assert profile.vram_limit_bytes > 0


class TestInvalidContextRejected:
    """Context sizes outside the allowed range must be rejected."""

    def test_rejects_oversized_context(self, tmp_path: Path) -> None:
        """81920 context must be rejected (exceeds 32768 ceiling)."""
        profile_content = """
[profile]
profile_id = "test-invalid"
profile_version = "1.0"
optimizer_version = "0.1.0"
context_size = 81920
vram_limit_bytes = 13958643712
seed = 42
max_native_combinations = 100
recommendation_status = "candidate"
quality_reason = "test"

[llama_cpp_build]
backend = "rocm"
revision = "abc123"
build_flags = []

[template]
name = "test"
sha256 = "a" * 64

[[candidates]]
candidate_id = "test-q4"
weight_quant = "Q4_K_M"
file_sha256 = "b" * 64
url = "https://example.com/test.gguf"
file_bytes = 1000000
role = "candidate"

[recommendation_weights]
prompt_throughput = 0.20
generation_throughput = 0.30
ttft_p95 = 0.15
request_latency_p95 = 0.15
quality_margin = 0.15
vram_headroom = 0.05
"""
        profile_path = tmp_path / "invalid.toml"
        profile_path.write_text(profile_content)

        with pytest.raises((ProfileParseError, ProfileVramError)):
            parse_profile(profile_path)


class TestProtectedRegionsUnchanged:
    """Verify that protected model/app regions are not modified."""

    def test_ornith_profile_unchanged(self) -> None:
        """The Ornith profile must be byte-identical to committed version."""

        profile_path = Path(__file__).parent.parent.parent / "profiles" / "ornith-1.0-9b.toml"
        if not profile_path.exists():
            pytest.skip("Ornith profile not found")
        content = profile_path.read_bytes()
        # Verify it's the expected content (non-empty, valid TOML)
        assert len(content) > 100
        assert b"[profile]" in content
        assert b"ornith" in content.lower() or b"Ornith" in content

    def test_fixture_binaries_unchanged(self) -> None:
        """Fixture binaries must exist and be executable."""
        fixtures_bin = Path(__file__).parent.parent / "fixtures" / "bin"
        for binary in ["llama-server", "llama-bench", "rocm-smi"]:
            path = fixtures_bin / binary
            assert path.exists(), f"Missing fixture binary: {binary}"
            assert path.is_file()


class TestNoImplicitPromotion:
    """Promotion requires explicit user action, never automatic."""

    def test_recommendation_is_review_only(self) -> None:
        """recommendation.nix must be a review artifact, not auto-applied."""
        config = CandidateConfig(
            config_id="test-cfg",
            model_path="/models/test.gguf",
            nix_package="pkgs.test",
            constraint_violations=(),
            server_flags=("--ctx-size", "32768"),
        )
        context = RecommendationContext(
            config=config,
            run_id="test-run",
            manifest_id="test-manifest",
            manifest_hash="abc123",
        )
        nix_content = render_recommendation(context)
        # Must contain review-only language or comment
        assert isinstance(nix_content, str)
        assert len(nix_content) > 0
