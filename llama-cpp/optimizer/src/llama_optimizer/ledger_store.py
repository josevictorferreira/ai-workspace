"""Lifecycle row CRUD and deterministic IDs for the durable trial ledger (T4).

Queries use ``?``-bound parameters only (no interpolation). IDs are
deterministic content hashes: the same run+config -> the same trial, and the
same trial+attempt number -> the same attempt (idempotent, no duplicates).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from llama_optimizer.ledger_materialize import (
    row_index_int,
    row_index_opt_int,
    row_to_attempt,
    row_to_run,
    row_to_trial,
)
from llama_optimizer.ledger_records import (
    AttemptRecord,
    RunRecord,
    TrialRecord,
    exec_write,
)
from llama_optimizer.lifecycle import (
    AttemptId,
    AttemptPhase,
    ConfigHash,
    Generation,
    NonScoredOutcome,
    RunPhase,
    TrialId,
    TrialPhase,
)

if TYPE_CHECKING:
    import sqlite3


def utc_now_iso() -> str:
    """Return the current UTC instant as a deterministic ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def derive_trial_id(run_id: str, config_id: str, config_hash: ConfigHash) -> TrialId:
    """Derive a deterministic trial id from run + config identity."""
    digest = hashlib.sha256(f"{run_id}\x1f{config_id}\x1f{config_hash}".encode()).hexdigest()
    return TrialId("t-" + digest[:16])


def derive_attempt_id(trial_id: TrialId, attempt_number: int) -> AttemptId:
    """Derive a deterministic attempt id from trial + attempt number."""
    digest = hashlib.sha256(f"{trial_id}\x1f{attempt_number}".encode()).hexdigest()
    return AttemptId("a-" + digest[:16])


