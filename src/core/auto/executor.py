"""
The three additive actions `auto apply` carries out for a case, each from the
plan `decide` made a moment before (docs/architecture/auto.md §13):

    do_history   case organise history --update --clean --compile
    do_upload    send the files the plan lists, each checked, never deleting
    do_post      submit `run post` for the first stretch the plan lists

Nothing here deletes a file, and nothing moves a file except the run
directory's history into archive/. A Step says what happened; a failed one
carries the detail to read.
"""

import io
import os
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
            size = local.stat().st_size
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
        ledger.record(conf.remote, snap.name, rel, res.size, res.md5, res.verified)
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
