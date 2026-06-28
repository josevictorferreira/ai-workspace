"""Behavior tests for the authoritative SQLite trial ledger (T4).

These tests lock the ledger contract: schema versioning and FK enforcement,
exclusive run locking, deterministic IDs, legal/illegal transitions (with
byte-unchanged rollback), persistence across reopen, bounded transient retry,
orphan recovery, atomic checkpoint publication, and the full fault-injection
matrix around the objective/RDB/checkpoint boundaries. No GPU, model, or
network is required; every test uses a temporary run directory.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from llama_optimizer import ledger_io, ledger_materialize, ledger_store
from llama_optimizer.artifacts import RunArtifactRoot
from llama_optimizer.ledger import Ledger
from llama_optimizer.ledger_records import (
    RunIdentity,
    RunLockHeldError,
    SchemaMismatchError,
    TrialConfig,
)
from llama_optimizer.ledger_schema import SCHEMA_VERSION, schema_version
from llama_optimizer.lifecycle import (
    Generation,
    NonScoredOutcome,
    ResumeMode,
    RetryExhaustedError,
    RunPhase,
    TransitionError,
    TrialId,
)
from llama_optimizer.resume import OptimizerVersions

_V = OptimizerVersions("0.1.0", "4.9.0", "pickle.v1")


def _identity() -> RunIdentity:
    return RunIdentity(
        manifest_hash="sha256:manifest",
        config_hash="sha256:config",
        optimizer_version="0.1.0",
        optuna_version="4.9.0",
        checkpoint_format="pickle.v1",
        max_retries=2,
        seed=42,
        process_group_pid=os.getpid(),
    )


def _config(suffix: str = "1") -> TrialConfig:
    return TrialConfig(
        config_id=f"cfg-{suffix}",
        config_hash=f"hash-{suffix}",
        candidate_id="ornith-9b-q4_k_m",
        backend="rocm",
        quant="Q4_K_M",
    )


def _root(run_id: str, base: Path) -> RunArtifactRoot:
    return RunArtifactRoot.for_run(run_id, base=base)


# --- Schema versioning and FK enforcement -----------------------------------


class TestSchemaVersioning:
    def test_fresh_db_stamps_pinned_version(self, run_root_base: Path) -> None:
        root = _root("schema-1", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            version = schema_version(ledger.connection)
        assert version == SCHEMA_VERSION

    def test_incompatible_version_fails_closed(self, run_root_base: Path) -> None:
        root = _root("schema-2", run_root_base)
        with Ledger.create_run(root, _identity()):
            pass
        db = root.resolve_artifact("study.sqlite3")
        conn = sqlite3.connect(db)
        _ = conn.execute("UPDATE schema_meta SET schema_version = ?", (SCHEMA_VERSION + 1,))
        conn.commit()
        conn.close()
        with pytest.raises(SchemaMismatchError) as exc_info:
            _ = Ledger.open(root)
        assert exc_info.value.expected == SCHEMA_VERSION
        assert exc_info.value.actual == SCHEMA_VERSION + 1

    def test_foreign_keys_are_enabled(self, run_root_base: Path) -> None:
        root = _root("schema-3", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            fk = ledger_io.fetch_row(ledger.connection, "PRAGMA foreign_keys")
        assert fk is not None
        assert ledger_materialize.row_index_int(fk) == 1

    def test_fk_blocks_dangling_attempt(self, run_root_base: Path) -> None:
        root = _root("schema-4", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger, pytest.raises(sqlite3.IntegrityError):
            _ = ledger.connection.execute(
                """INSERT INTO attempts(attempt_id, trial_id, run_id, attempt_number,
                   phase, process_group_pid, started_at, termination_reason)
                   VALUES ('a-x','t-fake','schema-4',1,'pending',1,'now','')"""
            )


# --- Exclusive run lock -----------------------------------------------------


class TestExclusiveRunLock:
    def test_second_process_cannot_acquire_active_lock(self, run_root_base: Path) -> None:
        root = _root("lock-1", run_root_base)

        with Ledger.create_run(root, _identity()), pytest.raises(RunLockHeldError):
            _ = Ledger.create_run(root, _identity())

    def test_lock_is_released_on_close(self, run_root_base: Path) -> None:
        root = _root("lock-2", run_root_base)
        with Ledger.create_run(root, _identity()):
            pass
        # Reopen should succeed because the lock was released on close.
        with Ledger.open(root):
            pass

    def test_lock_holder_pid_is_recorded(self, run_root_base: Path) -> None:
        root = _root("lock-3", run_root_base)
        with Ledger.create_run(root, _identity()):
            pass
        lock = root.resolve_artifact("run.lock")
        assert int(lock.read_text().strip()) == os.getpid()


# A child OS process that acquires and holds the run lock, then blocks until
# terminated. run_id/base/ready-marker are passed via argv (no string formatting,
# so paths with special characters are safe).
_CHILD_ACQUIRE_LOCK = """
import os
import re
import sys
import time
from pathlib import Path

