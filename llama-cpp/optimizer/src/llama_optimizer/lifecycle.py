"""Closed lifecycle state machine for the durable trial ledger (T4).

This module is pure: closed phase/outcome enums, legal-transition tables,
typed transition errors, and bounded retry eligibility. The durable ledger
(:mod:`llama_optimizer.ledger`) is the only caller that mutates rows; nothing
here touches a database or the filesystem. Exact- versus history-resume
verdict lives in :mod:`llama_optimizer.resume`.

Optuna may own candidate suggestion and Pareto bookkeeping, but it must
NOT own lifecycle truth. Every failure outcome here is non-scored; only
confirmed ``transient-failure`` is retry-eligible, and only within an
explicitly bounded, lineage-preserving budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NewType

# --- Semantic primitives ---------------------------------------------------
# Distinct ids/counts so the compiler refuses to mix a run id with a trial id,
# or a search-boundary generation with an arbitrary integer.
RunId = NewType("RunId", str)
TrialId = NewType("TrialId", str)
AttemptId = NewType("AttemptId", str)
Generation = NewType("Generation", int)
AttemptNumber = NewType("AttemptNumber", int)
ConfigHash = NewType("ConfigHash", str)


class RunPhase(StrEnum):
    """Closed run lifecycle phases."""

    INITIALIZED = "initialized"
    RUNNING = "running"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class TrialPhase(StrEnum):
    """Closed trial lifecycle phases."""

    PENDING = "pending"
    RUNNING = "running"
    COMMITTED = "committed"
    ABANDONED = "abandoned"


class AttemptPhase(StrEnum):
    """Closed attempt lifecycle phases."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    NON_SCORED = "non_scored"


class NonScoredOutcome(StrEnum):
    """Closed non-scored attempt outcomes (failures are never scored as zero)."""

    INVALID = "invalid"
    UNSUPPORTED = "unsupported"
    RESOURCE_INFEASIBLE = "resource-infeasible"
    DETERMINISTIC_LOAD_FAILURE = "deterministic-load-failure"
    QUALITY_FAILURE = "quality-failure"
    MEASUREMENT_FAILURE = "measurement-failure"
    TELEMETRY_LOSS = "telemetry-loss"
    CRASH = "crash"
    HANG = "hang"
    TRANSIENT_FAILURE = "transient-failure"
    CANCELLED = "cancelled"
    CLEANUP_FAILURE = "cleanup-failure"


class ResumeMode(StrEnum):
    """History resume inspects committed records; exact resume restores sampler state."""

    HISTORY = "history"
    EXACT = "exact"


class CheckpointStatus(StrEnum):
    """Publication status of an atomically committed sampler checkpoint."""

    PENDING = "pending"
    COMMITTED = "committed"


# --- Closed terminal sets + transition tables ------------------------------
TERMINAL_RUN_PHASES: Final[frozenset[RunPhase]] = frozenset(
    {RunPhase.COMPLETED, RunPhase.ABANDONED}
)
TERMINAL_TRIAL_PHASES: Final[frozenset[TrialPhase]] = frozenset(
    {TrialPhase.COMMITTED, TrialPhase.ABANDONED}
)
TERMINAL_ATTEMPT_PHASES: Final[frozenset[AttemptPhase]] = frozenset(
    {AttemptPhase.SUCCEEDED, AttemptPhase.NON_SCORED}
)
RETRY_ELIGIBLE_OUTCOMES: Final[frozenset[NonScoredOutcome]] = frozenset(
    {NonScoredOutcome.TRANSIENT_FAILURE}
)

LEGAL_RUN_TRANSITIONS: Final[dict[RunPhase, frozenset[RunPhase]]] = {
    RunPhase.INITIALIZED: frozenset({RunPhase.RUNNING}),
    RunPhase.RUNNING: frozenset({RunPhase.COMPLETED, RunPhase.ABANDONED}),
    RunPhase.COMPLETED: frozenset(),
    RunPhase.ABANDONED: frozenset(),
}
LEGAL_TRIAL_TRANSITIONS: Final[dict[TrialPhase, frozenset[TrialPhase]]] = {
    TrialPhase.PENDING: frozenset({TrialPhase.RUNNING}),
    TrialPhase.RUNNING: frozenset({TrialPhase.COMMITTED, TrialPhase.ABANDONED}),
    TrialPhase.COMMITTED: frozenset(),
    TrialPhase.ABANDONED: frozenset(),
}
LEGAL_ATTEMPT_TRANSITIONS: Final[dict[AttemptPhase, frozenset[AttemptPhase]]] = {
    AttemptPhase.PENDING: frozenset({AttemptPhase.IN_PROGRESS}),
    AttemptPhase.IN_PROGRESS: frozenset({AttemptPhase.SUCCEEDED, AttemptPhase.NON_SCORED}),
    AttemptPhase.SUCCEEDED: frozenset(),
    AttemptPhase.NON_SCORED: frozenset(),
}


