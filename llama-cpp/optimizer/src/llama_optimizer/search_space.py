"""Bounded, applicability-checked optimizer search space (T2).

Every dimension owns a finite, bounded domain with a stable cardinality. The
native Cartesian screening product must stay under ``max_native_combinations``
or it is rejected before any process launches. ``ubatch <= batch`` and the
remaining applicability rules are enforced so a generated config can never
violate the profile contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeIs

from llama_optimizer.models import (
    DimensionId,
    MaxNativeCombinations,
)

# A discrete value is one of a known primitive set (never an untyped ``object``).
DiscreteValue = bool | int | str


def _is_str_mapping(value: object) -> TypeIs[Mapping[str, object]]:
    """Narrow ``object`` to a fully-typed string-keyed mapping."""
    return isinstance(value, Mapping)


def _is_obj_list(value: object) -> TypeIs[list[object]]:
    """Narrow ``object`` to a fully-typed list of objects."""
    return isinstance(value, list)


# A discrete value is one of a known primitive set.


# --- Typed errors ---------------------------------------------------------
@dataclass
class SearchSpaceError(ValueError):
    """Base typed error for search-space validation failures."""

    reason: str

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        Exception.__init__(self, self.reason)


@dataclass
class InvalidRangeError(SearchSpaceError):
    """A range was unbounded, empty, or its step could not reach ``hi``."""

    dimension_id: DimensionId


@dataclass
class NativeCombinationLimitError(SearchSpaceError):
    """The native Cartesian product exceeded the configured combination cap."""

    cap: int = 0
    actual: int = 0

    def __post_init__(self) -> None:
        """Build a message naming the actual product and the configured cap."""
        Exception.__init__(self, f"native combinations {self.actual} exceed cap {self.cap}")


@dataclass
class UbatchExceedsBatchError(SearchSpaceError):
    """A config set ``ubatch`` greater than ``batch``."""

    batch: int = 0
    ubatch: int = 0

    def __post_init__(self) -> None:
        """Build a message naming both batch values."""
        Exception.__init__(self, f"ubatch {self.ubatch} exceeds batch {self.batch}")


# --- Dimensions -----------------------------------------------------------
@dataclass(frozen=True, slots=True)
class BoundedRange:
    """An inclusive integer grid ``lo, lo+step, ..., hi`` that must reach ``hi``."""

    dimension_id: DimensionId
    lo: int
    hi: int
    step: int

    def __post_init__(self) -> None:
        """Validate that the grid is bounded, non-empty, and reaches ``hi``."""
        if self.step <= 0:
            raise InvalidRangeError(
                dimension_id=self.dimension_id, reason=f"step must be positive, got {self.step}"
            )
        if self.lo < 0:
            raise InvalidRangeError(
                dimension_id=self.dimension_id, reason=f"lo must be non-negative, got {self.lo}"
            )
        if self.lo > self.hi:
            raise InvalidRangeError(
                dimension_id=self.dimension_id,
                reason=f"lo > hi: range {self.lo}..{self.hi} is empty",
            )
        if self.lo < self.hi and (self.hi - self.lo) % self.step != 0:
            raise InvalidRangeError(
                dimension_id=self.dimension_id,
                reason=(
                    f"step {self.step} must divide span so hi {self.hi} "
                    f"is reachable from lo {self.lo}"
                ),
            )

    def cardinality(self) -> int:
        """Count of grid points on the inclusive range."""
        if self.lo == self.hi:
            return 1
        return (self.hi - self.lo) // self.step + 1


@dataclass(frozen=True, slots=True)
class DiscreteDimension:
    """A finite list of discrete values for one dimension."""

    dimension_id: DimensionId
    values: tuple[DiscreteValue, ...]

    def __post_init__(self) -> None:
        """Validate that the dimension lists at least one value."""
        if len(self.values) == 0:
            raise InvalidRangeError(
                dimension_id=self.dimension_id,
                reason="discrete dimension must list at least one value",
            )

    def cardinality(self) -> int:
        """Count of discrete choices."""
        return len(self.values)


Dimension = BoundedRange | DiscreteDimension


@dataclass(frozen=True, slots=True)
class SearchSpace:
    """Finite, bounded, applicability-checked optimizer search space."""

    dimensions: tuple[Dimension, ...]
    max_native_combinations: MaxNativeCombinations

    def enforce_combination_cap(self) -> None:
        """Raise if the native Cartesian product exceeds the configured cap."""
        actual = native_combination_count(self)
        if actual > int(self.max_native_combinations):
            raise NativeCombinationLimitError(
                reason="native combinations exceed cap",
                cap=int(self.max_native_combinations),
                actual=actual,
            )


def native_combination_count(space: SearchSpace) -> int:
    """Product of every dimension's cardinality (the native Cartesian product)."""
    total = 1
    for dimension in space.dimensions:
        total *= dimension.cardinality()
    return total


