"""
case status: the case's notes (.casestatus.md) with what its files say now.

    case status [case]                    show it (writes the file the first time)
    case status update [case]             edit it in $EDITOR
    case status update [case] -m TEXT     add a line to its log
    case status update [case] --state S   set the state (logged too)
    case status '*'                       one line per registered case

The file holds only what a person knows; the step the run reached, the last
PLT and the job in the queue are read from the case each time, so they are
never out of date. See src/core/case_status.py for the format.
"""

import os
import shlex
import shutil
import subprocess
from pathlib import Path

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from ....core import case_status as cs
from ...case_iteration import is_wildcard_case

STATE_STYLE = {'new': 'cyan', 'meshing': 'cyan', 'running': 'green', 'stopped': 'yellow',
               'done': 'bold green', 'failed': 'bold red', 'archived': 'dim'}


def execute_status(args):
    console = Console()
    if getattr(args, 'help', False):
        from .help_messages import print_status_help
        print_status_help()
        return 0

    update = getattr(args, 'what', None) == 'update'
    name = args.case if update else (getattr(args, 'what', None) or args.case)
    if name is None:
        from src.cli.context import current_case
        name = current_case() or '.'

    if is_wildcard_case(name):
        if update:
            console.print("[red]Error:[/red] `case status update` takes one case, not '*'")
            return 2
        return _list_cases(console)

    case_dir = Path(name).expanduser()
    if not case_dir.is_dir():
        console.print(f"[red]Error:[/red] Case directory not found: {escape(str(case_dir))}")
        return 1
    if update:
        return _update(console, case_dir, args)
    return _show(console, case_dir, create=not getattr(args, 'no_create', False))


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------

def _show(console, case_dir: Path, create: bool) -> int:
    path = cs.path_for(case_dir)
    created = False
    if create and not path.exists():
        try:
            created = cs.ensure(case_dir)
        except OSError as e:
            console.print(f"[yellow]⚠[/yellow]  could not write {path.name}: {e}")
    loaded = cs.read(case_dir)
    meta, body = loaded if loaded else ({}, '')

    state = meta.get('state') or '—'
    tags = meta.get('tags') or []
    title = (f"[bold cyan]{escape(case_dir.resolve().name)}[/bold cyan]  "
             f"[{STATE_STYLE.get(state, 'white')}]{escape(state)}[/]"
             + (f"  [dim]{escape(' · '.join(tags))}[/dim]" if tags else ''))
    console.print()
    console.print(Panel(_facts(case_dir), title=title, title_align='left',
                        border_style='cyan', box=box.ROUNDED))
    if created:
        console.print(f"[dim]wrote {path.name} -- `case status update` to fill it in[/dim]")
    if loaded is None:
        console.print(f"[dim]no {path.name} here[/dim]")
    elif body.strip():
        console.print(Markdown(body))
    console.print()
    return 0


def _facts(case_dir: Path) -> Table:
    """What the files say now: setup, how far the run got, PLTs, the queue."""
    from ....core.simflow_config import SimflowConfig
    from ....core.def_config import DefConfig
    from ..report_impl.command import (_last_othd_timestep, _last_othd_timestep_in_dir,
                                       _last_binary_plt_timestep)

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style='dim', no_wrap=True)
    grid.add_column()
    try:
        cfg = SimflowConfig.find(case_dir)
    except Exception:
        grid.add_row('config', '[yellow]no simflow.config[/yellow]')
        return grid

    problem = cfg.problem
    max_steps = None
    if problem:
        try:
            max_steps = DefConfig.find(case_dir, problem).max_time_steps
        except Exception:
            pass
    setup = [f"problem {problem or '?'}"]
    for label, value in (('np', cfg.np), ('nsg', cfg.nsg), ('outFreq', cfg.out_freq),
                         ('maxTimeSteps', max_steps)):
        if value:
            setup.append(f"{label} {value}")
    grid.add_row('setup', escape(' · '.join(setup)))

    run_dir = cfg.run_dir(case_dir)
    reached = [s for s in (_last_othd_timestep(case_dir),
                           _last_othd_timestep_in_dir(run_dir) if run_dir and run_dir.is_dir()
                           else None) if s is not None]
    if reached:
        last = max(reached)
        of = f" of {max_steps} ({100 * last / max_steps:.0f}%)" if max_steps else ''
        grid.add_row('reached', f"step {last}{of}")
    if cfg.restart_flag and cfg.restart_tsid is not None:
        grid.add_row('restart', f"from {cfg.restart_tsid}")
    if problem:
        plt = _last_binary_plt_timestep(case_dir, problem)
        if plt is not None:
            grid.add_row('PLT', f"binary/ up to {plt}  [dim](case check plt for gaps)[/dim]")
    jobs = _queued_jobs(case_dir.resolve().name)
    if jobs:
        grid.add_row('queue', escape(', '.join(jobs)))
    return grid


