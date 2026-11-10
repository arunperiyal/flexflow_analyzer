"""auto show [case]: what auto would do for a case, or for every case with
`use case:*`. Reads only."""

import re
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
# a case's lines, grouped under these headings in this order
TOPICS = (('needs', 'Needs you', 'bold red'),
          ('flag', 'Worth a look', 'yellow'),
          ('history', 'History (.othd, .oisd)', 'cyan'),
          ('post', 'Post-processing', 'green'),
          ('upload', 'Upload to {remote}', 'green'),
          ('delete', 'Delete here, once the copy on {remote} is checked', 'magenta'),
          ('thin', 'Thin restart files (.rst)', 'magenta'),
          ('other', 'Notes', 'dim'))


def _print_case(console, plan, conf):
    """The facts line, then the case's lines under their headings."""
    from rich.table import Table
    from src.core.auto.decide import _size_text
    if plan.facts:
        facts = '  ·  '.join(plan.facts)
        console.print(f"  {escape(facts[:1].upper() + facts[1:])}")
    if all(i.kind == 'note' for i in plan.items):
        console.print("  [green]✓[/green] nothing to do")
    for topic, heading, style in TOPICS:
        items = [i for i in plan.items if i.topic == topic]
        if not items:
            continue
        heading = heading.format(remote=conf.remote)
        if topic == 'upload' and plan.uploads:
            total = sum(plan.uploads.values())
            heading += f"  [dim]{_size_text(total)}, {_duration(total * 8 / (_speed_mbps() * 1e6))}[/dim]"
        console.print(f"  [{style}]{heading}[/]")
        lines = Table.grid(padding=(0, 1))
        lines.add_column(width=5, no_wrap=True)       # indent + mark
        lines.add_column(overflow='fold')
        for item in items:
            mark, mark_style = STYLE[item.kind]
            lines.add_row(f"    [{mark_style}]{mark}[/]", escape(item.text))
        console.print(lines)


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
    return f"about {hours} h {minutes} min" if hours else f"about {minutes} min"


def resolve_cases(case, base_dir: Path):
    """The case folders `auto show` looks at: `case` is the argument or the
    `use case:` context. '*' is every case in base_dir's .cases.yml, as for
    case check. Raises AutoConfError when nothing names a case."""
    from src.core import cases_file
    from src.core.auto.conf import AutoConfError
    from src.commands.case_iteration import is_wildcard_case
    if not case:
        raise AutoConfError("no case given: auto show <case>, or `use case:<dir>` "
                            f"(`use case:*` for every case in {cases_file.FILENAME})")
    if is_wildcard_case(case):
        try:
            entries = cases_file.read(base_dir).cases
        except cases_file.CasesFileError as e:
            raise AutoConfError(str(e))
        if not entries:
            raise AutoConfError(f"no cases in {cases_file.path_for(base_dir)} "
                                f"(run `case add` first)")
        return [Path(e['path']) for e in entries]
    path = Path(case).expanduser()
    path = path if path.is_absolute() else base_dir / path
    if not path.is_dir():
        raise AutoConfError(f"case folder not found: {path}")
    return [path.resolve()]


