"""Behavior tests for drift-aware finalist scheduling (T9).

Asserts that finalist order is seeded-shuffled (reproducible from the run
seed), that request specs are interleaved round-robin with warmup first, and
that total request counts are correct.
"""

from __future__ import annotations

from llama_optimizer.lifecycle import TrialId
from llama_optimizer.server_schedule import (
    interleave_requests,
    schedule_finalists,
    total_request_count,
)
from llama_optimizer.server_types import (
    CODING_SPEC,
    CONCURRENCY_SPEC,
    DEFAULT_SERVER_CONFIG,
    LATENCY_SPEC,
    TOOL_USE_SPEC,
    EligibilityStatus,
    FinalistEntry,
    ServerConfig,
    ServerIdentity,
)


def _identity(name: str) -> ServerIdentity:
    return ServerIdentity(
        model_filename=f"{name}.gguf",
        backend="rocm",
        build_label="b1234",
        n_gpu_layers=99,
        n_batch=2048,
        n_ubatch=512,
        type_k="f16",
        type_v="f16",
        n_threads=16,
        flash_attn=1,
        use_mmap=True,
    )


def _finalist(name: str) -> FinalistEntry:
    return FinalistEntry(
        finalist_id=f"f-{name}",
        identity=_identity(name),
        trial_id=TrialId(f"t-{name}"),
        eligibility=EligibilityStatus.ELIGIBLE,
    )


class TestSeededReproducibility:
    def test_same_seed_produces_same_order(self) -> None:
        finalists = tuple(_finalist(n) for n in ("a", "b", "c", "d", "e"))
        sched1 = schedule_finalists(finalists, seed=42)
        sched2 = schedule_finalists(finalists, seed=42)
        ids1 = [s.finalist.finalist_id for s in sched1]
        ids2 = [s.finalist.finalist_id for s in sched2]
        assert ids1 == ids2

    def test_positions_are_zero_indexed_contiguous(self) -> None:
        finalists = tuple(_finalist(n) for n in ("a", "b", "c"))
        sched = schedule_finalists(finalists, seed=99)
        positions = [s.position for s in sched]
        assert positions == [0, 1, 2]

    def test_all_finalists_present_exactly_once(self) -> None:
        finalists = tuple(_finalist(n) for n in ("a", "b", "c", "d"))
        sched = schedule_finalists(finalists, seed=7)
        ids = sorted(s.finalist.finalist_id for s in sched)
        assert ids == ["f-a", "f-b", "f-c", "f-d"]


class TestDifferentSeeds:
    def test_different_seeds_can_differ(self) -> None:
        finalists = tuple(_finalist(n) for n in ("a", "b", "c", "d", "e", "f"))
        sched1 = schedule_finalists(finalists, seed=1)
        sched2 = schedule_finalists(finalists, seed=2)
        ids1 = [s.finalist.finalist_id for s in sched1]
        ids2 = [s.finalist.finalist_id for s in sched2]
        assert ids1 != ids2

    def test_single_finalist_unchanged_by_seed(self) -> None:
        finalists = (_finalist("solo"),)
        sched = schedule_finalists(finalists, seed=123)
        assert len(sched) == 1
        assert sched[0].finalist.finalist_id == "f-solo"

    def test_empty_input_yields_empty_schedule(self) -> None:
        sched = schedule_finalists((), seed=42)
        assert sched == ()


class TestInterleaveRequests:
    def test_warmup_runs_first(self) -> None:
        config = ServerConfig(
            repetitions=2,
            delay_seconds=0,
            parallel=1,
            readiness_timeout_seconds=5,
            cooldown_seconds=0,
            request_specs=(CODING_SPEC, TOOL_USE_SPEC),
        )
        seq = interleave_requests(config)
        warmup_specs = [r for r in seq if r.is_warmup]
        assert len(warmup_specs) == 2
        assert all(r.repetition == 0 for r in warmup_specs)
        assert warmup_specs[0].spec.name == "coding-v1"
        assert warmup_specs[1].spec.name == "tool-use-v1"

    def test_repetitions_round_robin(self) -> None:
        config = ServerConfig(
            repetitions=2,
            delay_seconds=0,
            parallel=1,
            readiness_timeout_seconds=5,
            cooldown_seconds=0,
            request_specs=(CODING_SPEC, TOOL_USE_SPEC),
        )
        seq = interleave_requests(config)
        raw = [r for r in seq if not r.is_warmup]
        assert len(raw) == 4
        assert raw[0].spec.name == "coding-v1"
        assert raw[0].repetition == 1
        assert raw[1].spec.name == "tool-use-v1"
        assert raw[1].repetition == 1
        assert raw[2].spec.name == "coding-v1"
        assert raw[2].repetition == 2
        assert raw[3].spec.name == "tool-use-v1"
        assert raw[3].repetition == 2

    def test_default_config_has_all_four_kinds(self) -> None:
        seq = interleave_requests(DEFAULT_SERVER_CONFIG)
        names = {r.spec.name for r in seq}
        assert "coding-v1" in names
        assert "tool-use-v1" in names
        assert "concurrency-v1" in names
        assert "latency-v1" in names


class TestTotalRequestCount:
    def test_warmup_plus_raw(self) -> None:
        config = ServerConfig(
            repetitions=3,
            delay_seconds=0,
            parallel=1,
            readiness_timeout_seconds=5,
            cooldown_seconds=0,
            request_specs=(CODING_SPEC, TOOL_USE_SPEC, CONCURRENCY_SPEC, LATENCY_SPEC),
        )
        assert total_request_count(config) == 4 + 4 * 3

    def test_matches_interleave_length(self) -> None:
        assert total_request_count(DEFAULT_SERVER_CONFIG) == len(
            interleave_requests(DEFAULT_SERVER_CONFIG)
        )
