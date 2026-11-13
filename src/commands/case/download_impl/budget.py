"""
Will a binary transfer finish before the shell's session timeout?

`set transfer_speed N` (Mbps, default 10) is the planned link speed. Before
`case upload|download plt` sends anything, the selection's size is set
against the time the session has left (rt.time_left(); none in a one-shot
command, so no check there). When it does not fit, the steps are added up
in order from the first and the last step whose files all fit is offered as
--t2, so the upload can be done in pieces that each finish.

Only SAFETY of the time left is planned for: SFTP rarely runs at the link's
rated speed, and a transfer cut off by the timeout is worse than one that
stops a little early.
"""

from dataclasses import dataclass
from typing import Dict, Optional

DEFAULT_MBPS = 10.0
SAFETY = 0.9
# Below this a measured rate says more about per-file overheads than the link
RATE_MIN_BYTES = 50 * 1024 * 1024


def seconds_for(nbytes: int, mbps: float) -> float:
    """Seconds to move `nbytes` at `mbps` megabits per second."""
    return nbytes * 8 / (mbps * 1e6)


def bytes_in(seconds: float, mbps: float) -> int:
    return int(seconds * mbps * 1e6 / 8)


def mbps_of(nbytes: int, seconds: float) -> Optional[float]:
    return nbytes * 8 / seconds / 1e6 if seconds > 0 else None


def duration(seconds: float) -> str:
    """'1 h 31 min', '5 min', '40 s'."""
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    hours, rest = divmod(seconds, 3600)
    minutes = rest // 60 + (1 if rest % 60 >= 30 else 0)
    if hours:
        return f"{hours} h {minutes} min" if minutes else f"{hours} h"
    return f"{minutes} min"


def size(nbytes: int) -> str:
    for unit, scale in (('GB', 1024 ** 3), ('MB', 1024 ** 2), ('KB', 1024)):
        if nbytes >= scale:
            return f"{nbytes / scale:.1f} {unit}"
    return f"{nbytes} B"


@dataclass
class Fit:
    """The steps from the first that fit: up to and including `last`."""
    first: int
    last: int
    files: int
    nbytes: int


def fit(sizes: Dict[str, int], budget_bytes: int, step_of) -> Optional[Fit]:
    """The longest run of whole steps, from the first, whose files add up to
    no more than `budget_bytes`; None when not even the first step fits.
    Files without a step are left out: a window cannot name them."""
    by_step: Dict[int, list] = {}
    for name, nbytes in sizes.items():
        step = step_of(name)
        if step is not None:
            by_step.setdefault(step, []).append(nbytes)
    if not by_step:
        return None
    steps = sorted(by_step)
    total = files = 0
    last = None
    for step in steps:
        step_bytes = sum(by_step[step])
        if total + step_bytes > budget_bytes:
            break
        total += step_bytes
        files += len(by_step[step])
        last = step
    if last is None:
        return None
    return Fit(steps[0], last, files, total)


@dataclass
class Plan:
    """What the time check found for one selection."""
    nbytes: int
    files: int
    seconds: float          # at the planned speed
    left: float             # seconds the session has left
    mbps: float
    cut: Optional[Fit]      # what fits, when the whole does not

    @property
    def fits(self) -> bool:
        return self.seconds <= self.left * SAFETY


def plan(sizes: Dict[str, int], left: Optional[float], mbps: float,
         step_of) -> Optional[Plan]:
    """The plan for sending `sizes` with `left` seconds of session, or None
    when there is no timeout to plan against."""
    if left is None:
        return None
    nbytes = sum(sizes.values())
    p = Plan(nbytes, len(sizes), seconds_for(nbytes, mbps), left, mbps, None)
    if not p.fits:
        p.cut = fit(sizes, bytes_in(left * SAFETY, mbps), step_of)
    return p
