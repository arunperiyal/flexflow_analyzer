"""services/spatial.py — per-node snapshots and time-window statistics.

A spatial plot flips the usual axes: x is position along the probe (the
picker's own projection coordinate, already known to the browser -- this
module has no opinion on it), y is one number per node -- either its value
at a single time, or a statistic reduced over a time window. Reuses the
same cached arrays loader.load() already holds; no new file reads.
"""

import numpy as np

STATS = {
    'rms': lambda v: float(np.sqrt(np.mean(v ** 2))),
    'mean': lambda v: float(np.mean(v)),
    'peak_abs': lambda v: float(np.max(np.abs(v))),
    'peak_to_peak': lambda v: float(np.max(v) - np.min(v)),
}


def nearest_time_index(times, time: float) -> int:
    return int(np.argmin(np.abs(times - time)))


def window_mask(times, t1, t2):
    """Boolean mask selecting times in [t1, t2], each end open (None -> whole range)."""
    lo = times[0] if t1 is None else t1
    hi = times[-1] if t2 is None else t2
    return (times >= lo) & (times <= hi)
