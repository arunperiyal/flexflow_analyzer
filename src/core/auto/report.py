"""
A case's plan as labelled sections, for `auto show`, `auto commands` and
`auto status`. Pure: everything comes from the snapshot, the plan and what
decide recorded in plan.ctx.

    for section in build(snap, plan, conf):
        section.key, section.title, section.subtitle, section.rows, section.actions

Rows are (label, value). An action is a command the user can run as it is
(the case and the remote named, so it is safe whatever `use case:` is), or a
line starting with AUTO_ONLY for what only `auto apply` does safely
(deleting after an md5 check).
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .decide import CasePlan, _size_text, runs_text, steps_phrase, steps_text
from .observe import CaseSnapshot

SECTIONS = ('state', 'needs', 'flags', 'log', 'history', 'plt', 'out', 'rst', 'inputs')
AUTO_ONLY = 'auto apply: '
NOT_YET = ' [not built yet: delete by hand for now]'      # deleting is a later stage of apply


def _predate(steps):
    return 'predates' if len(steps) == 1 else 'predate'


def _by_hand(commands) -> str:
    """The NOT_YET note with the commands that do the same by hand."""
    if not commands:
        return NOT_YET
    return " [not built yet; by hand: " + '; '.join(commands) + "]"


def _runs_apart(steps, others):
    """`steps` split into runs (first, last) so that no step of `others` lies inside a run:
    a range command cannot touch a file that is not in the list."""
    steps, others = sorted(set(steps)), sorted(set(others) - set(steps))
    runs, start, prev = [], None, None
    for t in steps:
        if start is not None and any(prev < o < t for o in others):
            runs.append((start, prev))
            start = None
        if start is None:
            start = t
        prev = t
    if start is not None:
        runs.append((start, prev))
    return runs


@dataclass
class Section:
    key: str
    title: str
    subtitle: str = ''
    rows: List[Tuple[str, str]] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)

    def row(self, label, value):
        self.rows.append((label, value))


def ago(when: Optional[float], now: Optional[float] = None) -> str:
    if not when:
        return '-'
    s = max(0, (now or time.time()) - when)
    for unit, n in (('d', 86400), ('h', 3600), ('min', 60)):
        if s >= n:
            return f"{int(s // n)} {unit} ago"
    return "just now"


def _when(stamp: str) -> str:
    """sacct's 2026-11-08T04:30:38 as 11-08 04:30; '' for Unknown/None."""
    if not stamp or not stamp[:4].isdigit():
        return ''
    return f"{stamp[5:10]} {stamp[11:16]}"


def _runs(numbers) -> str:
    return ', '.join(map(str, sorted(numbers))) if numbers else 'none'


def _present_missing(present, missing, freq) -> str:
    p = f"{steps_text(present, freq)}" if present else 'none'
    m = f"{steps_text(missing, freq)}" if missing else 'none'
    return f"present {p} · missing {m}"


