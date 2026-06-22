"""Helpers to locate PLT files / zones within a case (shared by field subcommands)."""

import re
from pathlib import Path


def problem_name(case_dir):
    try:
        from ...core.simflow_config import SimflowConfig
        return SimflowConfig.find(case_dir).problem
    except Exception:
        return None


def _step(path):
    m = re.search(r"\.(\d+)\.plt$", path.name)
    return int(m.group(1)) if m else -1


def find_plt(binary_dir, problem, timestep=None):
    """Return the PLT file for `timestep` (or the latest if None), else None."""
    binary_dir = Path(binary_dir)
    plt_files = sorted(binary_dir.glob("*.plt"))
    if not plt_files:
        return None
    if timestep is not None:
        if problem:
            cand = binary_dir / f"{problem}.{timestep}.plt"
            if cand.exists():
                return cand
        for f in plt_files:
            if _step(f) == timestep:
                return f
        return None
    return max(plt_files, key=_step)


def zone_index(plt, zone_name):
    """Resolve a zone name (case-insensitive) to its index, or None."""
    for i, z in enumerate(plt.zones):
        if z["name"].lower() == zone_name.lower():
            return i
    return None


def list_steps(binary_dir, problem=None):
    """Return the sorted list of timestep numbers of the PLT files present."""
    binary_dir = Path(binary_dir)
    steps = []
    for f in binary_dir.glob("*.plt"):
        if problem and not f.name.startswith(problem + "."):
            continue
        s = _step(f)
        if s >= 0:
            steps.append(s)
    return sorted(set(steps))
