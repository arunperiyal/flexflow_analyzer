"""auto show: what auto would do for each case of this folder. Reads only."""

from pathlib import Path

from rich.console import Console
from rich.markup import escape

STYLE = {
    'flag': ('⚑', 'yellow'), 'history': ('↻', 'cyan'), 'post': ('▶', 'green'),
    'upload': ('↑', 'green'), 'delete': ('✗', 'magenta'), 'wait': ('…', 'yellow'),
    'needs': ('!', 'bold red'), 'note': ('·', 'dim'),
}
STATE_STYLE = {'running': 'green', 'queued': 'yellow', 'post running': 'yellow',
               'done': 'bold green', 'stopped': 'cyan', 'new': 'dim', 'skipped': 'red'}
ORDER = ('flag', 'needs', 'wait', 'history', 'post', 'upload', 'delete', 'note')


def _speed_mbps() -> float:
    try:
        from shellkit.runtime import current_runtime
        rt = current_runtime()
        if rt is not None and 'transfer_speed' in rt.settings.specs:
            return float(rt.settings.get('transfer_speed'))
    except Exception:
        pass
    return 10.0


def _duration(seconds: float) -> str:
    minutes = int(round(seconds / 60))
    if minutes < 1:
        return "under a minute"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"


def gather(folder: Path, only=None, console=None):
    """(conf, [(snapshot, plan)], problems) for the folder; problems are the
    folder-wide reasons nothing could be decided (queue unreadable, ...)."""
    from src.core import slurm
    from src.core.auto import conf as auto_conf
    from src.core.auto.cloud import CloudError, open_cloud
    from src.core.auto.decide import decide
    from src.core.auto.observe import observe_case
    from src.commands.case_iteration import load_cases_from_directory

    conf = auto_conf.read(folder)
    entries = load_cases_from_directory(folder)
    if not entries:
        raise auto_conf.AutoConfError(f"no cases in {folder / '.cases'} (run `case add` first)")
    if only:
        entries = [e for e in entries if e['name'] == only or Path(e['path']).name == only]
        if not entries:
            raise auto_conf.AutoConfError(f"no case named {only!r} in .cases")

    try:
        queue = slurm.read_queue()
    except slurm.QueueError as e:
        return conf, [], [f"the queue could not be read ({e}), so no case is looked at: "
                          f"one that looks idle may be running"]
    problems, sacct_ok = [], True
    try:
        ended = slurm.read_ended()
    except slurm.QueueError as e:
        ended, sacct_ok = [], False
        problems.append(f"sacct could not be read ({e}): no post decisions")
    cloud, cloud_ok = None, True
    try:
        cloud = open_cloud(conf)
    except CloudError as e:
        cloud_ok = False
        problems.append(f"cloud not reachable ({e}): no post decisions or uploads")

    results = []
    try:
        for entry in entries:
            listing = None
            if cloud is not None:
                try:
                    listing = cloud.listing(Path(entry['path']).name)
                except CloudError as e:
                    problems.append(f"{entry['name']}: {e}")
            snap = observe_case(entry['path'], queue, ended, listing)
            results.append((snap, decide(snap, conf, cloud_ok=listing is not None, sacct_ok=sacct_ok)))
    finally:
        if cloud is not None:
            cloud.close()
    return conf, results, problems


def execute_show(args) -> int:
    from src.cli.context import current_dir
    from src.core.auto.conf import AutoConfError

    console = Console()
    folder = Path(current_dir())
    try:
        conf, results, problems = gather(folder, getattr(args, 'case', None))
    except AutoConfError as e:
        console.print(f"[red]Error:[/red] {escape(str(e))}")
        return 2

    console.print()
    console.print(f"[bold]auto show[/bold]  [dim]{escape(str(folder))} -> {escape(conf.remote)}:"
                  f"{escape(conf.path)}[/dim]")
    for problem in problems:
        console.print(f"  [bold red]![/bold red] {escape(problem)}")
    if not results:
        console.print()
        return 1

    total, posts, needs = 0, 0, 0
    for snap, plan in results:
        console.print()
        facts = '  ·  '.join(plan.facts)
        console.print(f"[bold cyan]{escape(plan.name)}[/bold cyan]  "
                      f"[{STATE_STYLE.get(plan.state, 'white')}]{plan.state}[/]"
                      + (f"  [dim]{escape(facts)}[/dim]" if facts else ''))
        items = sorted(plan.items, key=lambda i: ORDER.index(i.kind))
        if all(i.kind == 'note' for i in items):
            console.print("  [green]✓[/green] nothing to do")
        for item in items:
            mark, style = STYLE[item.kind]
            label = 'needs you: ' if item.kind == 'needs' else ''
            console.print(f"  [{style}]{mark}[/] {label}{escape(item.text)}")
        total += sum(plan.uploads.values())
        posts += plan.post is not None
        needs += plan.needs_you

    console.print()
    speed = _speed_mbps()
    if total:
        from src.core.auto.decide import _size_text
        upload = (f"{_size_text(total)} to upload: {_duration(total * 8 / (speed * 1e6))} "
                  f"at {speed:g} Mbps (set transfer_speed)")
    else:
        upload = "nothing to upload"
    console.print(f"[bold]{len(results)} case(s)[/bold] · {posts} post job(s) · {upload} · "
                  + (f"[bold red]{needs} need(s) you[/bold red]" if needs else "[green]none needs you[/green]"))
    console.print("[dim]Nothing was changed. `auto apply` will carry this out (not built yet).[/dim]")
    console.print()
    return 1 if needs or problems else 0
