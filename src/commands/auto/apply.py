"""auto apply: carry out what `auto show` lists, the additive steps only --
organise the history, upload (checked, never deleting), submit a post job.

    auto apply [case] --remote NAME [--only history,upload,post] [--dry-run] [--yes]

For each case, in this order, with the plan made again from the files and the
queue right before each step (so a step runs on what is there now, not on what
was there when the run started):

    history   case organise history --update --clean --compile
    upload    the files the plan lists, to <remote>/<case>/..., each checked
    post      `run post` for the first stretch of steps with no PLT yet

A step that fails stops that case (the steps after it depend on it); the other
cases go on. Everything is written to <folder>/auto_logs/auto_<time>.log.
"""

from contextlib import ExitStack
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from .show import _collect, _size_text_of

KINDS = ('history', 'upload', 'post')
MARK = {'history': '↻', 'upload': '↑', 'post': '▶'}


def _kinds(args):
    from src.core.auto.conf import AutoConfError
    raw = getattr(args, 'only', None)
    if not raw:
        return set(KINDS)
    wanted = {w.strip().lower() for w in raw.split(',') if w.strip()}
    unknown = wanted - set(KINDS)
    if unknown:
        raise AutoConfError(f"--only for apply: unknown {', '.join(sorted(unknown))} "
                            f"(history, upload, post)")
    return wanted


def _upload_breakdown(plan):
    """The files of the plan's upload steps by what they are: [text], largest groups first."""
    import re
    from src.core.auto.decide import _size_text, steps_text
    groups = {}                                  # label -> [files, bytes]
    sets = {}                                    # restart step -> [files, bytes]
    live = {rel for step in plan.steps_of('live') for rel in step.files}
    sending = plan.to_send()
    for rel, size in sending.items():
        m = re.search(r'\.(\d+)_\d+\.rst$', rel)
        if m:
            entry = sets.setdefault(int(m.group(1)), [0, 0])
        else:
            if rel in live:
                label = 'live history copy'
            elif rel.startswith(('othd_files/', 'oisd_files/')):
                label = 'history files'
            elif rel.startswith('binary/'):
                label = 'binary PLTs'
            else:
                label = 'inputs and case files'
            entry = groups.setdefault(label, [0, 0])
        entry[0] += 1
        entry[1] += size
    lines = []
    if sets:
        why = plan.ctx.get('rst_why') or {}
        replaced = sorted(t for t, (_, differ, _) in why.items() if differ)
        lines.append((sum(v[1] for v in sets.values()),
                      f"restart sets {steps_text(sorted(sets))}: {sum(v[0] for v in sets.values())} "
                      f"files, {_size_text(sum(v[1] for v in sets.values()))}"
                      + (f"; set {', '.join(map(str, replaced))} replaces files on the remote that "
                         f"differ in size" if replaced else '')))
    old = set(plan.ctx.get('stale_plt') or [])
    replaced_plt = sorted({int(m.group(1)) for rel in sending
                           if rel.startswith('binary/') and (m := re.search(r'\.(\d+)\.plt$', rel))
                           and int(m.group(1)) in old})
    for label, (n, size) in groups.items():
        extra = ''
        if label == 'binary PLTs' and replaced_plt:
            extra = (f"; replaces {len(replaced_plt)} on the remote "
                     f"({steps_text(replaced_plt)}, from before the restart)")
        lines.append((size, f"{label}: {n} files, {_size_text(size)}{extra}"))
    return [text for _, text in sorted(lines, key=lambda x: -x[0])]


def _intended(plan, only):
    """What the plan's steps have apply do, in order: [(kind, text)]; a 'detail'
    line belongs to the one before it. The same steps `auto show` lists
    (plan.steps): the history step, the upload steps as one transfer, the
    first post step."""
    out = []
    if 'history' in only:
        for step in plan.due('history'):
            out.append(('history', step.command.replace(f"case organise history {plan.name} ",
                                                        "organise history ", 1)))
    sending = plan.to_send()
    if 'upload' in only and sending:
        out.append(('upload', f"{len(sending)} files, {_size_text_of(sending)}"))
        out += [('detail', line) for line in _upload_breakdown(plan)]
    if 'post' in only and plan.due('post'):
        a, b, d, mode = plan.post_jobs[0]
        waiting = len(plan.steps_of('post')) - 1
        more = f" (+{waiting} more after it)" if waiting else ''
        out.append(('post', f"run post {mode} --t1 {a} --t2 {b} --freq {d}{more}"))
    return out


