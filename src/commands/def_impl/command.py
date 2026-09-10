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


def _resolve_case_path(args):
    """
    Determine the case directory for the def command.

    Resolution order, matching the rest of the CLI:
      1. --case/-c argument
      2. the active interactive case context (`use case <dir>`)
      3. the current working directory
    """
    case_arg = getattr(args, 'case', None)
    if case_arg:
        return case_arg

    try:
        from src.cli.interactive import InteractiveShell
        if (hasattr(InteractiveShell, '_instance') and
                InteractiveShell._instance and
                InteractiveShell._instance._current_case and
                InteractiveShell._instance._current_case != '*'):
            return InteractiveShell._instance._current_case
    except Exception:
        pass

    return os.getcwd()


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

    case_path = Path(_resolve_case_path(args)).resolve()
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


# Maps the short CLI names to the actual timeSteppingControl{} key and the
# DefConfig property that reads it.
_TIME_FIELDS = {
    'maxTime': ('maxTimeSteps', 'max_time_steps'),
    'inc':     ('initialTimeIncrement', 'initial_time_increment'),
}


def execute_time(args):
    """
    Execute `def time [maxTime|inc] [value]`.

    - No kind        -> print all timeSteppingControl{} values as a table.
    - kind only      -> print the value of that field.
    - kind + value   -> edit the field's value in the .def file.
    """
    console = Console()

    case_path = Path(_resolve_case_path(args)).resolve()
    if not case_path.exists():
        console.print(f"[red]Error:[/red] Case directory not found: {case_path}")
        return 1

    cfg = _resolve_def_config(case_path, console)
    if cfg is None:
        return 1

    kind = getattr(args, 'kind', None)
    value = getattr(args, 'value', None)

    if kind is not None and kind not in _TIME_FIELDS:
        console.print(
            f"[red]Error:[/red] Unknown time field [cyan]{kind}[/cyan]. "
            f"Expected 'maxTime' or 'inc'."
        )
        return 1

    # ── Edit: def time <kind> <value> ───────────────────────────────────────
    if kind and value is not None:
        key, prop = _TIME_FIELDS[kind]
        old = getattr(cfg, prop)
        if old is None:
            console.print(
                f"[red]Error:[/red] [cyan]{key}[/cyan] not found in "
                f"timeSteppingControl{{}} in {cfg.path.name}"
            )
            return 1
        if not cfg.set_time_stepping_control(key, value):
            console.print(
                f"[red]Error:[/red] Failed to update [cyan]{key}[/cyan] in "
                f"{cfg.path.name}"
            )
            return 1
        console.print(
            f"[green]✓[/green] [cyan]{key}[/cyan]: "
            f"[yellow]{old}[/yellow] → [bold green]{value}[/bold green]  "
            f"[dim]({cfg.path.name})[/dim]"
        )
        return 0

    # ── Show one: def time <kind> ───────────────────────────────────────────
    if kind:
        key, prop = _TIME_FIELDS[kind]
        current = getattr(cfg, prop)
        if current is None:
            console.print(f"[red]Error:[/red] [cyan]{key}[/cyan] not set in {cfg.path.name}")
            return 1
        console.print(f"[cyan]{key}[/cyan] = [bold]{current}[/bold]")
        return 0

    # ── Show all: def time ───────────────────────────────────────────────────
    rows = [
        ('maxTimeSteps', cfg.max_time_steps),
        ('initialTimeIncrement', cfg.initial_time_increment),
        ('order', cfg.order),
        ('highFrequencyDampingFactor', cfg.high_frequency_damping),
    ]
    if all(val is None for _, val in rows):
        console.print(f"[yellow]No timeSteppingControl{{}} block found in {cfg.path.name}[/yellow]")
        return 0

    table = Table(
        title=f"timeSteppingControl{{}} — {cfg.path.name}",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold yellow",
        title_style="bold cyan",
    )
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    for field, val in rows:
        table.add_row(field, '(not set)' if val is None else str(val))

    console.print()
    console.print(table)
    console.print()
    return 0
