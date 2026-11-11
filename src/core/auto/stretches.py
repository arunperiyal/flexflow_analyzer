"""
Output steps as stretches of constant spacing.

A run need not write output at one frequency: every 50 steps up to 500, then
every 5 up to 5000. outFreq in simflow.config only says what the latest run
was asked for, so what a case wrote is read from the steps found (PLTs on the
remote and here, .out, ASCII .plt):

    stretches([50, 100, ..., 500, 505, 510, ..., 5000])
        -> [Stretch(50, 500, 50, 10), Stretch(505, 5000, 5, 900)]

A stretch needs at least SOLID (3) steps; fewer are listed one by one, since
two steps say nothing about a schedule. A change of spacing is not a hole. A
step missing inside a stretch is:

    gaps([50, 100, 200, 250], lo=1, hi=250, freq=50)  ->  [150]

`freq` (outFreq) is used only where the files give no spacing: before the
first step found, after the last one, between two single steps.
"""

from dataclasses import dataclass
from typing import Iterable, List, Optional


SOLID = 3            # steps it takes for equal spacing to mean a schedule, not a coincidence


@dataclass(frozen=True)
class Stretch:
    first: int
    last: int
    step: Optional[int]         # None for a single step
    count: int

    @property
    def solid(self) -> bool:
        """Enough steps for the spacing to be believed."""
        return self.count >= SOLID


def stretches(steps: Iterable[int]) -> List[Stretch]:
    """Maximal runs of equally spaced steps, in order. A step that fits no run
    is a stretch of one."""
    s = sorted(set(steps))
    out: List[Stretch] = []
    i, n = 0, len(s)
    while i < n:
        if i == n - 1:
            out.append(Stretch(s[i], s[i], None, 1))
            break
        d = s[i + 1] - s[i]
        j = i + 1
        while j + 1 < n and s[j + 1] - s[j] == d:
            j += 1
        out.append(Stretch(s[i], s[j], d, j - i + 1))
        i = j + 1
    return out


def text(steps: Iterable[int], limit: int = 6) -> str:
    """'50–500 every 50 (10 steps), 505–5000 every 5 (900 steps)'. Steps that
    make no stretch of SOLID or more are listed one by one. Past `limit`
    parts the middle is elided."""
    parts: List[str] = []
    for r in stretches(steps):
        if r.solid:
            parts.append(f"{r.first}–{r.last} every {r.step} ({r.count} steps)")
        elif r.count == 1:
            parts.append(str(r.first))
        else:
            parts += [str(r.first), str(r.last)]
    if len(parts) > limit:
        parts = parts[:limit // 2] + [f"… {len(parts) - limit} more …"] + parts[-(limit // 2):]
    return ', '.join(parts)


def _effective(runs: List[Stretch], freq: int) -> List[int]:
    """The spacing to expect around each run: its own when it is solid, else the
    nearest solid stretch's (the finer one when both sides are equally near),
    else outFreq. A short run is a piece of whatever schedule it sits in."""
    solid = [i for i, r in enumerate(runs) if r.solid]
    out = []
    for i, r in enumerate(runs):
        if r.solid:
            out.append(r.step)
            continue
        left = next((j for j in reversed(solid) if j < i), None)
        right = next((j for j in solid if j > i), None)
        near = [runs[j].step for j in (left, right) if j is not None]
        if left is not None and right is not None:
            dl, dr = i - left, right - i
            near = [runs[left].step] if dl < dr else [runs[right].step] if dr < dl \
                else [runs[left].step, runs[right].step]
        out.append(min(near) if near else freq)
    return out


def gaps(steps: Iterable[int], lo: int, hi: int, freq: int) -> List[int]:
    """Steps of lo..hi that the files show should exist but are not among
    `steps`: before the first one, between stretches, after the last one.

    Inside a stretch the spacing is the stretch's own; a run too short to claim
    one takes the nearest stretch's. Between two stretches of different
    spacing nothing is a gap while they meet (the change of frequency); a wider
    space is, counted at the finer spacing. With no stretch to go by (no steps,
    a few odd ones) outFreq is used.
    """
    s = sorted(set(steps))
    if not freq or hi < lo:
        return []
    if not s:
        first = -(-lo // freq) * freq
        return list(range(first, hi // freq * freq + 1, freq))
    runs = stretches(s)
    eff = _effective(runs, freq)
    out: List[int] = []
    first = -(-lo // eff[0]) * eff[0]
    if s[0] > first:
        out += range(first, s[0], eff[0])
    for i in range(len(runs) - 1):
        a, b = runs[i], runs[i + 1]
        known = [eff[i], eff[i + 1]]
        if b.first - a.last > max(known):
            m = min(known)
            out += range(a.last + m, b.first, m)
    last = hi // eff[-1] * eff[-1]
    if last > s[-1]:
        out += range(s[-1] + eff[-1], last + 1, eff[-1])
    return sorted(set(out))
