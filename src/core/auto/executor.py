"""
The actions `auto apply` carries out for a case, each from the plan `decide`
made a moment before (docs/architecture/auto.md §13):

    do_history   case organise history --update --clean --compile
    do_upload    send the files the plan lists, each checked, never deleting
    do_delete    delete the files the plan lists, each checked again just before (13.13)
    do_post      submit `run post` for the first stretch the plan lists

Only do_delete deletes, and it deletes nothing the plan did not list. Nothing
moves a file except the run directory's history into archive/. A Step says
what happened; a failed one carries the detail to read.
"""

import io
import os
import re
import time
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional

from rich.console import Console


@dataclass
class Step:
    kind: str           # history | upload | post
    ok: bool
    text: str
    detail: str = ''


class _Quiet:
    """A logger that says nothing: the organiser's own table goes to the run log."""

    def __getattr__(self, name):
        return lambda *a, **k: None


# --- history -----------------------------------------------------------------------

def do_history(snap, plan) -> Step:
    from src.commands.case.organise_impl.organizer import CaseOrganizer
    mode, which = plan.ctx['organise']
    stages = ('update', 'clean', 'compile') if mode == 'update' else ('clean', 'compile')
    flags = dict(update=False, clean=False, compile=False, verify=False, prune=False,
                 dry_run=False, no_confirm=True, log=False, verbose=False, t1=None, t2=None)
    flags.update({stage: True for stage in stages})
    case = SimpleNamespace(case_directory=str(snap.dir), problem_name=snap.problem,
                           config={'dir': f"./{snap.run_rel}"})
    out = io.StringIO()
    try:
        organizer = CaseOrganizer(case, Namespace(**flags), _Quiet(),
                                  Console(file=out, width=160, color_system=None))
        organizer.organize('history')
    except Exception as e:
        return Step('history', False, f"organise history failed: {type(e).__name__}: {e}",
                    out.getvalue())
    detail = out.getvalue()
    run_dir = snap.dir / snap.run_rel
    if mode == 'update':
        left = [f.name for ext in ('othd', 'oisd') for f in run_dir.glob(f'{snap.problem}.{ext}')]
        if left:
            return Step('history', False,
                        f"{', '.join(left)} still in {snap.run_rel}/ after organise history",
                        detail)
        return Step('history', True,
                    f"moved {snap.run_rel}/{snap.problem}.othd and .oisd into archive/ as run "
                    f"{which}; cleaned and compiled", detail)
    return Step('history', True, f"cleaned and compiled archive run(s) "
                                 f"{', '.join(map(str, which))}", detail)


# --- upload ------------------------------------------------------------------------

def _upload_order(rel: str):
    if rel.startswith(('othd_files/', 'oisd_files/')):
        return 0, rel
    if rel.startswith('binary/'):
        return 1, rel
    if rel.endswith('.rst'):
        return 2, rel
    return 3, rel


def do_upload(snap, plan, conf, cloud, ledger, say: Callable[[str], None],
              big: int = 5 << 20) -> Step:
    """Send plan.uploads. `say` gets progress lines. Every file is checked by the
    cloud's put(); one that fails is reported and the rest still go, except that
    three failures in a row stop the run (the remote has probably gone)."""
    files = sorted(plan.uploads.items(), key=lambda kv: _upload_order(kv[0]))
    sent = nbytes = md5_ok = size_only = snapshots = 0
    failed, streak = [], 0
    started = time.monotonic()
    for rel, planned in files:
        local = snap.dir / rel
        snapshot = rel in snap.live_files
        try:
            st = local.stat()
            size, mtime = st.st_size, st.st_mtime
        except OSError as e:
            failed.append((rel, f"cannot read it: {e.strerror or e}"))
            continue
        if size != planned and not snapshot:
            failed.append((rel, f"changed since the plan ({planned} -> {size} bytes); "
                                f"left for the next run"))
            continue
        t0 = time.monotonic()
        res = cloud.put(local, snap.name, rel, snapshot=snapshot)
        if not res.ok:
            failed.append((rel, res.detail))
            streak += 1
            if streak >= 3:
                failed.append(('', 'three failures in a row: stopped'))
                break
            continue
        streak = 0
        sent += 1
        nbytes += res.size
        if res.verified == 'md5':
            md5_ok += 1
        elif res.verified == 'size':
            size_only += 1
        else:
            snapshots += 1
        ledger.record(conf.remote, snap.name, rel, res.size, res.md5, res.verified, mtime)
        if res.size >= big:
            dt = max(time.monotonic() - t0, 1e-6)
            say(f"{rel}  {res.size / 1e6:.1f} MB in {dt:.0f} s ({res.size / 1e6 / dt:.1f} MB/s), "
                f"{res.verified}")
    elapsed = time.monotonic() - started
    checks = [f"{md5_ok} md5-checked"]
    if size_only:
        checks.append(f"{size_only} by size only (no md5sum on the remote)")
    if snapshots:
        checks.append(f"{snapshots} live snapshot(s)")
    text = f"sent {sent} of {len(files)} files ({nbytes / 1e6:.1f} MB, {elapsed:.0f} s): " \
           + ', '.join(checks)
    if failed:
        detail = '\n'.join(f"{rel or '-'}: {why}" for rel, why in failed)
        return Step('upload', False, f"{text}; {len(failed)} failed", detail)
    return Step('upload', True, text)