def build(snap: CaseSnapshot, plan: CasePlan, conf, now: Optional[float] = None) -> List[Section]:
    if snap.error:
        s = Section('state', 'State')
        s.row('Skipped', snap.error)
        return [s]
    c, p, f, name = plan.ctx, snap.problem, snap.out_freq, snap.name
    remote = conf.remote
    cloud = c.get('cloud')
    sections = []

    # -- state --------------------------------------------------------------------
    s = Section('state', 'State')
    reached = c.get('reached')
    if reached:
        pct = f" ({100 * reached // snap.max_steps}%)" if snap.max_steps else ''
        s.row('Steps', f"{reached} of {snap.max_steps or '?'}{pct}")
    else:
        s.row('Steps', 'no run yet')
    jobs = []
    for job in list(c.get('main_now', [])) + list(c.get('post_now', [])):
        text = f"{job.kind} {job.jobid} {job.state}"
        entry = snap.sacct_entry(job.jobid)
        if job.state in ('RUNNING', 'COMPLETING') and entry and _when(entry.start):
            text += f", since {_when(entry.start)}"
        if job.kind == 'main' and job.pending and snap.restart_tsid is not None:
            text += f", restarts from {snap.restart_tsid}"
        jobs.append(text)
    s.row('Job', ' · '.join(jobs) if jobs else 'none in the queue')
    last = [f"{j.kind} {j.jobid} {j.state}" + (f", ended {_when(j.end)}" if _when(j.end) else '')
            for j in (c.get('last_main'), c.get('last_post')) if j]
    s.row('Last jobs', ' · '.join(last) if last else 'none in sacct')
    over = (f" (over disk_alert {_size_text(conf.disk_alert)})"
            if conf.disk_alert and snap.run_size > conf.disk_alert else '')
    s.row('Run dir', f"{snap.run_rel}/ {_size_text(snap.run_size)}{over}")
    if c.get('restart_from') is not None:
        s.actions.append(f"run main restart {name} --time {c['restart_from']}")
    sections.append(s)

    for key, kind, title in (('needs', 'needs', 'Needs you'), ('flags', 'flag', 'Worth a look')):
        items = [i.text for i in plan.items if i.kind == kind]
        if items:
            sec = Section(key, title)
            for n, text in enumerate(items, 1):
                sec.row(f"{n}", text)
            sections.append(sec)

    # -- history --------------------------------------------------------------------
    h = snap.history.get('othd')
    for kind in ('main', 'post'):
        job = snap.last_ended(kind)
        if not job or job.jobid not in snap.log_tails or snap.active(kind):
            continue
        tail = snap.log_tails[job.jobid]
        s = Section('log', 'Job log')
        s.row('Job', f"{kind} {job.jobid} {job.state}, ended {_when(job.end) or '?'}")
        if tail is None:
            s.row('File', f"slurm-{job.jobid}.out is not in the case folder")
        elif not tail:
            s.row('File', f"slurm-{job.jobid}.out is empty")
        else:
            s.row('File', f"slurm-{job.jobid}.out, last {len(tail)} lines")
            for line in tail:
                s.row('', line)
        sections.append(s)

    s = Section('history', 'History', '.othd / .oisd')
    if snap.live:
        stays = ' (stays while the main job is queued or running)' if c.get('main_now') else ''
        s.row('Run dir', f"{p}.othd steps {snap.live[0]}–{snap.live[1]}, "
                         f"changed {ago(snap.live_time, now)}{stays}")
    else:
        s.row('Run dir', 'none')
    if h and h.archive:
        newest = max(h.archive)
        rng = (f", steps {snap.archive_range[0]}–{snap.archive_range[1]}"
               if snap.archive_range else '')
        s.row('Archive', f"runs {_runs(h.archive)} · newest {p}{newest}{rng}")
    else:
        s.row('Archive', 'none')
    if h:
        redone = set(c.get('redone_runs') or []) & set(h.archive)
        late = sorted(set(h.archive) - set(h.cleaned) - redone)
        s.row('Cleaned', f"runs {_runs(h.cleaned)}" + (f" · not yet: {_runs(late)}" if late else '')
              + (f" · none for {_runs(redone - set(h.cleaned))} (rewritten by a later run)"
                 if redone - set(h.cleaned) else ''))
        s.row('Compiled', f"{p}.othd" if h.compiled else 'none')
    hist_here = {k: v for k, v in snap.files.items() if k.startswith(('othd_files/', 'oisd_files/'))}
    size = _size_text(sum(hist_here.values()) + sum(snap.live_files.values()))
    if cloud is None:
        s.row('Remote', 'not listed')
    else:
        missing = c.get('hist_missing', {})
        shown = sorted(missing)
        names = (': ' + ', '.join(shown[:4]) + (', ...' if len(shown) > 4 else '')) if shown else ''
        shrink = c.get('hist_shrink') or {}
        s.row('Remote', f"present {len(hist_here) - len(missing) - len(shrink)} · missing "
                        f"{len(missing)} files{names}"
              + (f" · larger there, not sent: {', '.join(sorted(shrink))}" if shrink else ''))
        on_remote = sum(v for k, v in cloud.items() if k.startswith(('othd_files/', 'oisd_files/')))
        size += f" here · {_size_text(on_remote)} on {remote}"
    s.row('Size', size)
    only = c.get('hist_only_remote') or {}
    if only:
        parts = []
        for kind in ('archive', 'cleaned'):
            runs = sorted(set(only.get(('othd', kind), [])) | set(only.get(('oisd', kind), [])))
            if runs:
                parts.append(f"{kind} runs {runs_text(runs)}")
        s.row('Only there', ' · '.join(parts) + f" (on {remote}, not here)")
    if only and (only.get(('othd', 'archive')) or only.get(('oisd', 'archive'))):
        s.actions.append(f"case download history {name} --archive --remote {remote}")
    organise = c.get('organise')
    if organise and organise[0] == 'update':
        s.actions.append(f"case organise history {name} --update --clean --compile")
    elif organise:
        s.actions.append(f"case organise history {name} --clean --compile")
    if cloud is not None and (organise or c.get('hist_missing')):
        s.actions.append(f"case upload history {name} --remote {remote}")
    if c.get('live_upload'):
        s.actions.append(AUTO_ONLY + f"copy the live {p}.othd/.oisd to {remote} "
                                     f"({_size_text(sum(c['live_upload'].values()))})")
    sections.append(s)

    # -- PLT files --------------------------------------------------------------------
    grid = c.get('grid') or []
    lost = c.get('lost') or []
    s = Section('plt', 'PLT files')
    if c.get('src'):
        s.subtitle = f"run {c['src']}: output steps {steps_text(grid) if grid else 'none'}"
    plt_cloud = {int(k.split('.')[-2]): v for k, v in (cloud or {}).items()
                 if k.startswith('binary/') and k.endswith('.plt') and k.split('.')[-2].isdigit()}
    ok_here = sorted(t for t, chk in snap.binary.items() if chk.ok)
    broken = sorted(t for t, chk in snap.binary.items() if not chk.ok)
    if cloud is None:
        s.row('Remote', 'not listed')
    else:
        # everything the remote holds, whatever the frequency; missing is what the run
        # needs that is not there (steps only in binary/ are not uploaded yet)
        gone = [t for t in grid if plt_cloud.get(t, 0) == 0]
        s.row('Remote', f"present {steps_text(sorted(plt_cloud)) if plt_cloud else 'none'}"
                        f" · missing {steps_text(gone) if gone else 'none'}")
        if c.get('stale_plt'):
            s.row('Old run', f"{steps_text(c['stale_plt'])} on {remote} {_predate(c['stale_plt'])} the restart: "
                                 f"posted again and replaced")
    s.row('Binary', f"present {steps_text(ok_here) if ok_here else 'none'}"
                    f" · broken {steps_text(broken) if broken else 'none'}")
    s.row('ASCII', f"present {steps_text(sorted(snap.ascii)) if snap.ascii else 'none'}")
    if c.get('stale_local_plt'):
        s.row('Old here', f"binary {steps_text(c['stale_local_plt'])} here "
                              f"{_predate(c['stale_local_plt'])} the restart: not trusted, not uploaded")
    if lost:
        s.row('Lost', f"{steps_text(lost)}: no PLT and no .out anywhere")
    if c.get('later'):
        one = len(c['later']) == 1
        s.row('Skipped', f"{steps_text(c['later'])}: the queued job restarts from "
                         f"{snap.restart_tsid} and computes {'it' if one else 'them'} again")
    sizes = [f"binary {_size_text(sum(chk.size for chk in snap.binary.values()))} here"]
    if cloud is not None:
        sizes.append(f"{_size_text(sum(plt_cloud.values()))} on {remote}")
    if snap.ascii_size:
        sizes.append(f"ASCII {_size_text(sum(snap.ascii_size.values()))} here")
    s.row('Size', ' · '.join(sizes))
    if snap.binary_time:
        s.row('Newest', f"binary PLT made {ago(max(snap.binary_time.values()), now)}")
    if c.get('post_now'):
        s.actions.append(f"wait: post job {c['post_now'][0].jobid} is "
                         f"{c['post_now'][0].state.lower()}")
    jobs = plan.post_jobs
    for a, b, d, mode in jobs:
        freq_part = f" --freq {d}" if (len(jobs) > 1 or d != f) else ''
        s.actions.append(f"run post {mode} {name} --t1 {a} --t2 {b}{freq_part} --no-remote")
    if len(jobs) > 1:
        s.actions.append("wait: submit each post job after the previous one has ended")
    if c.get('plt_upload'):
        up = c['plt_upload']
        # --missing skips a file the remote holds at the same size, which would leave an
        # earlier run's PLT in place after a restart
        flag = '' if set(up) & set(c.get('stale_plt') or []) else ' --missing'
        s.actions.append(f"case upload binary {name} --t1 {up[0]} --t2 {up[-1]}{flag} "
                         f"--remote {remote}")
    if c.get('del_ascii'):
        s.actions.append(AUTO_ONLY + f"delete ASCII PLTs, {steps_phrase(c['del_ascii']).lower()}, "
                                     f"once the binary copy on {remote} is md5-checked"
                         + _by_hand([f"case organise plt {name} --delete-ascii --t1 {a} --t2 {b}"
                                     for a, b in _runs_apart(c['del_ascii'], [])]))
    if c.get('del_binary'):
        s.actions.append(AUTO_ONLY + f"delete binary PLTs, {steps_phrase(c['del_binary']).lower()}, "
                                     f"once their copy on {remote} is md5-checked"
                         + _by_hand([f"case organise plt {name} --delete-binary --t1 {a} --t2 {b}"
                                     for a, b in _runs_apart(
                                         c['del_binary'], set(snap.binary) - set(c['del_binary']))]))
    sections.append(s)

    # -- OUT files --------------------------------------------------------------------
    s = Section('out', 'OUT files')
    steps = sorted(snap.out)
    s.row('Present', steps_text(steps) if steps else 'none')
    if steps:
        s.row('Finished', f"{len(snap.settled)} of {len(steps)}"
              + (f" · not: {steps_text(sorted(snap.unsettled))} "
                 f"({snap.unsettled[max(snap.unsettled)]})" if snap.unsettled else ''))
        s.row('Size', f"{_size_text(sum(snap.out_size.values()))} here")
        s.row('Newest', f"written {ago(max(snap.out_time.values()), now)}"
              if snap.out_time else '-')
    if c.get('del_out'):
        outs = c['del_out']
        freed = _size_text(sum(snap.out_size.get(t, 0) for t in outs))
        s.actions.append(AUTO_ONLY + f"delete .out of {steps_phrase(outs).lower()} ({freed}) once "
                                     f"{'its' if len(outs) == 1 else 'their'} PLT on {remote} is "
                                     f"md5-checked"
                         + _by_hand([f"case organise output {name} --all-out --keep-freq "
                                     f"{conf.keep_rst} --t1 {a} --t2 {b}"
                                     for a, b in _runs_apart(outs, set(snap.out) - set(outs))]
                                    if conf.keep_rst else []))
    sections.append(s)

    # -- RST files --------------------------------------------------------------------
    grids = [f"keep_rst {conf.keep_rst}" if conf.keep_rst else 'keep_rst not set',
             f"keep_newest_rst {conf.keep_newest_rst}",
             f"upload_rst {conf.upload_rst}" if conf.upload_rst else 'upload_rst not set']
    s = Section('rst', 'RST files', ' · '.join(grids))
    if snap.rst:
        old = set(c.get('stale_rst') or [])
        complete = sorted(t for t, n in snap.rst.items() if snap.nsg and n == snap.nsg
                          and t not in old)
        partial = sorted(t for t, n in snap.rst.items() if t not in complete and t not in old)
        s.row('Present', f"{len(snap.rst)} sets: {steps_text(sorted(snap.rst))}")
        newest_note = ''
        if complete and c.get('pending') and snap.restart_tsid is not None \
                and max(complete) > snap.restart_tsid:
            newest_note = (f" (the queued job restarts from {snap.restart_tsid} and computes "
                           f"it again)")
        s.row('Complete', (f"newest {max(complete)}{newest_note}" if complete else 'none')
              + (f" · incomplete: {steps_text(partial)}" if partial else ''))
        if snap.restart_tsid is not None:
            s.row('Restart', f"restartTsId {snap.restart_tsid} (kept)")
        if old:
            s.row('Old run', f"{steps_text(sorted(old))}: above the solver's step, written "
                                 f"before the restart; not counted, sent or deleted")
        if c.get('rst_newest_kept'):
            sets = c['rst_newest_kept']
            s.row('Also kept', f"{', '.join(map(str, reversed(sets)))} "
                               f"(the newest {conf.keep_newest_rst}, whatever the grid)")
        here = sum(sum(files.values()) for files in snap.rst_files.values())
        thin = c.get('thin') or []
        freed = sum(sum(snap.rst_files.get(t, {}).values()) for t in thin)
        s.row('Size', f"{_size_text(here)} here" + (f" · thinning frees {_size_text(freed)}"
                                                      if thin else ''))
    else:
        s.row('Present', 'none')
    # what the remote holds, what is due on the upload grid, what is nowhere
    if cloud is not None:
        held = c.get('rst_remote') or {}
        whole = sorted(t for t, n in held.items() if snap.nsg and n == snap.nsg)
        part = sorted(t for t in held if t not in whole)
        s.row('Remote', (f"{len(whole)} sets: {steps_text(whole)}" if whole else 'none')
              + (f" · incomplete: {steps_text(part)}" if part else ''))
        there_only = sorted(t for t in held if t not in snap.rst)
        if there_only:
            s.row('Only there', f"{steps_text(there_only)} (on {remote}, not here)")
    if conf.upload_rst:
        due, todo = c.get('rst_due') or [], c.get('rst_todo') or {}
        why = c.get('rst_why') or {}

        def reason(t):
            absent, differ, total = why.get(t, (0, 0, 0))
            if differ:
                return f"{t} (replaces {differ} of {total} files that differ in size)"
            if absent and absent < total:
                return f"{t} ({absent} of {total} files missing there)"
            return f"{t} (not there)"
        if cloud is not None:
            now = ', '.join(reason(t) for t in sorted(todo)) if todo else 'none, up to date'
            s.row('Upload', f"every {conf.upload_rst}"
                            + (f" + the final set {c['rst_final']}" if c.get('rst_final') else '')
                            + f": due {now}")
        if c.get('rst_lost'):
            s.row('Lost', f"{steps_text(c['rst_lost'])}: on the upload grid, but neither here "
                          f"nor on {remote}")
        grid_due = [t for t in sorted(todo) if t != c.get('rst_final')]
        if grid_due:
            s.actions.append(f"case upload rst {name} --t1 {grid_due[0]} --t2 {grid_due[-1]} "
                             f"--freq {conf.upload_rst} --missing --remote {remote}")
        if c.get('rst_final') in todo:
            n = c['rst_final']
            s.actions.append(f"case upload rst {name} --t1 {n} --t2 {n} --missing --remote {remote}")
    thin = c.get('thin') or []
    if snap.rst and thin:                      # after the uploads: deleting follows from them
        s.actions.append(AUTO_ONLY + f"delete .rst of {steps_phrase(thin).lower()}: not "
                                     f"multiples of {conf.keep_rst}"
                         + _by_hand([f"case organise output {name} --keep-out --keep-freq "
                                     f"{conf.keep_rst} --keep-newest {conf.keep_newest_rst} "
                                     f"--t1 {min(thin)} --t2 {max(thin)}"] if conf.keep_rst else []))
    sections.append(s)

    # -- inputs and case files ----------------------------------------------------------
    s = Section('inputs', 'Inputs and case files')
    inputs = {k: v for k, v in snap.files.items() if not k.startswith(('othd_files/', 'oisd_files/'))}
    missing = c.get('inputs_missing', {})
    if cloud is None:
        s.row('Remote', 'not listed')
    else:
        s.row('Remote', f"present {len(inputs) - len(missing)} · missing {len(missing)}"
              + (f": {', '.join(sorted(missing))}" if missing else ''))
    s.row('Size', f"{_size_text(sum(inputs.values()))} here")
    if missing:
        s.actions.append(f"case upload {name} --files '{','.join(sorted(missing))}' --remote {remote}")
    sections.append(s)
    return sections


def commands(sections: List[Section]) -> List[str]:
    """The actions that are commands (not auto-apply-only), in order."""
    return [a for sec in sections for a in sec.actions
            if not a.startswith(AUTO_ONLY) and not a.startswith('wait:')]
