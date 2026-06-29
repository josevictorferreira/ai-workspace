"""Strict JSONL parser for llama-bench output."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import TypeIs

from llama_optimizer.bench_types import (
    BenchIdentity,
    BenchMeasurement,
    BenchResult,
    BenchSample,
    MeasurementFailureError,
)


def _is_str_mapping(value: object) -> TypeIs[Mapping[str, object]]:
    """Narrow ``object`` to a fully-typed string-keyed mapping."""
    return isinstance(value, Mapping)


def _is_obj_list(value: object) -> TypeIs[list[object]]:
    """Narrow ``object`` to a fully-typed list of objects."""
    return isinstance(value, list)


def _loads_mapping(line: str) -> Mapping[str, object]:
    """Parse one JSON line into a string-keyed mapping or raise typed error."""
    try:
        parsed: object = json.loads(line)  # pyright: ignore[reportAny]
    except json.JSONDecodeError as exc:
        raise MeasurementFailureError(reason=f"malformed JSON line: {exc}") from exc
    if not _is_str_mapping(parsed):
        raise MeasurementFailureError(reason="expected a JSON object")
    return parsed


def _req_str(obj: Mapping[str, object], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str):
        raise MeasurementFailureError(reason=f"missing or non-string field {key!r}")
    return value


def _req_int(obj: Mapping[str, object], key: str) -> int:
    value = obj.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise MeasurementFailureError(reason=f"missing or non-integer field {key!r}")
    return value


def _req_float(obj: Mapping[str, object], key: str) -> float:
    value = obj.get(key)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    raise MeasurementFailureError(reason=f"missing or non-numeric field {key!r}")


def _req_int_list(obj: Mapping[str, object], key: str) -> list[int]:
    value = obj.get(key)
    if not _is_obj_list(value):
        raise MeasurementFailureError(reason=f"missing or non-list field {key!r}")
    result: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            raise MeasurementFailureError(reason=f"non-integer in {key!r}")
        result.append(item)
    return result


def _req_float_list(obj: Mapping[str, object], key: str) -> list[float]:
    value = obj.get(key)
    if not _is_obj_list(value):
        raise MeasurementFailureError(reason=f"missing or non-list field {key!r}")
    result: list[float] = []
    for item in value:
        if isinstance(item, int | float) and not isinstance(item, bool):
            result.append(float(item))
        else:
            raise MeasurementFailureError(reason=f"non-numeric in {key!r}")
    return result


def _check_identity(obj: Mapping[str, object], expected: BenchIdentity) -> None:
    """Cross-check JSONL identity fields against the requested manifest."""
    checks: list[tuple[str, object, object]] = [
        ("model", _req_str(obj, "model"), expected.model_filename),
        ("n_gpu_layers", _req_int(obj, "n_gpu_layers"), expected.n_gpu_layers),
        ("n_batch", _req_int(obj, "n_batch"), expected.n_batch),
        ("n_ubatch", _req_int(obj, "n_ubatch"), expected.n_ubatch),
        ("type_k", _req_str(obj, "type_k"), expected.type_k),
        ("type_v", _req_str(obj, "type_v"), expected.type_v),
        ("n_threads", _req_int(obj, "n_threads"), expected.n_threads),
        ("flash_attn", _req_int(obj, "flash_attn"), expected.flash_attn),
    ]
    for field_name, actual, want in checks:
        if actual != want:
            raise MeasurementFailureError(
                reason=f"identity mismatch {field_name}: expected {want!r}, got {actual!r}"
            )


def parse_bench_jsonl(
    raw: str,
    expected: BenchIdentity,
    expected_workload_names: tuple[str, ...],
) -> BenchResult:
    """Parse raw JSONL lines, cross-check identity, and extract raw samples.

    Each line is one (config, workload) measurement. Identity fields are
    cross-checked against ``expected``. Per-repetition ``samples_ns`` and
    ``samples_ts`` arrays are retained in full. Malformed JSON, missing
    samples, NaN/negative throughput, and identity mismatches all raise
    :class:`MeasurementFailureError`.
    """
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        raise MeasurementFailureError(reason="empty JSONL output")

    measurements: list[BenchMeasurement] = []
    model = ""
    build = 0
    for line in lines:
        obj = _loads_mapping(line)
        _check_identity(obj, expected)
        if not model:
            model = _req_str(obj, "model")
            build = _req_int(obj, "build")
        name = _req_str(obj, "name")
        if name not in expected_workload_names:
            raise MeasurementFailureError(reason=f"unexpected workload {name!r}")
        avg_ts = _req_float(obj, "avg_ts")
        stddev_ts = _req_float(obj, "stddev_ts")
        if not math.isfinite(avg_ts) or avg_ts < 0:
            raise MeasurementFailureError(reason=f"avg_ts invalid for {name}: {avg_ts}")
        samples_ns = _req_int_list(obj, "samples_ns")
        samples_ts = _req_float_list(obj, "samples_ts")
        if not samples_ns or not samples_ts:
            raise MeasurementFailureError(reason=f"missing samples for {name}")
        if len(samples_ns) != len(samples_ts):
            raise MeasurementFailureError(reason=f"sample count mismatch for {name}")
        samples = tuple(
            BenchSample(ns=ns, ts=ts) for ns, ts in zip(samples_ns, samples_ts, strict=True)
        )
        measurements.append(
            BenchMeasurement(
                workload_name=name, avg_ts=avg_ts, stddev_ts=stddev_ts, samples=samples
            )
        )

    found = {m.workload_name for m in measurements}
    missing = set(expected_workload_names) - found
    if missing:
        raise MeasurementFailureError(reason=f"missing workloads: {sorted(missing)}")

    return BenchResult(
        model=model,
        build=build,
        measurements=tuple(measurements),
        raw_jsonl=raw,
    )
