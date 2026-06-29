"""Strict boundary parser for llama-server finalist artifacts (T9).

Parses readiness.json, metrics.json, and responses.jsonl written by
llama-server. Every field is typed at the boundary; missing, malformed, or
identity-mismatched data fails closed as a typed :class:`ServerError`.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeIs

from llama_optimizer.server_types import (
    MetricsParseError,
    ReadinessTimeoutError,
    ServerIdentityMismatchError,
    ServerMetrics,
)

if TYPE_CHECKING:
    from llama_optimizer.server_types import ServerIdentity


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    """Parsed readiness marker from the server."""

    ready: bool
    ready_at_ms: int
    slots: int


@dataclass(frozen=True, slots=True)
class ParsedResponse:
    """One parsed response line from responses.jsonl."""

    index: int
    response: str
    ttft_ms: float
    latency_ms: float
    quality_pass: bool


def _is_mapping(value: object) -> TypeIs[Mapping[str, object]]:
    """Narrow ``object`` to a string-keyed mapping."""
    return isinstance(value, Mapping)


def _loads_mapping(raw: str, *, error: type) -> Mapping[str, object]:
    """Parse JSON into a string-keyed mapping or raise the given typed error."""
    try:
        parsed: object = json.loads(raw)  # pyright: ignore[reportAny]
    except json.JSONDecodeError as exc:
        raise error(reason=f"malformed JSON: {exc}") from exc
    if not _is_mapping(parsed):
        raise error(reason="expected a JSON object")
    return parsed


def _req_str(obj: Mapping[str, object], key: str, *, error: type) -> str:
    value = obj.get(key)
    if not isinstance(value, str):
        raise error(reason=f"missing or non-string field {key!r}")
    return value


def _req_int(obj: Mapping[str, object], key: str, *, error: type) -> int:
    value = obj.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise error(reason=f"missing or non-integer field {key!r}")
    return value


def _req_float_list(obj: Mapping[str, object], key: str, *, error: type) -> list[float]:
    value = obj.get(key)
    if not isinstance(value, list):
        raise error(reason=f"missing or non-list field {key!r}")
    result: list[float] = []
    for item in value:
        if isinstance(item, int | float) and not isinstance(item, bool):
            result.append(float(item))
        else:
            raise error(reason=f"non-numeric in {key!r}")
    return result


def parse_readiness(raw: str) -> ReadinessResult:
    """Parse readiness.json strictly; empty/missing raises ReadinessTimeoutError."""
    if not raw.strip():
        raise ReadinessTimeoutError(reason="readiness marker not written")
    obj = _loads_mapping(raw, error=ReadinessTimeoutError)
    ready = obj.get("ready")
    if not isinstance(ready, bool) or not ready:
        raise ReadinessTimeoutError(reason="server reported not-ready")
    return ReadinessResult(
        ready=True,
        ready_at_ms=_req_int(obj, "ready_at_ms", error=ReadinessTimeoutError),
        slots=_req_int(obj, "slots", error=ReadinessTimeoutError),
    )


def _req_float(obj: Mapping[str, object], key: str, *, error: type) -> float:
    value = obj.get(key)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    raise error(reason=f"missing or non-numeric field {key!r}")

def parse_server_metrics(raw: str, expected: ServerIdentity) -> ServerMetrics:
    """Parse metrics.json strictly, cross-check identity, or raise MetricsParseError."""
    if not raw.strip():
        raise MetricsParseError(reason="metrics artifact not written")
    obj = _loads_mapping(raw, error=MetricsParseError)
    model = _req_str(obj, "model", error=MetricsParseError)
    if model != expected.model_filename:
        raise ServerIdentityMismatchError(
            reason=f"model mismatch: expected {expected.model_filename!r}, got {model!r}"
        )
    backend = _req_str(obj, "backend", error=MetricsParseError)
    if backend != expected.backend:
        raise ServerIdentityMismatchError(
            reason=f"backend mismatch: expected {expected.backend!r}, got {backend!r}"
        )
    p_ts = _req_float(obj, "prompt_throughput", error=MetricsParseError)
    g_ts = _req_float(obj, "generation_throughput", error=MetricsParseError)
    if not (math.isfinite(p_ts) and math.isfinite(g_ts)) or p_ts < 0 or g_ts < 0:
        raise MetricsParseError(reason=f"invalid throughput: pp={p_ts}, tg={g_ts}")
    ttft = tuple(_req_float_list(obj, "ttft_ms", error=MetricsParseError))
    lat = tuple(_req_float_list(obj, "request_latency_ms", error=MetricsParseError))
    errors = _req_int(obj, "errors", error=MetricsParseError)
    quality = obj.get("quality_pass")
    if not isinstance(quality, bool):
        raise MetricsParseError(reason="missing or non-bool field 'quality_pass'")
    return ServerMetrics(
        prompt_throughput=p_ts,
        generation_throughput=g_ts,
        ttft_ms=ttft,
        request_latency_ms=lat,
        slots=_req_int(obj, "slots", error=MetricsParseError),
        errors=errors,
        quality_pass=quality,
    )


def parse_responses(raw: str) -> tuple[ParsedResponse, ...]:
    """Parse responses.jsonl strictly into typed response records."""
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        raise MetricsParseError(reason="empty responses output")
    results: list[ParsedResponse] = []
    for line in lines:
        obj = _loads_mapping(line, error=MetricsParseError)
        quality = obj.get("quality_pass")
        if not isinstance(quality, bool):
            raise MetricsParseError(reason="missing or non-bool 'quality_pass' in response")
        results.append(
            ParsedResponse(
                index=_req_int(obj, "index", error=MetricsParseError),
                response=_req_str(obj, "response", error=MetricsParseError),
                ttft_ms=_req_float(obj, "ttft_ms", error=MetricsParseError),
                latency_ms=_req_float(obj, "latency_ms", error=MetricsParseError),
                quality_pass=quality,
            )
        )
    return tuple(results)
