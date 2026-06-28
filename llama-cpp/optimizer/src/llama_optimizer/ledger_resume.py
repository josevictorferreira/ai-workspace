"""Checkpoint publication and resume operations for the ledger (T4).

Checkpoints are published atomically (temp + fsync + rename + dirfsync, then a
transactional commit of the checkpoint row + committed boundary advance) so a
crash leaves a detectable, fail-closed state rather than a silent divergence.
Exact resume requires a version- and generation-compatible checkpoint aligned
to the latest committed search boundary; history resume is always eligible.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from llama_optimizer import ledger_evidence as evidence
from llama_optimizer import ledger_ids, ledger_io
from llama_optimizer import ledger_store as store
from llama_optimizer.ledger_records import CheckpointRecord, ResumeResult, RunRecord
from llama_optimizer.lifecycle import CheckpointStatus, Generation, ResumeMode
from llama_optimizer.resume import (
    CheckpointIdentity,
    OptimizerVersions,
    ResumeRequest,
    check_exact_resume,
)

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

    from llama_optimizer.artifacts import RunArtifactRoot


def publish_checkpoint(
    root: RunArtifactRoot,
    conn: sqlite3.Connection,
    run: RunRecord,
    *,
    generation: Generation,
    content: bytes,
) -> RunRecord:
    """Atomically publish a sampler checkpoint and advance the committed boundary."""
    rel = f"checkpoints/gen-{int(generation):04d}.ckpt"
    ledger_io.atomic_publish(root.resolve_artifact(rel), content)
    content_hash = hashlib.sha256(content).hexdigest()
    now = ledger_ids.utc_now_iso()
    row = CheckpointRecord(
        generation,
        run.run_id,
        CheckpointStatus.COMMITTED,
        rel,
        content_hash,
        run.optimizer_version,
        run.optuna_version,
        run.checkpoint_format,
        now,
    )
    with ledger_io.transaction(conn):
        evidence.upsert_checkpoint(conn, row)
        store.update_committed_generation(conn, run.run_id, generation, updated_at=now)
    return store.select_run(conn, run.run_id)


def resume(
    root: RunArtifactRoot,
    conn: sqlite3.Connection,
    run_id: str,
    *,
    mode: ResumeMode,
    expected: OptimizerVersions,
) -> ResumeResult:
    """Return the resume verdict and actionable facts (history or exact)."""
    run = store.select_run(conn, run_id)
    latest_trial_gen = store.latest_committed_trial_generation(conn, run_id)
    boundary = run.committed_generation
    checkpoint, checkpoint_path = _checkpoint_at(root, conn, boundary)
    orphans = bool(store.orphaned_in_progress_attempts(conn, run_id))
    request = ResumeRequest(
        mode=mode,
        run_optimizer_version=run.optimizer_version,
        run_optuna_version=run.optuna_version,
        latest_committed_generation=boundary,
        latest_trial_generation=latest_trial_gen,
        checkpoint=checkpoint,
        has_orphan_in_progress=orphans,
    )
    verdict = check_exact_resume(request, expected)
    return ResumeResult(
        verdict=verdict,
        committed_generation=boundary,
        checkpoint_path=checkpoint_path if verdict.eligible else None,
    )


def _checkpoint_at(
    root: RunArtifactRoot,
    conn: sqlite3.Connection,
    boundary: Generation | None,
) -> tuple[CheckpointIdentity | None, Path | None]:
    """Return the committed checkpoint identity+path at ``boundary``, or (None, None)."""
    if boundary is None:
        return None, None
    ckpt = evidence.select_checkpoint(conn, boundary)
    if ckpt is None or ckpt.status is not CheckpointStatus.COMMITTED:
        return None, None
    identity = CheckpointIdentity(
        ckpt.optimizer_version,
        ckpt.optuna_version,
        ckpt.checkpoint_format,
        ckpt.generation,
    )
    return identity, root.resolve_artifact(ckpt.relative_path)
