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
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .observe import CaseSnapshot
from .stretches import gaps as stretch_gaps, stretches

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
    post: Optional[Tuple[int, int, str]] = None              # (first t1, last t2, 'full' | 'convert')
    post_jobs: List[Tuple[int, int, int, str]] = field(default_factory=list)   # (t1, t2, freq, mode)
    ctx: Dict[str, object] = field(default_factory=dict)     # what decide worked out, for report.py

    def add(self, kind, text, topic=None):
        self.items.append(Item(kind, text, topic or TOPIC_OF[kind]))

    @property
    def needs_you(self) -> bool:
        return any(i.kind == 'needs' for i in self.items)


def steps_text(steps: List[int], freq: Optional[int] = None, limit: int = 8) -> str:
    """Steps as stretches of constant spacing, read from the steps themselves
    (stretches.py): '50–500 every 50 (10 steps), 505–5000 every 5 (900 steps)'.
    `freq` is kept for callers and no longer used: a case may change frequency."""
    from .stretches import text
    return text(steps, limit=limit)


def steps_phrase(steps: List[int], freq: Optional[int] = None) -> str:
    """'Step 750' or 'Steps 450–600 (4 steps)': the noun agrees with the count."""
    return f"{'Step' if len(steps) == 1 else 'Steps'} {steps_text(steps, freq)}"


def runs_text(runs) -> str:
    """Run numbers, consecutive ones joined: 1, 3, 5-7 (en dash)."""
    runs, out = sorted(set(runs)), []
    for n in runs:
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return ', '.join(str(a) if a == b else f"{a}–{b}" for a, b in out)


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