def _queued_jobs(case_name: str):
    """This case's jobs in the SLURM queue, as 'name id STATE'; [] without SLURM."""
    if not shutil.which('squeue'):
        return []
    try:
        out = subprocess.run(['squeue', '-h', '-u', os.environ.get('USER', ''),
                              '-o', '%j %i %T'], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in out.splitlines() if case_name in line.split(' ')[0]]


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

def _update(console, case_dir: Path, args) -> int:
    message = getattr(args, 'message', None)
    state = getattr(args, 'state', None)
    path = cs.path_for(case_dir)
    if cs.ensure(case_dir):
        console.print(f"[dim]wrote {path.name}[/dim]")
    if state:
        old = cs.set_state(case_dir, state)
        console.print(f"state: {old or '—'} → [{STATE_STYLE.get(state, 'white')}]{state}[/]")
    if message:
        cs.add_log(case_dir, message)
        console.print(f"logged: {escape(message.strip().splitlines()[0])}")
    if state or message:
        return 0
    return _edit(console, path)


def _edit(console, path: Path) -> int:
    """Open the file in $VISUAL/$EDITOR (else vi, vim, nano)."""
    editor = os.environ.get('VISUAL') or os.environ.get('EDITOR')
    cmd = shlex.split(editor) if editor else next(
        ([e] for e in ('vi', 'vim', 'nano') if shutil.which(e)), None)
    if not cmd:
        console.print("[red]Error:[/red] no editor: set $EDITOR, or use "
                      "`case status update -m TEXT`")
        return 1
    try:
        return subprocess.call(cmd + [str(path)])
    except OSError as e:
        console.print(f"[red]Error:[/red] could not start {escape(cmd[0])}: {e}")
        return 1


# ---------------------------------------------------------------------------
# '*': every registered case
# ---------------------------------------------------------------------------

def _list_cases(console) -> int:
    from src.cli.context import current_dir
    from ...case_iteration import load_cases_from_directory
    cases = load_cases_from_directory(current_dir())
    if not cases:
        console.print("[red]Error:[/red] No cases found in .cases file (run `case add` first)")
        return 1
    tbl = Table(box=box.SIMPLE, header_style='bold yellow', pad_edge=False)
    tbl.add_column('case', style='cyan', no_wrap=True)
    tbl.add_column('state')
    tbl.add_column('last log line')
    for entry in cases:
        loaded = cs.read(entry['path']) if Path(entry['path']).is_dir() else None
        if loaded is None:
            tbl.add_row(escape(entry['name']), '[dim]—[/dim]', f'[dim]no {cs.FILENAME}[/dim]')
            continue
        meta, body = loaded
        state = meta.get('state') or '—'
        tbl.add_row(escape(entry['name']), f"[{STATE_STYLE.get(state, 'white')}]{escape(state)}[/]",
                    escape(cs.last_log_line(body) or ''))
    console.print(tbl)
    return 0
