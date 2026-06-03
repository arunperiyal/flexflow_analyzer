"""
Implementation of the `def var` subcommand.

Reads and edits define{} block variables in a case's .def file.
"""

import os
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import box

from ...core.def_config import DefConfig
from ...core.simflow_config import SimflowConfig


def _resolve_def_config(case_path: Path, console: Console):
    """
    Locate and load the .def file for a case directory.

    Uses the problem name from simflow.config when available so that the
    correct ``<problem>.def`` is chosen, otherwise falls back to the first
    ``*.def`` file in the directory.

    Returns
    -------
    DefConfig | None
        Parsed config, or None if no .def file exists.
    """
    problem_name = None
    simflow = SimflowConfig(case_path / 'simflow.config')
    if simflow.exists:
        problem_name = simflow.problem

    cfg = DefConfig.find(case_path, problem_name)
    if not cfg.exists:
        console.print(f"[red]Error:[/red] No .def file found in {case_path}")
        return None
    return cfg


def execute_var(args):
    """
    Execute `def var [name] [value]`.

    - No name        -> print all define{} variables as a table.
    - name only      -> print the value of that variable.
    - name + value   -> edit the variable's value in the .def file.
    """
    console = Console()

    case_path = Path(getattr(args, 'case', None) or os.getcwd()).resolve()
    if not case_path.exists():
        console.print(f"[red]Error:[/red] Case directory not found: {case_path}")
        return 1

    cfg = _resolve_def_config(case_path, console)
    if cfg is None:
        return 1

    name = getattr(args, 'name', None)
    value = getattr(args, 'value', None)

    # ── Edit: def var <name> <value> ──────────────────────────────────────
    if name and value is not None:
        old = cfg.variables.get(name)
        if old is None:
            console.print(
                f"[red]Error:[/red] Variable [cyan]{name}[/cyan] not found in "
                f"{cfg.path.name}"
            )
            return 1
        if not cfg.set_variable(name, value):
            console.print(
                f"[red]Error:[/red] Failed to update [cyan]{name}[/cyan] in "
                f"{cfg.path.name}"
            )
            return 1
        console.print(
            f"[green]✓[/green] [cyan]{name}[/cyan]: "
            f"[yellow]{old}[/yellow] → [bold green]{value}[/bold green]  "
            f"[dim]({cfg.path.name})[/dim]"
        )
        return 0

    # ── Show one: def var <name> ──────────────────────────────────────────
    if name:
        if name not in cfg.variables:
            console.print(
                f"[red]Error:[/red] Variable [cyan]{name}[/cyan] not found in "
                f"{cfg.path.name}"
            )
            return 1
        console.print(f"[cyan]{name}[/cyan] = [bold]{cfg.variables[name]}[/bold]")
        return 0

    # ── Show all: def var ─────────────────────────────────────────────────
    variables = cfg.variables
    if not variables:
        console.print(f"[yellow]No define{{}} variables found in {cfg.path.name}[/yellow]")
        return 0

    table = Table(
        title=f"define{{}} variables — {cfg.path.name}",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold yellow",
        title_style="bold cyan",
    )
    table.add_column("Variable", style="cyan")
    table.add_column("Value", style="white")
    for var, val in variables.items():
        table.add_row(var, val)

    console.print()
    console.print(table)
    console.print()
    return 0