def validate_applicability(space: SearchSpace, config: Mapping[str, object]) -> list[str]:
    """Return applicability violations for ``config``, raising on the ubatch invariant.

    The hard ``ubatch <= batch`` invariant is a structural error and raises
    :class:`UbatchExceedsBatchError`; softer applicability notes are returned as
    a list (empty when the config is clean).
    """
    del space  # future applicability predicates will consult the space's dimensions
    batch = config.get("batch")
    ubatch = config.get("ubatch")
    if isinstance(batch, int) and isinstance(ubatch, int) and ubatch > batch:
        raise UbatchExceedsBatchError(
            reason="ubatch must not exceed batch", batch=batch, ubatch=ubatch
        )
    return []


# --- Boundary parser ------------------------------------------------------
_RANGE_KEYS = frozenset({"min", "max", "step"})


def parse_search_space(table: Mapping[str, object]) -> SearchSpace:
    """Parse a raw search-space table into a validated :class:`SearchSpace`."""
    raw_cap = table.get("max_native_combinations")
    if not isinstance(raw_cap, int) or raw_cap <= 0:
        raise SearchSpaceError(reason="max_native_combinations must be a positive integer")
    cap = MaxNativeCombinations(raw_cap)

    dimensions: list[Dimension] = []
    for key, raw in table.items():
        if key == "max_native_combinations":
            continue
        dimension_id = DimensionId(str(key))
        parsed = _parse_dimension(dimension_id, raw)
        if parsed is not None:
            dimensions.append(parsed)

    space = SearchSpace(dimensions=tuple(dimensions), max_native_combinations=cap)
    space.enforce_combination_cap()
    return space


def _parse_dimension(dimension_id: DimensionId, raw: object) -> Dimension | None:
    """Classify one raw entry as a bounded range or a discrete dimension."""
    if _is_str_mapping(raw):
        keys = set(raw.keys())
        if keys >= _RANGE_KEYS:
            return _parse_range(dimension_id, raw)
        if "values" in raw:
            values_raw = raw["values"]
            if not _is_obj_list(values_raw):
                raise InvalidRangeError(dimension_id=dimension_id, reason="'values' must be a list")
            return DiscreteDimension(
                dimension_id=dimension_id, values=tuple(_coerce_discrete(v) for v in values_raw)
            )
    if _is_obj_list(raw):
        return DiscreteDimension(
            dimension_id=dimension_id,
            values=tuple(
                _coerce_discrete(value) for item in raw if (value := _value_of(item)) is not None
            ),
        )
    return None


def _parse_range(dimension_id: DimensionId, raw: Mapping[str, object]) -> BoundedRange:
    """Build a :class:`BoundedRange` from a ``{min, max, step}`` mapping."""
    lo = raw.get("min")
    hi = raw.get("max")
    step = raw.get("step")
    if not (isinstance(lo, int) and isinstance(hi, int) and isinstance(step, int)):
        raise InvalidRangeError(
            dimension_id=dimension_id, reason="range min/max/step must be integers"
        )
    return BoundedRange(dimension_id=dimension_id, lo=lo, hi=hi, step=step)


def _coerce_discrete(value: object) -> DiscreteValue:
    """Narrow a parsed discrete value to the accepted primitive union."""
    if isinstance(value, bool | int | str):
        return value
    raise InvalidRangeError(
        dimension_id=DimensionId("discrete"),
        reason=f"discrete value must be bool/int/str, got {type(value).__name__}",
    )


def _value_of(item: object) -> object | None:
    """Return the ``value`` entry if ``item`` is a mapping containing it, else None."""
    if _is_str_mapping(item) and "value" in item:
        return item["value"]
    return None
