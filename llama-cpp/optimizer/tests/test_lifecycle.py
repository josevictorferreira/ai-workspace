"""Behavior tests for the closed lifecycle state machine (T4).

The lifecycle model is pure: closed phase enums, legal-transition tables,
typed transition errors, bounded retry eligibility, and an exact-resume
verdict that depends only on identity + generation facts. Nothing here
touches a database or the filesystem.
"""

from __future__ import annotations

import pytest

from llama_optimizer.lifecycle import (
    LEGAL_ATTEMPT_TRANSITIONS,
    LEGAL_RUN_TRANSITIONS,
    LEGAL_TRIAL_TRANSITIONS,
    RETRY_ELIGIBLE_OUTCOMES,
    TERMINAL_ATTEMPT_PHASES,
    TERMINAL_RUN_PHASES,
    TERMINAL_TRIAL_PHASES,
    AttemptId,
    AttemptPhase,
    ConfigHash,
    Generation,
    NonScoredOutcome,
    ResumeMode,
    RetryExhaustedError,
    RunId,
    RunPhase,
    TransitionError,
    TrialId,
    TrialPhase,
    assert_attempt_transition,
    assert_run_transition,
    assert_trial_transition,
    can_retry,
    is_retry_eligible,
    is_terminal_attempt,
    is_terminal_run,
    is_terminal_trial,
)
from llama_optimizer.resume import (
    CheckpointIdentity,
    ExactResumeUnavailableError,
    OptimizerVersions,
    ResumeIncompatibilityReason,
    ResumeRequest,
    check_exact_resume,
)

_DEFAULT_GEN: Generation = Generation(3)

# --- Closed outcome taxonomy --------------------------------------------------

ALL_NON_SCORED_OUTCOMES = frozenset(NonScoredOutcome)


class TestClosedOutcomeTaxonomy:
    def test_contains_exactly_the_required_outcomes(self) -> None:
        # Given the plan's mandatory non-scored outcome list.
        required = {
            "invalid",
            "unsupported",
            "resource-infeasible",
            "deterministic-load-failure",
            "quality-failure",
            "measurement-failure",
            "telemetry-loss",
            "crash",
            "hang",
            "transient-failure",
            "cancelled",
        }
        # When reading the enum members.
        actual = {member.value for member in NonScoredOutcome}
        # Then the closed set matches the plan exactly (no extra, no missing).
        assert actual == required

    def test_only_transient_failure_is_retry_eligible(self) -> None:
        # Given every non-scored outcome.
        # When checking retry eligibility.
        eligible = {o for o in NonScoredOutcome if is_retry_eligible(o)}
        # Then exactly one outcome is retry-eligible.
        assert eligible == {NonScoredOutcome.TRANSIENT_FAILURE}
        assert frozenset({NonScoredOutcome.TRANSIENT_FAILURE}) == RETRY_ELIGIBLE_OUTCOMES

    @pytest.mark.parametrize("outcome", sorted(NonScoredOutcome))
    def test_outcome_is_a_closed_str_enum_value(self, outcome: NonScoredOutcome) -> None:
        # Given any non-scored outcome.
        # When inspecting its type.
        # Then it is a member of the closed StrEnum (exhaustive).
        assert isinstance(outcome.value, str)
        assert NonScoredOutcome(outcome.value) is outcome


# --- Run phase state machine --------------------------------------------------


class TestRunPhaseTransitions:
    def test_legal_run_transitions_match_closed_model(self) -> None:
        # Given the transition table.
        # When inspecting it.
        # Then exactly these forward transitions are legal and terminals have none.
        assert LEGAL_RUN_TRANSITIONS[RunPhase.INITIALIZED] == frozenset({RunPhase.RUNNING})
        assert LEGAL_RUN_TRANSITIONS[RunPhase.RUNNING] == frozenset(
            {RunPhase.COMPLETED, RunPhase.ABANDONED}
        )
        assert LEGAL_RUN_TRANSITIONS[RunPhase.COMPLETED] == frozenset()
        assert LEGAL_RUN_TRANSITIONS[RunPhase.ABANDONED] == frozenset()

    def test_terminal_run_phases_are_completed_and_abandoned(self) -> None:
        assert frozenset({RunPhase.COMPLETED, RunPhase.ABANDONED}) == TERMINAL_RUN_PHASES
        for phase in RunPhase:
            assert is_terminal_run(phase) == (phase in TERMINAL_RUN_PHASES)

    def test_legal_run_transition_is_accepted(self) -> None:
        # Given an initialized run.
        run_id = RunId("run-1")
        # When asserting a legal forward transition.
        # Then no exception is raised.
        assert_run_transition(RunPhase.INITIALIZED, RunPhase.RUNNING, run_id=run_id)

    def test_terminal_run_cannot_advance(self) -> None:
        run_id = RunId("run-1")
        with pytest.raises(TransitionError) as exc_info:
            assert_run_transition(RunPhase.COMPLETED, RunPhase.RUNNING, run_id=run_id)
        # Then the typed error names the entity and both phases.
        err = exc_info.value
        assert err.entity == "run"
        assert err.entity_id == "run-1"
        assert err.current == RunPhase.COMPLETED.value
        assert err.attempted == RunPhase.RUNNING.value

    def test_backward_run_transition_is_rejected(self) -> None:
        run_id = RunId("run-1")
        with pytest.raises(TransitionError):
            assert_run_transition(RunPhase.RUNNING, RunPhase.INITIALIZED, run_id=run_id)


