"""Standards-compliant JSON boundary for server artifacts (T9).

Parses raw JSON strings via the stdlib :mod:`json` decoder (the real
standards-compliant parser) using ``object_hook`` to capture typed
``Mapping[str, object]`` values without leaking ``Any`` through the boundary
under basedpyright ``reportAny``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


def loads_mapping(
    raw: str, *, error: type, malformed_reason: str = "malformed JSON"
) -> Mapping[str, object]:
    """Parse ``raw`` as standards-compliant JSON and return a typed mapping.

    Uses :func:`json.loads` with an ``object_hook`` that captures each decoded
    JSON object as a typed ``Mapping[str, object]``. The ``json.loads`` return
    value (``Any``) is never captured in a named binding. Any decode error or
    non-object top level raises ``error(reason=...)``.
    """
    stripped = raw.strip()
    if not stripped:
        msg = "empty JSON input"
        raise error(msg)
    holder: list[Mapping[str, object]] = []

    def _capture(obj: Mapping[str, object]) -> Mapping[str, object]:
        """Typed object_hook: store each decoded JSON object for retrieval."""
        holder.append(obj)
        return obj

    try:
        json.loads(stripped, object_hook=_capture)
    except json.JSONDecodeError as exc:
        msg = f"{malformed_reason}: {exc}"
        raise error(msg) from exc
    if not stripped.startswith("{") or not holder:
        msg = "expected a JSON object"
        raise error(msg)
    return holder[-1]
