"""Behavior tests for the ``llama-cpp-opt`` CLI scaffold (T1).

The help surface must list the seven reserved command groups, and every
unimplemented command must fail with a typed, clear, nonzero result and no
Python traceback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    from collections.abc import Sequence

from llama_optimizer.cli import app

EXPECTED_GROUPS = {"profile", "run", "resume", "report", "recommend", "smoke", "agent"}

UNIMPLEMENTED_INVOCATIONS: list[list[str]] = [
    ["run"],
    ["resume"],
    ["report"],
    ["recommend"],
    ["smoke"],
    ["agent"],
]


def _combined(result: object) -> str:
    output = getattr(result, "output", "") or ""
    try:
        stderr = getattr(result, "stderr", "") or ""
    except (ValueError, AttributeError):
        stderr = ""
    return output + stderr


class TestHelp:
    def test_help_lists_all_seven_command_groups_and_exits_zero(self) -> None:
        # Given the installed CLI entry point.
        runner = CliRunner()
        # When invoking --help.
        result = runner.invoke(app, ["--help"])
        # Then the help text lists every group and exits zero.
        assert result.exit_code == 0
        rendered = _combined(result)
        for group in EXPECTED_GROUPS:
            assert group in rendered, f"missing command group {group!r} in help"


class TestUnimplementedCommands:
    @pytest.mark.parametrize("argv", UNIMPLEMENTED_INVOCATIONS)
    def test_unimplemented_command_exits_nonzero_without_traceback(
        self,
        argv: Sequence[str],
    ) -> None:
        # Given a reserved-but-unimplemented command path.
        runner = CliRunner()
        # When invoking it.
        result = runner.invoke(app, list(argv))
        # Then it exits nonzero, prints a clear "not implemented" message, and emits no traceback.
        assert result.exit_code != 0
        rendered = _combined(result)
        assert "not implemented" in rendered.lower()
        assert "Traceback" not in rendered
