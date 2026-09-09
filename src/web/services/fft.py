"""services/fft.py — one-sided amplitude spectrum of a uniformly-sampled
real time series.

The mean is removed first so the DC bin doesn't dwarf everything else --
otherwise the one number every signal in this app already has (a nonzero
average displacement, a mean traction) would swamp whatever's actually
periodic in it. The frequency axis comes from the series' own dt: an FFT
assumes even spacing, so a case with adaptive/non-uniform time steps is
refused rather than handed a silently wrong spectrum.
"""

import numpy as np


def compute_fft(times, values):
    """(frequencies, amplitude) for one real time series.

    amplitude is the one-sided spectrum in the signal's own units --
    2/N * |rfft|, halved at DC (and at Nyquist, for an even-length signal)
    since neither has a mirrored negative-frequency bin to combine with, so
    a signal A*sin(2*pi*f0*t) reads back as amplitude A at f0, not A/2.

    Raises ValueError if `times` has fewer than 2 samples, or isn't (closely)
    evenly spaced.
    """
    times = np.asarray(times, dtype=float)
    values = np.asarray(values, dtype=float)
    n = len(times)
    if n < 2:
        raise ValueError('need at least 2 samples for an FFT')

    dt = np.diff(times)
    dt0 = dt[0]
    if dt0 <= 0 or not np.allclose(dt, dt0, rtol=1e-3):
        raise ValueError('time steps are not evenly spaced -- FFT needs uniform sampling')

    centered = values - values.mean()
    spectrum = np.fft.rfft(centered)
    freqs = np.fft.rfftfreq(n, d=dt0)
    amplitude = (2.0 / n) * np.abs(spectrum)
    amplitude[0] /= 2.0
    if n % 2 == 0:
        amplitude[-1] /= 2.0
    return freqs, amplitude