# --- delete ------------------------------------------------------------------------

def _gb(n: int) -> str:
    return f"{n / 1e9:.1f} GB"


def do_delete(snap, plan, conf, cloud, ledger, say: Callable[[str], None]) -> Step:
    """Delete plan.ctx['delete'], one file at a time, each checked again right before it
    goes (13.13). A file whose check fails is left and said so; the rest go on. Three
    remote failures in a row stop the stage. Restart sets (C4) are the one thing deleted
    without a copy."""
    from src.core.plt_valid import check_plt
    todo = plan.ctx.get('delete') or {}
    p, name, remote = snap.problem, snap.name, conf.remote
    state = {'streak': 0, 'stopped': False, 'mismatch': 0}
    counts = {'ascii': 0, 'binary': 0, 'out': 0, 'sets': set()}
    freed = {'copy': 0, 'rst': 0}
    left = []

    def leave(rel, why):
        left.append((rel, why))
        say(f"left {rel}: {why}")

    def remote_failed(rel, why):
        state['streak'] += 1
        leave(rel, why)
        if state['streak'] >= 3:
            state['stopped'] = True

    def plt_rel(t):
        return f"binary/{p}.{t}.plt"

    checks = {}

    def checked(t):
        """(True, written, how) when the binary PLT of step t has a copy on the remote
        whose md5, computed now, equals the local file's (or the ledger's when the file is
        gone here); else (False, reason). Once per step."""
        if t in checks:
            return checks[t]
        rel, local = plt_rel(t), snap.dir / plt_rel(t)
        there = cloud.remote_size(name, rel)
        if local.exists():
            c = check_plt(local)
            if not c.ok:
                res = (False, f"the binary PLT of step {t} is not whole here ({c.reason})")
            elif there != c.size:
                res = (False, f"the copy of binary PLT {t} on {remote} is "
                              f"{'missing' if there is None else f'{there} bytes, not {c.size}'}")
            else:
                got, mine = cloud.remote_md5(name, rel), file_md5_of(local)
                if got is None:
                    res = (False, f"the md5 of binary PLT {t} could not be read on {remote}", 'remote')
                elif got != mine:
                    ledger.mark_mismatch(remote, name, rel)
                    state['mismatch'] += 1
                    res = (False, f"md5 of binary PLT {t} differs on {remote} "
                                  f"({got} there, {mine} here)", 'mismatch')
                else:
                    st = local.stat()
                    ledger.record(remote, name, rel, st.st_size, mine, 'md5', st.st_mtime)
                    res = (True, st.st_mtime, f"md5 {mine[:8]} here and on {remote}")
        else:
            e = ledger.get(remote, name, rel)
            if not e or e.get('verified') != 'md5' or not e.get('md5') or e.get('mtime') is None:
                res = (False, f"binary PLT {t} is gone here and the ledger cannot vouch for it")
            elif there != e.get('size'):
                res = (False, f"the copy of binary PLT {t} on {remote} is not the one sent "
                              f"({there} bytes, ledger {e.get('size')})")
            else:
                got = cloud.remote_md5(name, rel)
                if got is None:
                    res = (False, f"the md5 of binary PLT {t} could not be read on {remote}", 'remote')
                elif got != e['md5']:
                    ledger.mark_mismatch(remote, name, rel)
                    state['mismatch'] += 1
                    res = (False, f"md5 of binary PLT {t} on {remote} differs from the ledger's "
                                  f"({got} there, {e['md5']} sent)", 'mismatch')
                else:
                    res = (True, e['mtime'], f"md5 {got[:8]} on {remote} equals the ledger's")
        checks[t] = res
        if len(res) == 3 and res[2] == 'remote':
            state['streak'] += 1
            if state['streak'] >= 3:
                state['stopped'] = True
        elif res[0]:
            state['streak'] = 0
        return res

    def unlink(rel, kind, size, how):
        try:
            os.unlink(snap.dir / rel)
        except OSError as e:
            leave(rel, f"cannot delete it: {e.strerror or e}")
            return False
        say(f"deleted {rel} ({kind}): {how}")
        return True

    def step_of(rel):
        m = re.search(r'\.(\d+)(?:_\d+\.out|\.plt|_\d+\.rst)$', rel)
        return int(m.group(1)) if m else None

    def newer_than(t, written, rel_list):
        """The binary PLT, written at `written`, is newer than every file in rel_list now."""
        for rel in rel_list:
            try:
                if os.stat(snap.dir / rel).st_mtime >= written:
                    return rel
            except OSError:
                pass
        return None

    # C1: ASCII PLTs
    for rel in sorted(todo.get('ascii', {})):
        if state['stopped']:
            break
        t = step_of(rel)
        res = checked(t)
        if not res[0]:
            leave(rel, res[1])
        elif newer_than(t, res[1], [rel]):
            leave(rel, f"written after the binary PLT of step {t}")
        elif unlink(rel, 'C1 ASCII PLT', 0, res[2]):
            counts['ascii'] += 1
            freed['copy'] += todo['ascii'][rel]
    # C2: binary PLTs
    for rel in sorted(todo.get('binary', {})):
        if state['stopped']:
            break
        t = step_of(rel)
        res = checked(t)
        if not res[0]:
            leave(rel, res[1])
        elif unlink(rel, 'C2 binary PLT', 0, res[2]):
            ledger.mark_deleted(remote, name, rel)
            counts['binary'] += 1
            freed['copy'] += todo['binary'][rel]
    # C3: .out parts, all of a step or none
    by_step = {}
    for rel in todo.get('out', {}):
        by_step.setdefault(step_of(rel), []).append(rel)
    for t, rels in sorted(by_step.items()):
        if state['stopped']:
            break
        res = checked(t)
        if not res[0]:
            for rel in rels:
                leave(rel, res[1])
            continue
        late = newer_than(t, res[1], rels)
        if late:
            for rel in rels:
                leave(rel, f"{Path(late).name} was written after the binary PLT of step {t}")
            continue
        for rel in sorted(rels):
            if unlink(rel, 'C3 .out', 0, res[2]):
                counts['out'] += 1
                freed['copy'] += todo['out'][rel]
    # C4: restart sets off the keep_rst grid: no copy, said so
    for rel in sorted(todo.get('rst', {})):
        if state['stopped']:
            break
        if unlink(rel, 'C4 restart set', 0, f"off the keep_rst grid ({conf.keep_rst}), no copy"):
            counts['sets'].add(step_of(rel))
            freed['rst'] += todo['rst'][rel]
    if state['stopped']:
        left.append(('', 'three remote failures in a row: stopped'))

    parts = [f"{n} {what}" for n, what in ((counts['ascii'], 'ASCII PLT'), (counts['binary'], 'binary PLT'),
                                           (counts['out'], '.out'), (len(counts['sets']), 'restart sets'))
             if n]
    total = freed['copy'] + freed['rst']
    if parts:
        try:
            from src.core import case_status
            case_status.add_log(snap.dir, f"auto deleted: {', '.join(parts)}; {_gb(total)}")
        except OSError as e:
            say(f"could not write .casestatus.md: {e}")
    text = (f"deleted {', '.join(parts) if parts else 'nothing'}; {_gb(total)} freed"
            + (f"; {len(left)} left" if left else ''))
    bad = state['mismatch'] or state['stopped'] or any('cannot delete it' in w for _, w in left)
    detail = '\n'.join(f"{rel or '-'}: {why}" for rel, why in left)
    return Step('delete', not bad, text, detail if bad else '')


