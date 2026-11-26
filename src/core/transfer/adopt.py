"""
Record the binary PLTs that are only on the remote and have no ledger entry,
without bringing them back.

A PLT that got to the remote by hand (not by `case upload`) has no record, so
`case organise out` cannot count it in place of the .out files it came from.
Downloading 200 to 400 MB per step to check it would defeat the purpose, so
this judges the copy where it lies:

  * whole: the header and the zone preambles are read over SFTP (a few KB) and
    must give exactly the size the remote lists (core/plt_valid.py)
  * newer than the .out of that step left here (the remote's write time), so a
    restart's new .out is not deleted on an earlier run's PLT; a step with no
    .out left has nothing to be older than
  * its md5, computed on the remote (md5sum), so a later change is seen

What is written to the ledger is marked `adopted`. It does not prove the copy
holds the same data as the local file it came from: there is none to compare
with. verify_plts reads it back like a verified record.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from ..plt_valid import check_plt_open
from .verify import _picked


@dataclass
class Adoption:
    adopted: List[str] = field(default_factory=list)
    refused: Dict[str, str] = field(default_factory=dict)    # name -> why
    recorded: List[str] = field(default_factory=list)        # already in the ledger, left alone
    here: List[str] = field(default_factory=list)            # in binary/ too: verify them instead

    @property
    def ok(self) -> bool:
        return not self.refused


def _newest_out(run_dir: Optional[Path], problem: str, step: int) -> Optional[float]:
    if not run_dir or not Path(run_dir).is_dir():
        return None
    newest = None
    for f in Path(run_dir).glob(f"{problem}.{step}_*.out"):
        try:
            t = f.stat().st_mtime
        except OSError:
            continue
        newest = t if newest is None or t > newest else newest
    return newest


def adopt_plts(case_dir, problem: str, cloud, remote_name: str, ledger,
               window: Optional[Tuple] = None, freq: Optional[int] = None,
               run_dir: Optional[Path] = None,
               say: Optional[Callable[[str], None]] = None) -> Adoption:
    case_dir = Path(case_dir)
    case = case_dir.name
    pattern = re.compile(rf'^{re.escape(problem)}\.(\d+)\.plt$')
    listing = cloud.listing(case)
    result = Adoption()
    for rel in sorted(listing, key=lambda r: (len(r), r)):
        head, _, name = rel.rpartition('/')
        m = pattern.match(name)
        if head != 'binary' or not m or not _picked(int(m.group(1)), window, freq):
            continue
        step = int(m.group(1))
        if (case_dir / rel).is_file():
            result.here.append(name)
            continue
        entry = ledger.get(remote_name, case, rel)
        if entry and entry.get('verified') in ('md5', 'adopted') and entry.get('md5'):
            result.recorded.append(name)
            continue

        def refuse(why):
            result.refused[name] = why
            if say:
                say(f"{name}  not adopted: {why}")

        size, written = listing[rel], listing.mtimes.get(rel)
        check = check_plt_open(name, size, cloud.opener(case, rel))
        if not check.ok:
            refuse(f"not whole on the remote: {check.reason}")
            continue
        if written is None:
            refuse("the remote gives no write time, so it cannot be compared with the .out")
            continue
        out = _newest_out(run_dir, problem, step)
        if out is not None and written <= out:
            refuse("written on the remote at or before its .out here (a restart may have "
                   "written the .out again): post this step again")
            continue
        md5 = cloud.remote_md5(case, rel)
        if not md5:
            refuse("the remote has no md5sum, so a later change could not be seen")
            continue
        ledger.record(remote_name, case, rel, size=size, md5=md5, verified='adopted',
                      mtime=written, path=cloud.path_of(case, rel))
        result.adopted.append(name)
        if say:
            say(f"{name}  adopted")
    return result
