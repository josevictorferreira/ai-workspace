"""Behavior tests for tiered, calibrated quality gates (T8).

Ordered gates: compatibility, coding/tool fixtures, exact-32768 long-context,
corpus PPL relative to reference, optional identity-bound KL. Weight quantization
and KV-cache quantization are separate dimensions. No universal thresholds;
calibration comes from the profile.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from llama_optimizer.quality import (
    COMPLEXITY_PPL_RESULT_RE,
    KL_IDENTITY_FIELDS,
    QUALITY_GATE_ORDER,
    CorpusMismatchError,
    ImatrixRequantizeError,
    PerplexityParseError,
    QualityConfig,
    QualityContext,
    QualityGateResult,
    QualityGateStatus,
    QualityIdentity,
    QualityOutcome,
    QuantDimension,
    ReferencePplResult,
    build_imatrix_command,
    build_perplexity_command,
    compute_corpus_sha256,
    evaluate_quality_gates,
    parse_perplexity_output,
    summarize_outcome,
)

_PERPLEXITY_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bin" / "llama-perplexity"
_IMATRIX_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bin" / "llama-imatrix"
_CORPORA_DIR = Path(__file__).resolve().parent.parent / "corpora"

CODING_SMOKE_HASH = "9dafe1fa0bd0a30140a85b414ec1181e83d871fb5124373007b555b6602bde15"
TOOL_USE_SMOKE_HASH = "cd78cb72ba3f6320824d88ac7e7dde28ba944400af8bae688fd7102d91c38071"
LONG_CONTEXT_SMOKE_HASH = "bb5456a9feb3d56618a154181ccb8212a1ceb1b7376105fe775a22548ecefa20"

REQUIRED_CONTEXT_SIZE = 32768
ORNITH_REVISION = "3296bc7a404871a72ac3f1903f561459c09b5c17"
TEMPLATE_HASH = "8b2e93558f2c1db595417095f2f78ed49c602f506364ab74ed5571cf31450613"


def _identity(
    *,
    revision: str = ORNITH_REVISION,
    template_hash: str = TEMPLATE_HASH,
    corpus_hash: str = CODING_SMOKE_HASH,
    context_size: int = REQUIRED_CONTEXT_SIZE,
) -> QualityIdentity:
    """Build a default matching identity for happy-path tests."""
    return QualityIdentity(
        model_filename="ornith-1.0-9b-Q4_K_M.gguf",
        revision=revision,
        file_sha256="5720d1f671b4996481274fffe01868c3c36e87c135cc8538471cc7bd6087b106",
        build_label="llama.cpp-rocm-local-pinned",
        backend="rocm",
        template_name="ornith-1.0-9b-chat",
        template_hash=template_hash,
        corpus_id="coding-smoke",
        corpus_hash=corpus_hash,
        context_size=context_size,
    )


def _config(
    *,
    quant_dim: QuantDimension = QuantDimension.WEIGHT,
    reference_ppl: float = 7.0,
    max_ppl_ratio: float = 1.15,
    kl_enabled: bool = False,
    max_kl: float = 0.0,
) -> QualityConfig:
    """Build a calibrated quality config for tests."""
    return QualityConfig(
        quant_dimension=quant_dim,
        reference_ppl=reference_ppl,
        max_ppl_ratio=max_ppl_ratio,
        kl_enabled=kl_enabled,
        max_kl=max_kl,
    )


def _make_ctx(
    *,
    identity: QualityIdentity | None = None,
    config: QualityConfig | None = None,
    reference: QualityIdentity | None = None,
    output_dir: str = "/tmp/test-quality",
) -> QualityContext:
    """Build a QualityContext with a default matching reference identity."""
    return QualityContext(
        identity=identity if identity is not None else _identity(),
        reference_identity=reference if reference is not None else _identity(),
        config=config if config is not None else _config(),
        perplexity_binary=str(_PERPLEXITY_FIXTURE),
        corpora_dir=str(_CORPORA_DIR),
        output_dir=output_dir,
    )


def _write_ppl_control(tmp_path: Path, *, mode: str = "happy", ppl: float = 7.25) -> str:
    path = tmp_path / "ppl_control.json"
    _ = path.write_text(json.dumps({"mode": mode, "ppl": ppl}))
    return str(path)


def _write_imatrix_control(tmp_path: Path, *, mode: str = "happy") -> str:
    path = tmp_path / "imatrix_control.json"
    _ = path.write_text(json.dumps({"mode": mode}))
    return str(path)


def _summarize_outcome(
    results: list[QualityGateResult],
    *,
    quant_dim: QuantDimension = QuantDimension.WEIGHT,
    reference_ppl: float = 7.0,
) -> QualityOutcome:
    """Helper: build a QualityOutcome from gate results."""
    return summarize_outcome(results, _config(quant_dim=quant_dim, reference_ppl=reference_ppl))


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Remove stale fake-control env vars so tests don't collide."""
    for key in ("LLAMA_PERPLEXITY_FAKE_CONTROL", "LLAMA_IMATRIX_FAKE_CONTROL"):
        monkeypatch.delenv(key, raising=False)


