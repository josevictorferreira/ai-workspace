"""Shared pytest fixtures for the optimizer test suite."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def run_root_base(tmp_path: Path) -> Path:
    """Isolated base directory mirroring ``.omo/optimizer-runs``."""
    return tmp_path / "optimizer-runs"
