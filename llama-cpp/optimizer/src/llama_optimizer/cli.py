"""``llama-cpp-opt`` command surface for the optimizer plan.

Task 1 exposes the seven reserved command groups (``profile``, ``run``,
``resume``, ``report``, ``recommend``, ``smoke``, ``agent``) as a typed,
documented help tree. No behavior is wired up yet: each command fails fast
with a typed ``CommandNotScaffoldedError`` translated into a clean nonzero
exit and no traceback.
"""

from __future__ import annotations

from typing import NoReturn, final

import typer

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


@profile_app.command("validate")
def profile_validate() -> None:
    """Validate a profile document (reserved for a later task)."""
    _fail_not_scaffolded("profile validate")


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