# --- Trial phase state machine ------------------------------------------------


class TestTrialPhaseTransitions:
    def test_legal_trial_transitions_match_closed_model(self) -> None:
        assert LEGAL_TRIAL_TRANSITIONS[TrialPhase.PENDING] == frozenset({TrialPhase.RUNNING})
        assert LEGAL_TRIAL_TRANSITIONS[TrialPhase.RUNNING] == frozenset(
            {TrialPhase.COMMITTED, TrialPhase.ABANDONED}
        )
        assert LEGAL_TRIAL_TRANSITIONS[TrialPhase.COMMITTED] == frozenset()
        assert LEGAL_TRIAL_TRANSITIONS[TrialPhase.ABANDONED] == frozenset()

    def test_terminal_trial_phases_are_committed_and_abandoned(self) -> None:
        assert frozenset({TrialPhase.COMMITTED, TrialPhase.ABANDONED}) == TERMINAL_TRIAL_PHASES
        for phase in TrialPhase:
            assert is_terminal_trial(phase) == (phase in TERMINAL_TRIAL_PHASES)

    def test_legal_trial_transition_is_accepted(self) -> None:
        trial_id = TrialId("trial-1")
        assert_trial_transition(TrialPhase.PENDING, TrialPhase.RUNNING, trial_id=trial_id)

    def test_committed_trial_cannot_be_reopened(self) -> None:
        trial_id = TrialId("trial-1")
        with pytest.raises(TransitionError) as exc_info:
            assert_trial_transition(TrialPhase.COMMITTED, TrialPhase.RUNNING, trial_id=trial_id)
        assert exc_info.value.entity == "trial"
        assert exc_info.value.entity_id == "trial-1"


# --- Attempt phase state machine ----------------------------------------------


class TestAttemptPhaseTransitions:
    def test_legal_attempt_transitions_match_closed_model(self) -> None:
        assert LEGAL_ATTEMPT_TRANSITIONS[AttemptPhase.PENDING] == frozenset(
            {AttemptPhase.IN_PROGRESS}
        )
        assert LEGAL_ATTEMPT_TRANSITIONS[AttemptPhase.IN_PROGRESS] == frozenset(
            {AttemptPhase.SUCCEEDED, AttemptPhase.NON_SCORED}
        )
        assert LEGAL_ATTEMPT_TRANSITIONS[AttemptPhase.SUCCEEDED] == frozenset()
        assert LEGAL_ATTEMPT_TRANSITIONS[AttemptPhase.NON_SCORED] == frozenset()

    def test_terminal_attempt_phases_are_succeeded_and_non_scored(self) -> None:
        assert (
            frozenset({AttemptPhase.SUCCEEDED, AttemptPhase.NON_SCORED}) == TERMINAL_ATTEMPT_PHASES
        )
        for phase in AttemptPhase:
            assert is_terminal_attempt(phase) == (phase in TERMINAL_ATTEMPT_PHASES)

    def test_pending_to_in_progress_is_legal(self) -> None:
        attempt_id = AttemptId("attempt-1")
        assert_attempt_transition(
            AttemptPhase.PENDING, AttemptPhase.IN_PROGRESS, attempt_id=attempt_id
        )

    def test_in_progress_to_succeeded_is_legal(self) -> None:
        attempt_id = AttemptId("attempt-1")
        assert_attempt_transition(
            AttemptPhase.IN_PROGRESS, AttemptPhase.SUCCEEDED, attempt_id=attempt_id
        )

    def test_in_progress_to_non_scored_is_legal(self) -> None:
        attempt_id = AttemptId("attempt-1")
        assert_attempt_transition(
            AttemptPhase.IN_PROGRESS, AttemptPhase.NON_SCORED, attempt_id=attempt_id
        )

    def test_succeeded_attempt_cannot_revert_to_in_progress(self) -> None:
        attempt_id = AttemptId("attempt-1")
        with pytest.raises(TransitionError) as exc_info:
            assert_attempt_transition(
                AttemptPhase.SUCCEEDED, AttemptPhase.IN_PROGRESS, attempt_id=attempt_id
            )
        assert exc_info.value.entity == "attempt"


