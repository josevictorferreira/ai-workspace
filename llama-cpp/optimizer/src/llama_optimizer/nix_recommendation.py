"""Emit-only, injection-safe Nix recommendation snippets (review only).

This module renders a ``recommendation.nix`` fragment for the selected
finalist's immutable identity. It is deliberately emit-only: it reads
but never mutates ``flake.nix`` and exposes no command to apply the recommendation.
Every interpolated token is validated against a strict allowlist before
it reaches the Nix string; a malformed identity cannot inject path traversal
or Nix/shell syntax into the emitted snippet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path

    from llama_optimizer.report_models import CandidateConfig

# Strict allowlists for interpolated tokens
_IDENTITY: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_FLAG: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9-][A-Za-z0-9._:=/-]{0,127}$")


class NixRecommendationError(Exception):
    """A token failed allowlist validation."""


def _validate(value: str, pattern: re.Pattern[str], label: str) -> str:
    """Validate a token against an allowlist pattern."""
    if not pattern.match(value):
        msg = f"Invalid {label} {value!r} does not match {pattern.pattern}"
        raise NixRecommendationError(msg)
    return value


@dataclass(frozen=True, slots=True)
class RecommendationContext:
    """Immutable context for generating a Nix recommendation snippet."""

    config: CandidateConfig
    run_id: str
    manifest_id: str
    manifest_hash: str


def render_recommendation(context: RecommendationContext) -> str:
    """Render an injection-safe Nix recommendation snippet.

    The snippet is review-only: it documents the selected finalist's
    identity and flags but does not modify any files.
    """
    config = context.config

    # Validate all interpolated tokens
    _validate(config.config_id, _IDENTITY, "config id")
    _validate(config.nix_package, _IDENTITY, "nix_package")
    _validate(context.run_id, _IDENTITY, "run_id")
    _validate(context.manifest_id, _IDENTITY, "manifest_id")
    _validate(context.manifest_hash, _IDENTITY, "manifest_hash")

    for flag in config.server_flags:
        _validate(flag, _FLAG, "server_flag")

    # Build the snippet
    flags_str = " ".join(f'"{f}"' for f in config.server_flags)
    return (
        f"  run: {context.run_id}\n"
        f"  manifest: {context.manifest_id} ({context.manifest_hash})\n"
        f"  config: {config.config_id}\n"
        "{\n"
        f"  {config.nix_package} = {{\n"
        f'    modelPath = "{config.model_path}";\n'
        f"    serverFlags = [ {flags_str} ];\n"
        "  };\n"
        "}\n"
    )


def write_recommendation(context: RecommendationContext, output_dir: Path) -> Path:
    """Write the recommendation snippet to disk and return the path."""
    content = render_recommendation(context)
    path = output_dir / "recommendation.nix"
    path.write_text(content)
    return path
