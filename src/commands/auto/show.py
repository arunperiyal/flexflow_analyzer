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

    from rich import box
    from rich.table import Table
    from src.core.auto.decide import _size_text

    console.print()
    console.rule(f"[bold]auto show[/bold]  [dim]{escape(folder.name)}[/dim]", style='cyan')
    console.print(f"[dim]cases   {escape(str(folder))}\n"
                  f"remote  {escape(conf.remote)}:{escape(conf.path)}[/dim]")
    for problem in problems:
        console.print(f"[bold red]![/bold red] {escape(problem)}")
    if not results:
        console.rule(style='cyan')
        console.print()
        return 1

    summary = []
    for snap, plan in results:
        console.print()
        state = f"[{STATE_STYLE.get(plan.state, 'white')}]{plan.state}[/]"
        console.rule(f"[bold cyan]{escape(plan.name)}[/bold cyan]  {state}", align='left',
                     style='grey50')
        if plan.facts:
            console.print(f"  [dim]{escape('  ·  '.join(plan.facts))}[/dim]")
        items = sorted(plan.items, key=lambda i: ORDER.index(i.kind))
        lines = Table.grid(padding=(0, 1))
        lines.add_column(width=3, no_wrap=True)       # indent + mark
        lines.add_column(overflow='fold')
        if all(i.kind == 'note' for i in items):
            lines.add_row("  [green]✓[/green]", "nothing to do")
        for item in items:
            mark, style = STYLE[item.kind]
            label = '[bold red]needs you:[/bold red] ' if item.kind == 'needs' else ''
            lines.add_row(f"  [{style}]{mark}[/]", label + escape(item.text))
        console.print(lines)
        summary.append((plan, sum(plan.uploads.values())))

    # summary
    console.print()
    console.rule("[bold]summary[/bold]", style='cyan')
    table = Table(box=box.SIMPLE_HEAD, header_style='bold', pad_edge=False, expand=False)
    table.add_column('case', style='cyan', no_wrap=True)
    table.add_column('state', no_wrap=True)
    table.add_column('post job', no_wrap=True)
    table.add_column('upload', justify='right', no_wrap=True)
    table.add_column('needs you', overflow='fold')
    for plan, size in summary:
        post = f"{plan.post[0]}-{plan.post[1]}" + (" (convert)" if plan.post[2] == 'convert' else '') \
            if plan.post else '[dim]-[/dim]'
        wait = next((i for i in plan.items if i.kind == 'wait'), None)
        if wait and not plan.post:
            post = '[yellow]waits[/yellow]'
        needs = [i.text for i in plan.items if i.kind == 'needs']
        first = needs[0].split(':')[0] if needs else ''
        more = f" (+{len(needs) - 1})" if len(needs) > 1 else ''
        table.add_row(escape(plan.name), f"[{STATE_STYLE.get(plan.state, 'white')}]{plan.state}[/]",
                      post, _size_text(size) if size else '[dim]-[/dim]',
                      f"[red]{escape(first)}{more}[/red]" if needs else '')
    console.print(table)

    total = sum(size for _, size in summary)
    posts = sum(plan.post is not None for plan, _ in summary)
    needs = sum(plan.needs_you for plan, _ in summary)
    speed = _speed_mbps()
    upload = (f"{_size_text(total)} to upload, {_duration(total * 8 / (speed * 1e6))} at "
              f"{speed:g} Mbps (set transfer_speed)" if total else "nothing to upload")
    console.print(f"[bold]{len(summary)} case(s)[/bold] · {posts} post job(s) · "
                  + (f"[bold red]{needs} need(s) you[/bold red]" if needs
                     else "[green]none needs you[/green]"))
    console.print(upload)
    console.print("[dim]Nothing was changed. `auto apply` will carry this out (not built yet).[/dim]")
    console.rule(style='cyan')
    console.print()
    return 1 if needs or problems else 0
