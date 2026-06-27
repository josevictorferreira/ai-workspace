"""Behavior tests for run artifact path safety (T1 scaffold).

These tests lock the artifact-root contract: valid run identifiers resolve
under ``<base>/<run-id>/`` while traversal, escape, and malformed identifiers
are rejected with typed errors before any filesystem side effect.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from llama_optimizer.artifacts import (
    ArtifactPathEscapeError,
    InvalidRunIdError,
    RunArtifactRoot,
)


class TestRunArtifactRootCreation:
    def test_valid_run_id_resolves_under_run_root(self, run_root_base: Path) -> None:
        # Given a fresh base directory and a well-formed run identifier.
        run_id = "2026-06-27T10-00-00_gemma26b_q3"
        # When creating the artifact root.
        root = RunArtifactRoot.for_run(run_id, base=run_root_base)
        # Then the resolved root lives directly under the base, named with the run id.
        assert root.path == run_root_base.joinpath(run_id).resolve()
        assert root.path.parent == run_root_base.resolve()

    def test_pre_existing_run_directory_is_not_misreported(self, run_root_base: Path) -> None:
        # Given the run directory already exists from a previous run (stale state).
        run_id = "stable-run"
        (run_root_base / run_id).mkdir(parents=True)
        # When creating the artifact root again.
        root = RunArtifactRoot.for_run(run_id, base=run_root_base)
        # Then the root still points at the canonical path without escaping conventions.
        assert root.path == run_root_base.joinpath(run_id).resolve()

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "..",
            ".",
            "../escape",
            "a/../b",
            "/abs/x",
            "a/b",
            "a\\b",
            "run?bad",
            "x" * 200,
        ],
    )
    def test_invalid_run_ids_are_rejected_with_typed_error(
        self,
        run_root_base: Path,
        bad: str,
    ) -> None:
        # Given a malformed run identifier.
        # When creating the artifact root.
        with pytest.raises(InvalidRunIdError) as exc_info:
            _ = RunArtifactRoot.for_run(bad, base=run_root_base)
        # Then the typed error carries the offending value and a non-empty reason.
        assert exc_info.value.run_id == bad
        assert exc_info.value.reason


class TestArtifactEscapeProtection:
    def test_traversal_relative_is_rejected(self, run_root_base: Path) -> None:
        # Given a valid run root.
        root = RunArtifactRoot.for_run("valid-run", base=run_root_base)
        # When resolving an artifact that traverses outside the root.
        with pytest.raises(ArtifactPathEscapeError):
            _ = root.resolve_artifact("../neighbor/file.json")

    def test_absolute_artifact_path_is_rejected(self, run_root_base: Path) -> None:
        # Given a valid run root.
        root = RunArtifactRoot.for_run("valid-run", base=run_root_base)
        # When resolving an absolute artifact path outside the root.
        with pytest.raises(ArtifactPathEscapeError):
            _ = root.resolve_artifact("/etc/passwd")

    def test_in_root_artifact_resolves_inside_root(self, run_root_base: Path) -> None:
        # Given a valid run root.
        root = RunArtifactRoot.for_run("valid-run", base=run_root_base)
        # When resolving a nested in-root artifact.
        resolved = root.resolve_artifact("trial-001/metrics.json")
        # Then the resolved path stays inside the run root.
        assert root.path in resolved.parents
        assert resolved.name == "metrics.json"
