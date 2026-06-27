"""Behavior tests for the immutable TOML profile and normalized manifest (T2).

The profile is parsed exactly once at the boundary (``tomllib``) into frozen,
slotted typed dataclasses. The normalized manifest binds immutable provenance
and is emitted as canonical deterministic JSON. Semantic primitives stay
distinct (NewType); publisher SHA-256 is never confused with a Nix SRI hash.
"""

from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from typer.testing import CliRunner

from llama_optimizer.cli import app
from llama_optimizer.models import (
    Backend,
    CandidateRole,
    InvalidSha256Error,
    MutableUrlError,
    RecommendationStatus,
    WeightQuant,
)
from llama_optimizer.profiles import (
    DuplicateIdentityError,
    IneligibleWeightError,
    Manifest,
    MissingIdentityError,
    Profile,
    ProfileContextError,
    ProfileParseError,
    ProfileVramError,
    build_manifest,
    canonical_manifest_json,
    parse_profile,
    parse_profile_bytes,
)

ORNITH_PROFILE = "optimizer/profiles/ornith-1.0-9b.toml"

# Exact constants pinned by the plan.
REQUIRED_CONTEXT_SIZE = 32768
REQUIRED_VRAM_LIMIT_BYTES = 13_958_643_712
ORNITH_REVISION = "3296bc7a404871a72ac3f1903f561459c09b5c17"

# Exact publisher SHA-256 provenance (never Nix SRI).
PUBLISHER_SHA256 = {
    WeightQuant.Q4_K_M: "5720d1f671b4996481274fffe01868c3c36e87c135cc8538471cc7bd6087b106",
    WeightQuant.Q5_K_M: "d1b36095636c096b04ea09e798a7a378956f2fa9099340bd54add1954aaf149c",
    WeightQuant.Q6_K: "33b6f6a3e3f05078438e12df8a4b55c8acf78ceadcc639d2af1cf35a026e8387",
    WeightQuant.Q8_0: "d0e4bebaa8b3450c62090df1408f2ee5ccb2094f9c610ffde564a654483d4f37",
    WeightQuant.BF16: "27bc753487eed85539c3aef63dd602b79cd060401b928c9ff7d30d5556eca260",
}

# Exact balanced recommendation weights.
EXPECTED_WEIGHTS = {
    "prompt_throughput": 0.20,
    "generation_throughput": 0.30,
    "ttft_p95": 0.15,
    "request_latency_p95": 0.15,
    "quality_margin": 0.15,
    "vram_headroom": 0.05,
}

REQUIRED_QUANTS = {WeightQuant.Q4_K_M, WeightQuant.Q5_K_M, WeightQuant.Q6_K, WeightQuant.Q8_0}


