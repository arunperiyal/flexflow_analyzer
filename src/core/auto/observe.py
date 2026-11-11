"""
One read-only snapshot of a case: what decide.py needs, and nothing it
changes. Reading is the only thing done here; no file is written.

    snap = observe_case(case_dir, jobs=queue, ended=sacct_jobs, cloud_files=listing)

`jobs`/`ended` are the whole queue and sacct list (read once for the folder);
the case's own are picked by working directory (src/core/slurm.py). A case
whose config cannot be read gets `error` set and nothing else.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .. import slurm
from ..plt_valid import PltCheck, check_plt
from ..settled import out_steps, settled_steps

PROGRAM_FILES = ('domain.yml', '.restarts', '.casestatus.md')
JOB_SCRIPTS = ('preFlex.sh', 'mainFlex.sh', 'postFlex.sh', 'simflow_env.sh')
HISTORY = ('othd', 'oisd')


@dataclass
class History:
    archive: Dict[int, Path] = field(default_factory=dict)    # run number -> part
    cleaned: Dict[int, Path] = field(default_factory=dict)
    compiled: Optional[Path] = None

    @property
    def any(self) -> bool:
        return bool(self.archive or self.cleaned or self.compiled)


@dataclass
class CaseSnapshot:
    name: str
    dir: Path
    error: Optional[str] = None
    problem: str = ''
    nsg: Optional[int] = None
    out_freq: Optional[int] = None
    max_steps: Optional[int] = None
    restart_tsid: Optional[int] = None          # restartTsId when restartFlag is on
    run_rel: str = ''                           # run dir relative to the case (RUN_1)
    jobs: List[slurm.Job] = field(default_factory=list)       # in the queue now
    ended: List[slurm.Job] = field(default_factory=list)      # from sacct, oldest first
    live: Optional[Tuple[int, int]] = None      # first/last tsId of the run dir's .othd
    history: Dict[str, History] = field(default_factory=dict)
    archive_range: Optional[Tuple[int, int]] = None   # newest archive/ .othd part's tsIds
    out: Dict[int, List[Path]] = field(default_factory=dict)
    out_time: Dict[int, float] = field(default_factory=dict)  # step -> newest .out part's mtime
    out_size: Dict[int, int] = field(default_factory=dict)    # step -> bytes of its .out parts
    ascii_size: Dict[int, int] = field(default_factory=dict)  # step -> bytes of its ASCII .plt
    binary_time: Dict[int, float] = field(default_factory=dict)
    log_tails: Dict[str, Optional[List[str]]] = field(default_factory=dict)  # job id -> last lines (None: no file)
    cloud_mtime: Dict[str, float] = field(default_factory=dict)  # remote path -> when written
    main_start: Optional[float] = None          # when the newest main job started (sacct)
    sent_at: Dict[str, float] = field(default_factory=dict)   # remote path -> when auto sent it
    live_time: Optional[float] = None                         # mtime of the run dir's .othd
    post_windows: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # post job id -> steps
    settled: List[int] = field(default_factory=list)
    unsettled: Dict[int, str] = field(default_factory=dict)
    rst: Dict[int, int] = field(default_factory=dict)         # step -> parts
    binary: Dict[int, PltCheck] = field(default_factory=dict)
    ascii: Set[int] = field(default_factory=set)
    run_size: int = 0
    script_names: Dict[str, str] = field(default_factory=dict)   # mainFlex.sh -> its -J
    files: Dict[str, int] = field(default_factory=dict)       # inputs, program files, history
    live_files: Dict[str, int] = field(default_factory=dict)  # the run dir's .othd/.oisd
    rst_files: Dict[int, Dict[str, int]] = field(default_factory=dict)
    cloud: Optional[Dict[str, int]] = None                    # None: not known

    def active(self, kind: str) -> List[slurm.Job]:
        return [j for j in self.jobs if j.kind == kind and j.active]

    def last_ended(self, kind: str) -> Optional[slurm.Job]:
        """The newest job of this kind that has ended (sacct lists queued and
        running ones too)."""
        done = [j for j in self.ended if j.kind == kind and not j.active]
        return done[-1] if done else None

    def sacct_entry(self, jobid: str) -> Optional[slurm.Job]:
        return next((j for j in self.ended if j.jobid == jobid), None)


def tsid_range(path, chunk: int = 1 << 16) -> Optional[Tuple[int, int]]:
    """First and last tsId of an .othd/.oisd, read from its two ends."""
    pat = re.compile(rb'^tsId (\d+)', re.MULTILINE)
    try:
        with open(path, 'rb') as f:
            head = f.read(chunk)
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - chunk))
            tail = f.read()
    except OSError:
        return None
    first = pat.search(head)
    last = pat.findall(tail)
    if not first or not last:
        return None
    return int(first.group(1)), int(last[-1])


def _history(case_dir: Path, ext: str, problem: str) -> History:
    h = History()
    pat = re.compile(rf'^{re.escape(problem)}(\d+)\.{ext}$')
    for kind in ('archive', 'cleaned'):
        folder = case_dir / f'{ext}_files' / kind
        if folder.is_dir():
            for p in folder.iterdir():
                m = pat.match(p.name)
                if m:
                    getattr(h, kind)[int(m.group(1))] = p
    compiled = case_dir / f'{ext}_files' / f'{problem}.{ext}'
    h.compiled = compiled if compiled.exists() else None
    return h


def _script_name(path: Path) -> Optional[str]:
    try:
        for line in path.read_text(errors='replace').splitlines():
            m = re.match(r'#SBATCH\s+(?:-J|--job-name)[\s=]+(\S+)', line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return None


def _mtime(path: Path) -> Optional[float]:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _size(path: Path) -> Optional[int]:
    try:
        return path.stat().st_size
    except OSError:
        return None


LOG_LINES = 15


def _tail(case_dir, jobid, lines: int = LOG_LINES) -> Optional[List[str]]:
    """The last lines of the job's slurm-<id>.out in the case folder; None when there is
    no such file. Reads only the end of the file."""
    path = Path(case_dir) / f"slurm-{jobid}.out"
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 64 * 1024))
            data = f.read()
    except OSError:
        return None
    text = data.decode('utf-8', errors='replace').rstrip('\n')
    return [l.rstrip() for l in text.split('\n')[-lines:]] if text else []


def _parse_time(text) -> Optional[float]:
    """sacct's 2026-11-09T03:31:00 or the ledger's 2026-11-09 03:31:00, as seconds; None
    when it is not a time ('Unknown' for a job that has not started)."""
    import time as _time
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return _time.mktime(_time.strptime(str(text).strip(), fmt))
        except ValueError:
            continue
    return None


def _newest_main_start(ended) -> Optional[float]:
    for job in reversed(ended):
        if job.kind == 'main':
            t = _parse_time(job.start)
            if t is not None:
                return t
    return None


def observe_case(case_dir, jobs: List[slurm.Job], ended: List[slurm.Job],
                 cloud_files: Optional[Dict[str, int]],
                 sent: Optional[Dict[str, str]] = None) -> CaseSnapshot:
    from ..simflow_config import SimflowConfig
    from ..def_config import DefConfig

    case_dir = Path(case_dir)
    snap = CaseSnapshot(name=case_dir.name, dir=case_dir, cloud=cloud_files)
    if not case_dir.is_dir():
        snap.error = "folder not found"
        return snap
    try:
        cfg = SimflowConfig.find(case_dir)
    except Exception as e:
        snap.error = f"simflow.config unreadable: {e}"
        return snap
    if not cfg.problem:
        snap.error = "simflow.config has no `problem`"
        return snap
    snap.problem = p = cfg.problem
    snap.nsg, snap.out_freq = cfg.nsg, cfg.out_freq
    if not snap.out_freq:
        snap.error = "simflow.config has no `outFreq`"
        return snap
    try:
        snap.max_steps = DefConfig.find(case_dir, p).max_time_steps
    except Exception:
        snap.max_steps = None
    if cfg.restart_flag and cfg.restart_tsid is not None:
        snap.restart_tsid = int(cfg.restart_tsid)
    run_dir = cfg.run_dir(case_dir)
    if run_dir is None:
        snap.error = "simflow.config has no run directory (`dir`)"
        return snap
    snap.run_rel = run_dir.relative_to(case_dir).as_posix() if run_dir.is_relative_to(case_dir) \
        else run_dir.name

    snap.jobs = slurm.jobs_for_case(case_dir, jobs)
    snap.ended = slurm.jobs_for_case(case_dir, ended)
    snap.main_start = _newest_main_start(snap.ended)
    snap.cloud_mtime = dict(getattr(cloud_files, 'mtimes', {}) or {})
    for kind in ('main', 'post'):
        job = snap.last_ended(kind)
        if job and job.state.split()[0] not in ('COMPLETED', 'TIMEOUT', 'CANCELLED'):
            snap.log_tails[job.jobid] = _tail(case_dir, job.jobid)
    for rel, when in (sent or {}).items():
        t = _parse_time(when)
        if t is not None:
            snap.sent_at[rel] = t

    # history
    for ext in HISTORY:
        snap.history[ext] = _history(case_dir, ext, p)
    othd = snap.history['othd']
    if othd.archive:
        snap.archive_range = tsid_range(othd.archive[max(othd.archive)])
    live = run_dir / f'{p}.othd'
    if live.exists():
        snap.live = tsid_range(live)
        snap.live_time = _mtime(live)
        for ext in HISTORY:
            f = run_dir / f'{p}.{ext}'
            if f.exists():
                snap.live_files[f"{snap.run_rel}/{f.name}"] = f.stat().st_size

    # run directory: .out, .rst, ASCII PLT, size
    snap.out = out_steps(run_dir, p)
    for step, parts in snap.out.items():
        stats = []
        for x in parts:
            try:
                stats.append(x.stat())
            except OSError:
                pass
        if stats:
            snap.out_time[step] = max(st.st_mtime for st in stats)
            snap.out_size[step] = sum(st.st_size for st in stats)
    running = any(j.state in ('RUNNING', 'COMPLETING', 'CONFIGURING') for j in snap.active('main'))
    solver_at = snap.live[1] if snap.live else None
    snap.settled, snap.unsettled = settled_steps(snap.out, snap.nsg, running=running,
                                                 solver_at=solver_at)
    rst_pat = re.compile(rf'^{re.escape(p)}\.(\d+)_(\d+)\.rst$')
    plt_pat = re.compile(rf'^{re.escape(p)}\.(\d+)\.plt$')
    if run_dir.is_dir():
        for f in run_dir.iterdir():
            size = _size(f) or 0
            snap.run_size += size
            m = rst_pat.match(f.name)
            if m:
                step = int(m.group(1))
                snap.rst[step] = snap.rst.get(step, 0) + 1
                snap.rst_files.setdefault(step, {})[f"{snap.run_rel}/{f.name}"] = size
                continue
            m = plt_pat.match(f.name)
            if m:
                snap.ascii.add(int(m.group(1)))
                snap.ascii_size[int(m.group(1))] = size

    # binary PLTs, each checked from its header
    binary = case_dir / 'binary'
    if binary.is_dir():
        for f in binary.iterdir():
            m = plt_pat.match(f.name)
            if m:
                snap.binary[int(m.group(1))] = check_plt(f)
                snap.binary_time[int(m.group(1))] = _mtime(f) or 0.0

    # the steps each post job was given, from the line postFlex.sh logs:
    # "post job 1225966 started: steps 4050..4550 every 50"
    try:
        log = (case_dir / '.casestatus.md').read_text(errors='replace')
        for m in re.finditer(r'post job (\d+) started: steps (\d+)\.\.(\d+)', log):
            snap.post_windows[m.group(1)] = (int(m.group(2)), int(m.group(3)))
    except OSError:
        pass

    # job scripts' names
    for script in ('mainFlex.sh', 'postFlex.sh'):
        name = _script_name(case_dir / script)
        if name:
            snap.script_names[script] = name

    # files compared with the cloud: history, inputs, program files
    for ext, h in snap.history.items():
        for kind in ('archive', 'cleaned'):
            for part in getattr(h, kind).values():
                snap.files[f"{ext}_files/{kind}/{part.name}"] = part.stat().st_size
        if h.compiled:
            snap.files[f"{ext}_files/{h.compiled.name}"] = h.compiled.stat().st_size
    inputs = [f'{p}.def', 'simflow.config', *JOB_SCRIPTS, *PROGRAM_FILES]
    try:
        from src.commands.case.download_impl.command import def_inputs
        inputs += def_inputs(case_dir / f'{p}.def')
    except Exception:
        pass
    inputs += [f.name for f in case_dir.glob('othd.*.map')]
    for rel in inputs:
        size = _size(case_dir / rel)
        if size is not None:
            snap.files[rel] = size
    return snap