# --- Typed lifecycle errors -------------------------------------------------
@dataclass
class TransitionError(ValueError):
    """A run/trial/attempt phase transition was illegal (no DB mutation occurs)."""

    entity: str
    entity_id: str
    current: str
    attempted: str
    reason: str = ""

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        msg = f"illegal {self.entity} transition {self.current!r}->{self.attempted!r}"
        if self.reason:
            msg = f"{msg} for {self.entity_id!r}: {self.reason}"
        else:
            msg = f"{msg} for {self.entity_id!r}"
        Exception.__init__(self, msg)


@dataclass
class RetryExhaustedError(ValueError):
    """A transient failure occurred but the bounded retry budget is spent."""

    trial_id: TrialId
    attempted_count: int
    max_retries: int

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        msg = "".join(
            (
                f"retry exhausted: trial {self.trial_id!r}, ",
                f"{self.attempted_count} attempts (max 1 initial + {self.max_retries} retries)",
            )
        )
        Exception.__init__(self, msg)


# --- Pure transition + retry predicates -------------------------------------
def is_terminal_run(phase: RunPhase) -> bool:
    """Return whether ``phase`` is a terminal run phase."""
    return phase in TERMINAL_RUN_PHASES


def is_terminal_trial(phase: TrialPhase) -> bool:
    """Return whether ``phase`` is a terminal trial phase."""
    return phase in TERMINAL_TRIAL_PHASES


def is_terminal_attempt(phase: AttemptPhase) -> bool:
    """Return whether ``phase`` is a terminal attempt phase."""
    return phase in TERMINAL_ATTEMPT_PHASES


def is_retry_eligible(outcome: NonScoredOutcome) -> bool:
    """Return whether ``outcome`` is the sole retry-eligible outcome."""
    return outcome in RETRY_ELIGIBLE_OUTCOMES


def can_retry(*, outcome: NonScoredOutcome, attempt_count: int, max_retries: int) -> bool:
    """Return whether a new attempt is permitted for ``outcome`` within the bound.

    ``attempt_count`` is the number of already-attempted attempts (>=1 for the
    initial). ``max_retries`` is the additional retries permitted after the
    initial attempt. Only confirmed ``transient-failure`` is eligible, and only
    while ``attempt_count < 1 + max_retries``.
    """
    if not is_retry_eligible(outcome):
        return False
    if max_retries < 0:
        return False
    return attempt_count < 1 + max_retries


def assert_run_transition(current: RunPhase, target: RunPhase, *, run_id: RunId) -> None:
    """Raise :class:`TransitionError` unless ``current->target`` is a legal run transition."""
    if target not in LEGAL_RUN_TRANSITIONS[current]:
        raise TransitionError(
            entity="run", entity_id=str(run_id), current=current.value, attempted=target.value
        )


def assert_trial_transition(current: TrialPhase, target: TrialPhase, *, trial_id: TrialId) -> None:
    """Raise :class:`TransitionError` unless ``current->target`` is a legal trial transition."""
    if target not in LEGAL_TRIAL_TRANSITIONS[current]:
        raise TransitionError(
            entity="trial", entity_id=str(trial_id), current=current.value, attempted=target.value
        )


def assert_attempt_transition(
    current: AttemptPhase, target: AttemptPhase, *, attempt_id: AttemptId
) -> None:
    """Raise :class:`TransitionError` unless ``current->target`` is a legal attempt transition."""
    if target not in LEGAL_ATTEMPT_TRANSITIONS[current]:
        raise TransitionError(
            entity="attempt",
            entity_id=str(attempt_id),
            current=current.value,
            attempted=target.value,
        )
