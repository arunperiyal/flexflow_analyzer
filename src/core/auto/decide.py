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


@dataclass
class Item:
    kind: str
    text: str


@dataclass
class CasePlan:
    name: str
    state: str
    facts: List[str] = field(default_factory=list)
    items: List[Item] = field(default_factory=list)
    uploads: Dict[str, int] = field(default_factory=dict)    # relative path -> bytes
    post: Optional[Tuple[int, int, str]] = None              # (t1, t2, 'full' | 'convert')

    def add(self, kind, text):
        self.items.append(Item(kind, text))

    @property
    def needs_you(self) -> bool:
        return any(i.kind == 'needs' for i in self.items)


def steps_text(steps: List[int], freq: Optional[int], limit: int = 8) -> str:
    """Steps as runs: '450-600 (4), 700'."""
    runs: List[List[int]] = []
    for t in sorted(steps):
        if runs and freq and t - runs[-1][-1] == freq:
            runs[-1].append(t)
        else:
            runs.append([t])
    parts = [str(r[0]) if len(r) == 1 else f"{r[0]}-{r[-1]} ({len(r)})" for r in runs]
    if len(parts) > limit:
        parts = parts[:limit // 2] + [f"... {len(parts) - limit} more ..."] + parts[-limit // 2:]
    return ', '.join(parts)


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
        plan.add('needs', f"skipped: {snap.error}")
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
        of = f" of {snap.max_steps}" if snap.max_steps else ''
        plan.facts.append(f"step {reached}{of}")
    for job in main_now + post_now:
        plan.facts.append(f"{job.name} {job.jobid} {job.state}")
    cloud = snap.cloud if cloud_ok else None

    # -- flags ------------------------------------------------------------------
    for job in snap.jobs:
        if job.kind != 'other' and not job.named_for(name):
            plan.add('flag', f"job {job.jobid} is named {job.name}, not {job.kind}{name} "
                             f"(a job script copied from another case?)")
    for script, kind in (('mainFlex.sh', 'main'), ('postFlex.sh', 'post')):
        got = snap.script_names.get(script)
        if got and got != f"{kind}{name}":
            plan.add('flag', f"{script} names its job {got}, not {kind}{name}")
    if running and conf.disk_alert and snap.run_size > conf.disk_alert:
        plan.add('flag', f"run directory {_size_text(snap.run_size)}, over disk_alert "
                         f"({_size_text(conf.disk_alert)})")
    if last_main and last_main.state == 'FAILED' and not main_now:
        plan.add('needs', f"last main job {last_main.jobid} FAILED: find the cause (run list log)")

    # -- the folder rule: archive/ and cleaned/ ---------------------------------
    broken_rule = []
    for ext, h in snap.history.items():
        if h.cleaned and not set(h.cleaned) <= set(h.archive):
            missing = sorted(set(h.cleaned) - set(h.archive))
            broken_rule.append(f"{ext}_files/archive/ lacks run(s) {', '.join(map(str, missing))} "
                               f"that cleaned/ has")
    if broken_rule:
        plan.add('needs', "archive/ pruned or missing: " + '; '.join(broken_rule) +
                 " -- every case keeps archive/ and cleaned/ (case download history --archive)")

    # -- history ------------------------------------------------------------------
    organising = False
    if snap.live:
        if main_now:
            plan.add('note', f"history stays in {snap.run_rel}/ while main job is "
                             f"{main_now[0].state.lower()}")
            if running and cloud is not None:
                stale = {k: v for k, v in snap.live_files.items() if cloud.get(k) != v}
                if stale:
                    plan.uploads.update(stale)
                    plan.add('upload', f"snapshot of the live {p}.othd/.oisd "
                                       f"({_size_text(sum(stale.values()))})")
        elif not broken_rule:
            numbers = [n for h in snap.history.values() for n in (*h.archive, *h.cleaned)]
            n = max(numbers, default=0) + 1
            plan.add('history', f"organise history --update --clean --compile: "
                                f"{snap.run_rel}/{p}.othd -> archive/{p}{n}.othd")
            organising = True
    if not organising and not broken_rule:
        uncleaned = sorted(set(snap.history['othd'].archive) - set(snap.history['othd'].cleaned))
        if uncleaned:
            plan.add('history', f"organise history --clean --compile (archive part(s) "
                                f"{', '.join(map(str, uncleaned))} not in cleaned/)")
            organising = True
    if cloud is not None:
        hist = {k: v for k, v in snap.files.items() if k.startswith(('othd_files/', 'oisd_files/'))
                and cloud.get(k) != v}
        if organising:
            plan.add('upload', "the history, once organised")
        elif hist:
            plan.uploads.update(hist)
            plan.add('upload', f"history: {len(hist)} file(s), {_size_text(sum(hist.values()))}")

    # -- the post decision --------------------------------------------------------
    provisional = (lambda t: pending and snap.restart_tsid is not None and t > snap.restart_tsid)
    window = snap.live or snap.archive_range
    on_cloud = (lambda t: cloud is not None and cloud.get(f"binary/{p}.{t}.plt", 0) > 0)
    local_ok = (lambda t: t in snap.binary and snap.binary[t].ok)
    covered: List[int] = []                 # steps whose PLT is whole here or on the cloud
    if post_now:
        plan.add('wait', f"post job {post_now[0].jobid} is {post_now[0].state.lower()}: "
                         f"nothing posted or uploaded for its steps until it ends")
    elif broken_rule:
        pass
    elif window is None:
        if not has_history and not last_main:
            plan.add('note', "no run yet")
    elif cloud is None:
        plan.add('note', "post: not decided (the cloud could not be listed)")
    elif not sacct_ok:
        plan.add('note', "post: not decided (sacct could not be read, so how the last "
                         "post job ended is unknown)")
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
        bad_post = last_post if last_post and last_post.state in BAD_END else None
        # a post job that ended after these steps' .out were written should have
        # made their PLTs: if it did not, something is wrong -- do not repost blindly
        ended_at = _ended_at(last_post) if last_post else None
        given = snap.post_windows.get(last_post.jobid) if last_post else None
        missed = [t for t in missing if ended_at and t in snap.out_time
                  and snap.out_time[t] < ended_at
                  and (given is None or given[0] <= t <= given[1])]
        if not grid:
            plan.add('note', "post: no step settled yet")
        elif not missing:
            plan.add('note', f"post: PLTs of {t1}-{t2} all on the cloud or here")
        elif missed and not bad_post:
            plan.add('needs', f"post job {last_post.jobid} ended {last_post.state} after the .out "
                              f"of {steps_text(missed, f)} were written, but they have no whole "
                              f"PLT here or on the cloud: check its log (run list log)")
        elif bad_post:
            broken = [t for t in grid if t in snap.binary and not snap.binary[t].ok]
            detail = f"; broken: {steps_text(broken, f)}" if broken else ''
            plan.add('needs', f"last post job {bad_post.jobid} ended {bad_post.state}: no whole "
                              f"PLT for {steps_text(missing, f)}{detail}. Post them again by hand")
        else:
            prefix = grid[:len(have)] == have
            if have and not prefix:
                plan.add('needs', f"holes on the cloud: no PLT for {steps_text(missing, f)} in "
                                  f"{t1}-{t2}, while later steps have one")
            else:
                start = missing[0]
                todo = [t for t in grid if t >= start]
                no_input = [t for t in todo if t not in snap.settled and t not in snap.ascii]
                if no_input:
                    plan.add('needs', f"no PLT on the cloud and no .out here for "
                                      f"{steps_text(no_input, f)}")
                else:
                    mode = 'convert' if all(t in snap.ascii for t in todo) else 'full'
                    plan.post = (todo[0], todo[-1], mode)
                    src = f"live {p}.othd" if snap.live else \
                        f"archive/{p}{max(snap.history['othd'].archive)}.othd"
                    plan.add('post', f"run post {mode} --t1 {todo[0]} --t2 {todo[-1]} "
                                     f"({len(todo)} steps; window from {src})")
        later = [t for t in snap.out if pending and provisional(t)]
        if later:
            plan.add('note', f"{steps_text(sorted(later), f)} will be computed again by the "
                             f"queued restart from {snap.restart_tsid}: left alone")

    # -- uploads: binary PLTs, the newest restart set, inputs and program files ----
    if cloud is not None and not post_now:
        plts = {f"binary/{p}.{t}.plt": c.size for t, c in sorted(snap.binary.items())
                if c.ok and not provisional(t) and cloud.get(f"binary/{p}.{t}.plt") != c.size}
        if plts:
            plan.uploads.update(plts)
            plan.add('upload', f"binary PLT {steps_text([int(k.split('.')[1]) for k in plts], f)} "
                               f"({_size_text(sum(plts.values()))})")
        sets = [t for t, n in snap.rst.items() if snap.nsg and n == snap.nsg and not provisional(t)
                and not (running and snap.live and t >= snap.live[1])]
        if sets:
            newest = max(sets)
            stale = {k: v for k, v in snap.rst_files.get(newest, {}).items() if cloud.get(k) != v}
            if stale:
                plan.uploads.update(stale)
                plan.add('upload', f"newest restart set {newest} ({len(stale)} file(s), "
                                   f"{_size_text(sum(stale.values()))})")
        inputs = {k: v for k, v in snap.files.items()
                  if not k.startswith(('othd_files/', 'oisd_files/')) and cloud.get(k) != v}
        if inputs:
            plan.uploads.update(inputs)
            plan.add('upload', f"inputs and program files: {len(inputs)} file(s) "
                               f"({', '.join(sorted(inputs)[:4])}{', ...' if len(inputs) > 4 else ''})")
    for t, c in sorted(snap.binary.items()):
        if not c.ok:
            plan.add('flag', f"binary/{p}.{t}.plt: {c.reason}")

    # -- deletions, once the copies on the cloud are checked ----------------------
    if cloud is not None and not post_now:
        gone = [t for t in covered if not provisional(t)]
        outs = [t for t in gone if t in snap.out and (not running or t in snap.settled)]
        ascii = [t for t in gone if t in snap.ascii]
        binary = [t for t in gone if local_ok(t)]
        parts = []
        if ascii:
            parts.append(f"ASCII PLT {steps_text(ascii, f)}")
        if binary:
            parts.append(f"binary PLT {steps_text(binary, f)}")
        if outs:
            parts.append(f".out of {steps_text(outs, f)}")
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
            plan.add('delete', "once their copy on the cloud is checked: " + '; '.join(parts))
        if conf.keep_rst and snap.rst and thin:
            plan.add('delete', f"thin .rst to every {conf.keep_rst}: {steps_text(thin, f)} "
                               f"(restart point and newest set kept)")
        if snap.rst and not conf.keep_rst:
            plan.add('note', ".rst not thinned (auto.keep_rst not set in .cases.yml)")

    # -- stopped short --------------------------------------------------------------
    if state == 'stopped' and reached and snap.max_steps and reached < snap.max_steps \
            and last_main and last_main.state != 'FAILED':
        plan.add('needs', f"stopped at {reached} of {snap.max_steps} with nothing queued "
                          f"(last main job {last_main.state}): queue a restart?")
    return plan