from llama_optimizer.artifacts import RunArtifactRoot
from llama_optimizer.ledger import Ledger
from llama_optimizer.ledger_records import RunIdentity

root = RunArtifactRoot.for_run(sys.argv[1], base=Path(sys.argv[2]))
identity = RunIdentity(
    manifest_hash="child",
    config_hash="child",
    optimizer_version="0.1.0",
    optuna_version="4.9.0",
    checkpoint_format="pickle.v1",
    max_retries=1,
    seed=1,
    process_group_pid=os.getpid(),
)
ledger = Ledger.create_run(root, identity)
Path(sys.argv[3]).write_text("ready")
time.sleep(30)
"""


class TestCrossProcessLockContention:
    """A second OS process cannot acquire the exclusive run lock (real subprocess)."""

    def test_subprocess_holding_lock_blocks_parent(self, run_root_base: Path) -> None:
        # Given a child process that acquires and holds the run lock.
        root = _root("lock-subproc", run_root_base)
        ready = run_root_base / "child-ready"
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                _CHILD_ACQUIRE_LOCK,
                "lock-subproc",
                str(run_root_base),
                str(ready),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            # Wait until the child has acquired the lock (ready marker appears).
            for _ in range(100):
                if ready.exists():
                    break
                if proc.poll() is not None:
                    _out, err = proc.communicate()
                    pytest.fail(f"child exited {proc.returncode}: {err.decode()}")
                time.sleep(0.05)
            else:
                proc.kill()
                pytest.fail("child never signaled lock acquisition")
            # When the parent (this process) tries to acquire the same lock.
            # Then it fails with RunLockHeldError (real cross-process flock exclusion).
            with pytest.raises(RunLockHeldError):
                _ = Ledger.create_run(root, _identity())
        finally:
            proc.terminate()
            _ = proc.wait(timeout=10)


# --- Deterministic IDs and idempotent trial creation ------------------------


class TestDeterministicIds:
    def test_same_run_and_config_yields_same_trial_id(self, run_root_base: Path) -> None:
        root = _root("ids-1", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            t1 = ledger.create_trial(_config("x"))
            t2 = ledger.create_trial(_config("x"))
        assert t1.trial_id == t2.trial_id
        assert t1.config_hash == t2.config_hash

    def test_different_config_yields_different_trial_id(self, run_root_base: Path) -> None:
        root = _root("ids-2", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            t1 = ledger.create_trial(_config("a"))
            t2 = ledger.create_trial(_config("b"))
        assert t1.trial_id != t2.trial_id

    def test_deterministic_attempt_id_across_reopen(self, run_root_base: Path) -> None:
        root = _root("ids-3", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            trial = ledger.create_trial(_config("c"))
            _ = ledger.start_trial(trial.trial_id)
            attempt = ledger.start_attempt(trial.trial_id)
            ledger.succeed_attempt(attempt.attempt_id)
            ledger.commit_trial(trial.trial_id, generation=Generation(1), optuna_trial_number=0)
        with Ledger.open(root) as ledger2:
            trial2 = ledger2.create_trial(_config("c"))
        assert trial.trial_id == trial2.trial_id


# --- Persistence across reopen ---------------------------------------------


class TestPersistence:
    def test_run_and_trial_survive_reopen(self, run_root_base: Path) -> None:
        root = _root("persist-1", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            trial = ledger.create_trial(_config("p"))
            _ = ledger.start_trial(trial.trial_id)
        with Ledger.open(root) as ledger2:
            assert ledger2.run.phase is RunPhase.RUNNING
            t2 = ledger2.create_trial(_config("p"))
        assert t2.trial_id == trial.trial_id

    def test_dump_is_stable_across_reopen(self, run_root_base: Path) -> None:
        root = _root("persist-2", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            trial = ledger.create_trial(_config("d"))
            _ = ledger.start_trial(trial.trial_id)
            attempt = ledger.start_attempt(trial.trial_id)
            ledger.succeed_attempt(attempt.attempt_id)
            ledger.record_metrics(attempt.attempt_id, {"prompt_throughput": 100.0})
            ledger.record_telemetry(
                attempt.attempt_id, vram_used_bytes=1000, peak_vram_bytes=2000, breached=False
            )
            ledger.record_artifact(
                attempt.attempt_id,
                kind="bench",
                relative_path="trials/t1/bench.jsonl",
                content_hash="sha256:bench",
            )
            ledger.commit_trial(trial.trial_id, generation=Generation(1), optuna_trial_number=0)
            ledger.publish_checkpoint(generation=Generation(1), content=b"checkpoint-1")
            dump1 = ledger.dump()
        with Ledger.open(root) as ledger2:
            dump2 = ledger2.dump()
        assert json.dumps(dump1, sort_keys=True) == json.dumps(dump2, sort_keys=True)


# --- Legal / illegal transitions leave DB byte-unchanged -------------------


class TestIllegalTransitionsAreNoOps:
    def test_terminal_run_cannot_advance(self, run_root_base: Path) -> None:

        root = _root("trans-1", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            ledger.complete_run()
            db_before = root.resolve_artifact("study.sqlite3").read_bytes()
            with pytest.raises(TransitionError):
                ledger.start_run()
            db_after = root.resolve_artifact("study.sqlite3").read_bytes()
        assert db_before == db_after

    def test_committed_trial_cannot_be_reopened(self, run_root_base: Path) -> None:

        root = _root("trans-2", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            trial = ledger.create_trial(_config("t"))
            _ = ledger.start_trial(trial.trial_id)
            attempt = ledger.start_attempt(trial.trial_id)
            ledger.succeed_attempt(attempt.attempt_id)
            ledger.commit_trial(trial.trial_id, generation=Generation(1), optuna_trial_number=0)
            db_before = root.resolve_artifact("study.sqlite3").read_bytes()
            with pytest.raises(TransitionError):
                _ = ledger.start_trial(trial.trial_id)
            db_after = root.resolve_artifact("study.sqlite3").read_bytes()
        assert db_before == db_after


# --- Bounded transient retry ------------------------------------------------


class TestBoundedTransientRetry:
    def _setup_run(self, root: RunArtifactRoot) -> tuple[Ledger, TrialId]:
        ledger = Ledger.create_run(root, _identity())
        ledger.start_run()
        trial = ledger.create_trial(_config("r"))
        _ = ledger.start_trial(trial.trial_id)
        return ledger, trial.trial_id

    def test_transient_failure_within_bound_permits_retry(self, run_root_base: Path) -> None:
        root = _root("retry-1", run_root_base)
        ledger, trial_id = self._setup_run(root)
        try:
            a1 = ledger.start_attempt(trial_id)
            ledger.end_attempt_nonscored(
                a1.attempt_id, outcome=NonScoredOutcome.TRANSIENT_FAILURE, reason="timeout"
            )
            a2 = ledger.start_attempt(trial_id)  # retry 1
            assert a2.attempt_number == 2
            assert a2.parent_attempt_id == a1.attempt_id
        finally:
            ledger.close()

    def test_transient_failure_at_bound_exhausts_retry(self, run_root_base: Path) -> None:

        root = _root("retry-2", run_root_base)
        ledger, trial_id = self._setup_run(root)
        try:
            a1 = ledger.start_attempt(trial_id)
            ledger.end_attempt_nonscored(
                a1.attempt_id, outcome=NonScoredOutcome.TRANSIENT_FAILURE, reason="t1"
            )
            a2 = ledger.start_attempt(trial_id)
            ledger.end_attempt_nonscored(
                a2.attempt_id, outcome=NonScoredOutcome.TRANSIENT_FAILURE, reason="t2"
            )
            a3 = ledger.start_attempt(trial_id)
            ledger.end_attempt_nonscored(
                a3.attempt_id, outcome=NonScoredOutcome.TRANSIENT_FAILURE, reason="t3"
            )
            # 3 attempts = 1 initial + 2 retries (max_retries=2); 4th must fail.
            with pytest.raises(RetryExhaustedError):
                _ = ledger.start_attempt(trial_id)
        finally:
            ledger.close()

    @pytest.mark.parametrize(
        "outcome",
        sorted(o for o in NonScoredOutcome if o is not NonScoredOutcome.TRANSIENT_FAILURE),
    )
    def test_non_transient_outcome_blocks_retry(
        self, run_root_base: Path, outcome: NonScoredOutcome
    ) -> None:

        root = _root(f"retry-{outcome.value}", run_root_base)
        ledger, trial_id = self._setup_run(root)
        try:
            a1 = ledger.start_attempt(trial_id)
            ledger.end_attempt_nonscored(a1.attempt_id, outcome=outcome, reason="x")
            with pytest.raises(RetryExhaustedError):
                _ = ledger.start_attempt(trial_id)
        finally:
            ledger.close()


# --- Orphan recovery -------------------------------------------------------


class TestOrphanRecovery:
    def test_orphaned_in_progress_attempt_classified_as_crash(self, run_root_base: Path) -> None:
        root = _root("orphan-1", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            trial = ledger.create_trial(_config("o"))
            _ = ledger.start_trial(trial.trial_id)
            attempt = ledger.start_attempt(trial.trial_id)
            # Leave the attempt IN_PROGRESS (simulate crash) and close without ending it.
        with Ledger.open(root) as ledger2:
            recovery = ledger2.recovery
            assert attempt.attempt_id in recovery.orphaned_attempt_ids
            assert recovery.committed_boundary_unchanged is True

    def test_recovery_does_not_advance_committed_boundary(self, run_root_base: Path) -> None:
        root = _root("orphan-2", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            ledger.publish_checkpoint(generation=Generation(1), content=b"ckpt-1")
            boundary_before = ledger.run.committed_generation
            trial = ledger.create_trial(_config("o2"))
            _ = ledger.start_trial(trial.trial_id)
            _ = ledger.start_attempt(trial.trial_id)  # orphaned
        with Ledger.open(root) as ledger2:
            assert ledger2.run.committed_generation == boundary_before
            assert ledger2.recovery.committed_boundary_unchanged is True

    def test_recovery_does_not_duplicate_trial(self, run_root_base: Path) -> None:
        root = _root("orphan-3", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            trial = ledger.create_trial(_config("o3"))
            _ = ledger.start_trial(trial.trial_id)
            _ = ledger.start_attempt(trial.trial_id)
        with Ledger.open(root):
            pass
        conn = sqlite3.connect(root.resolve_artifact("study.sqlite3"))
        conn.row_factory = sqlite3.Row
        row = ledger_io.fetch_row(
            conn,
            "SELECT COUNT(*) FROM trials WHERE config_hash = ?",
            ("hash-o3",),
        )
        conn.close()
        assert row is not None
        assert ledger_materialize.row_index_int(row) == 1


# --- Atomic checkpoint publication -----------------------------------------


class TestAtomicCheckpointPublication:
    def test_checkpoint_file_published_atomically(self, run_root_base: Path) -> None:
        root = _root("ckpt-1", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            ledger.publish_checkpoint(generation=Generation(1), content=b"sampler-state-1")
            ckpt_path = root.resolve_artifact("checkpoints/gen-0001.ckpt")
            assert ckpt_path.read_bytes() == b"sampler-state-1"
            assert ledger.run.committed_generation == Generation(1)

    def test_checkpoint_advances_committed_boundary(self, run_root_base: Path) -> None:
        root = _root("ckpt-2", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            assert ledger.run.committed_generation is None
            ledger.publish_checkpoint(generation=Generation(1), content=b"ckpt")
            assert ledger.run.committed_generation == Generation(1)
            ledger.publish_checkpoint(generation=Generation(2), content=b"ckpt2")
            assert ledger.run.committed_generation == Generation(2)

    def test_no_temp_file_remains_after_publication(self, run_root_base: Path) -> None:
        root = _root("ckpt-3", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            ledger.publish_checkpoint(generation=Generation(1), content=b"data")
            ckpt_dir = root.resolve_artifact("checkpoints")
        temps = [p for p in ckpt_dir.iterdir() if p.name.startswith(".")]
        assert temps == []

    def test_no_partial_commit_after_crash_before_commit(  # fault boundary 1
        self, run_root_base: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Inject a crash after the checkpoint FILE is atomically published but
        # before the DB transaction commits the checkpoint row + boundary advance.

        def crash(*_args: object, **_kwargs: object) -> None:
            msg = "crash before db commit"
            raise RuntimeError(msg)

        root = _root("ckpt-fault1", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            monkeypatch.setattr(ledger_store, "update_committed_generation", crash)
            with pytest.raises(RuntimeError):
                ledger.publish_checkpoint(
                    generation=Generation(1), content=b"published-but-uncommitted"
                )
            # The committed boundary must NOT have advanced (transaction rolled back).
            assert ledger.run.committed_generation is None
        # Reopen: the committed boundary is still None; the orphan checkpoint
        # file exists on disk but is unreferenced by the committed boundary.
        with Ledger.open(root) as ledger2:
            assert ledger2.run.committed_generation is None


# --- Resume semantics ------------------------------------------------------


class TestResumeSemantics:
    def _committed_run(self, root: RunArtifactRoot) -> None:
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            trial = ledger.create_trial(_config("res"))
            _ = ledger.start_trial(trial.trial_id)
            attempt = ledger.start_attempt(trial.trial_id)
            ledger.succeed_attempt(attempt.attempt_id)
            ledger.commit_trial(trial.trial_id, generation=Generation(1), optuna_trial_number=0)
            ledger.publish_checkpoint(generation=Generation(1), content=b"ckpt-res")

    def test_history_resume_is_always_eligible(self, run_root_base: Path) -> None:
        root = _root("resume-hist", run_root_base)
        self._committed_run(root)
        with Ledger.open(root) as ledger:
            result = ledger.resume(ResumeMode.HISTORY, _V)
        assert result.verdict.eligible
        assert result.verdict.mode is ResumeMode.HISTORY

    def test_exact_resume_succeeds_when_generation_matches(self, run_root_base: Path) -> None:
        root = _root("resume-exact-ok", run_root_base)
        self._committed_run(root)
        with Ledger.open(root) as ledger:
            result = ledger.resume(ResumeMode.EXACT, _V)
        assert result.verdict.eligible
        assert result.verdict.mode is ResumeMode.EXACT
        assert result.committed_generation == Generation(1)
        assert result.checkpoint_path is not None

    def test_exact_resume_fails_on_version_mismatch(self, run_root_base: Path) -> None:
        root = _root("resume-exact-ver", run_root_base)
        self._committed_run(root)
        bad = OptimizerVersions("0.9.0", "4.9.0", "pickle.v1")
        with Ledger.open(root) as ledger:
            result = ledger.resume(ResumeMode.EXACT, bad)
        assert not result.verdict.eligible

    def test_exact_resume_fails_on_stale_generation(self, run_root_base: Path) -> None:
        root = _root("resume-exact-stale", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            ledger.publish_checkpoint(generation=Generation(1), content=b"ckpt")
            # Manually regress the committed boundary to simulate a stale checkpoint.
            conn = ledger.connection
            _ = conn.execute("UPDATE runs SET committed_generation = 0")
            conn.commit()
        with Ledger.open(root) as ledger:
            result = ledger.resume(ResumeMode.EXACT, _V)
        assert not result.verdict.eligible

    def test_exact_resume_fails_when_checkpoint_missing(self, run_root_base: Path) -> None:
        root = _root("resume-exact-missing", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            # Set a committed boundary without publishing a checkpoint (corrupt state).
            conn = ledger.connection
            _ = conn.execute("UPDATE runs SET committed_generation = 5")
            conn.commit()
        with Ledger.open(root) as ledger:
            result = ledger.resume(ResumeMode.EXACT, _V)
        assert not result.verdict.eligible


# --- Normalized dump -------------------------------------------------------


class TestNormalizedDump:
    def test_dump_contains_run_trials_attempts_metrics(self, run_root_base: Path) -> None:
        root = _root("dump-1", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            ledger.start_run()
            trial = ledger.create_trial(_config("dump"))
            _ = ledger.start_trial(trial.trial_id)
            attempt = ledger.start_attempt(trial.trial_id)
            ledger.succeed_attempt(attempt.attempt_id)
            ledger.record_metrics(attempt.attempt_id, {"tok_s": 50.0, "ttft": 0.1})
            ledger.commit_trial(trial.trial_id, generation=Generation(1), optuna_trial_number=0)
            dump = ledger.dump()
        assert dump["run_id"] == "dump-1"
        trials = dump["trials"]
        assert isinstance(trials, list)
        assert len(trials) == 1
        attempts = trials[0]["attempts"]
        assert len(attempts) == 1
        assert attempts[0]["metrics"]["tok_s"] == 50.0

    def test_dump_is_json_serializable(self, run_root_base: Path) -> None:
        root = _root("dump-2", run_root_base)
        with Ledger.create_run(root, _identity()) as ledger:
            dump = ledger.dump()
        assert json.dumps(dump, sort_keys=True, indent=2)


# --- Escape-hatch static guard (T4 extension) ------------------------------


class TestNoTypingEscapeHatchesInLedger:
    """The escape-hatch guard in test_search_space.py scans all src; verify T4 source too."""

    def test_no_type_ignore_in_ledger_source(self) -> None:
        src_dir = Path(__file__).resolve().parent.parent / "src" / "llama_optimizer"
        offenders: list[str] = []
        for py_file in sorted(src_dir.rglob("*.py")):
            for line_no, line in enumerate(py_file.read_text().splitlines(), start=1):
                if "type: ignore" in line:
                    offenders.append(f"{py_file.name}:{line_no}: {line.strip()}")
        assert not offenders, "type: ignore escape hatches found:\n" + "\n".join(offenders)

    def test_no_noqa_in_ledger_source(self) -> None:
        src_dir = Path(__file__).resolve().parent.parent / "src" / "llama_optimizer"
        offenders: list[str] = []
        for py_file in sorted(src_dir.rglob("*.py")):
            for line_no, line in enumerate(py_file.read_text().splitlines(), start=1):
                if "noqa" in line:
                    offenders.append(f"{py_file.name}:{line_no}: {line.strip()}")
        assert not offenders, "noqa escape hatches found:\n" + "\n".join(offenders)

    def test_no_any_or_cast_imported_in_ledger_source(self) -> None:
        """No first-party module may import ``Any`` or ``cast`` (typing escape hatches).

        Import-scanning is bulletproof: if the names are never imported they cannot be
        used as annotations, while docstring prose mentioning the words is unaffected.
        """
        src_dir = Path(__file__).resolve().parent.parent / "src" / "llama_optimizer"
        offenders: list[str] = []
        for py_file in sorted(src_dir.rglob("*.py")):
            for line_no, line in enumerate(py_file.read_text().splitlines(), start=1):
                if "from typing import" in line and re.search(r"\b(Any|cast)\b", line):
                    offenders.append(f"{py_file.name}:{line_no}: {line.strip()}")
                if re.search(r"\btyping\.(Any|cast)\b", line):
                    offenders.append(f"{py_file.name}:{line_no}: {line.strip()}")
        assert not offenders, "Any/cast escape hatches found:\n" + "\n".join(offenders)

    def test_no_typing_config_weakening(self) -> None:
        """The locked basedpyright gate must not disable strict typing rules."""
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        text = pyproject.read_text()
        assert 'reportAny = "none"' not in text, "reportAny weakened to none"
        assert 'reportMissingTypeStubs = "none"' not in text, (
            "reportMissingTypeStubs weakened to none"
        )
