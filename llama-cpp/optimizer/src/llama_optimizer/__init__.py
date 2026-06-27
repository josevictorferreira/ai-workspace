"""llama-cpp optimizer: deterministic trial, scoring, and safety core.

Task 1 ships only the typed CLI surface and artifact-path contracts. Profiles,
search behavior, the trial ledger, telemetry, and adapters arrive in later
tasks; this package intentionally exposes nothing beyond its version yet.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