# --- Bounded retry eligibility ------------------------------------------------


class TestRetryEligibility:
    def test_transient_failure_within_bound_is_retryable(self) -> None:
        assert can_retry(outcome=NonScoredOutcome.TRANSIENT_FAILURE, attempt_count=1, max_retries=2)

    def test_transient_failure_at_bound_is_not_retryable(self) -> None:
        # attempt_count counts completed attempts; with max_retries=2, a 3rd attempt
        # would exceed the bound (1 initial + 2 retries = 3 total).
        assert not can_retry(
            outcome=NonScoredOutcome.TRANSIENT_FAILURE, attempt_count=3, max_retries=2
        )

    @pytest.mark.parametrize(
        "outcome",
        sorted(o for o in NonScoredOutcome if o is not NonScoredOutcome.TRANSIENT_FAILURE),
    )
    def test_non_transient_outcomes_are_never_retryable(self, outcome: NonScoredOutcome) -> None:
        assert not can_retry(outcome=outcome, attempt_count=1, max_retries=5)

    def test_negative_retry_bound_rejects(self) -> None:
        # Given a transient failure with a nonsensical negative bound.
        # When checking eligibility.
        # Then it is rejected (no retry under an invalid bound).
        assert not can_retry(
            outcome=NonScoredOutcome.TRANSIENT_FAILURE, attempt_count=1, max_retries=-1
        )

    def test_retry_exhausted_error_carries_lineage_fields(self) -> None:
        # Given a trial that has exhausted its retry budget.
        trial_id = TrialId("trial-1")
        # When raising the typed error.
        with pytest.raises(RetryExhaustedError) as exc_info:
            raise RetryExhaustedError(trial_id=trial_id, attempted_count=3, max_retries=2)
        # Then the lineage fields are preserved and message is non-empty.
        err = exc_info.value
        assert err.trial_id == trial_id
        assert err.attempted_count == 3
        assert err.max_retries == 2
        assert str(err)


# --- Typed transition error ---------------------------------------------------


class TestTransitionError:
    def test_error_carries_entity_and_phases(self) -> None:
        with pytest.raises(TransitionError) as exc_info:
            raise TransitionError(
                entity="trial",
                entity_id="t-7",
                current="pending",
                attempted="committed",
                reason="illegal skip",
            )
        err = exc_info.value
        assert err.entity == "trial"
        assert err.entity_id == "t-7"
        assert err.current == "pending"
        assert err.attempted == "committed"
        assert err.reason == "illegal skip"
        assert isinstance(err, ValueError)
        assert str(err)


# --- Exact resume verdict (pure) ----------------------------------------------


def _checkpoint(
    *,
    generation: Generation,
    optimizer_version: str = "0.1.0",
    optuna_version: str = "4.9.0",
    fmt: str = "pickle.v1",
) -> CheckpointIdentity:
    return CheckpointIdentity(
        optimizer_version=optimizer_version,
        optuna_version=optuna_version,
        checkpoint_format=fmt,
        generation=generation,
    )


