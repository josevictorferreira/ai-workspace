"""Typed profile-boundary errors (T2).

Each malformed profile yields a field-specific typed error carrying the
offending value, so callers never see a bare string or a raw traceback.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProfileParseError(ValueError):
    """A profile document could not be parsed (invalid TOML or missing section)."""

    reason: str

    def __post_init__(self) -> None:
        """Populate the base ``ValueError`` message so ``str()`` is never empty."""
        Exception.__init__(self, self.reason)


@dataclass
class ProfileContextError(ProfileParseError):
    """The context size was not the required 32768."""

    actual: int = 0


@dataclass
class ProfileVramError(ProfileParseError):
    """The VRAM ceiling was not the required 13 GiB literal."""

    actual: int = 0


@dataclass
class DuplicateIdentityError(ProfileParseError):
    """Two candidates or backends shared an id."""

    kind: str = ""
    duplicate_id: str = ""


@dataclass
class MissingIdentityError(ProfileParseError):
    """A required template or corpus identity was absent."""

    identity: str = ""
