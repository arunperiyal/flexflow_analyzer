"""
`plot` figures of a --var selection: the columns `data table` would print,
drawn as a time history, a spectrum, or a 2D/3D trajectory.

Every function takes plain arrays -- times and {column label: values} -- so
what is plotted is exactly what `data table` with the same var, node and
window shows.
"""

import numpy as np
import matplotlib.pyplot as plt

PLOT_TYPES = ('time', 'fft', 'traj2d', 'traj3d')


def _legend(ax, legend_style):
    kwargs = {k: legend_style[k] for k in ('loc', 'fontsize', 'frameon')
              if legend_style and k in legend_style}
    ax.legend(**kwargs)


def time_plot(times, values, plot_style=None, title=None):
    """One axes per column, sharing the time axis."""
    labels = list(values)
    fig, axes = plt.subplots(len(labels), 1, sharex=True, squeeze=False,
                             figsize=(10, max(4.0, 2.6 * len(labels))))
    axes = list(axes[:, 0])
    for ax, label in zip(axes, labels):
        ax.plot(times, values[label], **(plot_style or {}))
        ax.set_ylabel(label)
        ax.grid(True, alpha=0.3)
    axes[-1].set_xlabel('Time')
    if title:
        axes[0].set_title(title)
    return fig, axes if len(axes) > 1 else axes[0]


def spectrum(times, signal):
    """(frequencies, one-sided amplitudes) of a signal about its mean, the
    zero frequency left out. The sampling interval is the median step, so a
    restart's repeated or missing step does not set it."""
    dt = float(np.median(np.diff(times)))
    x = np.asarray(signal, dtype=float) - np.mean(signal)
    amp = 2.0 * np.abs(np.fft.rfft(x)) / len(x)
    freq = np.fft.rfftfreq(len(x), dt)
    return freq[1:], amp[1:]


def uneven_sampling(times, tolerance=0.01) -> bool:
    """Whether the steps differ by more than `tolerance` of the median."""
    steps = np.diff(times)
    if len(steps) < 2:
        return False
    dt = np.median(steps)
    return bool(dt > 0 and np.max(np.abs(steps - dt)) > tolerance * dt)


def fft_plot(times, values, plot_style=None, title=None):
    """One axes per column: the amplitude spectrum, the peak in the legend."""
    labels = list(values)
    fig, axes = plt.subplots(len(labels), 1, sharex=True, squeeze=False,
                             figsize=(10, max(4.0, 2.6 * len(labels))))
    axes = list(axes[:, 0])
    peaks = {}
    for ax, label in zip(axes, labels):
        freq, amp = spectrum(times, values[label])
        flat = not len(amp) or np.ptp(values[label]) == 0
        peak = float('nan') if flat else float(freq[np.argmax(amp)])
        peaks[label] = peak
        note = 'flat' if flat else f'peak {peak:.4g} Hz'
        ax.plot(freq, amp, label=f'{label}  ({note})', **(plot_style or {}))
        ax.set_ylabel(f'|{label}|')
        ax.grid(True, alpha=0.3)
        ax.legend()
    axes[-1].set_xlabel('Frequency (Hz)')
    if title:
        axes[0].set_title(title)
    return fig, (axes if len(axes) > 1 else axes[0]), peaks


def trajectory_plot(values, dims, plot_style=None, title=None, legend_style=None):
    """The first `dims` (2 or 3) columns against each other, start and end marked."""
    labels = list(values)[:dims]
    data = [np.asarray(values[l]) for l in labels]
    style = dict(color='blue', linewidth=2, linestyle='-')
    style.update({k: v for k, v in (plot_style or {}).items() if k != 'marker'})
    if dims == 2:
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.plot(*data, alpha=0.8, label='Trajectory', **style)
        ax.plot(data[0][0], data[1][0], 'go', markersize=10, label='Start', zorder=5)
        ax.plot(data[0][-1], data[1][-1], 'ro', markersize=10, label='End', zorder=5)
        ax.grid(True, alpha=0.3)
    else:
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        ax.plot(*data, alpha=0.8, label='Trajectory', **style)
        ax.scatter(*[d[:1] for d in data], color='green', s=60, label='Start')
        ax.scatter(*[d[-1:] for d in data], color='red', s=60, label='End')
        ax.set_zlabel(labels[2])
    ax.set_xlabel(labels[0])
    ax.set_ylabel(labels[1])
    if title:
        ax.set_title(title)
    _legend(ax, legend_style)
    return fig, ax
