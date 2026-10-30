"""
Whether a time history has settled -- `data check steady`.

An oscillating signal is cut at its upward zero crossings (about its mean,
with a hysteresis band of 0.1 std so noise does not add crossings) into whole
cycles, and the cycles into K blocks of equal count; leftover cycles are
dropped from the start, the end being what is judged. Whole cycles keep a
block's mean free of the part-cycle bias equal-length blocks carry (up to
about 0.45 std / cycles per block), which alone could fail the mean test.

Per block: mean m, amplitude a (rms about m) and period T. Steady when

    cycles                               >= min_cycles   (10)
    (max m - min m) / std                <= mean_tol     (0.1)
    (max a - min a) / mean a             <= tol          (0.05)
    (max T - min T) / mean T             <= tol          (0.05)

The mean shift is against the std, not the mean: a cross-flow displacement
has a mean near zero. A signal with fewer than 2 cycles whose std is under
tol of its mean (a mean drag) is flat: K equal blocks, steady when
(max m - min m) / |mean| <= tol. One that fluctuates but has too few cycles
is too short to say.

steady_from() finds the earliest cycle start from which the rest passes:
the transient to discard.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

BLOCKS = 4
TOL = 0.05
MEAN_TOL = 0.1
MIN_CYCLES = 10
HYSTERESIS = 0.1

STEADY, NOT_STEADY, TOO_SHORT = 'steady', 'not steady', 'too short'


@dataclass
class Block:
    start: int              # first sample
    end: int                # one past the last sample
    mean: float
    amplitude: float = float('nan')
    period: float = float('nan')


@dataclass
class Verdict:
    kind: str                           # 'oscillating', 'flat' or 'short'
    verdict: str                        # STEADY, NOT_STEADY or TOO_SHORT
    cycles: int = 0
    period: float = float('nan')
    mean_shift: float = float('nan')    # oscillating: in std; flat: of |mean|
    amp_spread: float = float('nan')
    period_spread: float = float('nan')
    failures: List[str] = field(default_factory=list)
    blocks: List[Block] = field(default_factory=list)

    @property
    def steady(self) -> bool:
        return self.verdict == STEADY


def upward_crossings(t, x):
    """(sample indices, interpolated times) of the upward zero crossings of
    x: a crossing counts only after x has been below -HYSTERESIS * std."""
    h = HYSTERESIS * x.std()
    event = np.where(x < -h, -1, np.where(x >= 0, 1, 0))
    idx = np.flatnonzero(event)
    e = event[idx]
    up = idx[1:][(e[1:] == 1) & (e[:-1] == -1)]
    # x[up - 1] < 0 <= x[up]: between the band and zero, or below it
    x0, x1 = x[up - 1], x[up]
    times = t[up - 1] + (0 - x0) * (t[up] - t[up - 1]) / (x1 - x0)
    return up, times


def _spread(values) -> float:
    values = np.asarray(values, dtype=float)
    mean = values.mean()
    return float((values.max() - values.min()) / mean) if mean else float('inf')


def _direction(first, last, up, down):
    return up if last > first else down


def analyse(t, x, blocks=BLOCKS, tol=TOL, mean_tol=MEAN_TOL,
            min_cycles=MIN_CYCLES) -> Verdict:
    t = np.asarray(t, dtype=float)
    x = np.asarray(x, dtype=float)
    mu, sd = float(x.mean()), float(x.std())
    up, tc = upward_crossings(t, x - mu) if sd > 0 else (np.array([], int), np.array([]))
    cycles = max(len(up) - 1, 0)

    if cycles < 2:
        if sd <= tol * abs(mu):
            return _flat(x, mu, blocks, tol)
        return Verdict('short', TOO_SHORT, cycles=cycles,
                       failures=[f"{cycles} cycle(s); needs {min_cycles}"])
    if cycles < blocks:
        return Verdict('short', TOO_SHORT, cycles=cycles,
                       failures=[f"{cycles} cycle(s); needs {min_cycles}"])

    per = cycles // blocks
    first = cycles - per * blocks            # leftover cycles, dropped from the start
    out = []
    for b in range(blocks):
        c0, c1 = first + b * per, first + (b + 1) * per
        i, j = int(up[c0]), int(up[c1])
        seg = x[i:j]
        m = float(seg.mean())
        out.append(Block(i, j, m, float(np.sqrt(np.mean((seg - m) ** 2))),
                         float((tc[c1] - tc[c0]) / per)))

    means = [b.mean for b in out]
    v = Verdict('oscillating', STEADY, cycles=cycles, blocks=out,
                period=float((tc[-1] - tc[first]) / (per * blocks)),
                mean_shift=(max(means) - min(means)) / sd,
                amp_spread=_spread([b.amplitude for b in out]),
                period_spread=_spread([b.period for b in out]))
    if cycles < min_cycles:
        v.failures.append(f"{cycles} cycle(s); needs {min_cycles}")
    if v.mean_shift > mean_tol:
        v.failures.append(_direction(out[0].mean, out[-1].mean,
                                     'mean drifting up', 'mean drifting down'))
    if v.amp_spread > tol:
        v.failures.append(_direction(out[0].amplitude, out[-1].amplitude,
                                     'amplitude growing', 'amplitude decaying'))
    if v.period_spread > tol:
        v.failures.append(_direction(out[0].period, out[-1].period,
                                     'period lengthening', 'period shortening'))
    if cycles < min_cycles:
        v.verdict = TOO_SHORT
    elif v.failures:
        v.verdict = NOT_STEADY
    return v


def _flat(x, mu, blocks, tol) -> Verdict:
    edges = np.linspace(0, len(x), blocks + 1).astype(int)
    if np.any(np.diff(edges) == 0):
        return Verdict('short', TOO_SHORT, failures=[f"{len(x)} step(s)"])
    out = [Block(int(i), int(j), float(x[i:j].mean())) for i, j in zip(edges, edges[1:])]
    means = [b.mean for b in out]
    shift = (max(means) - min(means)) / abs(mu) if mu else 0.0
    v = Verdict('flat', STEADY, mean_shift=shift, blocks=out)
    if shift > tol:
        v.failures.append(_direction(out[0].mean, out[-1].mean,
                                     'mean drifting up', 'mean drifting down'))
        v.verdict = NOT_STEADY
    return v


def steady_from(t, x, verdict: Optional[Verdict] = None, **limits) -> Optional[int]:
    """The first sample from which the rest of the window is steady, or None.

    Candidates are the upward crossings (the cycle starts) of the whole
    window, or for a flat signal twentieths of it, earliest first, while
    enough is left to judge; each rest is analysed afresh, mean and all. The
    answer is where the first block of the passing rest starts: the leftover
    cycles dropped from its start were not judged.
    """
    t = np.asarray(t, dtype=float)
    x = np.asarray(x, dtype=float)
    verdict = verdict or analyse(t, x, **limits)
    if verdict.steady:
        return verdict.blocks[0].start if verdict.blocks else 0
    if verdict.kind == 'flat':
        starts = [len(x) * k // 20 for k in range(1, 16)]
    else:
        sd = x.std()
        if not sd:
            return None
        up, _ = upward_crossings(t, x - x.mean())
        need = limits.get('min_cycles', MIN_CYCLES)
        starts = [int(i) for i in up[1:len(up) - need]]
    for start in starts:
        rest = analyse(t[start:], x[start:], **limits)
        if rest.steady:
            return start + (rest.blocks[0].start if rest.blocks else 0)
    return None
