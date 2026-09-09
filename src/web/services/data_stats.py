"""services/data_stats.py -- reductions over a time-history window, plus the
two "locator" functions that point at *which PLT file* best captures an
extreme or a zero crossing.

Ported near-verbatim from src/commands/data/stats_impl/command.py's FUNCS/
_locate/_zeroloc/plt_rows -- all pure numpy with zero CLI coupling, so this
module is that same math with a public (not underscore-prefixed) surface for
the web API to call directly, kept in one place so the CLI and the web
dashboard can never drift on what "the maximum" or "closest PLT" means.
"""

import numpy as np

# Every function is over the selected window, on the selected node.
FUNCS = {
    'min':   lambda v: float(np.nanmin(v)),
    'max':   lambda v: float(np.nanmax(v)),
    'mean':  lambda v: float(np.nanmean(v)),
    'rms':   lambda v: float(np.sqrt(np.nanmean(v ** 2))),
    'std':   lambda v: float(np.nanstd(v)),
    'range': lambda v: float(np.nanmax(v) - np.nanmin(v)),
}
# maxloc/minloc/zeroloc answer a different question from the rest -- a
# location, not a value -- so they are computed separately, against the
# tsIds, rather than folded into FUNCS.
LOCATORS = ('maxloc', 'minloc', 'zeroloc')


def plt_rows(tsids, freq):
    """Boolean mask of the rows that also have a PLT written for them.

    Taken from the steps the data actually covers rather than from
    arithmetic on freq, so a run that stopped between two outputs never
    offers a file that was never written.
    """
    if not freq:
        return np.zeros(len(tsids), dtype=bool)
    return (np.asarray(tsids) % freq) == 0


def locate(values, tsids, times, freq, direction, runners=3):
    """Where the extreme is, and which PLT file comes closest to it.

    `direction` is "max" or "min", and it means the signed extreme, not the
    largest excursion either way. The PLT to render is the one whose own
    value is most extreme in that direction, not the one nearest the peak in
    time -- the peak almost always falls between two outputs, so the
    question is never "where is the extreme" but "which of the files I have
    comes closest to it", read off the files rather than inferred.

    The runners-up come back too, since a frame is also chosen on what else
    is in it, and the second-best file is often as good a picture.
    """
    high = direction == 'max'
    idx = int(np.nanargmax(values) if high else np.nanargmin(values))
    found = {
        'direction': direction,
        'value': float(values[idx]),
        'tsId': int(tsids[idx]),
        'time': float(times[idx]),
        'plt_tsId': None,
        'plt_value': None,
        'plt_count': 0,
        'plt_ranked': [],
    }
    rows = plt_rows(tsids, freq)
    if not rows.any():
        return found

    plt_ts = np.asarray(tsids)[rows]
    plt_v = np.asarray(values)[rows]
    # Most extreme first; ties to the earlier file so the answer is stable.
    order = sorted(range(len(plt_ts)),
                   key=lambda i: (-plt_v[i] if high else plt_v[i], plt_ts[i]))
    found['plt_count'] = len(plt_ts)
    found['plt_ranked'] = [(int(plt_ts[i]), float(plt_v[i])) for i in order[:1 + runners]]
    found['plt_tsId'] = int(plt_ts[order[0]])
    found['plt_value'] = float(plt_v[order[0]])
    return found


def _crossings(values, direction):
    """Indices i where the signal crosses zero between sample i and i+1.

    Literal zero, not the window's mean: "the displacement is zero" is a
    statement about the undeflected position, and a signal with a steady
    offset crossing its own mean is a different question from crossing the
    axis.
    """
    v = np.asarray(values, dtype=float)
    if len(v) < 2:
        return np.array([], dtype=int)
    if direction == 'descending':
        return np.where((v[:-1] > 0) & (v[1:] <= 0))[0]
    return np.where((v[:-1] < 0) & (v[1:] >= 0))[0]


def zeroloc(values, tsids, times, freq, direction, runners=3):
    """The zero crossing best captured by an existing PLT, and the runners-up.

    Candidates are the PLT steps moving in the right direction, ranked by
    how close to zero they are. No sample lands exactly on zero, so a
    crossing is reported as whichever of the two straddling samples is
    nearer to it.
    """
    v = np.asarray(values, dtype=float)
    found = {
        'direction': direction,
        'count': 0,
        'tsId': None, 'time': None, 'value': None,
        'plt_tsId': None, 'plt_value': None, 'plt_ranked': [], 'plt_offset': None,
    }
    cross = _crossings(v, direction)
    found['count'] = len(cross)
    if not len(cross):
        return found

    # Each crossing stands at whichever of its two samples is nearer zero.
    reps = np.array([i if abs(v[i]) <= abs(v[i + 1]) else i + 1 for i in cross])

    def stand_at(idx):
        found['tsId'] = int(tsids[idx])
        found['time'] = float(times[idx])
        found['value'] = float(v[idx])

    slope = np.gradient(v) if len(v) > 1 else np.zeros_like(v)
    moving = slope < 0 if direction == 'descending' else slope > 0
    candidates = np.where(plt_rows(tsids, freq) & moving)[0]
    if not len(candidates):
        # Nothing on disk to render it with; the last crossing is the most
        # settled one, which is the best that can be said without files.
        stand_at(reps[-1])
        return found

    order = sorted(candidates, key=lambda i: (abs(v[i]), int(tsids[i])))
    found['plt_ranked'] = [(int(tsids[i]), float(v[i])) for i in order[:1 + runners]]
    best = order[0]
    found['plt_tsId'] = int(tsids[best])
    found['plt_value'] = float(v[best])
    # How near zero the best file actually is, as a fraction of the swing --
    # a coarse output frequency can mean the closest descending file is a
    # crest, not a crossing, and this fraction is how that shows up.
    amplitude = float(np.nanmax(np.abs(v))) or 1.0
    found['plt_offset'] = abs(found['plt_value']) / amplitude
    # Report the crossing that file actually sits on.
    stand_at(reps[int(np.argmin(np.abs(tsids[reps] - tsids[best])))])
    return found
