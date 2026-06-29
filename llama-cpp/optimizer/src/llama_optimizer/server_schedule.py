"""Drift-aware finalist scheduling from the run seed (T9).

Finalist order is randomized from the run seed so no finalist systematically
benefits from thermal warmup or cooldown position bias. Within each finalist,
versioned request specs are interleaved round-robin across raw repetitions,
with warmup always first. The schedule is fully deterministic from the seed
and the input order, so two runs with the same seed and finalists produce the
same interleaved sequence.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from llama_optimizer.server_types import ScheduledFinalist

if TYPE_CHECKING:
    from llama_optimizer.server_types import FinalistEntry, RequestSpec, ServerConfig

@dataclass(frozen=True, slots=True)
class ScheduledRequest:
    """One interleaved request slot: warmup or a raw repetition."""

    is_warmup: bool
    spec: RequestSpec
    repetition: int


def schedule_finalists(
    finalists: tuple[FinalistEntry, ...],
    seed: int,
) -> tuple[ScheduledFinalist, ...]:
    """Return finalists in a seeded-shuffled, reproducible order.

    An empty input yields an empty schedule. The shuffle uses a dedicated
    :class:`random.Random` seeded from ``seed`` so it is independent of global
    RNG state. The original input order is preserved for equal finalists.
    """
    if not finalists:
        return ()
    shuffled = list(finalists)
    rng = random.Random(seed)
    rng.shuffle(shuffled)
    return tuple(ScheduledFinalist(position=i, finalist=f) for i, f in enumerate(shuffled))


def interleave_requests(config: ServerConfig) -> tuple[ScheduledRequest, ...]:
    """Interleave request specs round-robin across repetitions; warmup first.

    Warmup runs every spec once (position 0) before the raw repetitions.
    Repetitions then round-robin: spec0-rep1, spec1-rep1, ..., spec0-rep2, ...
    so workload types are spread across the measurement window rather than
    clustered. The full per-repetition sequence is retained for evidence.
    """
    specs = config.request_specs
    sequence: list[ScheduledRequest] = []
    for spec in specs:
        sequence.append(ScheduledRequest(is_warmup=True, spec=spec, repetition=0))
    for rep in range(1, config.repetitions + 1):
        for spec in specs:
            sequence.append(ScheduledRequest(is_warmup=False, spec=spec, repetition=rep))
    return tuple(sequence)


def total_request_count(config: ServerConfig) -> int:
    """Return the total number of requests (warmup + raw repetitions)."""
    specs = len(config.request_specs)
    warmup = specs
    raw = specs * config.repetitions
    return warmup + raw
