"""auto log: read back what earlier `auto apply` runs did.

    auto log [--case NAME]            the newest run's log, one line per action
                               (only that case's lines when a case is given)
    auto log --list            the runs, newest first, one line each
    auto log --log N           the Nth newest run (1 is the newest), with or
                               without a case

The logs are <folder>/auto_logs/auto_<date>_<time>.log, written by `auto apply`.
The folder is the shell's directory, or the folder above it when it is a case.
"""

from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.table import Table

KIND_STYLE = {'history': 'cyan', 'upload': 'cyan', 'delete': 'magenta', 'post': 'yellow',
              'problem': 'bold red', 'start': 'dim', 'end': 'dim'}


def logs_folder(here: Path) -> Path:
    """The folder of cases whose auto_logs/ is read: here, else the folder above (when
    here is a case); here when neither has one."""
    from src.core.transfer.ledger import logs_dir
    for folder in (here, here.parent):
        if logs_dir(folder).is_dir():
            return folder
    return here


def case_name(case) -> str:
    """The case a name or path stands for; '' for every case ('*' or none)."""
    if not case or case == '*':
        return ''
    return Path(case).name


def _ago(when: datetime) -> str:
    seconds = (datetime.now() - when).total_seconds()
    if seconds < 90:
        return 'just now'
    if seconds < 5400:
        return f"{int(seconds // 60)} min ago"
    if seconds < 129600:
        return f"{int(seconds // 3600)} h ago"
    return f"{int(seconds // 86400)} days ago"


def _list(console, logs, folder) -> int:
    from src.core.auto.runlog import read_log, started_at, summarise
    table = Table(box=box.SIMPLE, header_style='bold', pad_edge=False)
    for col in ('#', 'started', 'cases', 'steps', 'failed', 'run'):
        table.add_column(col, no_wrap=col != 'run', overflow='fold')
    for n, path in enumerate(logs, 1):
        info = summarise(read_log(path))
        when = started_at(path)
        ended = ('' if info['end'] is not None
                 else ' [yellow](no end line: stopped part-way?)[/yellow]')
        table.add_row(str(n), f"{when:%Y-%m-%d %H:%M}" if when else path.name,
                      str(len(info['cases'])), str(info['steps']),
                      f"[bold red]{info['failed']}[/bold red]" if info['failed'] else '0',
                      escape(info['start'] or path.name) + ended)
    console.print(table)
    console.print(f"[dim]{len(logs)} run(s) in {escape(str(folder / 'auto_logs'))}; "
                  f"`auto log --log N` reads one.[/dim]")
    return 0


def execute_log(args) -> int:
    from src.cli.context import current_dir
    from src.core.auto.runlog import is_failure, list_logs, read_log, started_at

    console = Console()
    folder = logs_folder(Path(current_dir()))
    logs = list_logs(folder)
    if not logs:
        console.print(f"[dim]No auto logs in {escape(str(folder / 'auto_logs'))}: "
                      f"`auto apply` writes one each time it runs.[/dim]")
        return 0
    if getattr(args, 'list', False):
        return _list(console, logs, folder)

    n = getattr(args, 'log', None) or 1
    if not 1 <= n <= len(logs):
        console.print(f"[red]Error:[/red] there are {len(logs)} run(s); --log {n} is out of range "
                      f"(`auto log --list`)")
        return 2
    path = logs[n - 1]
    name = case_name(getattr(args, 'case', None))
    entries = [e for e in read_log(path) if not name or not e.case or e.case == name]
    when = started_at(path)
    console.print()
    console.rule(f"[bold]auto log[/bold]  [dim]{escape(path.name)}"
                 + (f" · {_ago(when)}" if when else '') + "[/dim]", style='cyan')
    shown = [e for e in entries if e.case or name == '' or e.kind in ('start', 'end')]
    if name and not any(e.case == name for e in entries):
        console.print(f"[dim]This run did nothing for {escape(name)}.[/dim]")
    for e in shown:
        style = 'bold red' if is_failure(e) else KIND_STYLE.get(e.kind, 'white')
        who = f"{e.case:<12}" if e.case else f"{'':<12}"
        console.print(f"[dim]{e.time}[/dim]  [bold]{escape(who)}[/bold] "
                      f"[{style}]{escape(e.kind):<8}[/] {escape(e.text)}", highlight=False)
    failed = sum(1 for e in shown if is_failure(e))
    console.print()
    console.print(f"[dim]{len(shown)} line(s)[/dim]"
                  + (f" · [bold red]{failed} failed[/bold red]" if failed else '')
                  + (f" · [dim]run {n} of {len(logs)}[/dim]" if len(logs) > 1 else ''))
    console.print()
    return 1 if failed else 0
