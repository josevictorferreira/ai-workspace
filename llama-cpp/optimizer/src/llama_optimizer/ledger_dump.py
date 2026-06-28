"""Normalized ledger dump for evidence and inspection (T4).

Reads every committed row into a JSON-serializable mapping using the typed
boundary accessors. The dump is read-only and never mutates the ledger; callers
serialize it with ``json.dumps(..., sort_keys=True, indent=2)`` for byte-stable
evidence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from llama_optimizer.ledger_materialize import (
    row_float,
    row_int,
    row_opt_gen,
    row_opt_int,
    row_opt_str,
    row_str,
)

if TYPE_CHECKING:
    import sqlite3


def dump(conn: sqlite3.Connection, run_id: str) -> dict[str, object]:
    """Return a normalized, JSON-serializable snapshot of the whole ledger."""
    return {
        "run_id": run_id,
        "schema_version": _scalar(conn, "SELECT schema_version FROM schema_meta LIMIT 1"),
        "run": _run(conn, run_id),
        "trials": _trials(conn, run_id),
        "checkpoints": _checkpoints(conn, run_id),
    }


def _scalar(conn: sqlite3.Connection, sql: str) -> object:
    row = conn.execute(sql).fetchone()
    return row[0]


def _run(conn: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        return {}
    return {
        "phase": row_str(row, "phase"),
        "optimizer_version": row_str(row, "optimizer_version"),
        "optuna_version": row_str(row, "optuna_version"),
        "checkpoint_format": row_str(row, "checkpoint_format"),
        "manifest_hash": row_str(row, "manifest_hash"),
        "config_hash": row_str(row, "config_hash"),
        "max_retries": row_int(row, "max_retries"),
        "seed": row_int(row, "seed"),
        "committed_generation": row_opt_gen(row, "committed_generation"),
        "termination_reason": row_str(row, "termination_reason"),
        "created_at": row_str(row, "created_at"),
        "updated_at": row_str(row, "updated_at"),
    }


def _trials(conn: sqlite3.Connection, run_id: str) -> list[dict[str, object]]:
    trials = conn.execute(
        "SELECT * FROM trials WHERE run_id = ? ORDER BY created_at", (run_id,)
    ).fetchall()
    result: list[dict[str, object]] = []
    for t in trials:
        trial_id = row_str(t, "trial_id")
        result.append(
            {
                "trial_id": trial_id,
                "config_id": row_str(t, "config_id"),
                "config_hash": row_str(t, "config_hash"),
                "candidate_id": row_str(t, "candidate_id"),
                "backend": row_str(t, "backend"),
                "quant": row_str(t, "quant"),
                "phase": row_str(t, "phase"),
                "outcome": row_opt_str(t, "outcome"),
                "optuna_trial_number": row_opt_int(t, "optuna_trial_number"),
                "committed_generation": row_opt_gen(t, "committed_generation"),
                "retry_parent_attempt_id": row_opt_str(t, "retry_parent_attempt_id"),
                "termination_reason": row_str(t, "termination_reason"),
                "created_at": row_str(t, "created_at"),
                "updated_at": row_str(t, "updated_at"),
                "attempts": _attempts(conn, trial_id),
            }
        )
    return result


def _attempts(conn: sqlite3.Connection, trial_id: str) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT * FROM attempts WHERE trial_id = ? ORDER BY attempt_number", (trial_id,)
    ).fetchall()
    result: list[dict[str, object]] = []
    for a in rows:
        attempt_id = row_str(a, "attempt_id")
        result.append(
            {
                "attempt_id": attempt_id,
                "attempt_number": row_int(a, "attempt_number"),
                "phase": row_str(a, "phase"),
                "outcome": row_opt_str(a, "outcome"),
                "process_group_pid": row_int(a, "process_group_pid"),
                "parent_attempt_id": row_opt_str(a, "parent_attempt_id"),
                "started_at": row_str(a, "started_at"),
                "ended_at": row_opt_str(a, "ended_at"),
                "phase_deadline": row_opt_str(a, "phase_deadline"),
                "termination_reason": row_str(a, "termination_reason"),
                "metrics": _metrics(conn, attempt_id),
                "telemetry": _telemetry(conn, attempt_id),
                "artifacts": _artifacts(conn, attempt_id),
            }
        )
    return result


def _metrics(conn: sqlite3.Connection, attempt_id: str) -> dict[str, float]:
    rows = conn.execute(
        "SELECT name, value FROM metrics WHERE attempt_id = ? ORDER BY name", (attempt_id,)
    ).fetchall()
    return {row_str(r, "name"): row_float(r, "value") for r in rows}


def _telemetry(conn: sqlite3.Connection, attempt_id: str) -> list[dict[str, object]]:
    rows = conn.execute(
        """SELECT vram_used_bytes, peak_vram_bytes, breached, sampled_at
           FROM telemetry WHERE attempt_id = ? ORDER BY sampled_at""",
        (attempt_id,),
    ).fetchall()
    return [
        {
            "vram_used_bytes": row_int(r, "vram_used_bytes"),
            "peak_vram_bytes": row_int(r, "peak_vram_bytes"),
            "breached": bool(row_int(r, "breached")),
            "sampled_at": row_str(r, "sampled_at"),
        }
        for r in rows
    ]


def _artifacts(conn: sqlite3.Connection, attempt_id: str) -> list[dict[str, str]]:
    rows = conn.execute(
        """SELECT kind, relative_path, content_hash, recorded_at
           FROM artifacts WHERE attempt_id = ? ORDER BY kind""",
        (attempt_id,),
    ).fetchall()
    return [
        {
            "kind": row_str(r, "kind"),
            "relative_path": row_str(r, "relative_path"),
            "content_hash": row_str(r, "content_hash"),
            "recorded_at": row_str(r, "recorded_at"),
        }
        for r in rows
    ]


def _checkpoints(conn: sqlite3.Connection, run_id: str) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT * FROM checkpoints WHERE run_id = ? ORDER BY generation", (run_id,)
    ).fetchall()
    return [
        {
            "generation": row_int(r, "generation"),
            "status": row_str(r, "status"),
            "relative_path": row_str(r, "relative_path"),
            "content_hash": row_str(r, "content_hash"),
            "optimizer_version": row_str(r, "optimizer_version"),
            "optuna_version": row_str(r, "optuna_version"),
            "checkpoint_format": row_str(r, "checkpoint_format"),
            "published_at": row_str(r, "published_at"),
        }
        for r in rows
    ]
