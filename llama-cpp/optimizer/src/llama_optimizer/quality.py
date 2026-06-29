"""Tiered, calibrated quality gates for the optimizer (T8).

Re-exports the split responsibility modules so callers can import from
``llama_optimizer.quality``. Quality requirements are calibrated profile values
plus derivation metadata, not module constants. Weight quantization and runtime
KV-cache quantization are separate dimensions. Full-logit KL is optional and
identity-bound, never in the inner loop.
"""

from __future__ import annotations

from llama_optimizer.quality_gates import (
    build_imatrix_command,
    build_perplexity_command,
    compute_corpus_sha256,
    evaluate_quality_gates,
    parse_perplexity_output,
    summarize_outcome,
)
from llama_optimizer.quality_types import (
    COMPLEXITY_PPL_RESULT_RE,
    KL_IDENTITY_FIELDS,
    QUALITY_GATE_ORDER,
    ArtifactHash,
    CorpusMismatchError,
    ImatrixRequantizeError,
    KlIdentityMismatchError,
    KlNotEnabledError,
    PerplexityParseError,
    QualityConfig,
    QualityContext,
    QualityError,
    QualityGateResult,
    QualityGateStatus,
    QualityIdentity,
    QualityOutcome,
    QuantDimension,
    ReferenceMissingError,
    ReferencePplResult,
)

__all__ = [
    "COMPLEXITY_PPL_RESULT_RE",
    "KL_IDENTITY_FIELDS",
    "QUALITY_GATE_ORDER",
    "ArtifactHash",
    "CorpusMismatchError",
    "ImatrixRequantizeError",
    "KlIdentityMismatchError",
    "KlNotEnabledError",
    "PerplexityParseError",
    "QualityConfig",
    "QualityContext",
    "QualityError",
    "QualityGateResult",
    "QualityGateStatus",
    "QualityIdentity",
    "QualityOutcome",
    "QuantDimension",
    "ReferenceMissingError",
    "ReferencePplResult",
    "build_imatrix_command",
    "build_perplexity_command",
    "compute_corpus_sha256",
    "evaluate_quality_gates",
    "parse_perplexity_output",
    "summarize_outcome",
]
