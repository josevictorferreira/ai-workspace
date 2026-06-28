"""Trial, attempt, and evidence operations for the ledger (T4).

Each operation asserts the legal transition against the closed state machine
before any write (so an illegal transition leaves the database unchanged),
then mutates rows within an explicit transaction. Retry eligibility is
enforced for every attempt after the first: only a confirmed ``transient-
failure`` within the run's bounded budget is permitted, with lineage preserved
via ``parent_attempt_id``. Checkpoint publication and resume live in
:mod:`llama_optimizer.ledger_resume`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from llama_optimizer import ledger_evidence as evidence
from llama_optimizer import ledger_io
from llama_optimizer import ledger_store as store
from llama_optimizer.ledger_records import (
    AttemptRecord,
    RunRecord,
    TrialConfig,
    TrialRecord,
)
from llama_optimizer.lifecycle import (
    AttemptId,
    AttemptPhase,
    ConfigHash,
    Generation,
    NonScoredOutcome,
    RetryExhaustedError,
    RunId,
    TransitionError,
    TrialId,
    TrialPhase,
    assert_trial_transition,
    can_retry,
)

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Mapping


def create_trial(
    conn: sqlite3.Connection,
    run_id: RunId,
    config: TrialConfig,
) -> TrialRecord:
    """Idempotently create a PENDING trial for a config (same config -> same trial)."""
    chash = ConfigHash(config.config_hash)
    existing = store.select_trial_by_config(conn, run_id, chash)
    if existing is not None:
        return existing
    trial_id = store.derive_trial_id(run_id, config.config_id, chash)
    now = store.utc_now_iso()
    record = TrialRecord(
        trial_id,
        run_id,
        config.config_id,
        config.config_hash,
        config.candidate_id,
        config.backend,
        config.quant,
        TrialPhase.PENDING,
        None,
        None,
        None,
        None,
        now,
        now,
        "",
    )
    with ledger_io.transaction(conn):
        store.insert_trial(conn, record)
    return record


def start_trial(conn: sqlite3.Connection, trial_id: TrialId) -> TrialRecord:
    """Move a trial PENDING -> RUNNING."""
    trial = store.select_trial(conn, trial_id)
    assert_trial_transition(trial.phase, TrialPhase.RUNNING, trial_id=trial_id)
    with ledger_io.transaction(conn):
        store.update_trial_phase(conn, trial_id, TrialPhase.RUNNING, updated_at=store.utc_now_iso())
    return store.select_trial(conn, trial_id)


def commit_trial(
    conn: sqlite3.Connection,
    trial_id: TrialId,
    *,
    generation: Generation,
    optuna_trial_number: int,
) -> None:
    """Move a trial RUNNING -> COMMITTED at a search boundary generation."""
    trial = store.select_trial(conn, trial_id)
    assert_trial_transition(trial.phase, TrialPhase.COMMITTED, trial_id=trial_id)
    with ledger_io.transaction(conn):
        store.commit_trial(
            conn,
            trial_id,
            generation,
            optuna_trial_number,
            updated_at=store.utc_now_iso(),
        )


def abandon_trial(
    conn: sqlite3.Connection,
    trial_id: TrialId,
    *,
    outcome: NonScoredOutcome,
    reason: str,
) -> None:
    """Move a trial RUNNING -> ABANDONED with a non-scored outcome."""
    trial = store.select_trial(conn, trial_id)
    assert_trial_transition(trial.phase, TrialPhase.ABANDONED, trial_id=trial_id)
    with ledger_io.transaction(conn):
        store.abandon_trial(conn, trial_id, outcome, reason, updated_at=store.utc_now_iso())


def start_attempt(
    conn: sqlite3.Connection,
    run: RunRecord,
    trial_id: TrialId,
    *,
    parent_attempt_id: AttemptId | None = None,
) -> AttemptRecord:
    """Create + begin the next attempt, enforcing bounded transient retry."""
    number = store.next_attempt_number(conn, trial_id)
    parent = parent_attempt_id
    if number > 1:
        prior = store.select_attempt(conn, store.derive_attempt_id(trial_id, number - 1))
        parent = prior.attempt_id
        enforce_retry_eligibility(run, prior, number - 1)
    attempt_id = store.derive_attempt_id(trial_id, number)
    now = store.utc_now_iso()
    record = AttemptRecord(
        attempt_id,
        trial_id,
        run.run_id,
        number,
        AttemptPhase.PENDING,
        None,
        run.process_group_pid,
        parent,
        now,
        None,
        None,
        "",
    )
    with ledger_io.transaction(conn):
        store.insert_attempt(conn, record)
        store.begin_attempt(conn, attempt_id, started_at=now)
    return store.select_attempt(conn, attempt_id)


def enforce_retry_eligibility(run: RunRecord, prior: AttemptRecord, completed_count: int) -> None:
    """Raise unless the prior terminal attempt is a retryable transient failure."""
    if prior.phase is AttemptPhase.IN_PROGRESS:
        raise TransitionError(
            entity="attempt",
            entity_id=prior.attempt_id,
            current=prior.phase.value,
            attempted="in_progress",
            reason="prior attempt still in progress",
        )
    if prior.phase is AttemptPhase.SUCCEEDED:
        raise TransitionError(
            entity="attempt",
            entity_id=prior.attempt_id,
            current=prior.phase.value,
            attempted="in_progress",
            reason="succeeded attempt cannot be retried",
        )
    outcome = prior.outcome if prior.outcome is not None else NonScoredOutcome.CRASH
    if not can_retry(outcome=outcome, attempt_count=completed_count, max_retries=run.max_retries):
        raise RetryExhaustedError(
            trial_id=TrialId(prior.trial_id),
            attempted_count=completed_count,
            max_retries=run.max_retries,
        )


def succeed_attempt(conn: sqlite3.Connection, attempt_id: AttemptId) -> None:
    """Move an attempt IN_PROGRESS -> SUCCEEDED."""
    _assert_in_progress(conn, attempt_id, AttemptPhase.SUCCEEDED)
    with ledger_io.transaction(conn):
        store.succeed_attempt(conn, attempt_id, ended_at=store.utc_now_iso())


def end_attempt_nonscored(
    conn: sqlite3.Connection,
    attempt_id: AttemptId,
    *,
    outcome: NonScoredOutcome,
    reason: str,
) -> None:
    """Move an attempt IN_PROGRESS -> NON_SCORED with a closed outcome."""
    _assert_in_progress(conn, attempt_id, AttemptPhase.NON_SCORED)
    with ledger_io.transaction(conn):
        store.nonscore_attempt(conn, attempt_id, outcome, reason, ended_at=store.utc_now_iso())


def _assert_in_progress(
    conn: sqlite3.Connection,
    attempt_id: AttemptId,
    target: AttemptPhase,
) -> None:
    """Raise TransitionError unless the attempt is currently IN_PROGRESS."""
    attempt = store.select_attempt(conn, attempt_id)
    if attempt.phase is not AttemptPhase.IN_PROGRESS:
        raise TransitionError(
            entity="attempt",
            entity_id=attempt.attempt_id,
            current=attempt.phase.value,
            attempted=target.value,
            reason="attempt not in progress",
        )


def record_metrics(
    conn: sqlite3.Connection,
    attempt_id: AttemptId,
    metrics: Mapping[str, float],
) -> None:
    """Record named metrics for an attempt."""
    with ledger_io.transaction(conn):
        for name, value in metrics.items():
            evidence.upsert_metric(conn, attempt_id, name, value)


def record_telemetry(
    conn: sqlite3.Connection,
    attempt_id: AttemptId,
    *,
    vram_used_bytes: int,
    peak_vram_bytes: int,
    breached: bool,
) -> None:
    """Append one telemetry sample for an attempt."""
    with ledger_io.transaction(conn):
        evidence.insert_telemetry(
            conn,
            attempt_id,
            vram_used_bytes,
            peak_vram_bytes,
            breached=breached,
        )


def record_artifact(
    conn: sqlite3.Connection,
    attempt_id: AttemptId,
    *,
    kind: str,
    relative_path: str,
    content_hash: str,
) -> None:
    """Record a raw artifact reference for an attempt."""
    with ledger_io.transaction(conn):
        evidence.upsert_artifact(conn, attempt_id, kind, relative_path, content_hash)
