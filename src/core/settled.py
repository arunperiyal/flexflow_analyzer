"""
Which steps' .out files are finished, so a post job may read them.

A step T is written as nsg files <problem>.T_<k>.out, k = 0..nsg-1. It is
*settled* when

- all nsg parts are there and none is empty, and
- if the case is running: the solver has moved past it (the last tsId in
  the live .othd is beyond T) and no part has changed for `quiet_secs`
  (default 10 min). The last tsId itself is the step being computed, so it
  is never settled while the run goes on.

A case that is not running has nothing writing its .out, so only the first
rule applies. When nsg is unknown no step is settled: the count of parts is
the only way to tell a complete step from one cut short.

    steps = out_steps(run_dir, 'riser')
    ok, why_not = settled_steps(steps, nsg=120, running=True, solver_at=4571)
"""

import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

QUIET_SECS = 600


def out_steps(run_dir, problem: str) -> Dict[int, List[Path]]:
    """{step: [its .out parts]} in run_dir; files not named <problem>.<T>_<k>.out
    (riser.dbg.out) are left out."""
    pattern = re.compile(rf'^{re.escape(problem)}\.(\d+)_(\d+)\.out$')
    steps: Dict[int, List[Path]] = {}
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        return steps
    for path in run_dir.iterdir():
        m = pattern.match(path.name)
        if m:
            steps.setdefault(int(m.group(1)), []).append(path)
    return steps


def settled_steps(steps: Dict[int, List[Path]], nsg: Optional[int], running: bool,
                  solver_at: Optional[int] = None, quiet_secs: float = QUIET_SECS,
                  now: Optional[float] = None) -> Tuple[List[int], Dict[int, str]]:
    """(settled steps, {step: why not}) for the steps in `steps`.

    solver_at is the last tsId of the live .othd; a running case with no
    solver_at has no settled step (it cannot be told which step is being
    computed).
    """
    now = time.time() if now is None else now
    settled: List[int] = []
    why_not: Dict[int, str] = {}
    for step in sorted(steps):
        parts = steps[step]
        if not nsg:
            why_not[step] = "nsg unknown, so a complete step cannot be told apart"
            continue
        if len(parts) != nsg:
            why_not[step] = f"{len(parts)} of {nsg} .out parts"
            continue
        try:
            stats = [p.stat() for p in parts]
        except OSError as e:
            why_not[step] = f"cannot read a part: {e.strerror or e}"
            continue
        empty = sum(1 for st in stats if st.st_size == 0)
        if empty:
            why_not[step] = f"{empty} empty .out part(s)"
            continue
        if running:
            if solver_at is None:
                why_not[step] = "running, and the step being computed is unknown"
                continue
            if solver_at <= step:
                why_not[step] = f"the solver is at {solver_at}, not past it yet"
                continue
            newest = max(st.st_mtime for st in stats)
            if now - newest < quiet_secs:
                why_not[step] = f"a part changed {now - newest:.0f} s ago"
                continue
        settled.append(step)
    return settled, why_not
