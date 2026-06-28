"""Evidence row CRUD for the durable trial ledger (T4).

Metrics, telemetry samples, raw artifact references, and sampler checkpoints.
Checkpoints are inserted as ``PENDING`` by the publication protocol and flipped
to ``COMMITTED`` only after the atomic file publish + generation commit pair.
Queries use ``?``-bound parameters only; row materialization lives in
:mod:`llama_optimizer.ledger_records`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from llama_optimizer.ledger_materialize import row_to_checkpoint
from llama_optimizer.ledger_records import (
    CheckpointRecord,
    exec_write,
)
from llama_optimizer.ledger_store import utc_now_iso
from llama_optimizer.lifecycle import CheckpointStatus

if TYPE_CHECKING:
    import sqlite3

    from llama_optimizer.lifecycle import AttemptId, Generation


def upsert_metric(conn: sqlite3.Connection, attempt_id: AttemptId, name: str, value: float) -> None:
    """Insert-or-replace one named metric for an attempt."""
    exec_write(
        conn,
        """INSERT INTO metrics(attempt_id, name, value, recorded_at) VALUES (?,?,?,?)
           ON CONFLICT(attempt_id, name) DO UPDATE SET value = excluded.value,
               recorded_at = excluded.recorded_at""",
        (attempt_id, name, value, utc_now_iso()),
    )


def insert_telemetry(
    conn: sqlite3.Connection,
    attempt_id: AttemptId,
    vram_used_bytes: int,
    peak_vram_bytes: int,
    *,
    breached: bool,
) -> None:
    """Append one telemetry sample (used bytes, peak, breach flag)."""
    exec_write(
        conn,
        """INSERT INTO telemetry(attempt_id, vram_used_bytes, peak_vram_bytes, breached,
               sampled_at) VALUES (?,?,?,?,?)""",
        (attempt_id, vram_used_bytes, peak_vram_bytes, 1 if breached else 0, utc_now_iso()),
    )


def upsert_artifact(
    conn: sqlite3.Connection,
    attempt_id: AttemptId,
    kind: str,
    relative_path: str,
    content_hash: str,
) -> None:
    """Insert-or-replace one raw artifact reference for an attempt."""
    exec_write(
        conn,
        """INSERT INTO artifacts(attempt_id, kind, relative_path, content_hash, recorded_at)
           VALUES (?,?,?,?,?) ON CONFLICT(attempt_id, kind) DO UPDATE SET
               relative_path = excluded.relative_path,
               content_hash = excluded.content_hash, recorded_at = excluded.recorded_at""",
        (attempt_id, kind, relative_path, content_hash, utc_now_iso()),
    )


def upsert_checkpoint(conn: sqlite3.Connection, row: CheckpointRecord) -> None:
    """Insert-or-replace a checkpoint row at its generation."""
    exec_write(
        conn,
        """INSERT INTO checkpoints(generation, run_id, status, relative_path, content_hash,
               optimizer_version, optuna_version, checkpoint_format, published_at)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(generation) DO UPDATE SET status = excluded.status,
               relative_path = excluded.relative_path, content_hash = excluded.content_hash,
               optimizer_version = excluded.optimizer_version,
               optuna_version = excluded.optuna_version,
               checkpoint_format = excluded.checkpoint_format,
               published_at = excluded.published_at""",
        (
            int(row.generation),
            row.run_id,
            row.status.value,
            row.relative_path,
            row.content_hash,
            row.optimizer_version,
            row.optuna_version,
            row.checkpoint_format,
            row.published_at,
        ),
    )


def set_checkpoint_committed(
    conn: sqlite3.Connection, generation: Generation, *, published_at: str
) -> None:
    """Flip a checkpoint row from PENDING to COMMITTED after atomic file publication."""
    exec_write(
        conn,
        "UPDATE checkpoints SET status = ?, published_at = ? WHERE generation = ?",
        (CheckpointStatus.COMMITTED.value, published_at, int(generation)),
    )


def select_checkpoint(conn: sqlite3.Connection, generation: Generation) -> CheckpointRecord | None:
    """Return the checkpoint row for a generation, or None."""
    row = conn.execute(
        "SELECT * FROM checkpoints WHERE generation = ?", (int(generation),)
    ).fetchone()
    return None if row is None else row_to_checkpoint(row)
