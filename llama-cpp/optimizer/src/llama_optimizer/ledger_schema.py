"""Explicit SQLite schema, versioning, and bootstrap for the durable trial ledger (T4).

The schema is explicit (no ORM, no Alembic, no implicit migration): the DDL is
a module constant, the schema version is a pinned integer stored in
``schema_meta``, and an unknown/incompatible version fails closed rather than
auto-upgrading. Foreign keys are enabled on every connection. The schema owns
runs, trials, attempts, metrics, telemetry samples, artifacts, and checkpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from llama_optimizer.ledger_io import fetch_row
from llama_optimizer.ledger_materialize import row_index_int
from llama_optimizer.ledger_records import SchemaMismatchError, exec_write

if TYPE_CHECKING:
    import sqlite3

# Pinned ledger schema version. Bump only with an explicit migration; an
# on-disk value that differs from this is a hard error, never auto-upgraded.
SCHEMA_VERSION: Final[int] = 1


# DDL is a fixed, literal string (no interpolation of any kind).
_DDL: Final[str] = """
CREATE TABLE IF NOT EXISTS schema_meta (
    schema_version INTEGER PRIMARY KEY,
    applied_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id               TEXT PRIMARY KEY,
    phase                TEXT NOT NULL,
    manifest_hash        TEXT NOT NULL,
    config_hash          TEXT NOT NULL,
    optimizer_version    TEXT NOT NULL,
    optuna_version       TEXT NOT NULL,
    checkpoint_format    TEXT NOT NULL,
    max_retries          INTEGER NOT NULL,
    process_group_pid    INTEGER NOT NULL,
    seed                 INTEGER NOT NULL,
    committed_generation INTEGER,
    termination_reason   TEXT NOT NULL DEFAULT '',
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trials (
    trial_id                TEXT PRIMARY KEY,
    run_id                  TEXT NOT NULL REFERENCES runs(run_id),
    config_id               TEXT NOT NULL,
    config_hash             TEXT NOT NULL,
    candidate_id            TEXT NOT NULL,
    backend                 TEXT NOT NULL,
    quant                   TEXT NOT NULL,
    phase                   TEXT NOT NULL,
    outcome                 TEXT,
    optuna_trial_number     INTEGER,
    committed_generation    INTEGER,
    retry_parent_attempt_id TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    termination_reason      TEXT NOT NULL DEFAULT '',
    UNIQUE(run_id, config_hash)
);

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id          TEXT PRIMARY KEY,
    trial_id            TEXT NOT NULL REFERENCES trials(trial_id),
    run_id              TEXT NOT NULL REFERENCES runs(run_id),
    attempt_number      INTEGER NOT NULL,
    phase               TEXT NOT NULL,
    outcome             TEXT,
    process_group_pid   INTEGER NOT NULL,
    parent_attempt_id   TEXT,
    started_at          TEXT NOT NULL,
    ended_at            TEXT,
    phase_deadline      TEXT,
    termination_reason  TEXT NOT NULL DEFAULT '',
    UNIQUE(trial_id, attempt_number)
);

CREATE TABLE IF NOT EXISTS metrics (
    metric_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id  TEXT NOT NULL REFERENCES attempts(attempt_id),
    name        TEXT NOT NULL,
    value       REAL NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE(attempt_id, name)
);

CREATE TABLE IF NOT EXISTS telemetry (
    sample_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id      TEXT NOT NULL REFERENCES attempts(attempt_id),
    vram_used_bytes INTEGER NOT NULL,
    peak_vram_bytes INTEGER NOT NULL,
    breached        INTEGER NOT NULL CHECK(breached IN (0, 1)),
    sampled_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id    TEXT NOT NULL REFERENCES attempts(attempt_id),
    kind          TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    recorded_at   TEXT NOT NULL,
    UNIQUE(attempt_id, kind)
);

CREATE TABLE IF NOT EXISTS checkpoints (
    generation        INTEGER PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES runs(run_id),
    status            TEXT NOT NULL,
    relative_path     TEXT NOT NULL,
    content_hash      TEXT NOT NULL,
    optimizer_version TEXT NOT NULL,
    optuna_version    TEXT NOT NULL,
    checkpoint_format TEXT NOT NULL,
    published_at      TEXT NOT NULL
);
"""


def enable_foreign_keys(conn: sqlite3.Connection) -> None:
    """Enable SQLite foreign-key enforcement on ``conn`` (mandatory)."""
    exec_write(conn, "PRAGMA foreign_keys = ON")


def schema_version(conn: sqlite3.Connection) -> int | None:
    """Return the on-disk schema version from ``schema_meta``, or None if absent."""
    exists = fetch_row(
        conn,
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_meta'",
    )
    if exists is None:
        return None
    row = fetch_row(conn, "SELECT schema_version FROM schema_meta LIMIT 1")
    return None if row is None else row_index_int(row)


def initialize_schema(conn: sqlite3.Connection, *, applied_at: str) -> None:
    """Bootstrap a fresh ledger schema and stamp it with :data:`SCHEMA_VERSION`.

    Assumes ``schema_meta`` does not yet exist; the caller asserts compatibility
    first so an existing incompatible schema is never silently overwritten.
    """
    _ = conn.executescript(_DDL)
    exec_write(
        conn,
        "INSERT INTO schema_meta(schema_version, applied_at) VALUES (?, ?)",
        (SCHEMA_VERSION, applied_at),
    )
    conn.commit()


def assert_schema_compatible(conn: sqlite3.Connection) -> None:
    """Raise :class:`SchemaMismatchError` unless the on-disk version matches.

    A missing ``schema_meta`` (fresh file) is acceptable: the caller bootstraps
    it. Any present-but-different version is a hard error; the ledger never
    auto-upgrades an unknown schema.
    """
    version = schema_version(conn)
    if version is not None and version != SCHEMA_VERSION:
        raise SchemaMismatchError(expected=SCHEMA_VERSION, actual=version)
