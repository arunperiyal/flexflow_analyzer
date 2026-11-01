"""
Implementation of the `def var`, `def time` and `def freq` subcommands.

Reads and edits define{} variables, timeSteppingControl{} values and the
outFreq of outputSimulation{} / outputRestart{} in a case's .def file.
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

    from src.cli.context import current_case
    case = current_case()
    if case and case != '*':
        return case

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


# `def freq` names: the block whose outFreq it is, and what that block writes.
_FREQ_FIELDS = {
    'out': ('outputSimulation', 'output'),
    'rst': ('outputRestart', 'restart'),
}


def _per_run(cfg, freq):
    """maxTimeSteps // freq: the files written over maxTimeSteps, or None."""
    steps = cfg.max_time_steps
    value = freq if isinstance(freq, int) else cfg.evaluate(freq) if freq else None
    if not steps or not value or value <= 0:
        return None
    return int(steps // value)


def execute_freq(args):
    """
    Execute `def freq [out|rst] [value]`.

    - No kind        -> both frequencies, with the files over maxTimeSteps.
    - kind only      -> that frequency.
    - kind + value   -> set it (a positive whole number of steps).
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

    if kind is not None and kind not in _FREQ_FIELDS:
        console.print(
            f"[red]Error:[/red] Unknown frequency [cyan]{kind}[/cyan]. "
            f"Expected 'out' or 'rst'."
        )
        return 1

    current = {'out': cfg.output_frequency, 'rst': cfg.restart_frequency}

    # ── Edit: def freq <kind> <value> ───────────────────────────────────────
    if kind and value is not None:
        block, _ = _FREQ_FIELDS[kind]
        if not value.isdigit() or int(value) < 1:
            console.print(f"[red]Error:[/red] A frequency is a positive whole number "
                          f"of steps, not [cyan]{value}[/cyan]")
            return 1
        old = current[kind]
        if old is None or not cfg.set_output_frequency(block, int(value)):
            console.print(f"[red]Error:[/red] [cyan]outFreq[/cyan] not found in "
                          f"{block}{{}} in {cfg.path.name}")
            return 1
        console.print(
            f"[green]✓[/green] [cyan]{block}.outFreq[/cyan]: "
            f"[yellow]{old}[/yellow] → [bold green]{int(value)}[/bold green]  "
            f"[dim]({cfg.path.name})[/dim]"
        )
        steps = cfg.max_time_steps
        if steps and steps % int(value):
            console.print(f"[dim]  maxTimeSteps {steps} is not a multiple of {int(value)}: "
                          f"the last {steps % int(value)} step(s) are not covered by "
                          f"an {_FREQ_FIELDS[kind][1]} file.[/dim]")
        return 0

    # ── Show one: def freq <kind> ───────────────────────────────────────────
    if kind:
        block, _ = _FREQ_FIELDS[kind]
        if current[kind] is None:
            console.print(f"[red]Error:[/red] [cyan]outFreq[/cyan] not set in "
                          f"{block}{{}} in {cfg.path.name}")
            return 1
        console.print(f"[cyan]{block}.outFreq[/cyan] = [bold]{current[kind]}[/bold]")
        return 0

    # ── Show both: def freq ─────────────────────────────────────────────────
    if all(v is None for v in current.values()):
        console.print(f"[yellow]No outFreq in outputSimulation{{}} or outputRestart{{}} "
                      f"in {cfg.path.name}[/yellow]")
        return 0

    table = Table(
        title=f"Output frequencies — {cfg.path.name}",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold yellow",
        title_style="bold cyan",
    )
    table.add_column("Kind", style="cyan")
    table.add_column("Block", style="white")
    table.add_column("outFreq", style="white", justify="right")
    table.add_column("Files", style="white", justify="right")
    for name, (block, _) in _FREQ_FIELDS.items():
        freq = current[name]
        count = _per_run(cfg, freq) if freq is not None else None
        table.add_row(name, f"{block}{{}}", '(not set)' if freq is None else str(freq),
                      '' if count is None else str(count))

    console.print()
    console.print(table)
    if cfg.max_time_steps:
        console.print(f"[dim]  Files: maxTimeSteps {cfg.max_time_steps} / outFreq[/dim]")
    console.print()
    return 0
