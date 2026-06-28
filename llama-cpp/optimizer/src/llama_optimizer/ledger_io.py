"""Process-level I/O primitives for the durable trial ledger (T4).

Exclusive run locking via ``flock`` (one writer), SQLite connection setup
(Row factory + foreign keys + autocommit), an explicit transaction context,
and the atomic file-publication protocol (temp + fsync + rename + dirfsync).
"""

from __future__ import annotations

import fcntl
import os
import sqlite3
from contextlib import contextmanager
from typing import TYPE_CHECKING

from llama_optimizer.ledger_records import RunLockHeldError, exec_write

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[None]:
    """Begin an IMMEDIATE transaction; commit on success, roll back on error."""
    exec_write(conn, "BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        exec_write(conn, "ROLLBACK")
        raise
    exec_write(conn, "COMMIT")


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection with the Row factory, foreign keys, and autocommit."""
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    exec_write(conn, "PRAGMA foreign_keys = ON")
    return conn


def acquire_lock(lock_path: Path) -> int:
    """Acquire an exclusive flock on the run lock or raise :class:`RunLockHeldError`."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(fd)
        raise RunLockHeldError(lock_path=lock_path, holder_pid=read_holder_pid(lock_path)) from exc
    _ = os.write(fd, f"{os.getpid()}\n".encode())
    return fd


def release_lock(fd: int) -> None:
    """Release and close the run lock file descriptor."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def read_holder_pid(lock_path: Path) -> int:
    """Best-effort read of the holder pid recorded in a lock file."""
    try:
        return int(lock_path.read_text().strip())
    except (OSError, ValueError):
        return -1


def atomic_publish(path: Path, content: bytes) -> None:
    """Publish ``content`` at ``path`` via temp + fsync + rename + dirfsync.

    The temp file lives in the same directory so the rename is atomic on one
    filesystem; the file is fsynced before rename and the directory is fsynced
    after, so a crash leaves either the old file or the new file, never a
    truncated half-write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp"
    with tmp.open("wb") as handle:
        _ = handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    _ = tmp.replace(path)
    fsync_dir(path.parent)


def fsync_dir(directory: Path) -> None:
    """Fsync a directory so a rename/create within it is durable on crash."""
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