class TestCorpusHashing:
    def test_coding_smoke_hash_matches_manifest(self) -> None:
        h = compute_corpus_sha256(_CORPORA_DIR / "coding-smoke.jsonl")
        assert h == CODING_SMOKE_HASH

    def test_tool_use_smoke_hash_matches_manifest(self) -> None:
        h = compute_corpus_sha256(_CORPORA_DIR / "tool-use-smoke.jsonl")
        assert h == TOOL_USE_SMOKE_HASH

    def test_long_context_smoke_hash_matches_manifest(self) -> None:
        h = compute_corpus_sha256(_CORPORA_DIR / "long-context-smoke.jsonl")
        assert h == LONG_CONTEXT_SMOKE_HASH

    def test_missing_corpus_file_raises_typed_error(self, tmp_path: Path) -> None:
        with pytest.raises(CorpusMismatchError):
            _ = compute_corpus_sha256(tmp_path / "nonexistent.jsonl")


class TestPerplexityParsing:
    def test_parse_valid_output_extracts_ppl(self) -> None:
        raw = "perplexity: model=test.gguf ctx=32768\nperplexity: final = 7.2500\n"
        ppl = parse_perplexity_output(raw)
        assert ppl == pytest.approx(7.25)

    def test_parse_malformed_output_raises_typed_error(self) -> None:
        with pytest.raises(PerplexityParseError):
            _ = parse_perplexity_output("this is not perplexity output\n")

    def test_parse_empty_output_raises(self) -> None:
        with pytest.raises(PerplexityParseError):
            _ = parse_perplexity_output("")

    def test_complexity_ppl_result_regex_matches_expected_format(self) -> None:
        assert COMPLEXITY_PPL_RESULT_RE.search("perplexity: final = 7.2500")
        assert not COMPLEXITY_PPL_RESULT_RE.search("perplexity: no final here")


class TestGateOrder:
    def test_gate_order_is_compatibility_first(self) -> None:
        assert QUALITY_GATE_ORDER[0] == "compatibility"

    def test_gate_order_has_kl_last(self) -> None:
        assert QUALITY_GATE_ORDER[-1] == "kl_identity"

    def test_gate_order_contains_all_six_gates(self) -> None:
        assert len(QUALITY_GATE_ORDER) == 6
        for name in (
            "compatibility",
            "coding_fixture",
            "tool_use_fixture",
            "long_context",
            "corpus_ppl",
            "kl_identity",
        ):
            assert name in QUALITY_GATE_ORDER


class TestQuantDimensions:
    def test_weight_and_kv_are_distinct_enums(self) -> None:
        assert QuantDimension.WEIGHT != QuantDimension.KV_CACHE
        assert QuantDimension.WEIGHT.value == "weight"
        assert QuantDimension.KV_CACHE.value == "kv_cache"