# --- runs -------------------------------------------------------------------
def insert_run(conn: sqlite3.Connection, row: RunRecord) -> None:
    """Insert a fresh run row in INITIALIZED phase."""
    exec_write(
        conn,
        """INSERT INTO runs(run_id, phase, manifest_hash, config_hash, optimizer_version,
               optuna_version, checkpoint_format, max_retries, process_group_pid, seed,
               termination_reason, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            row.run_id,
            row.phase.value,
            row.manifest_hash,
            row.config_hash,
            row.optimizer_version,
            row.optuna_version,
            row.checkpoint_format,
            row.max_retries,
            row.process_group_pid,
            row.seed,
            row.termination_reason,
            row.created_at,
            row.updated_at,
        ),
    )


def select_run(conn: sqlite3.Connection, run_id: str) -> RunRecord:
    """Return the run row, raising KeyError if absent."""
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        raise KeyError(run_id)
    return row_to_run(row)


def update_run_phase(
    conn: sqlite3.Connection, run_id: str, phase: RunPhase, *, updated_at: str
) -> None:
    """Advance a run's phase (caller asserts the transition is legal first)."""
    exec_write(
        conn,
        "UPDATE runs SET phase = ?, updated_at = ? WHERE run_id = ?",
        (phase.value, updated_at, run_id),
    )


def update_committed_generation(
    conn: sqlite3.Connection, run_id: str, generation: Generation, *, updated_at: str
) -> None:
    """Set the run's latest fully-published committed boundary."""
    exec_write(
        conn,
        "UPDATE runs SET committed_generation = ?, updated_at = ? WHERE run_id = ?",
        (int(generation), updated_at, run_id),
    )


# --- trials -----------------------------------------------------------------
def select_trial_by_config(
    conn: sqlite3.Connection, run_id: str, config_hash: ConfigHash
) -> TrialRecord | None:
    """Return the existing trial for a config, or None (idempotent create basis)."""
    row = conn.execute(
        "SELECT * FROM trials WHERE run_id = ? AND config_hash = ?", (run_id, config_hash)
    ).fetchone()
    return None if row is None else row_to_trial(row)


def insert_trial(conn: sqlite3.Connection, row: TrialRecord) -> None:
    """Insert a fresh PENDING trial row."""
    exec_write(
        conn,
        """INSERT INTO trials(trial_id, run_id, config_id, config_hash, candidate_id, backend,
               quant, phase, retry_parent_attempt_id, created_at, updated_at, termination_reason)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            row.trial_id,
            row.run_id,
            row.config_id,
            row.config_hash,
            row.candidate_id,
            row.backend,
            row.quant,
            row.phase.value,
            row.retry_parent_attempt_id,
            row.created_at,
            row.updated_at,
            row.termination_reason,
        ),
    )


def select_trial(conn: sqlite3.Connection, trial_id: TrialId) -> TrialRecord:
    """Return the trial row, raising KeyError if absent."""
    row = conn.execute("SELECT * FROM trials WHERE trial_id = ?", (trial_id,)).fetchone()
    if row is None:
        raise KeyError(trial_id)
    return row_to_trial(row)


def update_trial_phase(
    conn: sqlite3.Connection, trial_id: TrialId, phase: TrialPhase, *, updated_at: str
) -> None:
    """Advance a trial's phase (caller asserts the transition is legal first)."""
    exec_write(
        conn,
        "UPDATE trials SET phase = ?, updated_at = ? WHERE trial_id = ?",
        (phase.value, updated_at, trial_id),
    )


def commit_trial(
    conn: sqlite3.Connection,
    trial_id: TrialId,
    generation: Generation,
    optuna_trial_number: int,
    *,
    updated_at: str,
) -> None:
    """Mark a trial COMMITTED at a generation with its Optuna trial number."""
    exec_write(
        conn,
        """UPDATE trials SET phase = ?, committed_generation = ?, optuna_trial_number = ?,
               updated_at = ? WHERE trial_id = ?""",
        (TrialPhase.COMMITTED.value, int(generation), optuna_trial_number, updated_at, trial_id),
    )


def abandon_trial(
    conn: sqlite3.Connection,
    trial_id: TrialId,
    outcome: NonScoredOutcome,
    reason: str,
    *,
    updated_at: str,
) -> None:
    """Mark a trial ABANDONED with a non-scored outcome and reason."""
    exec_write(
        conn,
        """UPDATE trials SET phase = ?, outcome = ?, termination_reason = ?, updated_at = ?
           WHERE trial_id = ?""",
        (TrialPhase.ABANDONED.value, outcome.value, reason, updated_at, trial_id),
    )


def latest_committed_trial_generation(conn: sqlite3.Connection, run_id: str) -> Generation | None:
    """Return the highest committed_generation among COMMITTED trials, or None."""
    row = conn.execute(
        "SELECT MAX(committed_generation) FROM trials WHERE run_id = ? AND phase = ?",
        (run_id, TrialPhase.COMMITTED.value),
    ).fetchone()
    value = row_index_opt_int(row)
    return Generation(value) if value is not None else None


# --- attempts ---------------------------------------------------------------
def next_attempt_number(conn: sqlite3.Connection, trial_id: TrialId) -> int:
    """Return the next 1-based attempt number for a trial."""
    row = conn.execute(
        "SELECT COALESCE(MAX(attempt_number), 0) FROM attempts WHERE trial_id = ?", (trial_id,)
    ).fetchone()
    return row_index_int(row) + 1


def insert_attempt(conn: sqlite3.Connection, row: AttemptRecord) -> None:
    """Insert a fresh attempt row in PENDING phase."""
    exec_write(
        conn,
        """INSERT INTO attempts(attempt_id, trial_id, run_id, attempt_number, phase,
               process_group_pid, parent_attempt_id, started_at, ended_at, phase_deadline,
               termination_reason)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            row.attempt_id,
            row.trial_id,
            row.run_id,
            row.attempt_number,
            row.phase.value,
            row.process_group_pid,
            row.parent_attempt_id,
            row.started_at,
            row.ended_at,
            row.phase_deadline,
            row.termination_reason,
        ),
    )


def select_attempt(conn: sqlite3.Connection, attempt_id: AttemptId) -> AttemptRecord:
    """Return the attempt row, raising KeyError if absent."""
    row = conn.execute("SELECT * FROM attempts WHERE attempt_id = ?", (attempt_id,)).fetchone()
    if row is None:
        raise KeyError(attempt_id)
    return row_to_attempt(row)


def begin_attempt(conn: sqlite3.Connection, attempt_id: AttemptId, *, started_at: str) -> None:
    """Move an attempt PENDING -> IN_PROGRESS (caller asserts the transition)."""
    exec_write(
        conn,
        "UPDATE attempts SET phase = ?, started_at = ? WHERE attempt_id = ?",
        (AttemptPhase.IN_PROGRESS.value, started_at, attempt_id),
    )


def succeed_attempt(conn: sqlite3.Connection, attempt_id: AttemptId, *, ended_at: str) -> None:
    """Mark an attempt SUCCEEDED with no outcome."""
    exec_write(
        conn,
        "UPDATE attempts SET phase = ?, ended_at = ? WHERE attempt_id = ?",
        (AttemptPhase.SUCCEEDED.value, ended_at, attempt_id),
    )


def nonscore_attempt(
    conn: sqlite3.Connection,
    attempt_id: AttemptId,
    outcome: NonScoredOutcome,
    reason: str,
    *,
    ended_at: str,
) -> None:
    """Mark an attempt NON_SCORED with a closed non-scored outcome and reason."""
    exec_write(
        conn,
        """UPDATE attempts SET phase = ?, outcome = ?, termination_reason = ?, ended_at = ?
           WHERE attempt_id = ?""",
        (AttemptPhase.NON_SCORED.value, outcome.value, reason, ended_at, attempt_id),
    )


def orphaned_in_progress_attempts(conn: sqlite3.Connection, run_id: str) -> list[AttemptRecord]:
    """Return every still-IN_PROGRESS attempt (orphans when reopening a run)."""
    rows = conn.execute(
        "SELECT * FROM attempts WHERE run_id = ? AND phase = ?",
        (run_id, AttemptPhase.IN_PROGRESS.value),
    ).fetchall()
    return [row_to_attempt(r) for r in rows]


def attempt_count(conn: sqlite3.Connection, trial_id: TrialId) -> int:
    """Return the total number of attempts (terminal + in-progress) for a trial."""
    row = conn.execute("SELECT COUNT(*) FROM attempts WHERE trial_id = ?", (trial_id,)).fetchone()
    return row_index_int(row)
