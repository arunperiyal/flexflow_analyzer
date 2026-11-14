"""auto apply: carry out what `auto show` lists -- organise the history, upload
(checked), delete what has a checked copy (only when asked), submit a post job.

    auto apply [case] --remote NAME [--only history,upload,delete,post] [--delete]
                                    [--dry-run] [--yes]

For each case, in this order, with the plan made again from the files and the
queue right before each step (so a step runs on what is there now, not on what
was there when the run started):

    history   case organise history --update --clean --compile
    upload    the files the plan lists, to <remote>/<case>/..., each checked
    delete    --delete or --only delete: the local files whose copy on the remote passes
              an md5 check made at that moment, and the restart sets off the keep_rst
              grid (auto.md 13.13)
    post      `run post` for the first stretch of steps with no PLT yet

A step that fails stops that case (the steps after it depend on it); the other
cases go on. Everything is written to <folder>/auto_logs/auto_<time>.log.
"""

from contextlib import ExitStack
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from .show import _collect, _size_text_of

KINDS = ('history', 'upload', 'delete', 'post')
MARK = {'history': '↻', 'upload': '↑', 'delete': '✗', 'post': '▶'}


def _kinds(args):
    from src.core.auto.conf import AutoConfError
    raw = getattr(args, 'only', None)
    if not raw:
        # deleting is never part of a plain apply: it is asked for
        return set(KINDS) if getattr(args, 'delete', False) else set(KINDS) - {'delete'}
    wanted = {w.strip().lower() for w in raw.split(',') if w.strip()}
    unknown = wanted - set(KINDS)
    if unknown:
        raise AutoConfError(f"--only for apply: unknown {', '.join(sorted(unknown))} "
                            f"(history, upload, delete, post)")
    if getattr(args, 'delete', False):
        wanted.add('delete')
    return wanted


def _delete_words(files, size, sets, rst_size, remote):
    """'up to 12 files (1.2 GB) with a checked copy and 3 restart sets (2 KB) with none'."""
    parts = []
    if files:
        parts.append(f"{files} file{'s' if files != 1 else ''} ({_size_text_of({'x': size})}) "
                     f"whose copies{' on ' + remote if remote else ''} pass the md5 check")
    if sets:
        parts.append(f"{sets} restart set{'s' if sets != 1 else ''} "
                     f"({_size_text_of({'x': rst_size})}) that "
                     f"{'has' if sets == 1 else 'have'} no copy (off the keep_rst grid)")
    return 'up to ' + ' and '.join(parts) if files else ' and '.join(parts)


def delete_totals(plan):
    """What the plan would delete: (files with a copy, their bytes, restart sets, their bytes)."""
    import re
    d = plan.ctx.get('delete') or {}
    copy = {**d.get('ascii', {}), **d.get('binary', {}), **d.get('out', {})}
    sets = {re.search(r'\.(\d+)_\d+\.rst$', r).group(1) for r in d.get('rst', {})}
    return len(copy), sum(copy.values()), len(sets), sum(d.get('rst', {}).values())


RULE = {'ascii': 'C1', 'binary': 'C2', 'out': 'C3'}


def _delete_breakdown(plan):
    from src.core.auto.decide import _size_text, steps_phrase
    d, c = plan.ctx.get('delete') or {}, plan.ctx
    lines = []
    for key, label, steps in (('ascii', 'ASCII PLTs', c.get('del_ascii')),
                              ('binary', 'binary PLTs', c.get('del_binary')),
                              ('out', '.out files', c.get('del_out'))):
        if d.get(key):
            lines.append(f"{RULE[key]} "
                         f"{label}, {steps_phrase(steps or []).lower()}: {len(d[key])} files, "
                         f"{_size_text(sum(d[key].values()))}")
    if d.get('rst'):
        lines.append(f"C4 restart sets {steps_phrase(c.get('thin') or []).lower()}: no copy, off the "
                     f"keep_rst grid ({_size_text(sum(d['rst'].values()))})")
    if c.get('delete_hold'):
        lines.append("nothing is deleted while the case needs you (auto show)")
    return lines


def _upload_breakdown(plan):
    """The files of plan.uploads by what they are: [text], largest groups first."""
    import re
    from src.core.auto.decide import _size_text, steps_text
    groups = {}                                  # label -> [files, bytes]
    sets = {}                                    # restart step -> [files, bytes]
    live = set(plan.ctx.get('live_upload') or {})
    for rel, size in plan.uploads.items():
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
    replaced_plt = sorted({int(m.group(1)) for rel in plan.uploads
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
    """What the plan has apply do, in order: [(kind, text)]; a 'detail' line
    belongs to the one before it."""
    out = []
    organise = plan.ctx.get('organise')
    if 'history' in only and organise:
        out.append(('history', "organise history --update --clean --compile"
                    if organise[0] == 'update' else "organise history --clean --compile"))
    if 'upload' in only and plan.uploads:
        out.append(('upload', f"{len(plan.uploads)} files, {_size_text_of(plan.uploads)}"))
        out += [('detail', line) for line in _upload_breakdown(plan)]
    if 'delete' in only:
        n, size, sets, rst_size = delete_totals(plan)
        if n or sets:
            out.append(('delete', _delete_words(n, size, sets, rst_size, '')))
            out += [('detail', line) for line in _delete_breakdown(plan)]
        elif plan.ctx.get('delete_hold'):
            out.append(('detail', "delete: held back, the case needs you (auto show)"))
    if 'post' in only and plan.post_jobs:
        a, b, d, mode = plan.post_jobs[0]
        more = f" (+{len(plan.post_jobs) - 1} more after it)" if len(plan.post_jobs) > 1 else ''
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
        if kind == 'history' and plan.ctx.get('organise'):
            step = executor.do_history(snap, plan)
        elif kind == 'upload' and plan.uploads:
            cloud = clouds.get((conf.remote, conf.path))
            if cloud is None:
                continue
            step = executor.do_upload(snap, plan, conf, cloud, ledgers[Path(case_dir).parent],
                                      lambda text: (log.line(name, 'upload', text),
                                                    console.print(f"    [dim]{escape(text)}[/dim]")))
        elif kind == 'delete' and any((plan.ctx.get('delete') or {}).values()):
            cloud = clouds.get((conf.remote, conf.path))
            if cloud is None:
                continue
            step = executor.do_delete(snap, plan, conf, cloud, ledgers[Path(case_dir).parent],
                                      lambda text: (log.line(name, 'delete', text),
                                                    console.print(f"    [dim]{escape(text)}[/dim]")))
        elif kind == 'post' and plan.post_jobs:
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
    from src.core.auto.ledger import Ledger
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
        console.print("[dim]--dry-run: nothing was done."
                      + (" The md5 of each copy is only computed in a real run, so some of "
                         "these may be left." if 'delete' in only else '') + "[/dim]")
        console.rule(style='cyan')
        return 0
    if not getattr(args, 'yes', False):
        question = f"Do this for {len(todo)} case(s)? Nothing is deleted. [y/N] "
        if 'delete' in only:
            files = size = sets = rst_size = 0
            for _, plan, _ in todo:
                a, b, c, d = delete_totals(plan)
                files, size, sets, rst_size = files + a, size + b, sets + c, rst_size + d
            if files or sets:
                question = (f"Do this for {len(todo)} case(s)? This DELETES "
                            f"{_delete_words(files, size, sets, rst_size, remote)}. [y/N] ")
        try:
            answer = input(question)
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
