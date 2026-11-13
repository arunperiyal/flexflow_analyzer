"""
Whether the binary PLTs of a case have a checked copy on the remote: the size
and md5 of each file in binary/, read now, against the size and md5 of its
copy on the remote, read now. What matches is written to the ledger as
verified; what does not is taken out of it.

    result = verify_plts(case_dir, problem, cloud, 'cloud', ledger)
    result.ok           # every PLT looked at is whole and has an md5-checked copy
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
    only_there: List[str] = field(default_factory=list)    # on the remote, not in binary/

    @property
    def ok(self) -> bool:
        """Every PLT looked at is whole here and md5-checked there (and there is one)."""
        return self.total > 0 and len(self.verified) == self.total

    def summary(self) -> str:
        if not self.total:
            there = (f" ({len(self.only_there)} only on the remote)" if self.only_there else '')
            return f"PLT verify: no binary PLT in binary/ to verify{there}"
        parts = [f"{len(self.verified)} of {self.total} verified"]
        if self.size_only:
            parts.append(f"{len(self.size_only)} by size only")
        if self.differs:
            parts.append(f"{len(self.differs)} differ")
        if self.not_there:
            parts.append(f"{len(self.not_there)} not on the remote")
        if self.broken:
            parts.append(f"{len(self.broken)} broken here")
        if self.only_there:
            parts.append(f"{len(self.only_there)} only on the remote")
        return "PLT verify: " + ', '.join(parts)


def _picked(step: int, window: Optional[Tuple], freq: Optional[int]) -> bool:
    if window:
        lo, hi = window
        if (lo is not None and step < lo) or (hi is not None and step > hi):
            return False
    return not freq or step % freq == 0


def verify_plts(case_dir, problem: str, cloud, remote_name: str, ledger=None,
                window: Optional[Tuple] = None, freq: Optional[int] = None,
                say: Optional[Callable[[str], None]] = None) -> PltVerify:
    """Compare binary/<problem>.<step>.plt with <case>/binary/ on the remote.

    window is (first step, last step), either None for open; freq keeps the
    steps that are multiples of it. `say` gets one line per file as it is
    done. With a ledger, a verified file is recorded and any other file's
    entry is removed, so the ledger never says more than this check found.
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
    result.only_there = [f"{problem}.{s}.plt" for s in sorted(set(there) - set(here))]

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
            result.broken[name] = whole.reason
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
    return result
