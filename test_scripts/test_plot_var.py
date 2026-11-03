"""`plot --var NAME` (or `use var:`): the columns `data table` reads for the
same var, node and window, as a time history, spectrum or trajectory."""

import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use('Agg')
import numpy as np
import pytest

from src.commands.data import shared
from src.commands.visualization.plot_impl import command as plot
from src.commands.visualization.plot_impl import series_plot

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples' / 'BR0SG0U1P0'


@pytest.fixture(autouse=True)
def close_figures():
    yield
    import matplotlib.pyplot as plt
    plt.close('all')


class Log:
    def __init__(self):
        self.lines = []

    def info(self, msg):
        self.lines.append(msg)

    warning = success = error = info


def selection(n=400, labels=('aleDisp_x', 'aleDisp_y', 'aleDisp_z')):
    times = np.arange(n) * 0.05
    values = {l: np.sin(2 * np.pi * (0.5 + i) * times) for i, l in enumerate(labels)}
    return shared.Selection('othd', None, 0, 0, list(labels), times,
                            np.arange(1, n + 1), values)


def test_time_plot_one_panel_per_column():
    fig, axes = series_plot.time_plot(*(lambda s: (s.times, s.values))(selection()))
    assert len(axes) == 3
    assert [ax.get_ylabel() for ax in axes] == ['aleDisp_x', 'aleDisp_y', 'aleDisp_z']


def test_spectrum_finds_the_frequency():
    sel = selection()
    freq, amp = series_plot.spectrum(sel.times, sel.values['aleDisp_y'])
    assert freq[np.argmax(amp)] == pytest.approx(1.5, abs=0.06)
    assert amp.max() == pytest.approx(1.0, abs=0.1)


def test_fft_labels_the_peak_and_a_flat_signal():
    sel = selection(labels=('a', 'b'))
    sel.values['b'] = np.zeros_like(sel.times)
    fig, axes, peaks = series_plot.fft_plot(sel.times, sel.values)
    assert peaks['a'] == pytest.approx(0.5, abs=0.06)
    assert np.isnan(peaks['b'])
    assert '(flat)' in axes[1].get_legend().get_texts()[0].get_text()


def test_trajectory_takes_the_first_columns():
    log = Log()
    fig, ax = plot.build_figure('traj2d', selection(), {}, {}, None, log)
    assert (ax.get_xlabel(), ax.get_ylabel()) == ('aleDisp_x', 'aleDisp_y')
    assert any('of aleDisp_x, aleDisp_y, aleDisp_z' in l for l in log.lines)
    fig, ax = plot.build_figure('traj3d', selection(), {}, {}, None, log)
    assert ax.get_zlabel() == 'aleDisp_z'


def test_trajectory_needs_enough_columns():
    with pytest.raises(ValueError, match='needs 3 columns'):
        plot.build_figure('traj3d', selection(labels=('a', 'b')), {}, {}, None, Log())


def test_uneven_sampling():
    assert not series_plot.uneven_sampling(np.arange(10) * 0.1)
    assert series_plot.uneven_sampling(np.array([0, 0.1, 0.2, 0.4, 0.5]))


def test_time_cut():
    sel = plot.time_cut(selection(n=100), 1.0, 2.0)
    assert sel.times.min() >= 1.0 and sel.times.max() <= 2.0
    assert len(sel.values['aleDisp_y']) == len(sel.times) == len(sel.tsids)
    with pytest.raises(ValueError, match='No steps between'):
        plot.time_cut(selection(n=100), 50.0, 60.0)


def test_pendulum_selection(monkeypatch, tmp_path):
    class Reader:
        def __init__(self, files, group=None):
            self.tsIds = [1, 2, 3, 4, 5]

        def get_pendulum_data(self):
            t = np.arange(5) * 0.1
            return {'times': t, 'displacement': t * 2, 'velocity': t * 3,
                    'acceleration': t * 4}

    monkeypatch.setattr('src.core.readers.othd_reader.OTHDReader', Reader)
    monkeypatch.setattr(shared, 'find_files', lambda case, kind: ['x.othd'])
    args = SimpleNamespace(othid=None, t1=2, t2=None, last=2)
    sel = plot.select_pendulum(tmp_path, args, Log(), ['pd', 'pendVel'])
    assert list(sel.values) == ['pendDisp', 'pendVel']
    assert list(sel.tsids) == [4, 5]
    assert np.allclose(sel.values['pendVel'], [0.9, 1.2])


def args(**kw):
    base = dict(input_file=None, case=str(EXAMPLE), var=None, node=None, othid=None,
                osgid=None, group=None, othd=False, oisd=False, t1=None, t2=None,
                last=None, start_time=None, end_time=None, plot_type='time',
                plot_style=None, title=None, xlabel=None, ylabel=None, legend=None,
                legend_style=None, fontsize=None, fontname=None, output=None,
                restart=False, gnu=False, no_display=True, verbose=False)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.skipif(not (EXAMPLE / 'othd_files').is_dir(), reason='example case missing')
@pytest.mark.parametrize('var, plot_type', [(['dy'], 'time'), (['d'], 'fft'),
                                            (['dx,dy'], 'traj2d'), (['tty'], 'time')])
def test_plots_the_example_case(tmp_path, var, plot_type):
    out = tmp_path / 'p.png'
    plot.execute_plot(args(var=var, plot_type=plot_type, node=10, last=500, output=str(out)))
    assert out.stat().st_size > 10_000


def test_no_var_is_an_error(capsys):
    with pytest.raises(SystemExit):
        plot.execute_plot(args())
    assert 'use var:dy' in capsys.readouterr().err


def test_pendulum_and_other_variables_do_not_mix(capsys):
    with pytest.raises(SystemExit):
        plot.execute_plot(args(var=['pd,dy']))
    out = capsys.readouterr()
    assert 'plot them apart from dy' in out.out + out.err
