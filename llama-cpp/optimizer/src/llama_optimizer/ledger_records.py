"""Typed row records, materialization, result types, and ledger errors (T4).

Row records are frozen, slotted value objects. ``row_to_*`` materialize a
``sqlite3.Row`` into a record at the parse boundary (sqlite values are
dynamically typed, so each field is narrowed to its typed record exactly once
here, never re-validated in the interior). Ledger errors are mutable
``@dataclass`` exceptions (frozen/slots conflict with ``BaseException``
traceback layout, per T2's resolved convention).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from llama_optimizer.lifecycle import (
    AttemptId,
    AttemptPhase,
    CheckpointStatus,
    Generation,
    NonScoredOutcome,
    RunId,
    RunPhase,
    TrialId,
    TrialPhase,
)

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

    from llama_optimizer.resume import ResumeVerdict


# --- Typed ledger errors -----------------------------------------------------
@dataclass
class SchemaMismatchError(ValueError):
    """The on-disk schema version is unknown/incompatible; never auto-upgraded."""

    expected: int
    actual: int

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        Exception.__init__(
            self,
            f"incompatible ledger schema: expected version {self.expected}, found {self.actual}",
        )


@dataclass
class RunLockHeldError(ValueError):
    """Another process holds the exclusive run lock for this run."""

    lock_path: Path
    holder_pid: int

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        Exception.__init__(
            self,
            f"run lock held by pid {self.holder_pid} at {self.lock_path}",
        )


@dataclass
class CheckpointPublicationError(ValueError):
    """An atomic sampler-checkpoint publication failed at a detectable boundary."""

    generation: Generation
    reason: str

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        Exception.__init__(
            self,
            f"checkpoint publication failed at generation {self.generation}: {self.reason}",
        )


@dataclass
class LedgerIntegrityError(ValueError):
    """A ledger integrity invariant was violated (duplicate trial, dangling FK, ...)."""

    constraint: str
    detail: str = ""

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        msg = f"ledger integrity violation: {self.constraint}"
        if self.detail:
            msg = f"{msg}: {self.detail}"
        Exception.__init__(self, msg)


# --- Frozen row records -----------------------------------------------------
@dataclass(frozen=True, slots=True)
class RunIdentity:
    """The immutable identity bundle required to create a run (groups create_run inputs)."""

    manifest_hash: str
    config_hash: str
    optimizer_version: str
    optuna_version: str
    checkpoint_format: str
    max_retries: int
    seed: int
    process_group_pid: int


@dataclass(frozen=True, slots=True)
class TrialConfig:
    """The immutable config identity bundle required to create a trial."""

    config_id: str
    config_hash: str
    candidate_id: str
    backend: str
    quant: str


@dataclass(frozen=True, slots=True)
class RunRecord:
    """One run row (the authoritative run identity and committed boundary)."""

    run_id: RunId
    phase: RunPhase
    manifest_hash: str
    config_hash: str
    optimizer_version: str
    optuna_version: str
    checkpoint_format: str
    max_retries: int
    process_group_pid: int
    seed: int
    committed_generation: Generation | None
    termination_reason: str
    created_at: str
    updated_at: str

    @classmethod
    def initial(cls, run_id: str, identity: RunIdentity, *, now: str) -> RunRecord:
        """Build a fresh INITIALIZED run row from an identity bundle."""
        return cls(
            run_id=RunId(run_id),
            phase=RunPhase.INITIALIZED,
            manifest_hash=identity.manifest_hash,
            config_hash=identity.config_hash,
            optimizer_version=identity.optimizer_version,
            optuna_version=identity.optuna_version,
            checkpoint_format=identity.checkpoint_format,
            max_retries=identity.max_retries,
            process_group_pid=identity.process_group_pid,
            seed=identity.seed,
            committed_generation=None,
            termination_reason="",
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class TrialRecord:
    """One trial row (immutable config identity + lifecycle phase + outcome)."""

    trial_id: TrialId
    run_id: RunId
    config_id: str
    config_hash: str
    candidate_id: str
    backend: str
    quant: str
    phase: TrialPhase
    outcome: NonScoredOutcome | None
    optuna_trial_number: int | None
    committed_generation: Generation | None
    retry_parent_attempt_id: AttemptId | None
    created_at: str
    updated_at: str
    termination_reason: str


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    """One attempt row (process-group PID, phase, outcome, retry lineage)."""

    attempt_id: AttemptId
    trial_id: TrialId
    run_id: RunId
    attempt_number: int
    phase: AttemptPhase
    outcome: NonScoredOutcome | None
    process_group_pid: int
    parent_attempt_id: AttemptId | None
    started_at: str
    ended_at: str | None
    phase_deadline: str | None
    termination_reason: str


@dataclass(frozen=True, slots=True)
class CheckpointRecord:
    """One published sampler checkpoint row (generation + version identity)."""

    generation: Generation
    run_id: str
    status: CheckpointStatus
    relative_path: str
    content_hash: str
    optimizer_version: str
    optuna_version: str
    checkpoint_format: str
    published_at: str


# --- Result types -----------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """Summary of orphan recovery performed when opening an existing run."""

    orphaned_attempt_ids: tuple[str, ...] = field(default_factory=tuple)
    abandoned_trial_ids: tuple[str, ...] = field(default_factory=tuple)
    committed_boundary_unchanged: bool = True


@dataclass(frozen=True, slots=True)
class ResumeResult:
    """The outcome of a resume attempt: the verdict plus actionable facts."""

    verdict: ResumeVerdict
    committed_generation: Generation | None
    checkpoint_path: Path | None
    recovery: RecoveryReport = field(default_factory=RecoveryReport)


# --- Write helper (centralizes discarded cursor) ----------------------------
def exec_write(conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> None:
    """Execute a write statement, discarding its cursor.

    sqlite write statements return a ``Cursor`` that is unused; centralizing the
    single discarded result keeps the call-result check satisfied at one site.
    """
    _ = conn.execute(sql, params)
