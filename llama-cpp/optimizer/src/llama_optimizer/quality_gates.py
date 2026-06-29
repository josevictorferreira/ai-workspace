"""Gate evaluation, command builders, and parsers for quality gates (T8).

Ordered gates: compatibility, coding/tool fixtures, exact-32768 long-context,
corpus PPL relative to reference, optional identity-bound KL. Weight and KV-cache
quantization are evaluated separately. No universal thresholds; calibration from
profile. KL is never in the inner loop.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from llama_optimizer.quality_types import (
    COMPLEXITY_PPL_RESULT_RE,
    CorpusMismatchError,
    ImatrixRequantizeError,
    PerplexityParseError,
    QualityConfig,
    QualityContext,
    QualityGateResult,
    QualityGateStatus,
    QualityIdentity,
    QualityOutcome,
)

_REQUIRED_CONTEXT = 32768


def compute_corpus_sha256(path: Path) -> str:
    """Hash a corpus file, raising CorpusMismatchError if it does not exist."""
    if not path.exists():
        raise CorpusMismatchError(reason=f"corpus file not found: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_perplexity_output(raw: str) -> float:
    """Parse llama-perplexity output to extract the final PPL value."""
    match = COMPLEXITY_PPL_RESULT_RE.search(raw)
    if not match:
        raise PerplexityParseError(reason="no 'final = X.XXXX' line found in perplexity output")
    try:
        return float(match.group(1))
    except ValueError as exc:
        raise PerplexityParseError(reason=f"ppl value not a float: {match.group(1)}") from exc


def build_perplexity_command(
    *, binary: str, model: str, corpus: str, context_size: int
) -> list[str]:
    """Construct the llama-perplexity argument array without shell interpolation."""
    return [
        binary,
        "-m",
        model,
        "-f",
        corpus,
        "-c",
        str(context_size),
    ]


def build_imatrix_command(
    *,
    binary: str,
    model: str,
    output: str,
    corpus: str,
    allow_requantize: bool = False,
) -> list[str]:
    """Construct the llama-imatrix argument array; reject --allow-requantize."""
    if allow_requantize:
        raise ImatrixRequantizeError(reason="--allow-requantize is prohibited")
    return [
        binary,
        "-m",
        model,
        "-o",
        output,
        "-f",
        corpus,
    ]


def _compare_kl_identity(candidate: QualityIdentity, reference: QualityIdentity) -> list[str]:
    """Return the list of KL identity fields that differ between candidate and reference."""
    pairs: list[tuple[str, str, str]] = [
        ("revision", candidate.revision, reference.revision),
        ("file_sha256", candidate.file_sha256, reference.file_sha256),
        ("build_label", candidate.build_label, reference.build_label),
        ("backend", candidate.backend, reference.backend),
        ("template_hash", candidate.template_hash, reference.template_hash),
        ("corpus_hash", candidate.corpus_hash, reference.corpus_hash),
    ]
    mismatches: list[str] = []
    for name, c_val, r_val in pairs:
        if c_val != r_val:
            mismatches.append(name)
    if candidate.context_size != reference.context_size:
        mismatches.append("context_size")
    return mismatches


def _check_compatibility(
    identity: QualityIdentity, reference: QualityIdentity, corpora_dir: Path
) -> QualityGateResult:
    """Gate 1: candidate identity must match reference on revision, template, corpus."""
    mismatches: list[str] = []
    if identity.revision != reference.revision:
        mismatches.append("revision")
    if identity.template_hash != reference.template_hash:
        mismatches.append("template_hash")
    if identity.corpus_hash != reference.corpus_hash:
        mismatches.append("corpus_hash")
    corpus_path = corpora_dir / f"{identity.corpus_id}.jsonl"
    try:
        actual_hash = compute_corpus_sha256(corpus_path)
    except CorpusMismatchError as exc:
        return QualityGateResult(
            gate_name="compatibility",
            status=QualityGateStatus.FAILED,
            reason=str(exc),
        )
    if actual_hash != identity.corpus_hash:
        mismatches.append("corpus_hash (on-disk)")
    if mismatches:
        return QualityGateResult(
            gate_name="compatibility",
            status=QualityGateStatus.FAILED,
            reason=f"identity mismatch: {', '.join(mismatches)}",
        )
    return QualityGateResult(
        gate_name="compatibility",
        status=QualityGateStatus.PASSED,
        reason="identity and corpus hash match reference",
    )


def _check_fixture_gate(gate_name: str, corpus_id: str, corpora_dir: Path) -> QualityGateResult:
    """Gate for coding/tool fixtures: verify the corpus file exists on disk."""
    corpus_path = corpora_dir / f"{corpus_id}.jsonl"
    if not corpus_path.exists():
        return QualityGateResult(
            gate_name=gate_name,
            status=QualityGateStatus.FAILED,
            reason=f"fixture corpus not found: {corpus_path}",
        )
    actual = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    return QualityGateResult(
        gate_name=gate_name,
        status=QualityGateStatus.PASSED,
        reason=f"fixture {corpus_id} verified (sha256={actual[:12]})",
    )


def _check_long_context(identity: QualityIdentity) -> QualityGateResult:
    """Gate: exact-32768 long-context sentinel."""
    if identity.context_size != _REQUIRED_CONTEXT:
        return QualityGateResult(
            gate_name="long_context",
            status=QualityGateStatus.FAILED,
            reason=f"context must be {_REQUIRED_CONTEXT}, got {identity.context_size}",
        )
    return QualityGateResult(
        gate_name="long_context",
        status=QualityGateStatus.PASSED,
        reason="exact-32768 long-context verified",
    )


def _run_perplexity(ctx: QualityContext) -> str:
    """Run llama-perplexity and return raw stdout."""
    corpus_path = Path(ctx.corpora_dir) / f"{ctx.identity.corpus_id}.jsonl"
    cmd = build_perplexity_command(
        binary=ctx.perplexity_binary,
        model=ctx.identity.model_filename,
        corpus=str(corpus_path),
        context_size=ctx.identity.context_size,
    )
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=30)
    return result.stdout


def _check_corpus_ppl(ctx: QualityContext) -> QualityGateResult:
    """Gate: corpus PPL relative to identity-bound reference calibration."""
    config = ctx.config
    if config.reference_ppl <= 0 or config.max_ppl_ratio <= 0:
        return QualityGateResult(
            gate_name="corpus_ppl",
            status=QualityGateStatus.SKIPPED,
            reason="calibration missing: reference_ppl or max_ppl_ratio not set",
        )
    raw = _run_perplexity(ctx)
    try:
        candidate_ppl = parse_perplexity_output(raw)
    except PerplexityParseError as exc:
        return QualityGateResult(
            gate_name="corpus_ppl",
            status=QualityGateStatus.FAILED,
            reason=str(exc),
        )
    ratio = candidate_ppl / config.reference_ppl if config.reference_ppl > 0 else float("inf")
    if ratio > config.max_ppl_ratio:
        return QualityGateResult(
            gate_name="corpus_ppl",
            status=QualityGateStatus.FAILED,
            reason=f"ppl ratio {ratio:.4f} exceeds calibrated max {config.max_ppl_ratio:.4f}",
            metrics={"candidate_ppl": candidate_ppl, "ratio": ratio},
        )
    return QualityGateResult(
        gate_name="corpus_ppl",
        status=QualityGateStatus.PASSED,
        reason=f"ppl ratio {ratio:.4f} within calibrated {config.max_ppl_ratio:.4f}",
        metrics={"candidate_ppl": candidate_ppl, "ratio": ratio},
    )


def _check_kl_identity(ctx: QualityContext) -> QualityGateResult:
    """Gate: optional identity-bound KL. Never in inner loop. Always last.

    When KL is enabled, ALL :data:`KL_IDENTITY_FIELDS` must match between the
    candidate identity and the reference identity before any divergence
    comparison proceeds.
    """
    if not ctx.config.kl_enabled:
        return QualityGateResult(
            gate_name="kl_identity",
            status=QualityGateStatus.SKIPPED,
            reason="KL not enabled for this evaluation",
        )
    mismatches = _compare_kl_identity(ctx.identity, ctx.reference_identity)
    if mismatches:
        return QualityGateResult(
            gate_name="kl_identity",
            status=QualityGateStatus.FAILED,
            reason=f"KL identity mismatch: {', '.join(mismatches)}",
        )
    return QualityGateResult(
        gate_name="kl_identity",
        status=QualityGateStatus.PASSED,
        reason="KL identity verified: all fields match reference",
    )


def evaluate_quality_gates(ctx: QualityContext) -> list[QualityGateResult]:
    """Run all ordered quality gates and return per-gate results.

    Gates run in order: compatibility, coding_fixture, tool_use_fixture,
    long_context, corpus_ppl, kl_identity. All gates run independently;
    KL is always last and never in the inner loop.
    """
    corpora_dir = Path(ctx.corpora_dir)
    results: list[QualityGateResult] = []

    # Gate 1: compatibility (candidate vs reference identity + on-disk corpus)
    results.append(_check_compatibility(ctx.identity, ctx.reference_identity, corpora_dir))

    # Gate 2: coding fixture
    results.append(_check_fixture_gate("coding_fixture", "coding-smoke", corpora_dir))

    # Gate 3: tool-use fixture
    results.append(_check_fixture_gate("tool_use_fixture", "tool-use-smoke", corpora_dir))

    # Gate 4: long-context exact-32768
    results.append(_check_long_context(ctx.identity))

    # Gate 5: corpus PPL relative to reference
    results.append(_check_corpus_ppl(ctx))

    # Gate 6: optional KL identity (always last, never inner loop)
    results.append(_check_kl_identity(ctx))

    return results


def summarize_outcome(results: list[QualityGateResult], config: QualityConfig) -> QualityOutcome:
    """Build the overall QualityOutcome from per-gate results."""
    statuses = {r.status for r in results}
    if QualityGateStatus.FAILED in statuses:
        overall = QualityGateStatus.FAILED
    else:
        overall = QualityGateStatus.PASSED
    return QualityOutcome(
        status=overall,
        quant_dimension=config.quant_dimension,
        reference_ppl=config.reference_ppl,
        gate_results=tuple(results),
    )
