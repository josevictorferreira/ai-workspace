"""Optuna adapter for search optimization (T7)."""

from __future__ import annotations

import pickle
from typing import TYPE_CHECKING, Self, final

import optuna

from llama_optimizer.search_space import suggest_dimension

if TYPE_CHECKING:
    from collections.abc import Sequence

    from llama_optimizer.search_space import DiscreteValue, SearchSpace


class OptunaResumeError(ValueError):
    """Mismatched directions or state format on Optuna study resume."""


def _dominates(
    values_a: list[float],
    values_b: list[float],
    directions: list[optuna.study.StudyDirection],
) -> bool:
    """Return True if values_a dominates values_b."""
    better = False
    for val_a, val_b, direction in zip(values_a, values_b, directions, strict=True):
        if direction == optuna.study.StudyDirection.MINIMIZE:
            if val_a > val_b:
                return False
            if val_a < val_b:
                better = True
        else:
            if val_a < val_b:
                return False
            if val_a > val_b:
                better = True
    return better


def _is_dominated(
    candidate: optuna.trial.FrozenTrial,
    feasible: list[optuna.trial.FrozenTrial],
    c_values: list[float],
    directions: list[optuna.study.StudyDirection],
) -> bool:
    """Check if any other trial dominates the candidate."""
    for other in feasible:
        if other.number == candidate.number:
            continue
        other_values: object = other.values  # pyright: ignore[reportAny]
        if not isinstance(other_values, list):
            continue
        o_values: list[float] = [
            float(v)
            for v in other_values  # pyright: ignore[reportUnknownVariableType]
            if isinstance(v, int | float)
        ]
        if len(o_values) != len(directions):
            continue
        if _dominates(o_values, c_values, directions):
            return True
    return False


def _add_unique(
    non_dominated: list[optuna.trial.FrozenTrial],
    candidate: optuna.trial.FrozenTrial,
    c_values: list[float],
) -> None:
    """Add a candidate if its values are not duplicate on the Pareto front."""
    duplicate = False
    for exist in non_dominated:
        exist_values: object = exist.values  # pyright: ignore[reportAny]
        if not isinstance(exist_values, list):
            continue
        e_values: list[float] = [
            float(v)
            for v in exist_values  # pyright: ignore[reportUnknownVariableType]
            if isinstance(v, int | float)
        ]
        if e_values == c_values:
            duplicate = True
            break
    if not duplicate:
        non_dominated.append(candidate)


