"""plot marks the restarts in .restarts with dashed lines, as data lines (so
the terminal plots carry them) that leave the y range alone."""

import types

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pytest

from src.commands.visualization.plot_impl.command import (RESTART_GID, mark_restarts,
                                                          restart_times)
from src.core import restarts

LOG = types.SimpleNamespace(info=lambda m: None)


def write(case, rows):
    restarts.write(case, [dict(after=str(a), first=str(a + 1), time=t, reached=str(a + 50),
                               replaced='50', part='p', previous='q', recorded='x')
                          for a, t in rows])


def test_times_from_dt_or_recorded_time(tmp_path):
    write(tmp_path, [(1000, '5.0e+01'), (2050, '-')])
    assert restart_times(tmp_path, 0.05) == pytest.approx([50.0, 102.5])
    assert restart_times(tmp_path, None) == [50.0]       # no dt: the recorded time
    assert restart_times(tmp_path / 'none', 0.05) == []


def test_marks_only_inside_the_window_and_keeps_ylim(tmp_path):
    write(tmp_path, [(1000, '-'), (2050, '-'), (3050, '-')])
    fig, axes = plt.subplots(2, 1)
    for ax in axes:
        ax.plot([60, 200], [-1, 1])
    before = [ax.get_ylim() for ax in axes]
    assert mark_restarts(list(axes), tmp_path, 0.05, LOG) == 2     # 50 is before t=60
    for ax, ylim in zip(axes, before):
        marks = [l for l in ax.get_lines() if l.get_gid() == RESTART_GID]
        assert sorted(l.get_xdata()[0] for l in marks) == pytest.approx([102.5, 152.5])
        assert all(l.get_linestyle() == '--' and l.get_label().startswith('_') for l in marks)
        assert ax.get_ylim() == ylim


def test_no_file_no_marks(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    assert mark_restarts(ax, tmp_path, 0.05, LOG) == 0
    assert len(ax.get_lines()) == 1
