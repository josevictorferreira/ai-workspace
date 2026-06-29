"""Typed value objects and errors for tiered quality gates (T8).

Weight quantization and runtime KV-cache quantization are separate dimensions.
Calibration comes from the profile, not from module constants.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, NewType

# --- Semantic primitives -------------------------------------------------
ArtifactHash = NewType("ArtifactHash", str)


class QuantDimension(StrEnum):
    """Weight quantization and KV-cache quantization are deliberately separate."""

    WEIGHT = "weight"
    KV_CACHE = "kv_cache"


class QualityGateStatus(StrEnum):
    """Outcome of one quality gate."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


# Ordered gate names: compatibility first, KL identity last (never inner loop).
QUALITY_GATE_ORDER: Final[tuple[str, ...]] = (
    "compatibility",
    "coding_fixture",
    "tool_use_fixture",
    "long_context",
    "corpus_ppl",
    "kl_identity",
)

# KL identity requires ALL of these fields to match before comparison.
KL_IDENTITY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "revision",
        "file_sha256",
        "build_label",
        "backend",
        "template_hash",
        "corpus_hash",
        "context_size",
    }
)

# Regex for the standard llama-perplexity 'final = X.XXXX' output.
COMPLEXITY_PPL_RESULT_RE: Final[re.Pattern[str]] = re.compile(r"final\s*=\s*([0-9]+\.?[0-9]*)")


# --- Typed boundary errors -------------------------------------------------
@dataclass
class QualityError(ValueError):
    """Base typed error for quality-gate failures."""

    reason: str

    def __post_init__(self) -> None:
        """Populate the base ValueError message so str() is never empty."""
        Exception.__init__(self, self.reason)


@dataclass
class CorpusMismatchError(QualityError):
    """Corpus file hash did not match the manifest-declared hash."""


@dataclass
class PerplexityParseError(QualityError):
    """llama-perplexity output could not be parsed."""


@dataclass
class ReferenceMissingError(QualityError):
    """Reference model or calibration is missing for a gate."""


@dataclass
class KlIdentityMismatchError(QualityError):
    """KL identity fields did not match before comparison."""


@dataclass
class KlNotEnabledError(QualityError):
    """KL was invoked but not explicitly enabled."""


@dataclass
class ImatrixRequantizeError(QualityError):
    """An imatrix pipeline request included --allow-requantize."""


# --- Immutable value objects ----------------------------------------------
@dataclass(frozen=True, slots=True)
class QualityIdentity:
    """Identity cross-check target for quality gates.

    Every field must match between reference and candidate before KL comparison.
    """

    model_filename: str
    revision: str
    file_sha256: str
    build_label: str
    backend: str
    template_name: str
    template_hash: str
    corpus_id: str
    corpus_hash: str
    context_size: int


@dataclass(frozen=True, slots=True)
class QualityConfig:
    """Calibrated quality thresholds from the profile (no universal constants)."""

    quant_dimension: QuantDimension
    reference_ppl: float
    max_ppl_ratio: float
    kl_enabled: bool
    max_kl: float


@dataclass(frozen=True, slots=True)
class QualityContext:
    """Bundle of inputs for one quality evaluation.

    The ``identity`` is the candidate under test; ``reference_identity`` is the
    identity-bound reference used for calibrated comparison. When KL is enabled,
    all :data:`KL_IDENTITY_FIELDS` must match between the two before any
    divergence comparison proceeds.
    """

    identity: QualityIdentity
    reference_identity: QualityIdentity
    config: QualityConfig
    perplexity_binary: str
    corpora_dir: str
    output_dir: str


@dataclass(frozen=True, slots=True)
class QualityGateResult:
    """Result of one quality gate evaluation."""

    gate_name: str
    status: QualityGateStatus
    reason: str = ""
    metrics: dict[str, float] = field(default_factory=dict[str, float])


@dataclass(frozen=True, slots=True)
class ReferencePplResult:
    """Reference PPL measurement bound to identity."""

    identity: QualityIdentity
    ppl: float
    corpus_id: str
    corpus_hash: str


@dataclass(frozen=True, slots=True)
class QualityOutcome:
    """Overall quality outcome across all gates for one candidate."""

    status: QualityGateStatus
    quant_dimension: QuantDimension
    reference_ppl: float
    gate_results: tuple[QualityGateResult, ...]
