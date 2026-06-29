"""Behavior tests for Optuna resume capability under injected faults (T7)."""

from __future__ import annotations

import pickle

import optuna
import pytest

from llama_optimizer.optuna_adapter import OptunaAdapter, OptunaResumeError
from llama_optimizer.search_space import SearchSpace, parse_search_space


def _space() -> SearchSpace:
    return parse_search_space(
        {
            "max_native_combinations": 2_000_000,
            "gpu_layers": {"min": 1, "max": 99, "step": 1},
            "batch": {"min": 64, "max": 2048, "step": 64},
            "kv_cache_types": [{"value": "f16"}, {"value": "q8_0"}, {"value": "q4_0"}],
            "flash_attention": {"values": [True, False]},
        }
    )


class TestResumeFaults:
    def test_corrupt_checkpoint_bytes_raises_error(self) -> None:
        space = _space()
        directions = [optuna.study.StudyDirection.MAXIMIZE, optuna.study.StudyDirection.MINIMIZE]

        garbage = b"invalid-pickle-data"
        with pytest.raises(
            (TypeError, pickle.UnpicklingError, KeyError, AttributeError, IndexError)
        ):
            _ = OptunaAdapter.from_bytes(
                garbage,
                search_space=space,
                directions=directions,
                seed=42,
            )

    def test_invalid_pickle_tuple_raises_type_error(self) -> None:
        space = _space()
        directions = [optuna.study.StudyDirection.MAXIMIZE, optuna.study.StudyDirection.MINIMIZE]

        # Pickle a single object instead of a tuple of length 2
        bad_data = pickle.dumps("not-a-tuple")
        with pytest.raises(OptunaResumeError) as exc_info:
            _ = OptunaAdapter.from_bytes(
                bad_data,
                search_space=space,
                directions=directions,
                seed=42,
            )
        assert "valid state tuple" in str(exc_info.value)

    def test_mismatched_directions_count_raises_value_error(self) -> None:
        space = _space()
        directions = [optuna.study.StudyDirection.MAXIMIZE, optuna.study.StudyDirection.MINIMIZE]

        adapter = OptunaAdapter(space, directions, seed=42)
        state_bytes = adapter.to_bytes()

        # Try to resume with directions of different length
        wrong_directions = [optuna.study.StudyDirection.MAXIMIZE]
        with pytest.raises(ValueError, match="Directions count mismatch") as exc_info:
            _ = OptunaAdapter.from_bytes(
                state_bytes,
                search_space=space,
                directions=wrong_directions,
                seed=42,
            )
        assert "Directions count mismatch" in str(exc_info.value)

    def test_mismatched_direction_values_raises_value_error(self) -> None:
        space = _space()
        directions = [
            optuna.study.StudyDirection.MAXIMIZE,
            optuna.study.StudyDirection.MINIMIZE,
        ]

        adapter = OptunaAdapter(space, directions, seed=42)
        state_bytes = adapter.to_bytes()

        # Try to resume with different directions (e.g. reverse directions)
        wrong_directions = [
            optuna.study.StudyDirection.MINIMIZE,
            optuna.study.StudyDirection.MAXIMIZE,
        ]
        with pytest.raises(ValueError, match="Directions mismatch") as exc_info:
            _ = OptunaAdapter.from_bytes(
                state_bytes,
                search_space=space,
                directions=wrong_directions,
                seed=42,
            )
        assert "Directions mismatch" in str(exc_info.value)
