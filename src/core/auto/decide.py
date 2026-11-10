"""
The plan for one case, from its snapshot alone (docs/AUTO_PLAN.md §13).
No I/O here: everything comes in through CaseSnapshot, so every rule can be
tried on a made-up case.

    plan = decide(snap, conf, cloud_ok=True, sacct_ok=True)
    plan.state, plan.items, plan.uploads, plan.post, plan.needs_you

Item kinds, in the order a case shows them:
    flag     something to know (a job named for another case, a big run dir)
    history  organise the history (archive/clean/compile)
    post     submit a post job
    upload   files to send
    delete   what goes once its copy on the cloud is checked
    wait     nothing now (a job is busy with the case)
    needs    needs you: auto does nothing about it
    note     for information
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .observe import CaseSnapshot

RUNNING = ('RUNNING', 'COMPLETING', 'CONFIGURING')
BAD_END = ('FAILED', 'TIMEOUT', 'CANCELLED', 'NODE_FAIL', 'OUT_OF_MEMORY', 'PREEMPTED',
           'BOOT_FAIL', 'DEADLINE')


TOPIC_OF = {'needs': 'needs', 'flag': 'flag', 'history': 'history', 'post': 'post',
            'wait': 'post', 'upload': 'upload', 'delete': 'delete', 'note': 'other'}


@dataclass
class Item:
    kind: str
    text: str
    topic: str = 'other'        # the heading it is shown under: TOPIC_OF[kind] unless given


@dataclass
class CasePlan:
    name: str
    state: str
    facts: List[str] = field(default_factory=list)
    items: List[Item] = field(default_factory=list)
    uploads: Dict[str, int] = field(default_factory=dict)    # relative path -> bytes
    post: Optional[Tuple[int, int, str]] = None              # (t1, t2, 'full' | 'convert')

    def add(self, kind, text, topic=None):
        self.items.append(Item(kind, text, topic or TOPIC_OF[kind]))

    @property
    def needs_you(self) -> bool:
        return any(i.kind == 'needs' for i in self.items)


def steps_text(steps: List[int], freq: Optional[int], limit: int = 8) -> str:
    """Steps as runs: '450–600 (4 steps), 700'."""
    runs: List[List[int]] = []
    for t in sorted(steps):
        if runs and freq and t - runs[-1][-1] == freq:
            runs[-1].append(t)
        else:
            runs.append([t])
    parts = [str(r[0]) if len(r) == 1 else f"{r[0]}–{r[-1]} ({len(r)} steps)" for r in runs]
    if len(parts) > limit:
        parts = parts[:limit // 2] + [f"... {len(parts) - limit} more ..."] + parts[-limit // 2:]
    return ', '.join(parts)


def steps_phrase(steps: List[int], freq: Optional[int]) -> str:
    """'Step 750' or 'Steps 450–600 (4 steps)': the noun agrees with the count."""
    return f"{'Step' if len(steps) == 1 else 'Steps'} {steps_text(steps, freq)}"


def _size_text(n: int) -> str:
    for unit, div in (('GB', 1 << 30), ('MB', 1 << 20), ('KB', 1 << 10)):
        if n >= div:
            return f"{n / div:.1f} {unit}"
    return f"{n} B"


def _ended_at(job) -> Optional[float]:
    try:
        return datetime.strptime(job.end[:19], '%Y-%m-%dT%H:%M:%S').timestamp()
    except (ValueError, TypeError, AttributeError):
        return None


def decide(snap: CaseSnapshot, conf, cloud_ok: bool, sacct_ok: bool) -> CasePlan:
    if snap.error:
        plan = CasePlan(snap.name, 'skipped')
        plan.add('needs', f"Skipped: {snap.error}.")
        return plan

    p, f, name = snap.problem, snap.out_freq, snap.name
    main_now = snap.active('main')
    post_now = snap.active('post')
    running = any(j.state in RUNNING for j in main_now)
    pending = bool(main_now) and not running
    last_main, last_post = snap.last_ended('main'), snap.last_ended('post')
    reached = max([r[1] for r in (snap.live, snap.archive_range) if r] or [0]) or None
    has_history = bool(snap.live) or any(h.any for h in snap.history.values())

    state = ('running' if running else 'queued' if pending else 'post running' if post_now
             else 'done' if reached and snap.max_steps and reached >= snap.max_steps
             else 'stopped' if has_history or last_main else 'new')
    plan = CasePlan(name, state)
    if reached:
        of = (f" of {snap.max_steps} ({100 * reached // snap.max_steps}%)"
              if snap.max_steps else '')
        plan.facts.append(f"reached step {reached}{of}")
    for job in main_now + post_now:
        resume = (f", restarts from {snap.restart_tsid}"
                  if job.kind == 'main' and job.pending and snap.restart_tsid is not None else '')
        plan.facts.append(f"{job.kind} job {job.jobid} {job.state.lower()}{resume}")
    cloud = snap.cloud if cloud_ok else None

    # -- flags ------------------------------------------------------------------
    for job in snap.jobs:
        if job.kind != 'other' and not job.named_for(name):
            plan.add('flag', f"Job {job.jobid} is named {job.name}; for this case it should be "
                             f"{job.kind}{name}. Was its job script copied from another case?")
    for script, kind in (('mainFlex.sh', 'main'), ('postFlex.sh', 'post')):
        got = snap.script_names.get(script)
        if got and got != f"{kind}{name}":
            plan.add('flag', f"{script} names its jobs {got}; for this case it should be "
                             f"{kind}{name}.")
    if running and conf.disk_alert and snap.run_size > conf.disk_alert:
        plan.add('flag', f"The run directory holds {_size_text(snap.run_size)}, more than "
                         f"disk_alert ({_size_text(conf.disk_alert)}).")
    if last_main and last_main.state == 'FAILED' and not main_now:
        plan.add('needs', f"Main job {last_main.jobid} FAILED. Find the cause first "
                          f"(run list log, case check run).")

    # -- the folder rule: archive/ and cleaned/ ---------------------------------
    broken_rule = []
    for ext, h in snap.history.items():
        if h.cleaned and not set(h.cleaned) <= set(h.archive):
            missing = sorted(set(h.cleaned) - set(h.archive))
            broken_rule.append(f"{ext}_files/archive/ lacks run(s) {', '.join(map(str, missing))} "
                               f"that cleaned/ has")
    if broken_rule:
        plan.add('needs', "archive/ is pruned or missing: " + '; '.join(broken_rule) +
                 ". Every case keeps archive/ and cleaned/; restore it with "
                 "`case download history --archive`. No post decision until then.")

    # -- history ------------------------------------------------------------------
    organising = False
    if snap.live:
        if main_now:
            plan.add('note', f"Left in {snap.run_rel}/ while main job {main_now[0].jobid} is "
                             f"{main_now[0].state.lower()}; it is archived after the job ends.",
                     'history')
            if running and cloud is not None:
                stale = {k: v for k, v in snap.live_files.items() if cloud.get(k) != v}
                if stale:
                    plan.uploads.update(stale)
                    plan.add('upload', f"A copy of the live {p}.othd and {p}.oisd "
                                       f"({_size_text(sum(stale.values()))}), refreshed each run")
        elif not broken_rule:
            numbers = [n for h in snap.history.values() for n in (*h.archive, *h.cleaned)]
            n = max(numbers, default=0) + 1
            plan.add('history', f"Move {snap.run_rel}/{p}.othd and .oisd into archive/ as run "
                                f"{n}, then clean and compile "
                                f"(organise history --update --clean --compile)")
            organising = True
    if not organising and not broken_rule:
        uncleaned = sorted(set(snap.history['othd'].archive) - set(snap.history['othd'].cleaned))
        if uncleaned:
            plan.add('history', f"Clean and compile archive run(s) "
                                f"{', '.join(map(str, uncleaned))}, not yet in cleaned/ "
                                f"(organise history --clean --compile)")
            organising = True
    if cloud is not None:
        hist = {k: v for k, v in snap.files.items() if k.startswith(('othd_files/', 'oisd_files/'))
                and cloud.get(k) != v}
        if organising:
            plan.add('upload', "The history files, once organised")
        elif hist:
            plan.uploads.update(hist)
            plan.add('upload', f"History files: {len(hist)} ({_size_text(sum(hist.values()))})")

    # -- the post decision --------------------------------------------------------
    provisional = (lambda t: pending and snap.restart_tsid is not None and t > snap.restart_tsid)
    window = snap.live or snap.archive_range
    on_cloud = (lambda t: cloud is not None and cloud.get(f"binary/{p}.{t}.plt", 0) > 0)
    local_ok = (lambda t: t in snap.binary and snap.binary[t].ok)
    covered: List[int] = []                 # steps whose PLT is whole here or on the cloud
    if post_now:
        plan.add('wait', f"Post job {post_now[0].jobid} is {post_now[0].state.lower()}: nothing "
                         f"is posted or uploaded for this case until it ends.")
    elif broken_rule:
        pass
    elif window is None:
        if not has_history and not last_main:
            plan.add('note', "No run yet.")
    elif cloud is None:
        plan.add('note', "Not decided: the remote could not be listed.", 'post')
    elif not sacct_ok:
        plan.add('note', "Not decided: sacct could not be read, so how the last post job "
                         "ended is unknown.", 'post')
    else:
        t1 = math.ceil(window[0] / f) * f
        t2 = math.floor(window[1] / f) * f
        if snap.max_steps:
            t2 = min(t2, snap.max_steps)
        if running:
            done = [t for t in snap.settled if t <= t2]
            t2 = max(done) if done else t1 - f
        if pending and snap.restart_tsid is not None:
            t2 = min(t2, math.floor(snap.restart_tsid / f) * f)
        grid = list(range(t1, t2 + 1, f))
        have = [t for t in grid if on_cloud(t) or local_ok(t)]
        covered = have
        missing = [t for t in grid if t not in have]

        # which run, and why its output steps run from t1 to t2
        src = (f"{snap.run_rel}/{p}.othd" if snap.live
               else f"archive/{p}{max(snap.history['othd'].archive)}.othd")
        if running:
            cut = ", the last one the running job has finished."
        elif pending and snap.restart_tsid is not None and t2 < window[1]:
            cut = f"; it stops there because the queued job restarts from {snap.restart_tsid}."
        else:
            cut = '.'
        if grid:
            plan.add('note', f"The newest run is {src} (steps {window[0]}–{window[1]}). It writes "
                             f"output every {f} steps: {len(grid)} from {t1} to {t2}{cut}", 'post')
        n_cloud = sum(1 for t in grid if on_cloud(t))
        n_here = sum(1 for t in grid if local_ok(t) and not on_cloud(t))
        where = f"{n_cloud} on {conf.remote}" + (f", {n_here} only in binary/ (not uploaded yet)"
                                                 if n_here else '')
        bad_post = last_post if last_post and last_post.state in BAD_END else None
        # a post job that ended after these steps' .out were written should have
        # made their PLTs: if it did not, something is wrong -- do not repost blindly
        ended_at = _ended_at(last_post) if last_post else None
        given = snap.post_windows.get(last_post.jobid) if last_post else None
        missed = [t for t in missing if ended_at and t in snap.out_time
                  and snap.out_time[t] < ended_at
                  and (given is None or given[0] <= t <= given[1])]
        if not grid:
            plan.add('note', "No post job yet: no step of the run is finished.", 'post')
        elif not missing:
            plan.add('note', f"No post job needed: all {len(grid)} output steps have a PLT "
                             f"({where}). Matched by file name and size; the md5 is checked "
                             f"before anything is deleted.", 'post')
        elif missed and not bad_post:
            plan.add('needs', f"Post job {last_post.jobid} ended {last_post.state} after the .out "
                              f"of steps {steps_text(missed, f)} were written, yet they have no "
                              f"whole PLT here or on the remote. Check its log (run list log) "
                              f"before posting them again.")
        elif bad_post:
            broken = [t for t in grid if t in snap.binary and not snap.binary[t].ok]
            detail = f" (broken: {steps_text(broken, f)})" if broken else ''
            plan.add('needs', f"Post job {bad_post.jobid} ended {bad_post.state}: steps "
                              f"{steps_text(missing, f)} have no whole PLT{detail}. Post them again "
                              f"by hand once the cause is known.")
        else:
            prefix = grid[:len(have)] == have
            if have and not prefix:
                plan.add('needs', f"Holes on the remote: steps {steps_text(missing, f)} of "
                                  f"{t1}–{t2} have no PLT, while later steps have one. Find out "
                                  f"why before posting.")
            else:
                start = missing[0]
                todo = [t for t in grid if t >= start]
                no_input = [t for t in todo if t not in snap.settled and t not in snap.ascii]
                if no_input:
                    plan.add('needs', f"Steps {steps_text(no_input, f)} have no PLT on the remote "
                                      f"and no .out here to make one from.")
                else:
                    mode = 'convert' if all(t in snap.ascii for t in todo) else 'full'
                    plan.post = (todo[0], todo[-1], mode)
                    already = (f"; the {len(have)} before {todo[0]} have one ({where})"
                               if have else '')
                    plan.add('post', f"Submit `run post {mode} --t1 {todo[0]} --t2 {todo[-1]}`: "
                                     f"{len(todo)} output step{'s' if len(todo) != 1 else ''} "
                                     f"with no PLT yet{already}")
        later = [t for t in snap.out if pending and provisional(t)]
        if later:
            plan.add('note', f"{steps_phrase(sorted(later), f)} "
                             f"{'is' if len(later) == 1 else 'are'} left alone: the queued job "
                             f"restarts from {snap.restart_tsid} and computes "
                             f"{'it' if len(later) == 1 else 'them'} again.",
                     'post')

    # -- uploads: binary PLTs, the newest restart set, inputs and program files ----
    if cloud is not None and not post_now:
        plts = {f"binary/{p}.{t}.plt": c.size for t, c in sorted(snap.binary.items())
                if c.ok and not provisional(t) and cloud.get(f"binary/{p}.{t}.plt") != c.size}
        if plts:
            plan.uploads.update(plts)
            plan.add('upload', f"Binary PLTs, {steps_phrase([int(k.split('.')[1]) for k in plts], f).lower()}: "
                               f"{_size_text(sum(plts.values()))}")
        sets = [t for t, n in snap.rst.items() if snap.nsg and n == snap.nsg and not provisional(t)
                and not (running and snap.live and t >= snap.live[1])]
        if sets:
            newest = max(sets)
            stale = {k: v for k, v in snap.rst_files.get(newest, {}).items() if cloud.get(k) != v}
            if stale:
                plan.uploads.update(stale)
                plan.add('upload', f"Newest restart set, step {newest}: {len(stale)} files, "
                                   f"{_size_text(sum(stale.values()))}")
        inputs = {k: v for k, v in snap.files.items()
                  if not k.startswith(('othd_files/', 'oisd_files/')) and cloud.get(k) != v}
        if inputs:
            plan.uploads.update(inputs)
            plan.add('upload', f"Inputs and case files: {len(inputs)} files "
                               f"({', '.join(sorted(inputs)[:4])}{', ...' if len(inputs) > 4 else ''})")
    for t, c in sorted(snap.binary.items()):
        if not c.ok:
            plan.add('flag', f"binary/{p}.{t}.plt is broken: {c.reason}.")

    # -- deletions, once the copies on the cloud are checked ----------------------
    if cloud is not None and not post_now:
        gone = [t for t in covered if not provisional(t)]
        outs = [t for t in gone if t in snap.out and (not running or t in snap.settled)]
        ascii = [t for t in gone if t in snap.ascii]
        binary = [t for t in gone if local_ok(t)]
        parts = []
        if ascii:
            parts.append(f"ASCII PLTs, {steps_phrase(ascii, f).lower()}")
        if binary:
            parts.append(f"Binary PLTs, {steps_phrase(binary, f).lower()}")
        if outs:
            parts.append(f".out files, {steps_phrase(outs, f).lower()}")
        thin = []
        if conf.keep_rst and snap.rst:
            keep = set()
            if snap.restart_tsid is not None:
                keep.add(snap.restart_tsid)
            complete = [t for t, n in snap.rst.items() if snap.nsg and n == snap.nsg]
            if complete:
                keep.add(max(complete))
            keep.add(max(snap.rst))
            thin = [t for t in snap.rst if t % conf.keep_rst and t not in keep
                    and not provisional(t) and not (running and snap.live and t >= snap.live[1])]
        if parts:
            for part in parts:
                plan.add('delete', part)
        if conf.keep_rst and snap.rst and thin:
            plan.add('delete', f"{steps_phrase(thin, f)}: not a multiple of {conf.keep_rst}. "
                               f"The restart point and the newest set stay.", 'thin')
        if snap.rst and not conf.keep_rst:
            plan.add('note', "Not thinned: auto.keep_rst is not set (auto init --keep-rst N).",
                     'thin')

    # -- stopped short --------------------------------------------------------------
    if state == 'stopped' and reached and snap.max_steps and reached < snap.max_steps \
            and last_main and last_main.state != 'FAILED':
        plan.add('needs', f"Stopped at step {reached} of {snap.max_steps} with nothing queued "
                          f"(main job {last_main.jobid} ended {last_main.state}). Queue a restart "
                          f"(run main restart <tsId>)?")
    return plan
