"""
Where a case keeps its OTHD/OISD history (`case organise history`).

    othd_files/archive/riserN.othd   one per job, as the solver wrote it: moved
                                     here by mainFlex.sh or `history --update`
    othd_files/cleaned/riserN.othd   run N's steps that no later run redid
                                     (`history --clean`)
    othd_files/riser.othd            cleaned/ joined into one file (`--compile`)

and the same under oisd_files/. N numbers the jobs in the order they ran, so
"the later run wins" is the later N; one N is the same run in archive/ and
cleaned/. `--prune` deletes archive/ once cleaned/ checks out, so cleaned/
always holds the whole history and archive/ only what is not yet pruned.

Before this, the parts sat directly in othd_files/ (riserN.othd), and the
compiled file in othd_files/compiled/. The flat parts are still read until a
`history` step moves them into archive/; compiled/ is not read.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional

TYPES = ('othd', 'oisd')


def type_dir(case_dir, ext: str) -> Path:
    return Path(case_dir) / f'{ext}_files'


def archive_dir(case_dir, ext: str) -> Path:
    return type_dir(case_dir, ext) / 'archive'


def cleaned_dir(case_dir, ext: str) -> Path:
    return type_dir(case_dir, ext) / 'cleaned'


def compiled_path(case_dir, ext: str, problem: str) -> Path:
    return type_dir(case_dir, ext) / f'{problem}.{ext}'


def problem_of(case_dir) -> Optional[str]:
    """`problem` from simflow.config, or None."""
    from .simflow_config import SimflowConfig
    config = Path(case_dir) / 'simflow.config'
    return SimflowConfig(config).problem if config.exists() else None


def run_pattern(ext: str, problem: Optional[str]):
    """{problem}N.{ext}, with N as group 1 (any stem without a problem)."""
    stem = re.escape(problem) if problem else r'.*?'
    return re.compile(rf'^{stem}(\d+)\.{ext}$')


def numbered(directory: Path, ext: str, problem: Optional[str]) -> Dict[int, Path]:
    """{N: path} of the {problem}N.{ext} files in `directory` (any stem without a problem)."""
    if not directory.is_dir():
        return {}
    pattern = run_pattern(ext, problem)
    found = {}
    for path in directory.iterdir():
        match = pattern.match(path.name)
        if match and path.is_file():
            found[int(match.group(1))] = path
    return dict(sorted(found.items()))


def archived(case_dir, ext: str, problem: Optional[str]) -> Dict[int, Path]:
    return numbered(archive_dir(case_dir, ext), ext, problem)


def cleaned(case_dir, ext: str, problem: Optional[str]) -> Dict[int, Path]:
    return numbered(cleaned_dir(case_dir, ext), ext, problem)


def flat(case_dir, ext: str, problem: Optional[str]) -> Dict[int, Path]:
    """Parts in the old layout, directly in {ext}_files/."""
    return numbered(type_dir(case_dir, ext), ext, problem)


def next_number(case_dir, ext: str, problem: Optional[str]) -> int:
    """The number the next job's file takes: one past every run already kept."""
    taken = [*archived(case_dir, ext, problem), *cleaned(case_dir, ext, problem),
             *flat(case_dir, ext, problem)]
    return max(taken, default=0) + 1


def runs(case_dir, ext: str, problem: Optional[str]) -> Dict[int, Path]:
    """
    {N: file} holding each run: the archived part, or the cleaned one once
    the part is pruned. Every run is there, so read in order with the later
    one winning, these give the whole history.
    """
    found = dict(cleaned(case_dir, ext, problem))
    found.update(archived(case_dir, ext, problem))
    return dict(sorted(found.items()))


def _newest(paths) -> float:
    return max((os.stat(p).st_mtime for p in paths if os.path.exists(p)), default=0.0)


def compiled_is_fresh(case_dir, ext: str, problem: Optional[str]) -> bool:
    """
    Whether the compiled file is newer than everything it could be missing.
    A file moved into archive/ keeps its own mtime, so the directories count
    too: adding, replacing or removing a file there changes theirs.
    """
    if not problem:
        return False
    out = compiled_path(case_dir, ext, problem)
    if not out.is_file() or flat(case_dir, ext, problem):
        return False
    watched = [archive_dir(case_dir, ext), cleaned_dir(case_dir, ext),
               *runs(case_dir, ext, problem).values()]
    return out.stat().st_mtime >= _newest(watched)


def read_files(case_dir, ext: str, problem: Optional[str] = None) -> List[Path]:
    """
    The files a reader should take for the case's whole {ext} history, in
    order (a later file wins a step both have): the compiled file while it is
    up to date, else every run from archive/ or cleaned/, then any parts in
    the old flat layout — next to an archive/ those come from a job script
    older than it, so they are the newest runs.
    """
    if problem is None:
        problem = problem_of(case_dir)
    if compiled_is_fresh(case_dir, ext, problem):
        return [compiled_path(case_dir, ext, problem)]
    files = list(runs(case_dir, ext, problem).values()) + list(flat(case_dir, ext, problem).values())
    if not files and problem and compiled_path(case_dir, ext, problem).is_file():
        return [compiled_path(case_dir, ext, problem)]
    return files
