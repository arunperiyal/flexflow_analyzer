"""
What stands in for a file of a case, so that the file may be deleted
(docs/development/PLAN.md, "the deletion chain"):

    .out of a step   <-  its ASCII PLT      (whole, written after every .out part)
    ASCII PLT        <-  its binary PLT     (whole, written after the ASCII PLT)
    binary PLT       <-  its copy on the remote (same size and md5, read now)

A missing link is passed over: with no ASCII PLT the .out stand on the binary
PLT, and with no binary PLT here on its copy on the remote. A link that is
there but not good (cut short, older) does not stop a later one from standing
in: a whole binary PLT written after the .out covers them whatever the ASCII
PLT is like.

"Written after" is what keeps this safe across a restart: the resumed run
writes its steps again, and a PLT older than them was made from the earlier
run's output.

    chain = Chain(case_dir, problem, run_dir, remote=RemoteCopies(...))
    s = chain.for_out(step, out_paths)      # s.ok, s.by ('ascii'|'binary'|'remote'), s.why

Nothing here deletes anything.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple

from .plt_ascii import check_ascii_plt
from .plt_valid import check_plt


@dataclass(frozen=True)
class StandIn:
    ok: bool
    by: str = ''        # which link stands in: 'ascii', 'binary', 'remote'
    why: str = ''       # ok: what stands in; not ok: why nothing does
    found: bool = False     # not ok: whether any later link exists at all


class RemoteCopies:
    """The binary PLTs with a good copy on the remote, found once and on demand.

    `load` returns (good, verified, problem): good is {step: when the local
    file that was sent had been written} for every PLT whose copy on the
    remote is as it should be -- md5-checked against the local file just now,
    or, with no local file, against the ledger's record; verified is the set
    of steps checked against the local file just now; problem is why the
    remote could not be asked, or None.
    """

    def __init__(self, load: Optional[Callable[[], Tuple[Dict[int, float], set, Optional[str]]]],
                 unset: str = "no remote was given (--remote NAME)"):
        self._load, self._unset = load, unset
        self._good: Optional[Dict[int, float]] = None
        self._verified: set = set()
        self.problem: Optional[str] = None

    def _ask(self):
        if self._good is None:
            if self._load is None:
                self._good, self.problem = {}, self._unset
            else:
                self._good, self._verified, self.problem = self._load()

    def written(self, step: int) -> Optional[float]:
        """When the PLT of this step that the remote holds was written here,
        or None when the remote has no good copy of it."""
        self._ask()
        return self._good.get(step)

    def verified_now(self, step: int) -> bool:
        """The local binary PLT of this step matches its copy by md5, read now."""
        self._ask()
        return step in self._verified


def _mtime(path) -> float:
    return os.stat(path).st_mtime


class Chain:
    def __init__(self, case_dir, problem: str, run_dir: Optional[Path],
                 remote: Optional[RemoteCopies] = None):
        self.case_dir, self.problem = Path(case_dir), problem
        self.run_dir = Path(run_dir) if run_dir else None
        self.remote = remote or RemoteCopies(None)
        self._ascii: Dict[int, object] = {}
        self._binary: Dict[int, object] = {}

    # --- the files of a step -------------------------------------------------------

    def ascii_path(self, step: int) -> Optional[Path]:
        return self.run_dir / f"{self.problem}.{step}.plt" if self.run_dir else None

    def binary_path(self, step: int) -> Path:
        return self.case_dir / 'binary' / f"{self.problem}.{step}.plt"

    def ascii_check(self, step: int):
        if step not in self._ascii:
            self._ascii[step] = check_ascii_plt(self.ascii_path(step))
        return self._ascii[step]

    def binary_check(self, step: int):
        if step not in self._binary:
            self._binary[step] = check_plt(self.binary_path(step))
        return self._binary[step]

    # --- what stands in ------------------------------------------------------------

    def _binary_or_remote(self, step: int, newest: Optional[float], than: str, strict: bool,
                          tried: list) -> Optional[StandIn]:
        """The binary PLT or its remote copy standing in for something last
        written at `newest`; None when neither does (why goes in `tried`)."""
        def old(written):
            return newest is not None and (written <= newest if strict else written < newest)

        binary = self.binary_path(step)
        if binary.is_file():
            check = self.binary_check(step)
            if not check.ok:
                tried.append(f"binary/{binary.name} is {check.reason}")
            elif old(_mtime(binary)):
                tried.append(f"binary/{binary.name} is not newer than {than}")
            else:
                return StandIn(True, 'binary', f"binary/{binary.name} is whole and newer")
            return None
        written = self.remote.written(step)
        if written is None:
            if self.remote.problem:
                tried.append(f"no binary PLT here, and the remote was not asked: "
                             f"{self.remote.problem}")
            return None
        if old(written):
            tried.append(f"the copy of {binary.name} on the remote is not newer than {than}")
            return None
        return StandIn(True, 'remote', f"{binary.name} is on the remote, as verified")

    def for_out(self, step: int, out_paths: Iterable) -> StandIn:
        """What stands in for the .out files of a step."""
        try:
            newest = max((_mtime(p) for p in out_paths), default=None)
        except OSError as e:
            return StandIn(False, why=f"cannot read the .out: {e.strerror or e}", found=True)
        tried = []
        ascii_plt = self.ascii_path(step)
        if ascii_plt is not None and ascii_plt.is_file():
            check = self.ascii_check(step)
            if not check.ok:
                tried.append(f"the ASCII {ascii_plt.name} is {check.reason}")
            elif newest is not None and _mtime(ascii_plt) < newest:
                tried.append(f"the ASCII {ascii_plt.name} is older than its .out")
            else:
                return StandIn(True, 'ascii', f"the ASCII {ascii_plt.name} is whole and newer")
        later = self._binary_or_remote(step, newest, "its .out", False, tried)
        if later:
            return later
        found = bool(tried) and not all('was not asked' in t for t in tried)
        return StandIn(False, why='; '.join(tried) or f"no {self.problem}.{step}.plt anywhere",
                       found=found)

    def for_ascii(self, step: int) -> StandIn:
        """What stands in for the ASCII PLT of a step."""
        tried = []
        try:
            newest = _mtime(self.ascii_path(step))
        except OSError as e:
            return StandIn(False, why=f"cannot read it: {e.strerror or e}", found=True)
        later = self._binary_or_remote(step, newest, "the ASCII PLT", True, tried)
        if later:
            return later
        found = bool(tried) and not all('was not asked' in t for t in tried)
        return StandIn(False, why='; '.join(tried) or "no binary PLT here or on the remote",
                       found=found)

    def for_binary(self, step: int) -> StandIn:
        """What stands in for the binary PLT of a step: only its copy on the
        remote, compared with it by md5 just now."""
        if self.remote.verified_now(step):
            return StandIn(True, 'remote', "its copy on the remote has the same md5")
        return StandIn(False, why=self.remote.problem or "no verified copy on the remote",
                       found=self.remote.problem is None)


def remote_copies(case_dir, problem: str, remote_name: Optional[str], window=None,
                  freq: Optional[int] = None, run_dir=None) -> RemoteCopies:
    """RemoteCopies for a case, asking the remote only when something needs it:
    verify_plts (md5 on both sides) over the steps picked, with the ledger of
    the case's folder."""
    case_dir = Path(case_dir)

    def load():
        from .transfer.cloud import CloudError, open_for_folder
        from .transfer.ledger import Ledger
        from .transfer.verify import verify_plts
        try:
            cloud = open_for_folder(case_dir.parent, remote_name)
        except CloudError as e:
            return {}, set(), str(e)
        try:
            ledger = Ledger(case_dir.parent)
            result = verify_plts(case_dir, problem, cloud, remote_name, ledger,
                                 window=window, freq=freq, run_dir=run_dir)
        except CloudError as e:
            return {}, set(), str(e)
        finally:
            cloud.close()
        good, verified = {}, set()
        for name in result.verified + result.kept_there:
            step = int(name.rsplit('.', 2)[-2])
            entry = ledger.get(remote_name, case_dir.name, f"binary/{name}") or {}
            if entry.get('mtime') is not None:
                good[step] = entry['mtime']
        for name in result.verified:
            verified.add(int(name.rsplit('.', 2)[-2]))
        return good, verified, None

    return RemoteCopies(load)