def _sha256_over(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _ornith_profile_text() -> str:
    return Path(ORNITH_PROFILE).read_text()


class TestOrnithProfileParsing:
    def test_parses_checked_in_profile_into_immutable_profile(self) -> None:
        # Given the checked-in Ornith example profile.
        # When parsing it.
        profile = parse_profile(ORNITH_PROFILE)
        # Then the result is a frozen Profile with the exact pinned constants.
        assert isinstance(profile, Profile)
        assert profile.context_size == REQUIRED_CONTEXT_SIZE
        assert profile.vram_limit_bytes == REQUIRED_VRAM_LIMIT_BYTES
        assert profile.optimizer_version

    def test_profile_is_frozen(self) -> None:
        # Given the parsed profile.
        profile = parse_profile(ORNITH_PROFILE)
        # When attempting to mutate a field.
        # Then a FrozenInstanceError is raised.
        _field = "context_size"
        with pytest.raises(FrozenInstanceError):
            setattr(profile, _field, 1)

    def test_required_candidate_quants_present_with_publisher_hashes(self) -> None:
        # Given the Ornith profile.
        profile = parse_profile(ORNITH_PROFILE)
        # When inspecting candidates.
        candidate_quants = {
            c.weight_quant: c.file_sha256
            for c in profile.candidates
            if c.role == CandidateRole.CANDIDATE
        }
        # Then all four required quants appear with their exact publisher SHA-256.
        assert set(candidate_quants) >= REQUIRED_QUANTS
        for quant in REQUIRED_QUANTS:
            assert candidate_quants[quant] == PUBLISHER_SHA256[quant]

    def test_bf16_is_optional_reference_only(self) -> None:
        # Given the Ornith profile.
        profile = parse_profile(ORNITH_PROFILE)
        # When inspecting reference-role candidates.
        references = [c for c in profile.candidates if c.role == CandidateRole.REFERENCE]
        # Then BF16 is present only as a reference, never as a search candidate.
        assert any(c.weight_quant == WeightQuant.BF16 for c in references)
        candidate_quants = {
            c.weight_quant for c in profile.candidates if c.role == CandidateRole.CANDIDATE
        }
        assert WeightQuant.BF16 not in candidate_quants

    def test_all_candidate_urls_pin_immutable_revision(self) -> None:
        # Given the Ornith profile.
        profile = parse_profile(ORNITH_PROFILE)
        # When inspecting every candidate URL and revision.
        # Then each URL resolves at the pinned revision and never uses resolve/main.
        for candidate in profile.candidates:
            assert candidate.revision == ORNITH_REVISION
            assert f"resolve/{ORNITH_REVISION}/" in candidate.url
            assert "resolve/main" not in candidate.url

    def test_rocm_primary_and_vulkan_baseline_backends_present(self) -> None:
        # Given the Ornith profile.
        profile = parse_profile(ORNITH_PROFILE)
        # When inspecting backends.
        backends = {b.backend for b in profile.backends}
        # Then ROCm (primary) and Vulkan (measured baseline) are both present.
        assert Backend.ROCM in backends
        assert Backend.VULKAN in backends

    def test_recommendation_status_is_blocked_without_calibration(self) -> None:
        # Given the Ornith profile (screening-only, no calibrated thresholds).
        profile = parse_profile(ORNITH_PROFILE)
        # When inspecting the recommendation status.
        # Then finalist recommendation is typed blocked until calibration exists.
        assert profile.recommendation_status == RecommendationStatus.BLOCKED

    def test_balanced_weights_match_plan_exactly_and_sum_to_one(self) -> None:
        # Given the Ornith profile.
        profile = parse_profile(ORNITH_PROFILE)
        # When inspecting the recommendation weights.
        weights = profile.recommendation_weights
        # Then the six weights equal the plan's exact values and sum to 1.0.
        assert weights.prompt_throughput == pytest.approx(0.20)
        assert weights.generation_throughput == pytest.approx(0.30)
        assert weights.ttft_p95 == pytest.approx(0.15)
        assert weights.request_latency_p95 == pytest.approx(0.15)
        assert weights.quality_margin == pytest.approx(0.15)
        assert weights.vram_headroom == pytest.approx(0.05)
        assert sum(weights.to_dict().values()) == pytest.approx(1.0)

    def test_template_and_corpus_identities_are_bound(self) -> None:
        # Given the Ornith profile.
        profile = parse_profile(ORNITH_PROFILE)
        # When inspecting identities.
        # Then template and at least one corpus identity are present with valid SHA-256.
        assert profile.template.name
        assert profile.template.sha256
        assert len(str(profile.template.sha256)) == 64
        assert len(profile.corpora) >= 1
        for corpus in profile.corpora:
            assert corpus.corpus_id
            assert len(str(corpus.sha256)) == 64

    def test_max_native_combinations_is_finite(self) -> None:
        # Given the Ornith profile.
        profile = parse_profile(ORNITH_PROFILE)
        # When inspecting the combination cap.
        # Then it is a finite positive integer.
        assert profile.max_native_combinations > 0
        assert isinstance(profile.max_native_combinations, int)


class TestCanonicalManifest:
    def test_builds_manifest_from_profile(self) -> None:
        # Given the parsed profile.
        profile = parse_profile(ORNITH_PROFILE)
        # When building the normalized manifest.
        manifest = build_manifest(profile)
        # Then it is an immutable Manifest binding the exact constants.
        assert isinstance(manifest, Manifest)
        assert manifest.context_size == REQUIRED_CONTEXT_SIZE
        assert manifest.vram_limit_bytes == REQUIRED_VRAM_LIMIT_BYTES

    def test_canonical_json_is_valid_and_contains_exact_constants(self) -> None:
        # Given the manifest.
        manifest = build_manifest(parse_profile(ORNITH_PROFILE))
        # When emitting canonical JSON.
        text = canonical_manifest_json(manifest)
        # Then the required pinned constants appear exactly in canonical sorted-keys JSON.
        assert '"context_size": 32768' in text
        assert '"vram_limit_bytes": 13958643712' in text
        assert '"recommendation_status": "blocked"' in text

    def test_canonical_json_weights_sum_to_one(self) -> None:
        # Given the typed manifest bound from the profile.
        weights = build_manifest(parse_profile(ORNITH_PROFILE)).recommendation_weights.to_dict()
        # Then the six weights match the plan's exact values and sum to 1.0.
        assert set(weights) == set(EXPECTED_WEIGHTS)
        for key, value in EXPECTED_WEIGHTS.items():
            assert weights[key] == pytest.approx(value)
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_canonical_json_urls_are_immutable(self) -> None:
        # Given the canonical manifest JSON text.
        text = canonical_manifest_json(build_manifest(parse_profile(ORNITH_PROFILE)))
        # Then every URL pins the immutable revision and none use resolve/main.
        assert "resolve/main" not in text
        assert f"resolve/{ORNITH_REVISION}/" in text

    def test_publisher_sha_present_and_distinct_from_nix_sri(self) -> None:
        # Given the canonical manifest JSON text.
        text = canonical_manifest_json(build_manifest(parse_profile(ORNITH_PROFILE)))
        # Then each publisher SHA is a bare 64-hex value, never a sha256-... SRI token.
        assert '"sha256-' not in text
        for sha in PUBLISHER_SHA256.values():
            assert f'"{sha}"' in text

    def test_canonical_json_is_byte_deterministic(self) -> None:
        # Given two independent emissions of the same manifest.
        manifest = build_manifest(parse_profile(ORNITH_PROFILE))
        first = canonical_manifest_json(manifest)
        second = canonical_manifest_json(build_manifest(parse_profile(ORNITH_PROFILE)))
        # When comparing byte-for-byte.
        # Then they are identical and SHA-256-stable.
        assert first == second
        assert _sha256_over(first) == _sha256_over(second)

    def test_manifest_is_frozen(self) -> None:
        # Given a built manifest.
        manifest = build_manifest(parse_profile(ORNITH_PROFILE))
        # When attempting to mutate a field.
        # Then a FrozenInstanceError is raised.
        _field = "context_size"
        with pytest.raises(FrozenInstanceError):
            setattr(manifest, _field, 1)


# --- Block constants for text-based profile mutation (exact TOML substrings) ---
TEMPLATE_BLOCK = '''[template]
name = "ornith-1.0-9b-chat"
sha256 = "8b2e93558f2c1db595417095f2f78ed49c602f506364ab74ed5571cf31450613"'''

CORPORA_BLOCK = '''[[corpora]]
id = "coding-smoke"
sha256 = "440cf4b9241ff2c2fac42f91adbb2ee4c96d98b2ed4c4c25583d79f202598bd8"

[[corpora]]
id = "tool-use-smoke"
sha256 = "5095aeb2d8eff2cb08b49674f1d9405920ad286b1c47e0a56c1bf15da6879514"

[[corpora]]
id = "long-context-smoke"
sha256 = "3c78d1c1c2ac2b22a7263d224abcae52dc191d6b5989b4b1cc68b05bbd8ee019"'''

Q4_REVISION_LINE = 'revision = "3296bc7a404871a72ac3f1903f561459c09b5c17"'
Q4_SHA_LINE = 'file_sha256 = "5720d1f671b4996481274fffe01868c3c36e87c135cc8538471cc7bd6087b106"'


def _toml_with(*replacements: tuple[str, str]) -> bytes:
    """Read the checked-in profile text, apply (old, new) substitutions, return bytes."""
    text = _ornith_profile_text()
    for old, new in replacements:
        text = text.replace(old, new, 1)
    return text.encode()


class TestProfileTypedErrors:
    """Each malformed profile must yield a field-specific typed error, no traceback."""

    def test_context_other_than_32768_is_rejected(self) -> None:
        # Given a profile whose context is 81920.
        # When parsing the mutated TOML text.
        with pytest.raises(ProfileContextError) as exc_info:
            _ = parse_profile_bytes(_toml_with(("context_size = 32768", "context_size = 81920")))
        # Then the typed error reports the offending value.
        assert exc_info.value.actual == 81920

    def test_wrong_vram_literal_is_rejected(self) -> None:
        # Given a profile whose VRAM ceiling is wrong.
        with pytest.raises(ProfileVramError) as exc_info:
            _ = parse_profile_bytes(
                _toml_with(("vram_limit_bytes = 13958643712", "vram_limit_bytes = 1000"))
            )
        assert exc_info.value.actual == 1000

    def test_resolve_main_url_is_rejected_as_mutable(self) -> None:
        # Given a candidate URL that uses the mutable main ref.
        pinned = (
            "https://huggingface.co/deepreinforce-ai/Ornith-1.0-9B-GGUF/"
            "resolve/3296bc7a404871a72ac3f1903f561459c09b5c17/ornith-1.0-9b-Q4_K_M.gguf"
        )
        mutable = (
            "https://huggingface.co/deepreinforce-ai/Ornith-1.0-9B-GGUF/"
            "resolve/main/ornith-1.0-9b-Q4_K_M.gguf"
        )
        with pytest.raises(MutableUrlError):
            _ = parse_profile_bytes(_toml_with((pinned, mutable)))

    def test_missing_template_identity_is_rejected(self) -> None:
        # Given a profile with no template section.
        with pytest.raises(MissingIdentityError) as exc_info:
            _ = parse_profile_bytes(_toml_with((TEMPLATE_BLOCK, "")))
        assert "template" in exc_info.value.identity.lower()

    def test_missing_corpus_identity_is_rejected(self) -> None:
        # Given a profile with no corpora.
        with pytest.raises(MissingIdentityError) as exc_info:
            _ = parse_profile_bytes(_toml_with((CORPORA_BLOCK, "")))
        assert "corpus" in exc_info.value.identity.lower()

    def test_duplicate_candidate_ids_are_rejected(self) -> None:
        # Given two candidates sharing an id.
        with pytest.raises(DuplicateIdentityError) as exc_info:
            _ = parse_profile_bytes(
                _toml_with(('id = "ornith-1.0-9b-q5_k_m"', 'id = "ornith-1.0-9b-q4_k_m"'))
            )
        assert exc_info.value.kind == "candidate"

    def test_duplicate_backend_ids_are_rejected(self) -> None:
        # Given two backends sharing an id.
        with pytest.raises(DuplicateIdentityError) as exc_info:
            _ = parse_profile_bytes(_toml_with(('id = "vulkan"', 'id = "rocm"')))
        assert exc_info.value.kind == "backend"

    def test_weights_not_summing_to_one_are_rejected(self) -> None:
        # Given weights that no longer sum to 1.0.
        with pytest.raises(IneligibleWeightError):
            _ = parse_profile_bytes(
                _toml_with(
                    ("generation_throughput_weight = 0.30", "generation_throughput_weight = 0.05")
                )
            )

    def test_non_finite_weight_is_rejected(self) -> None:
        # Given a non-finite weight (TOML supports the inf literal).
        with pytest.raises(IneligibleWeightError):
            _ = parse_profile_bytes(
                _toml_with(
                    ("generation_throughput_weight = 0.30", "generation_throughput_weight = inf")
                )
            )

    def test_negative_weight_is_rejected(self) -> None:
        # Given a negative weight.
        with pytest.raises(IneligibleWeightError):
            _ = parse_profile_bytes(
                _toml_with(("quality_margin_weight = 0.15", "quality_margin_weight = -0.1"))
            )

    def test_malformed_publisher_sha_is_rejected(self) -> None:
        # Given a candidate whose file_sha256 is not 64-hex.
        with pytest.raises(InvalidSha256Error):
            _ = parse_profile_bytes(_toml_with((Q4_SHA_LINE, 'file_sha256 = "deadbeef"')))

    def test_publisher_sha_confused_with_nix_sri_is_rejected(self) -> None:
        # Given a candidate whose file_sha256 looks like a Nix SRI token.
        with pytest.raises(InvalidSha256Error) as exc_info:
            _ = parse_profile_bytes(
                _toml_with(
                    (
                        Q4_SHA_LINE,
                        'file_sha256 = "sha256-VyDR9nG0mWSBJ0//4Bhow8Nuh8E1zIU4RxzHvWCHsQY="',
                    )
                )
            )
        assert "sri" in exc_info.value.reason.lower()

    def test_invalid_toml_is_rejected_cleanly(self) -> None:
        # Given byte content that is not valid TOML.
        with pytest.raises(ProfileParseError):
            _ = parse_profile_bytes(b"this is = = not toml [[")

    def test_missing_profile_section_is_rejected(self) -> None:
        # Given an empty document.
        with pytest.raises(ProfileParseError):
            _ = parse_profile_bytes(b"")


class TestProfileValidateCli:
    """The CLI emits canonical deterministic JSON on success and a typed error on failure."""

    def test_validate_emits_canonical_json_and_exits_zero(self) -> None:
        # Given the checked-in profile invoked through the CLI.
        runner = CliRunner()
        # When validating with --json.
        result = runner.invoke(app, ["profile", "validate", "--profile", ORNITH_PROFILE, "--json"])
        # Then it exits zero and emits valid canonical JSON with the pinned constants.
        assert result.exit_code == 0, result.output
        assert '"context_size": 32768' in result.output
        assert '"vram_limit_bytes": 13958643712' in result.output

    def test_validate_is_byte_deterministic_across_runs(self) -> None:
        # Given two independent CLI validations.
        runner = CliRunner()
        # When running validate --json twice.
        first = runner.invoke(app, ["profile", "validate", "--profile", ORNITH_PROFILE, "--json"])
        second = runner.invoke(app, ["profile", "validate", "--profile", ORNITH_PROFILE, "--json"])
        # Then both stdout bytes and their SHA-256 are identical.
        assert first.exit_code == 0
        assert first.output == second.output
        assert _sha256_over(first.output) == _sha256_over(second.output)

    def test_malformed_profile_exits_nonzero_with_typed_message_no_traceback(
        self, tmp_path: Path
    ) -> None:
        # Given a temp profile with a wrong context (mutated TOML text).
        bad_profile = tmp_path / "bad.toml"
        _ = bad_profile.write_bytes(_toml_with(("context_size = 32768", "context_size = 81920")))
        # When validating.
        runner = CliRunner()
        result = runner.invoke(
            app, ["profile", "validate", "--profile", str(bad_profile), "--json"]
        )
        # Then it exits nonzero with a typed field-specific message and no traceback.
        assert result.exit_code != 0
        rendered = (result.output or "") + (getattr(result, "stderr", "") or "")
        assert "context" in rendered.lower()
        assert "Traceback" not in rendered

    def test_validate_does_not_create_a_run_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Given a clean working directory and the absolute profile path.
        run_root = tmp_path / "optimizer-runs"
        profile_abs = Path(ORNITH_PROFILE).resolve()
        monkeypatch.chdir(tmp_path)
        # When validating the checked-in profile.
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["profile", "validate", "--profile", str(profile_abs), "--json"],
        )
        # Then validation succeeds and no optimizer-runs directory is ever created.
        assert result.exit_code == 0
        assert not run_root.exists()
