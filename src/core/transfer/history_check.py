"""
The OTHD/OISD history of a case against its copy on the remote, read now: for each
file in archive/, cleaned/ and the compiled file, the size and md5 here and there.

    result = compare_history(case_dir, problem, cloud, parts=('archive', 'cleaned'))
    result.ok          # every file here has an identical copy there
    result.summary()   # one line

`case check history --remote` prints it. It only reads: nothing is sent, nothing
is written to the ledger.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .cloud import file_md5

PARTS = ('archive', 'cleaned', 'compiled')


@dataclass
class HistoryCompare:
    same: List[str] = field(default_factory=list)            # same size and md5 on both sides
    size_only: List[str] = field(default_factory=list)       # same size; the remote gave no md5
    differs: Dict[str, str] = field(default_factory=dict)    # rel -> how the copy differs
    not_there: List[str] = field(default_factory=list)       # here, no copy on the remote
    only_there: List[str] = field(default_factory=list)      # on the remote, not here (pruned?)

    @property
    def total(self) -> int:
        return len(self.same) + len(self.size_only) + len(self.differs) + len(self.not_there)

    @property
    def ok(self) -> bool:
        """Something compared and nothing wrong: every file here has an identical copy."""
        return bool(self.same) and not (self.size_only or self.differs or self.not_there)

    def summary(self) -> str:
        if not self.total and not self.only_there:
            return "History vs remote: no history files here or on the remote"
        parts = [f"{len(self.same)} of {self.total} identical" if self.total
                 else "no history files here"]
        if self.size_only:
            parts.append(f"{len(self.size_only)} by size only")
        if self.differs:
            parts.append(f"{len(self.differs)} differ")
        if self.not_there:
            parts.append(f"{len(self.not_there)} not on the remote")
        if self.only_there:
            parts.append(f"{len(self.only_there)} only on the remote")
        return "History vs remote: " + ", ".join(parts)


def _local_files(case_dir: Path, problem: Optional[str], parts) -> Dict[str, Path]:
    """{rel: path} of the history files of the chosen parts."""
    from .. import history
    found: Dict[str, Path] = {}
    for ext in history.TYPES:
        if 'archive' in parts:
            found.update({p.relative_to(case_dir).as_posix(): p
                          for p in history.archived(case_dir, ext, problem).values()})
        if 'cleaned' in parts:
            found.update({p.relative_to(case_dir).as_posix(): p
                          for p in history.cleaned(case_dir, ext, problem).values()})
        if 'compiled' in parts and problem:
            path = history.compiled_path(case_dir, ext, problem)
            if path.is_file():
                found[path.relative_to(case_dir).as_posix()] = path
    return found


def _remote_names(listing, case_dir: Path, problem: Optional[str], parts) -> List[str]:
    """The rels in the remote listing that belong to the chosen parts."""
    out = []
    for rel in listing:
        head = rel.split('/')
        if len(head) < 2 or head[0] not in ('othd_files', 'oisd_files'):
            continue
        if len(head) == 3 and head[1] in ('archive', 'cleaned') and head[1] in parts:
            out.append(rel)
        elif len(head) == 2 and 'compiled' in parts and problem \
                and head[1] == f"{problem}.{head[0].split('_')[0]}":
            out.append(rel)
    return out


def compare_history(case_dir, problem: Optional[str], cloud, parts=PARTS,
                    say=None) -> HistoryCompare:
    """Compare the chosen parts of the history with the copy on `cloud`."""
    case_dir = Path(case_dir)
    parts = tuple(parts) or PARTS
    result = HistoryCompare()
    local = _local_files(case_dir, problem, parts)
    listing = cloud.listing(case_dir.name)
    for rel, path in sorted(local.items()):
        size = path.stat().st_size
        if rel not in listing:
            result.not_there.append(rel)
            continue
        if listing[rel] != size:
            result.differs[rel] = f"{size} bytes here, {listing[rel]} there"
            continue
        if say:
            say(f"md5 {rel}")
        there = cloud.remote_md5(case_dir.name, rel)
        if there is None:
            result.size_only.append(rel)
        elif there == file_md5(path):
            result.same.append(rel)
        else:
            result.differs[rel] = "same size, different md5"
    result.only_there = sorted(r for r in _remote_names(listing, case_dir, problem, parts)
                               if r not in local)
    return result