def gather(case_dirs, remote):
    """([(snapshot, plan)], {folder: conf}, problems) for these case folders,
    against this remote.

    Each case uses its parent folder's .cases.yml: the remote's folder there
    and auto's settings; a folder without them raises AutoConfError. The queue and sacct are
    read once; each remote is opened once. When the queue cannot be read no
    case is looked at (problems says why).
    """
    from src.core import slurm
    from src.core.auto import conf as auto_conf
    from src.core.auto.cloud import CloudError, open_cloud
    from src.core.auto.decide import decide
    from src.core.auto.observe import observe_case

    confs = {}
    for case_dir in case_dirs:
        folder = Path(case_dir).parent
        if folder not in confs:
            confs[folder] = auto_conf.read(folder, remote)

    try:
        queue = slurm.read_queue()
    except slurm.QueueError as e:
        return [], confs, [f"the queue could not be read ({e}), so no case is looked at: "
                           f"one that looks idle may be running"]
    problems, sacct_ok = [], True
    try:
        ended = slurm.read_ended()
    except slurm.QueueError as e:
        ended, sacct_ok = [], False
        problems.append(f"sacct could not be read ({e}): no post decisions")

    clouds = {}                                  # (remote, path) -> cloud, or None
    results = []
    try:
        for case_dir in case_dirs:
            conf = confs[Path(case_dir).parent]
            key = (conf.remote, conf.path)
            if key not in clouds:
                try:
                    clouds[key] = open_cloud(conf)
                except CloudError as e:
                    clouds[key] = None
                    problems.append(f"{conf.remote}:{conf.path} not reachable ({e}): "
                                    f"no post decisions or uploads")
            cloud, listing = clouds[key], None
            if cloud is not None:
                try:
                    listing = cloud.listing(Path(case_dir).name)
                except CloudError as e:
                    problems.append(f"{Path(case_dir).name}: {e}")
            snap = observe_case(case_dir, queue, ended, listing)
            results.append((snap, decide(snap, conf, cloud_ok=listing is not None,
                                         sacct_ok=sacct_ok)))
    finally:
        for cloud in clouds.values():
            if cloud is not None:
                cloud.close()
    return results, confs, problems


def execute_show(args) -> int:
    from src.cli.context import current_dir
    from src.core.auto.conf import AutoConfError

    console = Console()
    base = Path(current_dir())
    try:
        case_dirs = resolve_cases(getattr(args, 'case', None), base)
        results, confs, problems = gather(case_dirs, getattr(args, 'remote', None))
    except AutoConfError as e:
        console.print(f"[red]Error:[/red] {escape(str(e))}")
        return 2

    from rich import box
    from rich.table import Table
    from src.core.auto.decide import _size_text

    console.print()
    title = case_dirs[0].name if len(case_dirs) == 1 else f"{len(case_dirs)} cases"
    console.rule(f"[bold]auto show[/bold]  [dim]{escape(title)}[/dim]", style='cyan')
    for folder, conf in confs.items():
        console.print(f"[dim]folder  {escape(str(folder))}\n"
                      f"remote  {escape(conf.remote)}:{escape(conf.path)}[/dim]")
    for problem in problems:
        console.print(f"[bold red]![/bold red] {escape(problem)}")
    if not results:
        console.rule(style='cyan')
        console.print()
        return 1

    summary = []
    for snap, plan in results:
        conf = confs[Path(snap.dir).parent]
        console.print()
        state = f"[{STATE_STYLE.get(plan.state, 'white')}]{plan.state}[/]"
        console.rule(f"[bold cyan]{escape(plan.name)}[/bold cyan]  {state}", align='left',
                     style='grey50')
        _print_case(console, plan, conf)
        summary.append((plan, sum(plan.uploads.values())))

    # summary: the table for several cases, the totals always
    console.print()
    console.rule("[bold]summary[/bold]" if len(summary) > 1 else '', style='cyan')
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
        first = re.split(r'[:.](?:\s|$)', needs[0])[0] if needs else ''
        more = f" (+{len(needs) - 1})" if len(needs) > 1 else ''
        table.add_row(escape(plan.name), f"[{STATE_STYLE.get(plan.state, 'white')}]{plan.state}[/]",
                      post, _size_text(size) if size else '[dim]-[/dim]',
                      f"[red]{escape(first)}{more}[/red]" if needs else '')
    if len(summary) > 1:
        console.print(table)

    total = sum(size for _, size in summary)
    posts = sum(plan.post is not None for plan, _ in summary)
    needs = sum(plan.needs_you for plan, _ in summary)
    speed = _speed_mbps()
    upload = (f"{_size_text(total)} to upload, {_duration(total * 8 / (speed * 1e6))} at "
              f"{speed:g} Mbps (change with `set transfer_speed`)" if total else "nothing to upload")
    console.print(f"[bold]{len(summary)} case(s)[/bold] · {posts} post job(s) · "
                  + (f"[bold red]{needs} need(s) you[/bold red]" if needs
                     else "[green]none needs you[/green]"))
    console.print(upload)
    console.print("[dim]Nothing was changed. `auto apply` will carry this out (not built yet).[/dim]")
    console.rule(style='cyan')
    console.print()
    return 1 if needs or problems else 0
