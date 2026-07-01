"""Immutable value types for deterministic optimizer reports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llama_optimizer.ledger_dump import LedgerDump


class MetricDirection(StrEnum):
    """Whether a larger or smaller metric value is preferred."""

    BENEFIT = "benefit"
    COST = "cost"


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """One required balanced-selection metric."""

    name: str
    direction: MetricDirection
    weight: float


@dataclass(frozen=True, slots=True)
class CandidateConfig:
    """Immutable identity and launch flags for one finalist configuration."""

    config_id: str
    model_path: str
    nix_package: str
    server_flags: tuple[str, ...]
    constraint_violations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportMetadata:
    """Manifest, environment, resume, and reproduction metadata."""

    manifest_id: str
    manifest_hash: str
    provenance: tuple[str, ...]
    environment: tuple[str, ...]
    resume_mode: str
    drift_diagnostics: tuple[str, ...]
    reproduction_commands: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportRequest:
    """All authoritative inputs needed to generate one report."""

    ledger: LedgerDump
    metadata: ReportMetadata
    configs: tuple[CandidateConfig, ...]
    metrics: tuple[MetricSpec, ...]


@dataclass
class ReportWeightError(ValueError):
    """The configured balanced metric set is malformed."""

    reason: str

    def __post_init__(self) -> None:
        """Initialize the exception with the reason."""
        Exception.__init__(self, self.reason)


@dataclass(frozen=True, slots=True)
class MetricContribution:
    """Transparent contribution of one metric to a candidate score."""

    name: str
    direction: MetricDirection
    value: float
    minimum: float
    maximum: float
    normalized: float
    weight: float
    contribution: float


@dataclass(frozen=True, slots=True)
class ReportCandidate:
    """One Pareto-frontier candidate with reproducible balanced scoring."""

    config: CandidateConfig
    metrics: tuple[tuple[str, float], ...]
    contributions: tuple[MetricContribution, ...]
    score: float


@dataclass(frozen=True, slots=True)
class ReportResult:
    """In-memory report plus its deterministic serialized forms."""

    frontier: tuple[ReportCandidate, ...]
    selected: ReportCandidate | None
    incomplete: tuple[str, ...]
    json_text: str
    markdown_text: str
