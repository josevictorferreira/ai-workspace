"""``llama-cpp-opt`` command surface for the optimizer plan.

Task 1 exposes the seven reserved command groups (``profile``, ``run``,
``resume``, ``report``, ``recommend``, ``smoke``, ``agent``) as a typed,
documented help tree. Task 2 wires ``profile validate`` to real behavior
(parse the immutable TOML profile and emit canonical deterministic JSON);
the remaining six groups still fail fast with a typed
``CommandNotScaffoldedError`` translated into a clean nonzero exit.
"""

from __future__ import annotations

from typing import Annotated, Final, NoReturn, final

import typer

from llama_optimizer.models import SchemaError
from llama_optimizer.profile_errors import ProfileParseError
from llama_optimizer.profiles import (
    build_manifest,
    canonical_manifest_json,
    parse_profile,
)
from llama_optimizer.search_space import SearchSpaceError

app = typer.Typer(
    name="llama-cpp-opt",
    help="Deterministic llama.cpp optimizer scaffold (T1: typed CLI surface).",
    no_args_is_help=True,
    add_completion=False,
)
profile_app = typer.Typer(help="Profile definition and validation commands.")
app.add_typer(profile_app, name="profile")


@final
class CommandNotScaffoldedError(Exception):
    """A CLI command reserved for a later plan task is not yet wired up."""

    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__(f"command '{command}' is not implemented in this scaffold")


def _fail_not_scaffolded(command: str) -> NoReturn:
    """Translate the typed domain error into a clean nonzero CLI exit."""
    error = CommandNotScaffoldedError(command)
    typer.echo(f"error: {error}", err=True)
    raise typer.Exit(code=2) from error


# Typed validation errors translated into a clean nonzero CLI exit.
_PROFILE_ERRORS: Final[tuple[type[Exception], ...]] = (
    ProfileParseError,
    SchemaError,
    SearchSpaceError,
    FileNotFoundError,
    OSError,
)


@profile_app.command("validate")
def profile_validate(
    *,
    profile: Annotated[str, typer.Option(help="Path to the TOML profile to validate.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit canonical deterministic JSON.")
    ] = False,
) -> None:
    """Validate an immutable profile document and optionally emit its canonical manifest."""
    try:
        parsed = parse_profile(profile)
    except _PROFILE_ERRORS as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    if json_output:
        manifest = build_manifest(parsed)
        typer.echo(canonical_manifest_json(manifest), nl=False)
        return
    typer.echo(f"ok: profile {parsed.profile_id!r} validated (context={int(parsed.context_size)})")


@app.command()
def run() -> None:
    """Run the optimizer search (reserved for a later task)."""
    _fail_not_scaffolded("run")


@app.command()
def resume() -> None:
    """Resume an interrupted optimizer run (reserved for a later task)."""
    _fail_not_scaffolded("resume")


@app.command()
def report() -> None:
    """Emit a run report (reserved for a later task)."""
    _fail_not_scaffolded("report")


@app.command()
def recommend() -> None:
    """Emit a balanced feasible recommendation (reserved for a later task)."""
    _fail_not_scaffolded("recommend")


@app.command()
def smoke() -> None:
    """Run an opt-in hardware smoke check (reserved for a later task)."""
    _fail_not_scaffolded("smoke")


@app.command()
def agent() -> None:
    """Adapter entry point for launch/report agents (reserved for a later task)."""
    _fail_not_scaffolded("agent")


def main() -> None:
    """Console-script entry point for ``llama-cpp-opt``."""
    app()


if __name__ == "__main__":
    main()
