"""auto show / commands / status: what auto would do for a case, or for every
case with `use case:*`. Reads only.

    auto show [case] [--detail] [--only SECTIONS]   labelled sections per case
    auto commands [case]                             just the commands, numbered
    auto status [case]                               one line per case
"""

import re
from pathlib import Path

from rich.console import Console
from rich.markup import escape

STATE_STYLE = {'running': 'green', 'queued': 'yellow', 'post running': 'yellow',
               'done': 'bold green', 'stopped': 'cyan', 'new': 'dim', 'skipped': 'red'}
SECTION_STYLE = {'state': 'bold', 'needs': 'bold red', 'flags': 'yellow', 'log': 'red', 'history': 'cyan',
                 'plt': 'cyan', 'out': 'cyan', 'rst': 'cyan', 'inputs': 'cyan'}


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


def gather(case_dirs, remote, clouds=None):
    """([(snapshot, plan)], {folder: conf}, problems) for these case folders,
    against this remote. `clouds` is a {(remote, path): cloud} cache: pass one
    to reuse open connections across calls (the caller closes them); without
    it they are opened here and closed before returning.

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

    own = clouds is None
    clouds = {} if own else clouds               # (remote, path) -> cloud, or None
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
            from src.core.auto.ledger import Ledger
            sent = {rel: e.get('when') for rel, e in
                    Ledger(Path(case_dir).parent).data.get(conf.remote, {})
                    .get(Path(case_dir).name, {}).items()}
            snap = observe_case(case_dir, queue, ended, listing, sent)
            results.append((snap, decide(snap, conf, cloud_ok=listing is not None,
                                         sacct_ok=sacct_ok)))
    finally:
        if own:
            for cloud in clouds.values():
                if cloud is not None:
                    cloud.close()
    return results, confs, problems


def _size_text_of(files: dict) -> str:
    from src.core.auto.decide import _size_text
    return _size_text(sum(files.values()))


def _only(args):
    """--only plt,history -> {'plt', 'history'} (state always shown); None for all."""
    from src.core.auto.report import SECTIONS
    raw = getattr(args, 'only', None)
    if not raw:
        return None
    wanted = {w.strip().lower() for w in raw.split(',') if w.strip()}
    unknown = wanted - set(SECTIONS)
    if unknown:
        from src.core.auto.conf import AutoConfError
        raise AutoConfError(f"--only: unknown section(s) {', '.join(sorted(unknown))} "
                            f"(sections: {', '.join(SECTIONS)})")
    return wanted | {'state'}


def _print_sections(console, sections, only=None):
    from rich.table import Table
    from src.core.auto.report import AUTO_ONLY
    for sec in sections:
        if only is not None and sec.key not in only:
            continue
        title = f"[{SECTION_STYLE.get(sec.key, 'cyan')}]{escape(sec.title)}[/]"
        if sec.subtitle:
            title += f"  [dim]{escape(sec.subtitle)}[/dim]"
        console.print(f"  {title}")
        grid = Table.grid(padding=(0, 1))
        grid.add_column(width=4, no_wrap=True)
        grid.add_column(style='dim', no_wrap=True, width=11)   # same label width in every section
        grid.add_column(overflow='fold')
        for label, value in sec.rows:
            grid.add_row('', f"{escape(label)}:" if label else '', escape(str(value)))
        if sec.key not in ('needs', 'flags'):
            if not sec.actions:
                grid.add_row('', 'Action:', '[dim]none[/dim]')
            for n, action in enumerate(sec.actions, 1):
                label = 'Action:' if n == 1 else ''
                if action.startswith(AUTO_ONLY):
                    text = f"[magenta]{n}: {escape(action)}[/magenta]"
                elif action.startswith('wait:'):
                    text = f"[yellow]{n}: {escape(action)}[/yellow]"
                else:
                    text = f"{n}: [green]{escape(action)}[/green]"
                grid.add_row('', label, text)
        console.print(grid)


def _summary_table(console, results):
    from rich import box
    from rich.table import Table
    from src.core.auto.decide import _size_text
    table = Table(box=box.SIMPLE_HEAD, header_style='bold', pad_edge=False, expand=False)
    table.add_column('case', style='cyan', no_wrap=True)
    table.add_column('state', no_wrap=True)
    table.add_column('steps', justify='right', no_wrap=True)
    table.add_column('post job', no_wrap=True)
    table.add_column('upload', justify='right', no_wrap=True)
    table.add_column('needs you', overflow='fold')
    for snap, plan in results:
        post = (f"{plan.post[0]}-{plan.post[1]}" + (" (convert)" if plan.post[2] == 'convert' else '')
                if plan.post else '[dim]-[/dim]')
        if plan.ctx.get('post_now') and not plan.post:
            post = '[yellow]waits[/yellow]'
        needs = [i.text for i in plan.items if i.kind == 'needs']
        first = re.split(r'[:.](?:\s|$)', needs[0])[0] if needs else ''
        more = f" (+{len(needs) - 1})" if len(needs) > 1 else ''
        reached, top = plan.ctx.get('reached'), snap.max_steps
        steps = (f"{reached}/{top}" if reached and top else str(reached or '-'))
        size = sum(plan.uploads.values())
        table.add_row(escape(plan.name), f"[{STATE_STYLE.get(plan.state, 'white')}]{plan.state}[/]",
                      steps, post, _size_text(size) if size else '[dim]-[/dim]',
                      f"[red]{escape(first)}{more}[/red]" if needs else '')
    console.print(table)


def _window_context():
    """'t1:450 t2:600' when a t1/t2 context is set, else ''. The commands below
    name every step range, but `case organise history` would still take a
    t1/t2 context as a window for the files it moves."""
    try:
        from shellkit.runtime import current_runtime
        rt = current_runtime()
        if rt is None:
            return ''
        return ' '.join(f"{k}:{rt.get(k)}" for k in ('t1', 't2') if rt.get(k) is not None)
    except Exception:
        return ''


def _collect(args):
    """(results, confs, problems), or an int exit code after printing why."""
    from src.cli.context import current_dir
    from src.core.auto.conf import AutoConfError
    try:
        case_dirs = resolve_cases(getattr(args, 'case', None), Path(current_dir()))
        return gather(case_dirs, getattr(args, 'remote', None))
    except AutoConfError as e:
        Console().print(f"[red]Error:[/red] {escape(str(e))}")
        return 2


def execute_show(args) -> int:
    from src.core.auto.conf import AutoConfError
    from src.core.auto.decide import _size_text
    from src.core.auto.report import build

    console = Console()
    try:
        only = _only(args)
    except AutoConfError as e:
        console.print(f"[red]Error:[/red] {escape(str(e))}")
        return 2
    got = _collect(args)
    if isinstance(got, int):
        return got
    results, confs, problems = got
    detail = len(results) == 1 or getattr(args, 'detail', False) or only is not None

    console.print()
    title = results[0][0].name if len(results) == 1 else f"{len(results)} cases"
    console.rule(f"[bold]auto show[/bold]  [dim]{escape(title)}[/dim]", style='cyan')
    for folder, conf in confs.items():
        console.print(f"[dim]folder  {escape(str(folder))}\n"
                      f"remote  {escape(conf.remote)}:{escape(conf.path)}[/dim]")
    for problem in problems:
        console.print(f"[bold red]![/bold red] {escape(problem)}")
    window = _window_context()
    if window:
        console.print(f"[yellow]Note:[/yellow] the context {escape(window)} is set; `case organise "
                      f"history` would use it. `unuse t1 t2` before running the actions.")
    if not results:
        console.rule(style='cyan')
        console.print()
        return 1

    if detail:
        for snap, plan in results:
            conf = confs[Path(snap.dir).parent]
            console.print()
            state = f"[{STATE_STYLE.get(plan.state, 'white')}]{plan.state}[/]"
            console.rule(f"[bold cyan]{escape(plan.name)}[/bold cyan]  {state}", align='left',
                         style='grey50')
            _print_sections(console, build(snap, plan, conf), only)
    if len(results) > 1:
        console.print()
        console.rule("[bold]summary[/bold]", style='cyan')
        _summary_table(console, results)
        if not detail:
            console.print("[dim]Each case in full: auto show <case>, or --detail; "
                          "the commands alone: auto commands.[/dim]")

    total = sum(sum(plan.uploads.values()) for _, plan in results)
    posts = sum(plan.post is not None for _, plan in results)
    needs = sum(plan.needs_you for _, plan in results)
    speed = _speed_mbps()
    upload = (f"{_size_text(total)} to upload, {_duration(total * 8 / (speed * 1e6))} at "
              f"{speed:g} Mbps (change with `set transfer_speed`)" if total else "nothing to upload")
    console.print()
    console.print(f"[bold]{len(results)} case(s)[/bold] · {posts} post job(s) · "
                  + (f"[bold red]{needs} need(s) you[/bold red]" if needs
                     else "[green]none needs you[/green]"))
    console.print(upload)
    console.print("[dim]Nothing was changed. `auto apply --dry-run` lists what it would do: "
                  "history, uploads, post jobs. Deleting is not built yet.[/dim]")
    console.rule(style='cyan')
    console.print()
    return 1 if needs or problems else 0


def execute_commands(args) -> int:
    """The commands of every case, plain text (no colour), numbered per case,
    so the output can be saved as a script and read before running it."""
    import sys
    from src.core.auto.report import AUTO_ONLY, build
    got = _collect(args)
    if isinstance(got, int):
        return got
    results, confs, problems = got
    out = sys.stdout
    for problem in problems:
        out.write(f"# ! {problem}\n")
    window = _window_context()
    if window:
        out.write(f"# ! the context {window} is set: `unuse t1 t2` before running these\n")
    for snap, plan in results:
        conf = confs[Path(snap.dir).parent]
        sections = build(snap, plan, conf)
        out.write(f"\n# {plan.name} ({plan.state})\n")
        n = 0
        for need in (i.text for i in plan.items if i.kind == 'needs'):
            out.write(f"#   needs you: {need}\n")
        for sec in sections:
            for action in sec.actions:
                if action.startswith(AUTO_ONLY) or action.startswith('wait:'):
                    out.write(f"#   {action}\n")
                else:
                    n += 1
                    out.write(f"{action}    # {n}, {sec.title}\n")
        if n == 0:
            out.write("#   no commands\n")
    return 1 if problems else 0


def execute_status(args) -> int:
    """One line per case: state, steps, jobs, what is next."""
    from rich.table import Table
    from rich import box
    from src.core.auto.decide import _size_text
    got = _collect(args)
    if isinstance(got, int):
        return got
    results, confs, problems = got
    console = Console()
    for problem in problems:
        console.print(f"[bold red]![/bold red] {escape(problem)}")
    table = Table(box=box.SIMPLE, header_style='bold', pad_edge=False)
    for col in ('case', 'state', 'steps', 'job', 'next'):
        table.add_column(col, no_wrap=col != 'next', overflow='fold')
    for snap, plan in results:
        c = plan.ctx
        reached = c.get('reached')
        steps = (f"{reached}/{snap.max_steps}" if reached and snap.max_steps else str(reached or '-'))
        jobs = ' '.join(f"{j.kind} {j.state.lower()}" for j in
                        list(c.get('main_now', [])) + list(c.get('post_now', []))) or '-'
        nxt = []
        if plan.needs_you:
            nxt.append('[red]needs you[/red]')
        if c.get('post_now'):
            nxt.append(f"[yellow]waits for post job {c['post_now'][0].jobid}[/yellow]")
        if plan.post:
            nxt.append(f"post {plan.post[0]}-{plan.post[1]}")
        if c.get('organise'):
            nxt.append('organise history')
        if plan.uploads:
            nxt.append(f"upload {_size_text(sum(plan.uploads.values()))}")
        if c.get('del_out') or c.get('del_binary') or c.get('thin'):
            nxt.append('clean up')
        table.add_row(escape(plan.name), f"[{STATE_STYLE.get(plan.state, 'white')}]{plan.state}[/]",
                      steps, jobs, ', '.join(nxt) or '[green]nothing[/green]')
    console.print(table)
    return 1 if problems or any(plan.needs_you for _, plan in results) else 0