class TestExactResumeVerdict:
    def test_history_mode_never_requires_checkpoint(self) -> None:
        # Given history resume with no checkpoint and no committed boundary.
        verdict = check_exact_resume(_history_request(), _V)
        # Then history resume is always eligible (read-only, no sampler continuity).
        assert verdict.mode is ResumeMode.HISTORY
        assert verdict.eligible
        assert verdict.reason is None

    def test_exact_resume_succeeds_when_all_identity_matches(self) -> None:
        verdict = check_exact_resume(_request(checkpoint=_checkpoint(generation=_DEFAULT_GEN)), _V)
        assert verdict.mode is ResumeMode.EXACT
        assert verdict.eligible
        assert verdict.reason is None

    def test_exact_resume_rejects_orphan_in_progress(self) -> None:
        verdict = check_exact_resume(
            _request(has_orphan=True, checkpoint=_checkpoint(generation=_DEFAULT_GEN)), _V
        )
        assert not verdict.eligible
        assert verdict.reason is ResumeIncompatibilityReason.ORPHAN_IN_PROGRESS

    def test_exact_resume_rejects_optimizer_version_mismatch(self) -> None:
        verdict = check_exact_resume(
            _request(checkpoint=_checkpoint(generation=_DEFAULT_GEN)), _V_OTHER_OPT
        )
        assert not verdict.eligible
        assert verdict.reason is ResumeIncompatibilityReason.OPTIMIZER_VERSION_MISMATCH

    def test_exact_resume_rejects_optuna_version_mismatch(self) -> None:
        verdict = check_exact_resume(
            _request(checkpoint=_checkpoint(generation=_DEFAULT_GEN)), _V_OTHER_OPTUNA
        )
        assert not verdict.eligible
        assert verdict.reason is ResumeIncompatibilityReason.OPTUNA_VERSION_MISMATCH

    def test_exact_resume_rejects_checkpoint_format_mismatch(self) -> None:
        # Given a checkpoint whose format differs from the current expectation.
        verdict = check_exact_resume(
            _request(
                committed=Generation(0),
                trial=Generation(0),
                checkpoint=_checkpoint(generation=Generation(0), fmt="pickle.v1"),
            ),
            OptimizerVersions("0.1.0", "4.9.0", "other.v2"),
        )
        assert not verdict.eligible
        assert verdict.reason is ResumeIncompatibilityReason.CHECKPOINT_FORMAT_MISMATCH

    def test_exact_resume_rejects_missing_checkpoint(self) -> None:
        # Given exact resume with no sampler checkpoint file at all.
        verdict = check_exact_resume(_request(checkpoint=None), _V)
        assert not verdict.eligible
        assert verdict.reason is ResumeIncompatibilityReason.MISSING_CHECKPOINT

    def test_exact_resume_rejects_stale_generation(self) -> None:
        # committed boundary (3) is behind the latest committed trial (4) ->
        # partial publication, cannot claim exactness at the latest boundary.
        verdict = check_exact_resume(
            _request(
                committed=Generation(3),
                trial=Generation(4),
                checkpoint=_checkpoint(generation=Generation(3)),
            ),
            _V,
        )
        assert not verdict.eligible
        assert verdict.reason is ResumeIncompatibilityReason.PARTIAL_PUBLICATION

    def test_exact_resume_rejects_checkpoint_generation_ahead_of_boundary(self) -> None:
        verdict = check_exact_resume(
            _request(
                committed=Generation(2),
                trial=Generation(2),
                checkpoint=_checkpoint(generation=Generation(3)),
            ),
            _V,
        )
        assert not verdict.eligible
        assert verdict.reason is ResumeIncompatibilityReason.STALE_GENERATION

    def test_exact_resume_rejects_no_boundary_when_checkpoint_present(self) -> None:
        verdict = check_exact_resume(
            _request(
                committed=None,
                trial=None,
                checkpoint=_checkpoint(generation=Generation(0)),
            ),
            _V,
        )
        assert not verdict.eligible
        assert verdict.reason is ResumeIncompatibilityReason.NO_LATEST_BOUNDARY

    def test_exact_resume_unavailable_error_carries_reason(self) -> None:
        with pytest.raises(ExactResumeUnavailableError) as exc_info:
            raise ExactResumeUnavailableError(
                reason=ResumeIncompatibilityReason.MISSING_CHECKPOINT,
                detail="no file at checkpoints/gen-0003.ckpt",
            )
        err = exc_info.value
        assert err.reason is ResumeIncompatibilityReason.MISSING_CHECKPOINT
        assert "gen-0003" in err.detail
        assert str(err)


_V = OptimizerVersions("0.1.0", "4.9.0", "pickle.v1")
_V_OTHER_OPT = OptimizerVersions("0.2.0", "4.9.0", "pickle.v1")
_V_OTHER_OPTUNA = OptimizerVersions("0.1.0", "4.10.0", "pickle.v1")


def _history_request() -> ResumeRequest:
    return ResumeRequest(
        mode=ResumeMode.HISTORY,
        run_optimizer_version="0.1.0",
        run_optuna_version="4.9.0",
        latest_committed_generation=None,
        latest_trial_generation=None,
        checkpoint=None,
        has_orphan_in_progress=False,
    )


def _request(
    *,
    has_orphan: bool = False,
    committed: Generation | None = _DEFAULT_GEN,
    trial: Generation | None = _DEFAULT_GEN,
    checkpoint: CheckpointIdentity | None = None,
) -> ResumeRequest:
    return ResumeRequest(
        mode=ResumeMode.EXACT,
        run_optimizer_version="0.1.0",
        run_optuna_version="4.9.0",
        latest_committed_generation=committed,
        latest_trial_generation=trial,
        checkpoint=checkpoint,
        has_orphan_in_progress=has_orphan,
    )


class TestTypedPrimitivesAreDistinct:
    def test_lifecycle_newtypes_are_str_or_int_underlying(self) -> None:
        # Given the lifecycle semantic primitives.
        # When constructing them.
        # Then they wrap the correct underlying type (compiler-distinct semantics).
        assert isinstance(RunId("r").__class__, type)
        assert RunId("r") == "r"  # NewType is identity at runtime
        assert TrialId("t") == "t"
        assert AttemptId("a") == "a"
        assert Generation(3) == 3
        assert ConfigHash("deadbeef") == "deadbeef"
