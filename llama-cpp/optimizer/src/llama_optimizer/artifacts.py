"""Run artifact path contracts for the optimizer.

Untrusted run identifiers are parsed exactly once, at the boundary, into a
typed ``RunArtifactRoot``. Every artifact access goes through
``resolve_artifact``, which refuses to resolve outside the run root, so a
malformed or adversarial identifier can never reach the filesystem layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, final

RUN_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
DEFAULT_RUN_ROOT: Final[Path] = Path(".omo") / "optimizer-runs"
RUN_ID_MAX_LEN: Final[int] = 128


@final
class InvalidRunIdError(ValueError):
    """Run identifier failed boundary validation."""

    def __init__(self, run_id: str, reason: str) -> None:
        self.run_id = run_id
        self.reason = reason
        super().__init__(f"invalid run id {run_id!r}: {reason}")


@final
class ArtifactPathEscapeError(ValueError):
    """Resolved artifact path would escape the run root."""

    def __init__(self, *, attempted: Path, run_root: Path) -> None:
        self.attempted = attempted
        self.run_root = run_root
        super().__init__(f"artifact path {attempted} escapes run root {run_root}")


@dataclass(frozen=True, slots=True)
class RunArtifactRoot:
    """Canonical, validated root directory for one optimizer run's artifacts."""

    path: Path

    @classmethod
    def for_run(cls, run_id: str, *, base: Path | None = None) -> RunArtifactRoot:
        """Validate ``run_id`` and resolve the canonical artifact root for it."""
        root_base = DEFAULT_RUN_ROOT if base is None else base
        _validate_run_id(run_id)
        return cls(path=(root_base / run_id).resolve())

    def resolve_artifact(self, relative: str) -> Path:
        """Resolve ``relative`` under the run root, refusing any escape."""
        candidate = (self.path / relative).resolve()
        if not _is_within(candidate, self.path):
            raise ArtifactPathEscapeError(attempted=candidate, run_root=self.path)
        return candidate


def _validate_run_id(run_id: str) -> None:
    if not RUN_ID_PATTERN.match(run_id):
        raise InvalidRunIdError(run_id, _describe_invalid_run_id(run_id))


def _describe_invalid_run_id(run_id: str) -> str:
    if run_id == "":
        return "run id must not be empty"
    if len(run_id) > RUN_ID_MAX_LEN:
        return f"run id must be at most {RUN_ID_MAX_LEN} characters"
    if "/" in run_id or "\\" in run_id:
        return "run id must not contain path separators"
    if run_id.startswith((".", "-")):
        return "run id must start with an alphanumeric character"
    return "run id must contain only alphanumerics, '.', '_', or '-'"


def _is_within(child: Path, parent: Path) -> bool:
    if child == parent:
        return True
    return parent in child.parents
