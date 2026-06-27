"""Behavior tests for the bounded optimizer search space (T2).

The search space must be finite, bounded, and applicability-checked. Every
dimension owns a bounded domain; ``ubatch <= batch`` is enforced; and a native
Cartesian screening product above ``max_native_combinations`` is rejected before
any process is launched.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING

import pytest

from llama_optimizer.models import DimensionId
from llama_optimizer.search_space import (
    BoundedRange,
    InvalidRangeError,
    NativeCombinationLimitError,
    SearchSpaceError,
    UbatchExceedsBatchError,
    native_combination_count,
    parse_search_space,
    validate_applicability,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


def _well_formed_table() -> Mapping[str, object]:
    """A minimal finite, bounded search-space table accepted by the parser."""
    return {
        "max_native_combinations": 2_000_000,
        "gpu_layers": {"min": 1, "max": 99, "step": 1},
        "batch": {"min": 64, "max": 2048, "step": 64},
        "ubatch": {"min": 64, "max": 2048, "step": 64},
        "kv_cache_types": [{"value": "f16"}, {"value": "q8_0"}, {"value": "q4_0"}],
        "flash_attention": {"values": [True, False]},
        "threads": {"values": [8, 16]},
    }


class TestRangeBoundedness:
    def test_finite_range_rounds_to_correct_count(self) -> None:
        # Given a finite inclusive range with a step.
        table = _well_formed_table()
        # When parsing the gpu_layers dimension.
        space = parse_search_space(table)
        gpu_layers = next(
            d for d in space.dimensions if d.dimension_id == DimensionId("gpu_layers")
        )
        # Then the inclusive round count is 99 (1..99 step 1).
        assert gpu_layers.cardinality() == 99

    def test_range_with_explicit_step_rounds_correctly(self) -> None:
        # Given a range with step 64 from 64..2048.
        rng = BoundedRange(dimension_id=DimensionId("batch"), lo=64, hi=2048, step=64)
        # When computing the round count.
        count = rng.cardinality()
        # Then there are 32 values (64,128,...,2048).
        assert count == 32

    def test_single_value_range_has_cardinality_one(self) -> None:
        # Given a degenerate-but-bounded range where lo == hi.
        rng = BoundedRange(dimension_id=DimensionId("x"), lo=512, hi=512, step=1)
        # When computing cardinality.
        assert rng.cardinality() == 1

    @pytest.mark.parametrize(
        ("lo", "hi", "step", "reason_fragment"),
        [
            (100, 10, 1, "lo > hi"),  # inverted -> empty
            (10, 10, 0, "step"),  # zero step
            (-1, 10, 1, "lo"),  # negative bound
            (10, 100, 200, "step"),  # step larger than span (no value at hi)
        ],
    )
    def test_unbounded_or_empty_ranges_are_rejected(
        self,
        lo: int,
        hi: int,
        step: int,
        reason_fragment: str,
    ) -> None:
        # Given an invalid range.
        # When constructing it.
        with pytest.raises(InvalidRangeError) as exc_info:
            _ = BoundedRange(dimension_id=DimensionId("batch"), lo=lo, hi=hi, step=step)
        # Then the typed reason mentions the offending property.
        assert reason_fragment in exc_info.value.reason.lower()


class TestNativeCombinationCount:
    def test_product_of_dimension_cardinalities(self) -> None:
        # Given a well-formed finite space.
        space = parse_search_space(_well_formed_table())
        # When computing the native Cartesian product size.
        count = native_combination_count(space)
        # Then it is the product of each dimension's cardinality (99*32*32*3*2*2).
        assert count == 99 * 32 * 32 * 3 * 2 * 2

    def test_product_below_cap_is_accepted(self) -> None:
        # Given a cap larger than the product.
        space = parse_search_space(_well_formed_table())
        # When validating the combination cap.
        # Then no error is raised.
        space.enforce_combination_cap()

    def test_product_above_cap_is_rejected(self) -> None:
        # Given a cap smaller than the product.
        tight = {**_well_formed_table(), "max_native_combinations": 4}
        # When parsing.
        with pytest.raises(NativeCombinationLimitError) as exc_info:
            _ = parse_search_space(tight)
        # Then the typed error reports the cap and the actual product.
        assert exc_info.value.cap == 4
        assert exc_info.value.actual > 4


class TestApplicability:
    def test_ubatch_greater_than_batch_is_rejected(self) -> None:
        # Given a config candidate where ubatch exceeds batch.
        space = parse_search_space(_well_formed_table())
        # When checking applicability.
        with pytest.raises(UbatchExceedsBatchError) as exc_info:
            _ = validate_applicability(space, {"batch": 512, "ubatch": 1024})
        # Then the typed error reports both values.
        assert exc_info.value.batch == 512
        assert exc_info.value.ubatch == 1024

    def test_ubatch_equal_to_batch_is_accepted(self) -> None:
        # Given a config where ubatch equals batch.
        space = parse_search_space(_well_formed_table())
        # When checking applicability.
        violations = validate_applicability(space, {"batch": 512, "ubatch": 512})
        # Then there are no violations.
        assert violations == []

    def test_ubatch_less_than_batch_is_accepted(self) -> None:
        # Given a config where ubatch is below batch.
        space = parse_search_space(_well_formed_table())
        # When checking applicability.
        assert validate_applicability(space, {"batch": 1024, "ubatch": 256}) == []


class TestSearchSpaceImmutability:
    def test_search_space_is_frozen(self) -> None:
        # Given a parsed space.
        space = parse_search_space(_well_formed_table())
        # When attempting to mutate a field.
        # Then a FrozenInstanceError is raised.
        _field = "max_native_combinations"
        with pytest.raises(FrozenInstanceError):
            setattr(space, _field, 1)

    def test_search_space_error_carries_typed_fields(self) -> None:
        # Given the base error type.
        err = SearchSpaceError(reason="example")
        # When constructing it.
        # Then it exposes the typed reason field and a non-empty message.
        assert err.reason == "example"
        assert str(err)
