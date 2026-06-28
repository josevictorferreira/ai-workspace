"""The authoritative SQLite trial ledger facade (T4).

One optimizer process holds an exclusive ``run.lock`` (flock) for a run; a
second process fails with :class:`RunLockHeldError` without corrupting state.
All lifecycle transitions are asserted against the closed state machine before
any write, so an illegal transition leaves the database byte-for-byte
unchanged. Orphaned in-progress attempts are classified as crashed on open,
never duplicated, and never silently continued. The trial/attempt/evidence
operations live in :mod:`llama_optimizer.ledger_ops`; checkpoint publication
and resume in :mod:`llama_optimizer.ledger_resume`; row CRUD in
:mod:`llama_optimizer.ledger_store` and :mod:`llama_optimizer.ledger_evidence`;
I/O primitives in :mod:`llama_optimizer.ledger_io`; the normalized dump in
:mod:`llama_optimizer.ledger_dump`.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Self, final

from llama_optimizer import ledger_dump, ledger_ids, ledger_io
from llama_optimizer import ledger_ops as ops
from llama_optimizer import ledger_resume as resume_ops
from llama_optimizer import ledger_store as store
from llama_optimizer.ledger_records import (
    RecoveryReport,
    RunIdentity,
    RunRecord,
    TrialConfig,
)
from llama_optimizer.ledger_schema import (
    assert_schema_compatible,
    initialize_schema,
    schema_version,
)
from llama_optimizer.lifecycle import (
    AttemptId,
    NonScoredOutcome,
    RunId,
    RunPhase,
    assert_run_transition,
)

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Mapping

    from llama_optimizer.artifacts import RunArtifactRoot
    from llama_optimizer.ledger_records import AttemptRecord, ResumeResult, TrialRecord
    from llama_optimizer.lifecycle import Generation, ResumeMode, TrialId
    from llama_optimizer.resume import OptimizerVersions


@final
class Ledger:
    """The authoritative, single-writer SQLite trial ledger for one run."""

    def __init__(
        self,
        root: RunArtifactRoot,
        conn: sqlite3.Connection,
        lock_fd: int,
        run: RunRecord,
    ) -> None:
        """Hold the run root, connection, lock fd, and current run record."""
        self._root = root
        self._conn = conn
        self._lock_fd = lock_fd
        self._run = run
        self._run_id = RunId(run.run_id)
        self.recovery = RecoveryReport()

    def __enter__(self) -> Self:
        """Enter the ledger context."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the connection and release the run lock on exit."""
        self.close()

    @property
    def run(self) -> RunRecord:
        """The current run record (refreshed after boundary-advancing writes)."""
        return self._run

    @property
    def connection(self) -> sqlite3.Connection:
        """The underlying connection (read/inspection access for tests and evidence)."""
        return self._conn

    def close(self) -> None:
        """Close the connection and release the exclusive run lock."""
        self._conn.close()
        ledger_io.release_lock(self._lock_fd)

    @classmethod
    def create_run(cls, root: RunArtifactRoot, identity: RunIdentity) -> Ledger:
        """Create a fresh INITIALIZED run, bootstrap the schema, acquire the lock."""
        run_id = root.path.name
        lock_fd = ledger_io.acquire_lock(root.resolve_artifact("run.lock"))
        try:
            conn = ledger_io.connect(root.resolve_artifact("study.sqlite3"))
        except BaseException:
            ledger_io.release_lock(lock_fd)
            raise
        assert_schema_compatible(conn)
        if schema_version(conn) is None:
            initialize_schema(conn, applied_at=ledger_ids.utc_now_iso())
        now = ledger_ids.utc_now_iso()
        run = RunRecord.initial(run_id, identity, now=now)
        with ledger_io.transaction(conn):
            store.insert_run(conn, run)
        return cls(root, conn, lock_fd, run)

    @classmethod
    def open(cls, root: RunArtifactRoot) -> Ledger:
        """Open an existing run, acquire the lock, and recover orphaned attempts."""
        run_id = root.path.name
        lock_fd = ledger_io.acquire_lock(root.resolve_artifact("run.lock"))
        try:
            conn = ledger_io.connect(root.resolve_artifact("study.sqlite3"))
        except BaseException:
            ledger_io.release_lock(lock_fd)
            raise
        assert_schema_compatible(conn)
        run = store.select_run(conn, run_id)
        ledger = cls(root, conn, lock_fd, run)
        ledger.recovery = ledger._recover_orphans()
        return ledger

    def _recover_orphans(self) -> RecoveryReport:
        """Classify orphaned in-progress attempts as crashed before any new work."""
        orphans = store.orphaned_in_progress_attempts(self._conn, self._run_id)
        if not orphans:
            return RecoveryReport()
        orphan_ids: list[str] = []
        now = ledger_ids.utc_now_iso()
        with ledger_io.transaction(self._conn):
            for att in orphans:
                store.nonscore_attempt(
                    self._conn,
                    AttemptId(att.attempt_id),
                    NonScoredOutcome.CRASH,
                    "orphaned: run lock reacquired by a new process",
                    ended_at=now,
                )
                orphan_ids.append(att.attempt_id)
        return RecoveryReport(tuple(orphan_ids))

    def start_run(self) -> None:
        """Move the run INITIALIZED -> RUNNING."""
        assert_run_transition(self._run.phase, RunPhase.RUNNING, run_id=self._run_id)
        self._advance_run(RunPhase.RUNNING)

    def complete_run(self) -> None:
        """Move the run RUNNING -> COMPLETED."""
        assert_run_transition(self._run.phase, RunPhase.COMPLETED, run_id=self._run_id)
        self._advance_run(RunPhase.COMPLETED)

    def _advance_run(self, phase: RunPhase) -> None:
        with ledger_io.transaction(self._conn):
            store.update_run_phase(
                self._conn, self._run_id, phase, updated_at=ledger_ids.utc_now_iso()
            )
        self._run = store.select_run(self._conn, self._run_id)

    def create_trial(self, config: TrialConfig) -> TrialRecord:
        """Idempotently create a PENDING trial for a config."""
        return ops.create_trial(self._conn, self._run_id, config)

    def start_trial(self, trial_id: TrialId) -> TrialRecord:
        """Move a trial PENDING -> RUNNING."""
        return ops.start_trial(self._conn, trial_id)

    def commit_trial(
        self,
        trial_id: TrialId,
        *,
        generation: Generation,
        optuna_trial_number: int,
    ) -> None:
        """Move a trial RUNNING -> COMMITTED at a generation."""
        ops.commit_trial(
            self._conn,
            trial_id,
            generation=generation,
            optuna_trial_number=optuna_trial_number,
        )

    def abandon_trial(self, trial_id: TrialId, *, outcome: NonScoredOutcome, reason: str) -> None:
        """Move a trial RUNNING -> ABANDONED with a non-scored outcome."""
        ops.abandon_trial(self._conn, trial_id, outcome=outcome, reason=reason)

    def start_attempt(
        self,
        trial_id: TrialId,
        *,
        parent_attempt_id: AttemptId | None = None,
    ) -> AttemptRecord:
        """Create + begin the next attempt, enforcing bounded transient retry."""
        return ops.start_attempt(
            self._conn,
            self._run,
            trial_id,
            parent_attempt_id=parent_attempt_id,
        )

    def succeed_attempt(self, attempt_id: AttemptId) -> None:
        """Move an attempt IN_PROGRESS -> SUCCEEDED."""
        ops.succeed_attempt(self._conn, attempt_id)

    def end_attempt_nonscored(
        self,
        attempt_id: AttemptId,
        *,
        outcome: NonScoredOutcome,
        reason: str,
    ) -> None:
        """Move an attempt IN_PROGRESS -> NON_SCORED with a closed outcome."""
        ops.end_attempt_nonscored(self._conn, attempt_id, outcome=outcome, reason=reason)

    def record_metrics(self, attempt_id: AttemptId, metrics: Mapping[str, float]) -> None:
        """Record named metrics for an attempt."""
        ops.record_metrics(self._conn, attempt_id, metrics)

    def record_telemetry(
        self,
        attempt_id: AttemptId,
        *,
        vram_used_bytes: int,
        peak_vram_bytes: int,
        breached: bool,
    ) -> None:
        """Append one telemetry sample for an attempt."""
        ops.record_telemetry(
            self._conn,
            attempt_id,
            vram_used_bytes=vram_used_bytes,
            peak_vram_bytes=peak_vram_bytes,
            breached=breached,
        )

    def record_artifact(
        self,
        attempt_id: AttemptId,
        *,
        kind: str,
        relative_path: str,
        content_hash: str,
    ) -> None:
        """Record a raw artifact reference for an attempt."""
        ops.record_artifact(
            self._conn,
            attempt_id,
            kind=kind,
            relative_path=relative_path,
            content_hash=content_hash,
        )

    def publish_checkpoint(self, *, generation: Generation, content: bytes) -> None:
        """Atomically publish a sampler checkpoint and advance the committed boundary."""
        self._run = resume_ops.publish_checkpoint(
            self._root,
            self._conn,
            self._run,
            generation=generation,
            content=content,
        )

    def resume(self, mode: ResumeMode, expected: OptimizerVersions) -> ResumeResult:
        """Return the resume verdict and actionable facts (history or exact)."""
        result = resume_ops.resume(
            self._root,
            self._conn,
            self._run_id,
            mode=mode,
            expected=expected,
        )
        return replace(result, recovery=self.recovery)

    def dump(self) -> ledger_dump.LedgerDump:
        """Return a normalized, JSON-serializable snapshot of the whole ledger."""
        return ledger_dump.dump(self._conn, self._run_id)