def file_md5_of(path) -> str:
    from .cloud import file_md5
    return file_md5(path)


# --- post --------------------------------------------------------------------------

def do_post(snap, plan, conf) -> Step:
    from src.commands.run.post_impl.command import (find_postprocessing_script,
                                                    submit_postprocessing_job)
    t1, t2, freq, mode = plan.post_jobs[0]
    command = f"run post {mode} {snap.name} --t1 {t1} --t2 {t2} --freq {freq} --no-remote"
    script = find_postprocessing_script(snap.dir)
    if script is None:
        return Step('post', False, "no postFlex.sh in the case", command)
    if not os.access(script, os.X_OK):
        return Step('post', False, f"{script.name} is not executable (chmod +x)", command)
    # `run post` asks what to do when the job name is wrong; there is nobody to
    # answer here (its output goes to the log), so the name is checked first
    from src.commands.run.shared_helpers import parse_script_jobname
    expected, got = f"post{snap.name}", parse_script_jobname(script)
    if got != expected:
        return Step('post', False,
                    f"{script.name} names its job {got or '(no name)'}, it should be {expected}; "
                    f"fix it with `run post full {snap.name}` (it offers to set the name)",
                    command)
    args = SimpleNamespace(
        case=str(snap.dir), words=[], post_mode=mode, convert=(mode == 'convert'),
        t1=t1, t2=t2, freq=freq, remote=None, no_remote=True, dependency=None,
        partition=conf.partition, account=conf.account, qos=conf.qos,
        cleanup=False, no_cleanup=True, cleanup_only=False, dry_run=False, show=False,
        verbose=False, help=False)
    out = io.StringIO()
    try:
        job_id = submit_postprocessing_job(script, snap.dir, args,
                                           Console(file=out, width=160, color_system=None))
    except Exception as e:
        return Step('post', False, f"submitting failed: {type(e).__name__}: {e}", out.getvalue())
    if job_id is None:
        return Step('post', False, "the post job was not submitted", out.getvalue())
    more = (f"; {len(plan.post_jobs) - 1} more stretch(es) after it has ended"
            if len(plan.post_jobs) > 1 else '')
    return Step('post', True, f"post job {job_id or '?'} submitted: {command}{more}",
                out.getvalue())