class TestCompatibilityGate:
    def test_matching_identity_passes_compatibility(self, tmp_path: Path) -> None:
        ctx = _make_ctx(output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        compat = next(r for r in results if r.gate_name == "compatibility")
        assert compat.status == QualityGateStatus.PASSED

    def test_template_hash_mismatch_fails_compatibility(self, tmp_path: Path) -> None:
        identity = _identity(template_hash="0" * 64)
        ctx = _make_ctx(identity=identity, output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        compat = next(r for r in results if r.gate_name == "compatibility")
        assert compat.status == QualityGateStatus.FAILED
        assert "template" in compat.reason.lower()

    def test_corpus_hash_mismatch_fails_compatibility(self, tmp_path: Path) -> None:
        identity = _identity(corpus_hash="0" * 64)
        ctx = _make_ctx(identity=identity, output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        compat = next(r for r in results if r.gate_name == "compatibility")
        assert compat.status == QualityGateStatus.FAILED
        assert "corpus" in compat.reason.lower()

    def test_revision_mismatch_fails_compatibility(self, tmp_path: Path) -> None:
        identity = _identity(revision="a" * 40)
        ctx = _make_ctx(identity=identity, output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        compat = next(r for r in results if r.gate_name == "compatibility")
        assert compat.status == QualityGateStatus.FAILED
        assert "revision" in compat.reason.lower()


class TestCorpusPplGate:
    def test_ppl_within_calibrated_ratio_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        control = _write_ppl_control(tmp_path, ppl=7.5)
        monkeypatch.setenv("LLAMA_PERPLEXITY_FAKE_CONTROL", control)
        ctx = _make_ctx(
            config=_config(reference_ppl=7.0, max_ppl_ratio=1.15),
            output_dir=str(tmp_path),
        )
        results = evaluate_quality_gates(ctx)
        ppl_gate = next(r for r in results if r.gate_name == "corpus_ppl")
        assert ppl_gate.status == QualityGateStatus.PASSED

    def test_ppl_exceeding_calibrated_ratio_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        control = _write_ppl_control(tmp_path, ppl=9.0)
        monkeypatch.setenv("LLAMA_PERPLEXITY_FAKE_CONTROL", control)
        ctx = _make_ctx(
            config=_config(reference_ppl=7.0, max_ppl_ratio=1.15),
            output_dir=str(tmp_path),
        )
        results = evaluate_quality_gates(ctx)
        ppl_gate = next(r for r in results if r.gate_name == "corpus_ppl")
        assert ppl_gate.status == QualityGateStatus.FAILED
        assert "ratio" in ppl_gate.reason.lower()

    def test_missing_calibration_skips_ppl_gate(self, tmp_path: Path) -> None:
        ctx = _make_ctx(
            config=_config(reference_ppl=0.0, max_ppl_ratio=0.0),
            output_dir=str(tmp_path),
        )
        results = evaluate_quality_gates(ctx)
        ppl_gate = next(r for r in results if r.gate_name == "corpus_ppl")
        assert ppl_gate.status == QualityGateStatus.SKIPPED
        assert "calibration" in ppl_gate.reason.lower()

    def test_perplexity_parse_failure_is_quality_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        control = _write_ppl_control(tmp_path, mode="malformed")
        monkeypatch.setenv("LLAMA_PERPLEXITY_FAKE_CONTROL", control)
        ctx = _make_ctx(output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        ppl_gate = next(r for r in results if r.gate_name == "corpus_ppl")
        assert ppl_gate.status == QualityGateStatus.FAILED


class TestLongContextGate:
    def test_long_context_with_exact_32768_passes(self, tmp_path: Path) -> None:
        ctx = _make_ctx(output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        lc_gate = next(r for r in results if r.gate_name == "long_context")
        assert lc_gate.status == QualityGateStatus.PASSED
        assert "32768" in lc_gate.reason or "context" in lc_gate.reason.lower()

    def test_long_context_with_wrong_context_fails(self, tmp_path: Path) -> None:
        identity = _identity(context_size=8192)
        # Reference stays at 32768 so compatibility also detects the mismatch,
        # but long_context gate independently fails.
        ctx = _make_ctx(identity=identity, output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        lc_gate = next(r for r in results if r.gate_name == "long_context")
        assert lc_gate.status == QualityGateStatus.FAILED


class TestCodingAndToolFixtures:
    def test_coding_fixture_gate_passes_with_valid_corpus(self, tmp_path: Path) -> None:
        ctx = _make_ctx(output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        coding_gate = next(r for r in results if r.gate_name == "coding_fixture")
        assert coding_gate.status == QualityGateStatus.PASSED

    def test_tool_use_fixture_gate_passes_with_valid_corpus(self, tmp_path: Path) -> None:
        ctx = _make_ctx(output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        tool_gate = next(r for r in results if r.gate_name == "tool_use_fixture")
        assert tool_gate.status == QualityGateStatus.PASSED


class TestKlIdentityGate:
    def test_kl_disabled_by_default_skips(self, tmp_path: Path) -> None:
        ctx = _make_ctx(config=_config(kl_enabled=False), output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        kl_gate = next(r for r in results if r.gate_name == "kl_identity")
        assert kl_gate.status == QualityGateStatus.SKIPPED

    def test_kl_enabled_with_matching_identity_passes(self, tmp_path: Path) -> None:
        ctx = _make_ctx(config=_config(kl_enabled=True, max_kl=0.1), output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        kl_gate = next(r for r in results if r.gate_name == "kl_identity")
        assert kl_gate.status == QualityGateStatus.PASSED

    def test_kl_identity_mismatch_fails(self, tmp_path: Path) -> None:
        identity = _identity(revision="b" * 40)
        ctx = _make_ctx(
            identity=identity,
            config=_config(kl_enabled=True, max_kl=0.1),
            output_dir=str(tmp_path),
        )
        results = evaluate_quality_gates(ctx)
        kl_gate = next(r for r in results if r.gate_name == "kl_identity")
        assert kl_gate.status == QualityGateStatus.FAILED
        assert "identity" in kl_gate.reason.lower() or "mismatch" in kl_gate.reason.lower()

    def test_kl_identity_fields_are_complete(self) -> None:
        for field in (
            "revision",
            "file_sha256",
            "build_label",
            "backend",
            "template_hash",
            "corpus_hash",
            "context_size",
        ):
            assert field in KL_IDENTITY_FIELDS


class TestWeightVsKvSeparation:
    def test_weight_quant_dimension_produces_weight_record(self, tmp_path: Path) -> None:
        ctx = _make_ctx(
            config=_config(quant_dim=QuantDimension.WEIGHT),
            output_dir=str(tmp_path),
        )
        results = evaluate_quality_gates(ctx)
        outcome = _summarize_outcome(results, quant_dim=QuantDimension.WEIGHT)
        assert outcome.quant_dimension == QuantDimension.WEIGHT

    def test_kv_cache_dimension_produces_kv_record(self, tmp_path: Path) -> None:
        ctx = _make_ctx(
            config=_config(quant_dim=QuantDimension.KV_CACHE),
            output_dir=str(tmp_path),
        )
        results = evaluate_quality_gates(ctx)
        outcome = _summarize_outcome(results, quant_dim=QuantDimension.KV_CACHE)
        assert outcome.quant_dimension == QuantDimension.KV_CACHE


class TestImatrixPipeline:
    def test_imatrix_command_contains_no_allow_requantize(self, tmp_path: Path) -> None:
        cmd = build_imatrix_command(
            binary=str(_IMATRIX_FIXTURE),
            model="model.gguf",
            output=str(tmp_path / "imatrix.dat"),
            corpus=str(_CORPORA_DIR / "coding-smoke.jsonl"),
        )
        assert "--allow-requantize" not in cmd

    def test_imatrix_command_includes_model_output_corpus(self, tmp_path: Path) -> None:
        cmd = build_imatrix_command(
            binary=str(_IMATRIX_FIXTURE),
            model="model.gguf",
            output=str(tmp_path / "imatrix.dat"),
            corpus=str(_CORPORA_DIR / "coding-smoke.jsonl"),
        )
        assert "-m" in cmd
        assert "-o" in cmd
        assert "-f" in cmd

    def test_imatrix_requantize_request_raises_typed_error(self, tmp_path: Path) -> None:
        with pytest.raises(ImatrixRequantizeError):
            _ = build_imatrix_command(
                binary=str(_IMATRIX_FIXTURE),
                model="model.gguf",
                output=str(tmp_path / "imatrix.dat"),
                corpus=str(_CORPORA_DIR / "coding-smoke.jsonl"),
                allow_requantize=True,
            )

    def test_imatrix_fake_writes_file_in_happy_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        control = _write_imatrix_control(tmp_path, mode="happy")
        monkeypatch.setenv("LLAMA_IMATRIX_FAKE_CONTROL", control)
        out = tmp_path / "imatrix.dat"
        cmd = build_imatrix_command(
            binary=str(_IMATRIX_FIXTURE),
            model="model.gguf",
            output=str(out),
            corpus=str(_CORPORA_DIR / "coding-smoke.jsonl"),
        )
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        assert result.returncode == 0
        assert out.exists()


class TestPerplexityCommand:
    def test_perplexity_command_contains_exact_32768(self) -> None:
        cmd = build_perplexity_command(
            binary=str(_PERPLEXITY_FIXTURE),
            model="model.gguf",
            corpus=str(_CORPORA_DIR / "coding-smoke.jsonl"),
            context_size=REQUIRED_CONTEXT_SIZE,
        )
        assert "-c" in cmd
        assert cmd[cmd.index("-c") + 1] == "32768"

    def test_perplexity_command_includes_model_and_corpus(self) -> None:
        cmd = build_perplexity_command(
            binary=str(_PERPLEXITY_FIXTURE),
            model="model.gguf",
            corpus=str(_CORPORA_DIR / "coding-smoke.jsonl"),
            context_size=REQUIRED_CONTEXT_SIZE,
        )
        assert "-m" in cmd
        assert "-f" in cmd


class TestOverallOutcome:
    def test_all_gates_pass_yields_passed_outcome(self, tmp_path: Path) -> None:
        ctx = _make_ctx(output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        outcome = _summarize_outcome(results)
        assert outcome.status == QualityGateStatus.PASSED

    def test_any_gate_fail_yields_failed_outcome(self, tmp_path: Path) -> None:
        identity = _identity(template_hash="0" * 64)
        ctx = _make_ctx(identity=identity, output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        outcome = _summarize_outcome(results)
        assert outcome.status == QualityGateStatus.FAILED

    def test_quality_outcome_carries_reference_ppl(self, tmp_path: Path) -> None:
        ctx = _make_ctx(config=_config(reference_ppl=7.0), output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        outcome = _summarize_outcome(results, reference_ppl=7.0)
        assert outcome.reference_ppl == pytest.approx(7.0)

    def test_kl_not_in_inner_loop(self, tmp_path: Path) -> None:
        ctx = _make_ctx(config=_config(kl_enabled=False), output_dir=str(tmp_path))
        results = evaluate_quality_gates(ctx)
        kl_index = next(i for i, r in enumerate(results) if r.gate_name == "kl_identity")
        ppl_index = next(i for i, r in enumerate(results) if r.gate_name == "corpus_ppl")
        assert kl_index > ppl_index


class TestReferencePplResult:
    def test_reference_ppl_result_carries_identity(self) -> None:
        identity = _identity()
        result = ReferencePplResult(
            identity=identity,
            ppl=7.0,
            corpus_id="coding-smoke",
            corpus_hash=CODING_SMOKE_HASH,
        )
        assert result.ppl == pytest.approx(7.0)
        assert result.corpus_id == "coding-smoke"
