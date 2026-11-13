"""
Whether the binary PLTs of a case have a checked copy on the remote: the size
and md5 of each file in binary/, read now, against the size and md5 of its
copy on the remote, read now. What matches is written to the ledger as
verified; what does not is taken out of it.

    result = verify_plts(case_dir, problem, cloud, 'cloud', ledger)
    result.ok           # every PLT here is whole and has an md5-checked copy, every
                        # PLT only there is as the ledger recorded it, no step is lost
    result.summary()    # one line

`case check plt --verify` prints it; `auto` reads it before anything that
relies on the remote copy.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .cloud import file_md5
from ..plt_valid import check_plt


@dataclass
class PltVerify:
    total: int = 0
    verified: List[str] = field(default_factory=list)      # same size and md5 on both sides
    size_only: List[str] = field(default_factory=list)     # same size; the remote has no md5sum
    differs: Dict[str, str] = field(default_factory=dict)  # name -> how the copy differs
    not_there: List[str] = field(default_factory=list)     # no copy on the remote
    broken: Dict[str, str] = field(default_factory=dict)   # name -> why the local file is not whole
    rebuild: Dict[str, str] = field(default_factory=dict)  # broken name -> how to make it again
    # on the remote and not in binary/ (deleted here to save space, as a rule):
    kept_there: List[str] = field(default_factory=list)    # ... as the ledger recorded it
    only_there: List[str] = field(default_factory=list)    # ... with no record to compare with
    changed_there: Dict[str, str] = field(default_factory=dict)  # ... not as recorded
    nowhere: List[int] = field(default_factory=list)       # steps of the series in neither place

    @property
    def ok(self) -> bool:
        """Nothing is wrong and there is something: every PLT here is whole and
        md5-checked there, every PLT only there is as recorded or unrecorded,
        and no step of the series is missing from both places."""
        wrong = (self.size_only or self.differs or self.not_there or self.broken
                 or self.changed_there or self.nowhere)
        return not wrong and bool(self.verified or self.kept_there or self.only_there)

    def summary(self) -> str:
        if not self.total and not (self.kept_there or self.only_there or self.changed_there):
            lost = f" ({len(self.nowhere)} steps in neither place)" if self.nowhere else ''
            return f"PLT verify: no binary PLT here or on the remote{lost}"
        parts = [f"{len(self.verified)} of {self.total} verified"] if self.total else \
                ["binary/ is empty here"]
        if self.size_only:
            parts.append(f"{len(self.size_only)} by size only")
        if self.differs:
            parts.append(f"{len(self.differs)} differ")
        if self.not_there:
            parts.append(f"{len(self.not_there)} not on the remote")
        if self.broken:
            parts.append(f"{len(self.broken)} broken here")
        if self.kept_there:
            parts.append(f"{len(self.kept_there)} only on the remote, as recorded")
        if self.only_there:
            parts.append(f"{len(self.only_there)} only on the remote, not recorded")
        if self.changed_there:
            parts.append(f"{len(self.changed_there)} on the remote not as recorded")
        if self.nowhere:
            parts.append(f"{len(self.nowhere)} in neither place")
        return "PLT verify: " + ', '.join(parts)


def _picked(step: int, window: Optional[Tuple], freq: Optional[int]) -> bool:
    if window:
        lo, hi = window
        if (lo is not None and step < lo) or (hi is not None and step > hi):
            return False
    return not freq or step % freq == 0


def how_to_rebuild(case_dir: Path, problem: str, step: int, run_dir: Optional[Path]) -> str:
    """What makes a broken binary PLT again, going back along the chain: its
    ASCII PLT (`run post convert`), else its .out files (`run post full`)."""
    span = f"{case_dir.name} --t1 {step} --t2 {step}"
    if run_dir is not None and run_dir.is_dir():
        ascii_plt = run_dir / f"{problem}.{step}.plt"
        if ascii_plt.is_file() and ascii_plt.stat().st_size > 0:
            return f"run post convert {span}"
        if any(run_dir.glob(f"{problem}.{step}_*.out")):
            return f"run post full {span}"
    return "no ASCII PLT and no .out of this step are left to make it from"


def verify_plts(case_dir, problem: str, cloud, remote_name: str, ledger=None,
                window: Optional[Tuple] = None, freq: Optional[int] = None,
                say: Optional[Callable[[str], None]] = None,
                run_dir: Optional[Path] = None) -> PltVerify:
    """Compare binary/<problem>.<step>.plt with <case>/binary/ on the remote.

    window is (first step, last step), either None for open; freq keeps the
    steps that are multiples of it. `say` gets one line per file as it is
    done. With a ledger, a verified file is recorded and any other file's
    entry is removed, so the ledger never says more than this check found.

    A PLT on the remote with none here (binary/ emptied to save space) is
    compared with what the ledger recorded when it was last verified: its
    size and md5 now against those. With both ends of the window and freq,
    the steps of that series found in neither place are listed.

    run_dir is where the ASCII PLTs and .out files are: a broken binary PLT
    gets the command that makes it again from them (result.rebuild).
    """
    case_dir = Path(case_dir)
    case = case_dir.name
    pattern = re.compile(rf'^{re.escape(problem)}\.(\d+)\.plt$')
    binary = case_dir / 'binary'
    here = {}
    if binary.is_dir():
        for f in binary.iterdir():
            m = pattern.match(f.name)
            if m and f.is_file() and _picked(int(m.group(1)), window, freq):
                here[int(m.group(1))] = f
    listing = cloud.listing(case)
    there = {}
    for rel, size in listing.items():
        head, _, name = rel.rpartition('/')
        m = pattern.match(name)
        if head == 'binary' and m and _picked(int(m.group(1)), window, freq):
            there[int(m.group(1))] = size

    result = PltVerify(total=len(here))
    if window and freq and window[0] is not None and window[1] is not None:
        first = int(-(-window[0] // freq) * freq)
        series = range(first, int(window[1]) + 1, freq)
        result.nowhere = [s for s in series if s and s not in here and s not in there]

    def done(name, rel, word, entry=None):
        if ledger is not None:
            if entry:
                ledger.record(remote_name, case, rel, **entry)
            else:
                ledger.forget(remote_name, case, rel)
        if say:
            say(f"{name}  {word}")

    for step in sorted(here):
        local = here[step]
        name, rel = local.name, f"binary/{local.name}"
        whole = check_plt(local)
        if not whole.ok:
            # the copy on the remote is the same broken file, or an older one:
            # the way back is the chain (ASCII PLT, then .out), not the remote
            result.broken[name] = whole.reason
            result.rebuild[name] = how_to_rebuild(case_dir, problem, step, run_dir)
            done(name, rel, f"broken here: {whole.reason}")
            continue
        if step not in there:
            result.not_there.append(name)
            done(name, rel, "not on the remote")
            continue
        before = local.stat()
        if there[step] != before.st_size:
            result.differs[name] = f"{before.st_size:,} bytes here, {there[step]:,} there"
            done(name, rel, f"differs: {result.differs[name]}")
            continue
        mine = file_md5(local)
        after = local.stat()
        if (after.st_size, after.st_mtime) != (before.st_size, before.st_mtime):
            result.differs[name] = "written again while it was being read"
            done(name, rel, f"differs: {result.differs[name]}")
            continue
        theirs = cloud.md5(case, rel)
        entry = dict(size=before.st_size, md5=mine, mtime=before.st_mtime,
                     path=cloud.path_of(case, rel))
        if theirs is None:
            result.size_only.append(name)
            done(name, rel, "same size (the remote gave no md5)", dict(entry, verified='size'))
        elif theirs != mine:
            result.differs[name] = f"md5 {mine} here, {theirs} there"
            done(name, rel, "differs: same size, another md5")
        else:
            result.verified.append(name)
            done(name, rel, "verified", dict(entry, verified='md5'))

    for step in sorted(set(there) - set(here)):
        name = f"{problem}.{step}.plt"
        rel = f"binary/{name}"
        entry = ledger.get(remote_name, case, rel) if ledger is not None else None
        if not entry or entry.get('verified') != 'md5' or not entry.get('md5'):
            result.only_there.append(name)
            word = "only on the remote, no record of a verified copy"
        elif entry.get('size') != there[step]:
            result.changed_there[name] = (f"{there[step]:,} bytes there, "
                                          f"{entry.get('size'):,} when verified")
            word = f"on the remote not as recorded: {result.changed_there[name]}"
        elif cloud.md5(case, rel) != entry['md5']:
            result.changed_there[name] = "another md5 than when verified"
            word = f"on the remote not as recorded: {result.changed_there[name]}"
        else:
            result.kept_there.append(name)
            word = "only on the remote, as recorded"
        if say:
            say(f"{name}  {word}")
    return result