def _run_case(case_dir, remote, only, clouds, ledgers, log, console):
    """The steps taken for one case: [Step]."""
    from src.commands.auto.show import gather
    from src.core.auto import executor
    steps = []
    name = Path(case_dir).name
    for kind in KINDS:
        if kind not in only:
            continue
        results, confs, problems = gather([case_dir], remote, clouds)
        if not results:
            for problem in problems:
                log.line(name, 'problem', problem)
            console.print(f"  [bold red]![/bold red] {escape(problems[0] if problems else 'nothing read')}")
            break
        snap, plan = results[0]
        conf = confs[Path(case_dir).parent]
        if kind == 'history' and plan.due('history'):
            step = executor.do_history(snap, plan)
        elif kind == 'upload' and plan.to_send():
            cloud = clouds.get((conf.remote, conf.path))
            if cloud is None:
                continue
            step = executor.do_upload(snap, plan, conf, cloud, ledgers[Path(case_dir).parent],
                                      lambda text: (log.line(name, 'upload', text),
                                                    console.print(f"    [dim]{escape(text)}[/dim]")))
        elif kind == 'post' and plan.due('post'):
            step = executor.do_post(snap, plan, conf)
        else:
            continue
        steps.append(step)
        log.line(name, step.kind, ('ok: ' if step.ok else 'FAILED: ') + step.text)
        if step.detail:
            log.line(name, step.kind, step.detail)
        if step.ok:
            console.print(f"  [green]{MARK[step.kind]}[/green] {escape(step.text)}")
        else:
            console.print(f"  [bold red]✗ {step.kind}:[/bold red] {escape(step.text)}")
            for line in step.detail.splitlines()[:6]:
                console.print(f"      [red]{escape(line)}[/red]")
            break
    return steps


def execute_apply(args) -> int:
    from src.commands.auto.show import gather
    from src.core.auto.conf import AutoConfError
    from src.core.transfer.ledger import Ledger
    from src.core.auto.runlog import AutoLockError, FolderLock, RunLog

    console = Console()
    try:
        only = _kinds(args)
    except AutoConfError as e:
        console.print(f"[red]Error:[/red] {escape(str(e))}")
        return 2
    got = _collect(args)
    if isinstance(got, int):
        return got
    first, confs, problems = got
    remote = getattr(args, 'remote', None)
    case_dirs = [snap.dir for snap, _ in first]
    for problem in problems:
        console.print(f"[bold red]![/bold red] {escape(problem)}")
    if not first:
        console.print("[red]Nothing was done.[/red]")
        return 1

    # what would be done
    todo = [(snap, plan, _intended(plan, only)) for snap, plan in first]
    todo = [t for t in todo if any(kind != 'detail' for kind, _ in t[2])]
    console.print()
    console.rule(f"[bold]auto apply[/bold]  [dim]{escape(remote or '')}[/dim]", style='cyan')
    if not todo:
        console.print("  [green]✓[/green] nothing to do"
                      + (f" ({sum(p.needs_you for _, p in first)} need you: `auto show`)"
                         if any(p.needs_you for _, p in first) else ''))
        console.rule(style='cyan')
        return 0
    for snap, plan, items in todo:
        console.print(f"  [bold cyan]{escape(snap.name)}[/bold cyan]")
        for kind, text in items:
            if kind == 'detail':
                console.print(f"        [dim]{escape(text)}[/dim]")
            else:
                console.print(f"    {MARK[kind]} {escape(text)}")
    if getattr(args, 'dry_run', False):
        console.print("[dim]--dry-run: nothing was done.[/dim]")
        console.rule(style='cyan')
        return 0
    if not getattr(args, 'yes', False):
        try:
            answer = input(f"Do this for {len(todo)} case(s)? Nothing is deleted. [y/N] ")
        except EOFError:
            answer = ''
        if answer.strip().lower() not in ('y', 'yes'):
            console.print("[yellow]Cancelled; nothing was done.[/yellow]")
            return 1

    folders = sorted({Path(d).parent for d in case_dirs})
    clouds, failures = {}, 0
    with ExitStack() as stack:
        try:
            for folder in folders:
                stack.enter_context(FolderLock(folder))
        except AutoLockError as e:
            console.print(f"[red]Error:[/red] {escape(str(e))}")
            return 1
        log = RunLog(folders[0])
        stack.callback(log.close)
        ledgers = {folder: Ledger(folder) for folder in folders}
        log.line('', 'start', f"auto apply --remote {remote} --only {','.join(sorted(only))} "
                              f"for {len(todo)} case(s)")
        try:
            for snap, _, _ in todo:
                console.print()
                console.rule(f"[bold cyan]{escape(snap.name)}[/bold cyan]", align='left',
                             style='grey50')
                steps = _run_case(snap.dir, remote, only, clouds, ledgers, log, console)
                failures += sum(1 for s in steps if not s.ok)
            # what is left
            results, _, _ = gather(case_dirs, remote, clouds)
        finally:
            for cloud in clouds.values():
                if cloud is not None:
                    cloud.close()
        left = sum(plan.needs_you for _, plan in results)
        log.line('', 'end', f"{failures} step(s) failed; {left} case(s) need you")
        console.print()
        console.rule("[bold]done[/bold]", style='cyan')
        console.print((f"[bold red]{failures} step(s) failed[/bold red] · " if failures
                       else "[green]no step failed[/green] · ")
                      + (f"[bold red]{left} case(s) need you[/bold red] (`auto show`)" if left
                         else "[green]none needs you[/green]"))
        console.print(f"[dim]Log: {escape(str(log.path))}[/dim]")
        console.rule(style='cyan')
        console.print()
    return 1 if failures else 0