def _post_jobs(todo: List[int], freq: int, ascii_steps) -> Tuple[List[Tuple[int, int, int, str]], List[int]]:
    """The `run post` jobs that convert these steps: ([(t1, t2, freq, mode)], steps
    that cannot be posted). One job per stretch of equal spacing, since one
    --freq cannot serve two schedules; steps too few to claim a spacing use
    outFreq and join a neighbouring job when contiguous at that spacing. A job
    must start and end on a multiple of its freq (run post rounds to it)."""
    pieces = []
    for r in stretches(todo):
        if r.solid:
            pieces.append((r.first, r.last, r.step))
        else:
            pieces += [(t, t, freq) for t in sorted({r.first, r.last})]
    jobs: List[List[int]] = []
    for a, b, d in pieces:
        if jobs and jobs[-1][2] == d and a - jobs[-1][1] == d:
            jobs[-1][1] = b
        else:
            jobs.append([a, b, d])
    out, off = [], []
    for a, b, d in jobs:
        steps = list(range(a, b + 1, d))
        if a % d or b % d:
            off += steps
            continue
        out.append((a, b, d, 'convert' if all(t in ascii_steps for t in steps) else 'full'))
    return out, off


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
    rst_remote = {}                              # restart set step -> parts on the remote
    if cloud is not None:
        rst_pat = re.compile(rf'^{re.escape(snap.run_rel)}/{re.escape(snap.problem)}'
                             rf'\.(\d+)_\d+\.rst$')
        for key in cloud:
            m = rst_pat.match(key)
            if m:
                rst_remote[int(m.group(1))] = rst_remote.get(int(m.group(1)), 0) + 1
    plan.ctx['rst_remote'] = rst_remote
    plan.ctx.update(running=running, pending=pending, main_now=main_now, post_now=post_now,
                    last_main=last_main, last_post=last_post, reached=reached,
                    cloud=cloud, remote=conf.remote)

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
    plan.ctx['broken_rule'] = broken_rule
    if broken_rule:
        lacking = sorted({(ext, n) for ext, h in snap.history.items()
                          for n in set(h.cleaned) - set(h.archive)})
        if cloud is None:
            how = (f"restore it with `case download history {name} --archive --from {conf.remote}` "
                   f"if {conf.remote} has it (it could not be listed)")
        else:
            there = [(ext, n) for ext, n in lacking
                     if f"{ext}_files/archive/{p}{n}.{ext}" in cloud]
            if len(there) == len(lacking):
                how = (f"{conf.remote} has it: restore with "
                       f"`case download history {name} --archive --from {conf.remote}`")
            elif there:
                how = (f"{conf.remote} has only some of it ("
                       f"{', '.join(f'{e} run {n}' for e, n in there)}): restore those with "
                       f"`case download history {name} --archive --from {conf.remote}`")
            else:
                how = (f"{conf.remote} has no archive/ copy either, so it cannot be restored "
                       f"from there")
        plan.add('needs', "archive/ is pruned or missing: " + '; '.join(broken_rule) +
                 f". Every case keeps archive/ and cleaned/; {how}. No post decision until "
                 f"then.")

    # history parts the remote holds that this case does not have (here: neither in
    # archive/ nor in cleaned/ under that run number)
    remote_hist = {}
    if cloud is not None:
        hist_pat = re.compile(rf'^(othd|oisd)_files/(archive|cleaned)/{re.escape(p)}(\d+)\.(othd|oisd)$')
        for key in cloud:
            m = hist_pat.match(key)
            if m and m.group(1) == m.group(4):
                remote_hist.setdefault((m.group(1), m.group(2)), set()).add(int(m.group(3)))
    only_remote = {}
    for (ext, kind), runs in remote_hist.items():
        extra = sorted(runs - set(getattr(snap.history[ext], kind)))
        if extra:
            only_remote[(ext, kind)] = extra
    plan.ctx.update(hist_remote=remote_hist, hist_only_remote=only_remote)
    gone_archive = sorted(set(only_remote.get(('othd', 'archive'), []))
                          | set(only_remote.get(('oisd', 'archive'), [])))
    if gone_archive:
        have = sorted(set(snap.history['othd'].archive) | set(snap.history['oisd'].archive))
        plan.add('flag', f"{conf.remote} holds archive run{'s' if len(gone_archive) > 1 else ''} "
                         f"{runs_text(gone_archive)} that this case does not have (archive/ here: "
                         f"{runs_text(have) if have else 'empty'}), so "
                         f"{'they exist' if len(gone_archive) > 1 else 'it exists'} only on "
                         f"{conf.remote}. Bring "
                         f"{'them' if len(gone_archive) > 1 else 'it'} back with "
                         f"`case download history {name} --archive --from {conf.remote}`.")

    # -- history ------------------------------------------------------------------
    organising = False
    if snap.live:
        if main_now:
            plan.add('note', f"Left in {snap.run_rel}/ while main job {main_now[0].jobid} is "
                             f"{main_now[0].state.lower()}; it is archived after the job ends.",
                     'history')
            if running and cloud is not None:
                stale = {k: v for k, v in snap.live_files.items() if cloud.get(k) != v}
                plan.ctx['live_upload'] = stale
                if stale:
                    plan.uploads.update(stale)
                    plan.add('upload', f"A copy of the live {p}.othd and {p}.oisd "
                                       f"({_size_text(sum(stale.values()))}), refreshed each run")
        elif not broken_rule:
            numbers = [n for h in snap.history.values() for n in (*h.archive, *h.cleaned)]
            n = max(numbers, default=0) + 1
            plan.ctx['organise'] = ('update', n)
            plan.add('history', f"Move {snap.run_rel}/{p}.othd and .oisd into archive/ as run "
                                f"{n}, then clean and compile "
                                f"(organise history --update --clean --compile)")
            organising = True
    if not organising and not broken_rule:
        uncleaned = sorted(set(snap.history['othd'].archive) - set(snap.history['othd'].cleaned))
        if uncleaned:
            plan.ctx['organise'] = ('clean', uncleaned)
            plan.add('history', f"Clean and compile archive run(s) "
                                f"{', '.join(map(str, uncleaned))}, not yet in cleaned/ "
                                f"(organise history --clean --compile)")
            organising = True
    if cloud is not None:
        hist = {k: v for k, v in snap.files.items() if k.startswith(('othd_files/', 'oisd_files/'))
                and cloud.get(k) != v}
        plan.ctx['hist_missing'] = hist
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
        lo, hi_run = window
        hi = min(hi_run, snap.max_steps) if snap.max_steps else hi_run
        if running:
            done = [t for t in snap.settled if t <= hi]
            hi = max(done) if done else lo - 1
        if pending and snap.restart_tsid is not None:
            hi = min(hi, snap.restart_tsid)

        # The run's output steps, from what the files show -- .out and ASCII PLTs
        # here, binary PLTs here and on the remote -- not from one outFreq: a run
        # may write every 50 steps and then every 5 (stretches.py).
        remote_plt = set()
        for key in cloud:
            m = re.match(rf'binary/{re.escape(p)}\.(\d+)\.plt$', key)
            if m:
                remote_plt.add(int(m.group(1)))
        seen = set(snap.out) | snap.ascii | set(snap.binary) | remote_plt
        E = sorted(t for t in seen if lo <= t <= hi)
        have = [t for t in E if on_cloud(t) or local_ok(t)]
        covered = have
        missing = [t for t in E if t not in have]
        # steps the stretches say should be there, with no file anywhere
        lost = stretch_gaps(E, lo, hi, f)

        # which run, and what its output steps are
        src = (f"{snap.run_rel}/{p}.othd" if snap.live
               else f"archive/{p}{max(snap.history['othd'].archive)}.othd")
        if running:
            cut = ", up to the last step the running job has finished."
        elif pending and snap.restart_tsid is not None and hi < hi_run:
            cut = f"; it stops there because the queued job restarts from {snap.restart_tsid}."
        else:
            cut = '.'
        if E:
            plan.add('note', f"The newest run is {src} (steps {lo}–{hi_run}). Its output steps: "
                             f"{steps_text(E)}{cut}", 'post')
        plan.ctx.update(window=window, src=src, t1=E[0] if E else lo, t2=E[-1] if E else hi,
                        grid=E, have=have, missing=missing, lost=lost,
                        cut=('running' if running else 'restart' if cut.startswith(';') else None))
        n_cloud = sum(1 for t in E if on_cloud(t))
        n_here = sum(1 for t in E if local_ok(t) and not on_cloud(t))
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
        if lost:
            plan.add('needs', f"{steps_phrase(lost, f)} {'has' if len(lost) == 1 else 'have'} no PLT "
                              f"and no .out anywhere ({conf.remote} or here): lost, or never "
                              f"written. {'It falls' if len(lost) == 1 else 'They fall'} inside "
                              f"the run's regular output steps"
                              + (f" ({steps_text(E)})" if E else '') + ".")
        if not E:
            if not lost:
                plan.add('note', "No post job yet: no step of the run is finished.", 'post')
        elif not missing:
            plan.add('note', f"No post job needed: all {len(E)} output steps have a PLT "
                             f"({where}). Matched by file name and size; the md5 is checked "
                             f"before anything is deleted.", 'post')
        elif missed and not bad_post:
            plan.add('needs', f"Post job {last_post.jobid} ended {last_post.state} after the .out "
                              f"of steps {steps_text(missed)} were written, yet they have no "
                              f"whole PLT here or on the remote. Check its log (run list log) "
                              f"before posting them again.")
        elif bad_post:
            broken = [t for t in E if t in snap.binary and not snap.binary[t].ok]
            detail = f" (broken: {steps_text(broken)})" if broken else ''
            plan.add('needs', f"Post job {bad_post.jobid} ended {bad_post.state}: steps "
                              f"{steps_text(missing)} have no whole PLT{detail}. Post them again "
                              f"by hand once the cause is known.")
        else:
            prefix = E[:len(have)] == have
            if have and not prefix:
                plan.add('needs', f"Holes on the remote: steps {steps_text(missing)} have no PLT, "
                                  f"while later steps have one. Find out why before posting.")
            else:
                todo = [t for t in E if t >= missing[0]]
                no_input = [t for t in todo if t not in snap.settled and t not in snap.ascii]
                if no_input:
                    plan.add('needs', f"{steps_phrase(no_input, f)} {'has' if len(no_input) == 1 else 'have'} "
                                      f"no PLT on the remote and no .out here to make "
                                      f"{'one' if len(no_input) == 1 else 'them'} from.")
                else:
                    jobs, off = _post_jobs(todo, f, snap.ascii)
                    if off:
                        plan.add('needs', f"{steps_phrase(off, f)} {'is' if len(off) == 1 else 'are'} "
                                          f"not on a multiple of the spacing around "
                                          f"{'it' if len(off) == 1 else 'them'}; `run post` only "
                                          f"converts multiples of its --freq. Post "
                                          f"{'it' if len(off) == 1 else 'them'} by hand.")
                    plan.post_jobs = jobs
                    if jobs:
                        plan.post = (jobs[0][0], jobs[-1][1],
                                     'convert' if all(j[3] == 'convert' for j in jobs) else 'full')
                    for n, (a, b, d, mode) in enumerate(jobs):
                        freq_part = f" --freq {d}" if (len(jobs) > 1 or d != f) else ''
                        count = len(range(a, b + 1, d))
                        already = (f"; the {len(have)} before {todo[0]} have one ({where})"
                                   if have and n == 0 else '')
                        plan.add('post', f"Submit `run post {mode} --t1 {a} --t2 {b}{freq_part}`: "
                                         f"{count} output step{'s' if count != 1 else ''} "
                                         f"with no PLT yet{already}")
                    if len(jobs) > 1:
                        plan.add('note', f"The run changed its output frequency, so it takes "
                                         f"{len(jobs)} post jobs (one --freq each). Submit the next "
                                         f"when the previous has ended.", 'post')
        later = [t for t in snap.out if pending and provisional(t)]
        plan.ctx['later'] = sorted(later)
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
        plan.ctx['plt_upload'] = sorted(int(k.split('.')[-2]) for k in plts)
        if plts:
            plan.uploads.update(plts)
            plan.add('upload', f"Binary PLTs, {steps_phrase([int(k.split('.')[1]) for k in plts], f).lower()}: "
                               f"{_size_text(sum(plts.values()))}")
        # Restart sets: the local ones (keep_rst) are insurance against a failed run; the
        # ones uploaded (upload_rst) are to resume the run in the future, so they are the
        # steps on that grid, plus the final set of a finished run. A set a queued
        # restart will compute again, or one still being written, waits.
        sets = [t for t, n in snap.rst.items() if snap.nsg and n == snap.nsg and not provisional(t)
                and not (running and snap.live and t >= snap.live[1])]
        due, final = [], None
        if conf.upload_rst:
            due = sorted(t for t in sets if t % conf.upload_rst == 0)
            if state == 'done' and sets and max(sets) % conf.upload_rst:
                final = max(sets)
                due.append(final)
        todo_rst, why = {}, {}
        for t in due:
            stale = {k: v for k, v in snap.rst_files.get(t, {}).items() if cloud.get(k) != v}
            if stale:
                todo_rst[t] = stale
                total = len(snap.rst_files.get(t, {}))
                absent = sum(1 for k in stale if k not in cloud)
                why[t] = (absent, len(stale) - absent, total)       # not there, differ, of
        plan.ctx.update(rst_due=due, rst_final=final, rst_todo=todo_rst, rst_why=why)
        for t, (absent, differ, total) in sorted(why.items()):
            if differ:
                plan.add('flag', f"Restart set {t}: {differ} of {total} files on {conf.remote} differ "
                                 f"in size from here, so they were probably written by an earlier "
                                 f"run (before a restart computed this step again). Sending the set "
                                 f"replaces them.")
        if todo_rst:
            files = {k: v for stale in todo_rst.values() for k, v in stale.items()}
            plan.uploads.update(files)
            note = f", {'including' if len(todo_rst) > 1 else 'the'} final set of the finished run" \
                if final in todo_rst else ''
            plan.add('upload', f"Restart sets, {steps_phrase(sorted(todo_rst)).lower()}: "
                               f"{len(files)} files, {_size_text(sum(files.values()))}{note}")
        elif not conf.upload_rst and snap.rst:
            plan.add('note', "Restart sets are not uploaded: auto.upload_rst is not set "
                             "(auto init --upload-rst N).", 'upload')
        # a set on the upload grid that exists neither here nor on the remote
        if conf.upload_rst:
            known = sorted(set(snap.rst) | set(rst_remote))
            if len(known) >= 3:
                lost_sets = [g for g in stretch_gaps(known, known[0], known[-1], conf.upload_rst)
                             if g % conf.upload_rst == 0]
                plan.ctx['rst_lost'] = lost_sets
                if lost_sets:
                    plan.add('flag', f"Restart {steps_phrase(lost_sets).lower()} "
                                     f"{'is' if len(lost_sets) == 1 else 'are'} on the upload grid "
                                     f"(every {conf.upload_rst}) but "
                                     f"{'exists' if len(lost_sets) == 1 else 'exist'} neither here "
                                     f"nor on {conf.remote}.")
        inputs = {k: v for k, v in snap.files.items()
                  if not k.startswith(('othd_files/', 'oisd_files/')) and cloud.get(k) != v}
        plan.ctx['inputs_missing'] = inputs
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
        plan.ctx.update(del_ascii=ascii, del_binary=binary, del_out=outs, thin=thin)
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