@final
class OptunaAdapter:
    """Adapts Optuna study and sampler states for the llama optimizer lifecycle."""

    search_space: SearchSpace
    directions: list[optuna.study.StudyDirection]
    seed: int
    sampler: optuna.samplers.TPESampler
    study: optuna.Study

    def __init__(
        self,
        search_space: SearchSpace,
        directions: Sequence[str | optuna.study.StudyDirection],
        seed: int,
    ) -> None:
        """Initialize a new study with a seeded TPESampler and constraints mapping."""
        self.search_space = search_space
        self.directions = [
            d
            if isinstance(d, optuna.study.StudyDirection)
            else optuna.study.StudyDirection[d.upper()]
            for d in directions
        ]
        self.seed = seed
        self.sampler = optuna.samplers.TPESampler(
            seed=seed,
            constraints_func=self._constraints_func,
        )
        self.study = optuna.create_study(
            directions=self.directions,
            sampler=self.sampler,
        )

    def _constraints_func(self, trial: optuna.trial.FrozenTrial) -> list[float]:
        """Return the constraint violation mapped from user attributes."""
        violation: object = trial.user_attrs.get("constraint_violation", 0.0)  # pyright: ignore[reportAny]
        if not isinstance(violation, int | float):
            return [0.0]
        return [float(violation)]

    def ask(self) -> tuple[optuna.Trial, dict[str, DiscreteValue]]:
        """Ask for a new parameter suggestion from the study search space."""
        trial = self.study.ask()
        config: dict[str, DiscreteValue] = {}
        for dim in self.search_space.dimensions:
            val = suggest_dimension(trial, dim)
            config[str(dim.dimension_id)] = val
        return trial, config

    def tell(self, trial: optuna.Trial, values: list[float]) -> None:
        """Mark a completed trial as business-feasible and report objective metrics."""
        trial.set_user_attr("constraint_violation", 0.0)
        _ = self.study.tell(trial, values)

    def tell_infeasible(
        self,
        trial: optuna.Trial,
        fallback_values: list[float] | None = None,
    ) -> None:
        """Mark a completed trial as infeasible (violating limits) with penalty objectives."""
        trial.set_user_attr("constraint_violation", 1.0)
        if fallback_values is None:
            fallback: list[float] = []
            for d in self.directions:
                if d == optuna.study.StudyDirection.MINIMIZE:
                    fallback.append(float("inf"))
                else:
                    fallback.append(float("-inf"))
        else:
            fallback = fallback_values
        _ = self.study.tell(trial, fallback)

    def best_feasible_trials(self) -> list[optuna.trial.FrozenTrial]:
        """Return the Multi-Objective Pareto front restricted to feasible trials."""
        feasible: list[optuna.trial.FrozenTrial] = []
        for trial in self.study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETE:
                violation: object = trial.user_attrs.get("constraint_violation", 0.0)  # pyright: ignore[reportAny]
                if isinstance(violation, int | float) and violation <= 0.0:
                    feasible.append(trial)

        non_dominated: list[optuna.trial.FrozenTrial] = []
        for candidate in feasible:
            candidate_values: object = candidate.values  # pyright: ignore[reportAny]
            if not isinstance(candidate_values, list):
                continue
            c_values: list[float] = [
                float(v)
                for v in candidate_values  # pyright: ignore[reportUnknownVariableType]
                if isinstance(v, int | float)
            ]
            if len(c_values) != len(self.directions):
                continue
            if not _is_dominated(candidate, feasible, c_values, self.directions):
                _add_unique(non_dominated, candidate, c_values)
        return non_dominated

    def to_bytes(self) -> bytes:
        """Serialize the study and sampler state atomically."""
        return pickle.dumps((self.study, self.sampler))

    @classmethod
    def from_bytes(
        cls,
        content: bytes,
        search_space: SearchSpace,
        directions: Sequence[str | optuna.study.StudyDirection],
        seed: int,
    ) -> Self:
        """Deserialize and restore the study and sampler state exactly."""
        val: object = pickle.loads(content)  # pyright: ignore[reportAny]
        expected_len = 2
        if not isinstance(val, tuple) or len(val) != expected_len:  # pyright: ignore[reportUnknownArgumentType]
            msg = "Loaded bytes do not represent a valid state tuple"
            raise OptunaResumeError(msg)
        study_val, sampler_val = val  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(study_val, optuna.Study) or not isinstance(
            sampler_val, optuna.samplers.TPESampler
        ):
            msg = "Loaded bytes do not represent a valid Study/TPESampler pair"
            raise OptunaResumeError(msg)
        inst = cls.__new__(cls)
        inst.search_space = search_space
        inst.directions = [
            d
            if isinstance(d, optuna.study.StudyDirection)
            else optuna.study.StudyDirection[d.upper()]
            for d in directions
        ]
        inst.seed = seed
        study_dirs = len(study_val.directions)
        expected_dirs = len(inst.directions)
        if study_dirs != expected_dirs:
            msg = f"Directions count mismatch: study={study_dirs} " + f"expected={expected_dirs}"
            raise OptunaResumeError(msg)
        for d1, d2 in zip(study_val.directions, inst.directions, strict=True):
            if d1 != d2:
                msg = f"Directions mismatch: study={d1.name} expected={d2.name}"
                raise OptunaResumeError(msg)
        inst.study = study_val
        inst.sampler = sampler_val
        return inst
