"""Tests for the resumable Optuna search adapter (T7).

Ensures seeded TPESampler determinism, state serialization continuity, and feasible
Pareto front computation under soft and hard constraints.
"""

from __future__ import annotations

import optuna

from llama_optimizer.optuna_adapter import OptunaAdapter
from llama_optimizer.search_space import DiscreteValue, SearchSpace, parse_search_space


def _search_space() -> SearchSpace:
    return parse_search_space(
        {
            "max_native_combinations": 2_000_000,
            "gpu_layers": {"min": 1, "max": 99, "step": 1},
            "batch": {"min": 64, "max": 2048, "step": 64},
            "kv_cache_types": [{"value": "f16"}, {"value": "q8_0"}, {"value": "q4_0"}],
            "flash_attention": {"values": [True, False]},
        }
    )


class TestOptunaAdapterSeeding:
    def test_reproducible_suggestions_with_same_seed(self) -> None:
        space = _search_space()
        directions = [optuna.study.StudyDirection.MAXIMIZE, optuna.study.StudyDirection.MINIMIZE]

        # Instantiate two adapters with the same seed
        adapter1 = OptunaAdapter(space, directions, seed=42)
        adapter2 = OptunaAdapter(space, directions, seed=42)

        configs1: list[dict[str, DiscreteValue]] = []
        configs2: list[dict[str, DiscreteValue]] = []

        for _ in range(5):
            t1, c1 = adapter1.ask()
            t2, c2 = adapter2.ask()
            configs1.append(c1)
            configs2.append(c2)
            adapter1.tell(t1, [50.0, 0.1])
            adapter2.tell(t2, [50.0, 0.1])

        assert configs1 == configs2

    def test_different_suggestions_with_different_seeds(self) -> None:
        space = _search_space()
        directions = [optuna.study.StudyDirection.MAXIMIZE, optuna.study.StudyDirection.MINIMIZE]

        adapter1 = OptunaAdapter(space, directions, seed=42)
        adapter2 = OptunaAdapter(space, directions, seed=43)

        _, c1 = adapter1.ask()
        _, c2 = adapter2.ask()

        # With 5 dimensions, different seeds should produce different configs
        assert c1 != c2


class TestOptunaAdapterSerialization:
    def test_serialize_and_resume_preserves_suggestions(self) -> None:
        space = _search_space()
        directions = [optuna.study.StudyDirection.MAXIMIZE, optuna.study.StudyDirection.MINIMIZE]

        adapter = OptunaAdapter(space, directions, seed=42)

        # Run 3 trials
        for i in range(3):
            t, _ = adapter.ask()
            adapter.tell(t, [10.0 + float(i), 1.0 / (float(i) + 1.0)])

        # Serialize
        state_bytes = adapter.to_bytes()
        assert isinstance(state_bytes, bytes)
        assert len(state_bytes) > 0

        # Restart adapter from bytes
        adapter_resumed = OptunaAdapter.from_bytes(
            state_bytes,
            search_space=space,
            directions=directions,
            seed=42,
        )

        # Confirm next suggestion matches exactly
        _, c_orig = adapter.ask()
        _, c_res = adapter_resumed.ask()

        assert c_orig == c_res


class TestOptunaAdapterConstraints:
    def test_feasible_and_infeasible_pareto_handling(self) -> None:
        space = _search_space()
        directions = [optuna.study.StudyDirection.MAXIMIZE, optuna.study.StudyDirection.MINIMIZE]

        adapter = OptunaAdapter(space, directions, seed=100)

        # Trial 1: Feasible and good: throughput=100.0, latency=0.05
        t1, _ = adapter.ask()
        adapter.tell(t1, [100.0, 0.05])

        # Trial 2: Feasible but dominated by Trial 1: throughput=50.0, latency=0.1
        t2, _ = adapter.ask()
        adapter.tell(t2, [50.0, 0.1])

        # Trial 3: Infeasible: throughput=200.0, latency=0.01 (but VRAM breached)
        t3, _ = adapter.ask()
        adapter.tell_infeasible(t3)

        # Get best feasible trials
        best = adapter.best_feasible_trials()

        # Should only contain Trial 1 (Trial 2 is dominated, Trial 3 is infeasible)
        assert len(best) == 1
        assert best[0].number == t1.number
        assert best[0].user_attrs.get("constraint_violation") == 0.0
