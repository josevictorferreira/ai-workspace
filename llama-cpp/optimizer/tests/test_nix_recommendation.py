"""Emit-only Nix recommendation snippet tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from llama_optimizer.nix_recommendation import (
    NixRecommendationError,
    RecommendationContext,
    render_recommendation,
    write_recommendation,
)
from llama_optimizer.reports import CandidateConfig

if TYPE_CHECKING:
    from pathlib import Path


def _config(
    config_id: str = "ornith-q4",
    *,
    nix_package: str = "Ornith-1.0-9B-Q4_K_M",
    flags: tuple[str, ...] = ("--ctx-size", "32768", "--flash-attn", "on"),
) -> CandidateConfig:
    return CandidateConfig(
        config_id=config_id,
        model_path="/nix/store/" + "a" * 32 + "-ornith.gguf",
        nix_package=nix_package,
        server_flags=flags,
        constraint_violations=(),
    )


def _context(config: CandidateConfig) -> RecommendationContext:
    return RecommendationContext(
        config=config,
        run_id="run-10",
        manifest_id="manifest-ornith-v1",
        manifest_hash="b" * 64,
    )


class TestRenderRecommendation:
    def test_snippet_embeds_validated_identity_and_flags(self) -> None:
        snippet = render_recommendation(_context(_config()))

        assert "run: run-10" in snippet
        assert "manifest: manifest-ornith-v1" in snippet
        assert "config: ornith-q4" in snippet
        assert "Ornith-1.0-9B-Q4_K_M" in snippet
        assert "--ctx-size" in snippet
        assert "32768" in snippet

    def test_snippet_is_byte_stable(self) -> None:
        first = render_recommendation(_context(_config()))
        second = render_recommendation(_context(_config()))
        assert first == second

    def test_write_emits_only_recommendation_without_touching_flake(self, tmp_path: Path) -> None:
        path = write_recommendation(_context(_config()), tmp_path)
        assert path.exists()
        assert path.name == "recommendation.nix"
        content = path.read_text()
        assert "ornith-q4" in content

    @pytest.mark.parametrize(
        "bad_id",
        [
            "../escape",
            "name space",
            'id"; -rf /',
            "-leadingdash",
            "id\nflag",
        ],
    )
    def test_path_injection_config_id_is_rejected(self, bad_id: str) -> None:
        with pytest.raises(NixRecommendationError, match="config id"):
            render_recommendation(_context(_config(config_id=bad_id)))

    @pytest.mark.parametrize(
        "bad_pkg",
        [
            'pkg"; evil',
            "../escape",
        ],
    )
    def test_path_injection_package_is_rejected(self, bad_pkg: str) -> None:
        with pytest.raises(NixRecommendationError, match="nix_package"):
            render_recommendation(_context(_config(nix_package=bad_pkg)))
