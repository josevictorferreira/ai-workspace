"""Core immutable domain primitives for the optimizer profile schema.

Semantic primitives stay distinct via ``NewType`` (zero runtime cost); publisher
SHA-256 and Hugging Face revisions are parsed exactly once at the boundary into
typed values. Weight quantization and KV-cache quantization are deliberately
separate dimensions with separate provenance. No value here is inferred from
file size, and a publisher SHA-256 is never accepted where a Nix SRI hash
belongs (or vice versa).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NewType

# --- Semantic primitives -------------------------------------------------
# Distinct ids/counts/weights so the compiler refuses to mix them.
Sha256Hex = NewType("Sha256Hex", str)
RevisionId = NewType("RevisionId", str)
CandidateId = NewType("CandidateId", str)
BackendId = NewType("BackendId", str)
TemplateName = NewType("TemplateName", str)
CorpusId = NewType("CorpusId", str)
DimensionId = NewType("DimensionId", str)
ContextSize = NewType("ContextSize", int)
VramBytes = NewType("VramBytes", int)
FileBytes = NewType("FileBytes", int)
MaxNativeCombinations = NewType("MaxNativeCombinations", int)
Seed = NewType("Seed", int)
MetricWeight = NewType("MetricWeight", float)
NixPackagePath = NewType("NixPackagePath", str)

_SHA256_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_REVISION_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$")
_NIX_SRI_PREFIX: Final[str] = "sha256-"
_WEIGHT_SUM_TOLERANCE: Final[float] = 1e-9


class Backend(StrEnum):
    """Measured outer backend identity (never an inferable within-study flag)."""

    ROCM = "rocm"
    VULKAN = "vulkan"


class WeightQuant(StrEnum):
    """Publisher weight quantization family (distinct from KV-cache quantization)."""

    Q4_K_M = "Q4_K_M"
    Q5_K_M = "Q5_K_M"
    Q6_K = "Q6_K"
    Q8_0 = "Q8_0"
    BF16 = "BF16"


class KvCacheType(StrEnum):
    """Runtime K/V cache quantization (a separate dimension from weight quantization)."""

    F16 = "f16"
    Q8_0 = "q8_0"
    Q4_0 = "q4_0"


class CandidateRole(StrEnum):
    """A candidate is searched; a reference is an optional high-precision source only."""

    CANDIDATE = "candidate"
    REFERENCE = "reference"


class RecommendationStatus(StrEnum):
    """Finalist recommendation is blocked until identity-bound calibration exists."""

    BLOCKED = "blocked"
    ELIGIBLE = "eligible"


# --- Typed boundary errors -------------------------------------------------
@dataclass
class SchemaError(ValueError):
    """Base typed error for schema-boundary validation failures."""

    field: str
    reason: str

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        Exception.__init__(self, f"{self.field}: {self.reason}")


@dataclass
class InvalidSha256Error(SchemaError):
    """A SHA-256 field was malformed or confused with a Nix SRI hash."""

    value: str = ""


@dataclass
class MutableUrlError(SchemaError):
    """A model URL or revision used a mutable ref instead of a pinned revision."""

    value: str = ""


@dataclass
class IneligibleWeightError(SchemaError):
    """A recommendation weight was non-finite, negative, or did not sum to 1.0."""

    actual_sum: float = 0.0


# --- Boundary parsers -----------------------------------------------------
def parse_sha256(raw: object, *, field: str) -> Sha256Hex:
    """Parse ``raw`` into a :class:`Sha256Hex`, refusing Nix SRI and non-hex tokens."""
    if not isinstance(raw, str):
        raise InvalidSha256Error(field=field, reason="sha256 must be a string", value=repr(raw))
    value = raw.strip().lower()
    if value.startswith(_NIX_SRI_PREFIX):
        raise InvalidSha256Error(
            field=field,
            reason="publisher file_sha256 must not be a Nix SRI 'sha256-...' token",
            value=raw,
        )
    if not _SHA256_PATTERN.match(value):
        raise InvalidSha256Error(
            field=field, reason="sha256 must be exactly 64 lowercase hex digits", value=raw
        )
    return Sha256Hex(value)


def parse_revision(raw: object, *, field: str) -> RevisionId:
    """Parse ``raw`` into a pinned :class:`RevisionId`, refusing mutable refs like ``main``."""
    if not isinstance(raw, str):
        raise MutableUrlError(field=field, reason="revision must be a string", value=repr(raw))
    value = raw.strip().lower()
    if value in {"main", "master", "dev"}:
        raise MutableUrlError(
            field=field, reason="revision must be pinned, not a mutable ref", value=raw
        )
    if not _REVISION_PATTERN.match(value):
        raise MutableUrlError(
            field=field,
            reason="revision must be exactly 40 lowercase hex digits (git sha)",
            value=raw,
        )
    return RevisionId(value)


def parse_metric_weight(raw: object, *, field: str) -> MetricWeight:
    """Parse ``raw`` into a finite :class:`MetricWeight` (NaN/inf rejected)."""
    if not isinstance(raw, int | float):
        raise IneligibleWeightError(field=field, reason="weight must be a number")
    value = float(raw)
    if not math.isfinite(value):
        raise IneligibleWeightError(field=field, reason="weight must be finite", actual_sum=value)
    return MetricWeight(value)


# --- Immutable value objects ----------------------------------------------
@dataclass(frozen=True, slots=True)
class ModelCandidate:
    """One immutable model artifact bound to publisher provenance."""

    candidate_id: CandidateId
    weight_quant: WeightQuant
    role: CandidateRole
    file_sha256: Sha256Hex
    file_bytes: FileBytes
    revision: RevisionId
    url: str
    filename: str
    nix_package: NixPackagePath


@dataclass(frozen=True, slots=True)
class BackendIdentity:
    """A measured outer backend identity and its future Nix package placeholder."""

    backend_id: BackendId
    backend: Backend
    nix_package: NixPackagePath


@dataclass(frozen=True, slots=True)
class TemplateIdentity:
    """Chat-template identity (the GGUF embeds a tool-call template)."""

    name: TemplateName
    sha256: Sha256Hex


@dataclass(frozen=True, slots=True)
class CorpusIdentity:
    """Versioned workload corpus identity."""

    corpus_id: CorpusId
    sha256: Sha256Hex


@dataclass(frozen=True, slots=True)
class LlamaCppBuild:
    """llama.cpp fork/build identity placeholders (T3 binds the real Nix package)."""

    build_label: str
    fork_ref: str


@dataclass(frozen=True, slots=True)
class HardwareSnapshot:
    """Hardware/driver placeholders (T5 binds live driver snapshot)."""

    gpu: str
    rocm_driver_label: str
    vram_total_bytes: VramBytes


@dataclass(frozen=True, slots=True)
class RecommendationWeights:
    """Balanced recommendation weights; validated to be finite, non-negative, summing to 1.0."""

    prompt_throughput: MetricWeight
    generation_throughput: MetricWeight
    ttft_p95: MetricWeight
    request_latency_p95: MetricWeight
    quality_margin: MetricWeight
    vram_headroom: MetricWeight

    def __post_init__(self) -> None:
        """Validate that the six weights are finite, non-negative, and sum to 1.0."""
        weights = self.to_dict()
        for name, value in weights.items():
            if value < 0:
                raise IneligibleWeightError(field=name, reason="weight must be non-negative")
        total = sum(weights.values())
        if not math.isfinite(total) or abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise IneligibleWeightError(
                field="recommendation", reason="weights must sum to 1.0", actual_sum=total
            )

    def to_dict(self) -> dict[str, float]:
        """Return the six weights as a plain mapping in canonical name order."""
        return {
            "prompt_throughput": self.prompt_throughput,
            "generation_throughput": self.generation_throughput,
            "ttft_p95": self.ttft_p95,
            "request_latency_p95": self.request_latency_p95,
            "quality_margin": self.quality_margin,
            "vram_headroom": self.vram_headroom,
        }
