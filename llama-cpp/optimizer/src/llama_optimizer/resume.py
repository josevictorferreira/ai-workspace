"""Exact- versus history-resume verdict for the durable trial ledger (T4).

History resume is read-only inspection of committed records and never
restores sampler state. Exact-sequence resume requires a version- and
generation-compatible sampler checkpoint aligned to the latest committed
search boundary. Any mismatch must fail closed with a typed reason rather
than silently recreating a seeded sampler and claiming exactness.

This module is pure: it consumes a :class:`ResumeRequest` (observed run
facts) plus :class:`OptimizerVersions` (current process identity) and
returns a :class:`ResumeVerdict`. The durable ledger
(:mod:`llama_optimizer.ledger`) collects those facts and raises
:class:`ExactResumeUnavailableError` when exact resume is impossible.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llama_optimizer.lifecycle import Generation, ResumeMode


class ResumeIncompatibilityReason(StrEnum):
    """Closed set of reasons exact resume must fail closed."""

    OPTIMIZER_VERSION_MISMATCH = "optimizer-version-mismatch"
    OPTUNA_VERSION_MISMATCH = "optuna-version-mismatch"
    CHECKPOINT_FORMAT_MISMATCH = "checkpoint-format-mismatch"
    MISSING_CHECKPOINT = "missing-checkpoint"
    CORRUPT_CHECKPOINT = "corrupt-checkpoint"
    STALE_GENERATION = "stale-generation"
    ORPHAN_IN_PROGRESS = "orphan-in-progress"
    NO_LATEST_BOUNDARY = "no-latest-boundary"
    PARTIAL_PUBLICATION = "partial-publication"


@dataclass
class ExactResumeUnavailableError(ValueError):
    """Exact-sequence resume is impossible; recovery or history resume is required."""

    reason: ResumeIncompatibilityReason
    detail: str = ""

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        msg = f"exact resume unavailable: {self.reason.value}"
        if self.detail:
            msg = f"{msg}: {self.detail}"
        Exception.__init__(self, msg)


@dataclass(frozen=True, slots=True)
class CheckpointIdentity:
    """Version-bound identity of an atomically published sampler checkpoint."""

    optimizer_version: str
    optuna_version: str
    checkpoint_format: str
    generation: Generation


@dataclass(frozen=True, slots=True)
class OptimizerVersions:
    """The current optimizer process's pinned versions (the exact-resume expectation)."""

    optimizer_version: str
    optuna_version: str
    checkpoint_format: str


@dataclass(frozen=True, slots=True)
class ResumeRequest:
    """The observed run facts a resume verdict is computed from."""

    mode: ResumeMode
    run_optimizer_version: str
    run_optuna_version: str
    latest_committed_generation: Generation | None
    latest_trial_generation: Generation | None
    checkpoint: CheckpointIdentity | None
    has_orphan_in_progress: bool


@dataclass(frozen=True, slots=True)
class ResumeVerdict:
    """The pure verdict for a resume attempt: eligible + incompatibility reason."""

    mode: ResumeMode
    eligible: bool
    reason: ResumeIncompatibilityReason | None
    detail: str


def check_exact_resume(request: ResumeRequest, expected: OptimizerVersions) -> ResumeVerdict:
    """Return the pure resume verdict for ``request`` against ``expected`` versions.

    History resume is always eligible (read-only inspection, no sampler
    continuity). Exact resume requires a matching optimizer/Optuna/checkpoint
    format whose generation equals both the latest committed run boundary and
    the latest committed trial boundary, with no orphaned in-progress attempt.
    Any mismatch yields a typed incompatibility reason; the caller must fail
    closed rather than silently recreate a seeded sampler.
    """
    if request.mode.value == "history":
        return ResumeVerdict(mode=request.mode, eligible=True, reason=None, detail="")
    reason, detail = _classify_exact(request, expected)
    return ResumeVerdict(mode=request.mode, eligible=reason is None, reason=reason, detail=detail)


def _classify_exact(
    request: ResumeRequest, expected: OptimizerVersions
) -> tuple[ResumeIncompatibilityReason | None, str]:
    """Classify the first exact-resume incompatibility in priority order.

    Ordered preconditions (not variant dispatch): each ``elif`` only fires once
    prior conditions are known-compatible, so a non-None ``checkpoint`` is
    narrowed before its fields are read.
    """
    reason: ResumeIncompatibilityReason | None = None
    detail = ""
    if request.has_orphan_in_progress:
        reason = ResumeIncompatibilityReason.ORPHAN_IN_PROGRESS
    elif request.run_optimizer_version != expected.optimizer_version:
        reason = ResumeIncompatibilityReason.OPTIMIZER_VERSION_MISMATCH
        detail = f"run={request.run_optimizer_version!r} expected={expected.optimizer_version!r}"
    elif request.run_optuna_version != expected.optuna_version:
        reason = ResumeIncompatibilityReason.OPTUNA_VERSION_MISMATCH
        detail = f"run={request.run_optuna_version!r} expected={expected.optuna_version!r}"
    elif request.latest_committed_generation is None:
        reason = ResumeIncompatibilityReason.NO_LATEST_BOUNDARY
    elif request.checkpoint is None:
        reason = ResumeIncompatibilityReason.MISSING_CHECKPOINT
        detail = f"generation={request.latest_committed_generation}"
    elif request.checkpoint.checkpoint_format != expected.checkpoint_format:
        reason = ResumeIncompatibilityReason.CHECKPOINT_FORMAT_MISMATCH
        detail = (
            f"checkpoint={request.checkpoint.checkpoint_format!r} "
            f"expected={expected.checkpoint_format!r}"
        )
    elif request.checkpoint.generation != request.latest_committed_generation:
        reason = ResumeIncompatibilityReason.STALE_GENERATION
        detail = (
            f"checkpoint={request.checkpoint.generation} "
            f"boundary={request.latest_committed_generation}"
        )
    elif (
        request.latest_trial_generation is not None
        and request.latest_trial_generation != request.latest_committed_generation
    ):
        reason = ResumeIncompatibilityReason.PARTIAL_PUBLICATION
        detail = (
            f"committed-run-boundary={request.latest_committed_generation} "
            f"committed-trial={request.latest_trial_generation}"
        )
    return reason, detail
