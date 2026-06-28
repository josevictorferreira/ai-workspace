"""Row materialization for the durable trial ledger (T4).

``sqlite3.Row`` values are dynamically typed; the public ``row_*`` accessors
parse a cell exactly once at the boundary (narrowing via ``isinstance``, so no
``Any`` leaks), and ``row_to_*`` build typed records. Interior code receives
typed records and never re-validates (parse, don't validate).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from llama_optimizer.ledger_records import (
    AttemptRecord,
    CheckpointRecord,
    RunRecord,
    TrialRecord,
)
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


def row_str(row: sqlite3.Row, key: str) -> str:
    """Read a required string cell, raising ``TypeError`` if the type differs."""
    value: object = row[key]
    if not isinstance(value, str):
        msg = f"expected str for {key}"
        raise TypeError(msg)
    return value


def row_int(row: sqlite3.Row, key: str) -> int:
    """Read a required integer cell, raising ``TypeError`` if the type differs."""
    value: object = row[key]
    if not isinstance(value, int):
        msg = f"expected int for {key}"
        raise TypeError(msg)
    return value


def row_float(row: sqlite3.Row, key: str) -> float:
    """Read a required float cell, raising ``TypeError`` if the type differs."""
    value: object = row[key]
    if not isinstance(value, (float, int)):
        msg = f"expected float for {key}"
        raise TypeError(msg)
    return float(value)


def row_opt_str(row: sqlite3.Row, key: str) -> str | None:
    """Read an optional string cell (None preserved)."""
    value: object = row[key]
    return value if isinstance(value, str) else None


def row_opt_int(row: sqlite3.Row, key: str) -> int | None:
    """Read an optional integer cell (None preserved)."""
    value: object = row[key]
    return value if isinstance(value, int) else None


def row_opt_gen(row: sqlite3.Row, key: str) -> Generation | None:
    """Read an optional generation (integer) cell as a :class:`Generation`."""
    value: object = row[key]
    return Generation(int(value)) if isinstance(value, int) else None


def row_index_int(row: sqlite3.Row, index: int = 0) -> int:
    """Read a required integer cell by positional index (for COUNT/MAX aggregates)."""
    value: object = row[index]
    if not isinstance(value, int):
        msg = f"expected int at index {index}"
        raise TypeError(msg)
    return value


def row_index_opt_int(row: sqlite3.Row, index: int = 0) -> int | None:
    """Read an optional integer cell by positional index (None preserved for empty MAX)."""
    value: object = row[index]
    return value if isinstance(value, int) else None


def row_to_run(row: sqlite3.Row) -> RunRecord:
    """Materialize a runs row into a :class:`RunRecord`."""
    return RunRecord(
        run_id=RunId(row_str(row, "run_id")),
        phase=RunPhase(row_str(row, "phase")),
        manifest_hash=row_str(row, "manifest_hash"),
        config_hash=row_str(row, "config_hash"),
        optimizer_version=row_str(row, "optimizer_version"),
        optuna_version=row_str(row, "optuna_version"),
        checkpoint_format=row_str(row, "checkpoint_format"),
        max_retries=row_int(row, "max_retries"),
        process_group_pid=row_int(row, "process_group_pid"),
        seed=row_int(row, "seed"),
        committed_generation=row_opt_gen(row, "committed_generation"),
        termination_reason=row_str(row, "termination_reason"),
        created_at=row_str(row, "created_at"),
        updated_at=row_str(row, "updated_at"),
    )


def row_to_trial(row: sqlite3.Row) -> TrialRecord:
    """Materialize a trials row into a :class:`TrialRecord`."""
    outcome = row_opt_str(row, "outcome")
    retry = row_opt_str(row, "retry_parent_attempt_id")
    return TrialRecord(
        trial_id=TrialId(row_str(row, "trial_id")),
        run_id=RunId(row_str(row, "run_id")),
        config_id=row_str(row, "config_id"),
        config_hash=row_str(row, "config_hash"),
        candidate_id=row_str(row, "candidate_id"),
        backend=row_str(row, "backend"),
        quant=row_str(row, "quant"),
        phase=TrialPhase(row_str(row, "phase")),
        outcome=None if outcome is None else NonScoredOutcome(outcome),
        optuna_trial_number=row_opt_int(row, "optuna_trial_number"),
        committed_generation=row_opt_gen(row, "committed_generation"),
        retry_parent_attempt_id=AttemptId(retry) if retry is not None else None,
        created_at=row_str(row, "created_at"),
        updated_at=row_str(row, "updated_at"),
        termination_reason=row_str(row, "termination_reason"),
    )


def row_to_attempt(row: sqlite3.Row) -> AttemptRecord:
    """Materialize an attempts row into an :class:`AttemptRecord`."""
    outcome = row_opt_str(row, "outcome")
    parent = row_opt_str(row, "parent_attempt_id")
    return AttemptRecord(
        attempt_id=AttemptId(row_str(row, "attempt_id")),
        trial_id=TrialId(row_str(row, "trial_id")),
        run_id=RunId(row_str(row, "run_id")),
        attempt_number=row_int(row, "attempt_number"),
        phase=AttemptPhase(row_str(row, "phase")),
        outcome=None if outcome is None else NonScoredOutcome(outcome),
        process_group_pid=row_int(row, "process_group_pid"),
        parent_attempt_id=AttemptId(parent) if parent is not None else None,
        started_at=row_str(row, "started_at"),
        ended_at=row_opt_str(row, "ended_at"),
        phase_deadline=row_opt_str(row, "phase_deadline"),
        termination_reason=row_str(row, "termination_reason"),
    )


def row_to_checkpoint(row: sqlite3.Row) -> CheckpointRecord:
    """Materialize a checkpoints row into a :class:`CheckpointRecord`."""
    return CheckpointRecord(
        generation=Generation(row_int(row, "generation")),
        run_id=RunId(row_str(row, "run_id")),
        status=CheckpointStatus(row_str(row, "status")),
        relative_path=row_str(row, "relative_path"),
        content_hash=row_str(row, "content_hash"),
        optimizer_version=row_str(row, "optimizer_version"),
        optuna_version=row_str(row, "optuna_version"),
        checkpoint_format=row_str(row, "checkpoint_format"),
        published_at=row_str(row, "published_at"),
    )
