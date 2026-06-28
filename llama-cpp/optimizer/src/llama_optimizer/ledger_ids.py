"""Deterministic identity and timestamp primitives for the durable trial ledger (T4).

Trial/attempt ids are content-derived SHA-256 digests: the same run+config -> the
same trial, and the same trial+attempt number -> the same attempt (idempotent, no
duplicates). ``utc_now_iso`` is the single deterministic ISO-8601 timestamp source
used across the ledger. These primitives are pure (no database, no filesystem).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from llama_optimizer.lifecycle import AttemptId, ConfigHash, TrialId


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
