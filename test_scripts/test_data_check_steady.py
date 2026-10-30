"""`data check steady`: whole cycles in K blocks, mean/amplitude/period
compared across them, and the first cycle from which the rest passes."""

import argparse

import numpy as np
import pytest

from src.commands.data.check_impl import steady
from src.commands.data.check_impl.command import execute_check

T = np.linspace(0, 60, 6001)                      # 60 cycles of period 1


def sine(amplitude=1.0, mean=0.0, t=T):
    return mean + amplitude * np.sin(2 * np.pi * t)


def test_crossings_ignore_noise_about_zero():
    rng = np.random.default_rng(0)
    x = sine() + 0.02 * rng.standard_normal(len(T))
    up, times = steady.upward_crossings(T, x)
    assert len(up) == 59            # x starts at 0: the first is not seen
    assert np.allclose(np.diff(times), 1.0, atol=0.02)


def test_a_steady_oscillation():
    v = steady.analyse(T, sine(mean=3.0))
    assert v.verdict == steady.STEADY and v.kind == 'oscillating'
    assert v.cycles == 58 and v.period == pytest.approx(1.0, rel=1e-3)
    assert v.mean_shift < 0.01 and v.amp_spread < 0.01 and v.period_spread < 0.01
    assert steady.steady_from(T, sine(mean=3.0), v) == v.blocks[0].start


def test_growing_amplitude_and_where_it_settles():
    x = (1 - np.exp(-T / 4)) * np.sin(2 * np.pi * T)
    v = steady.analyse(T, x)
    assert v.verdict == steady.NOT_STEADY and 'amplitude growing' in v.failures
    start = steady.steady_from(T, x, v)
    assert start is not None and 5 < T[start] < 30


def test_mean_drift():
    v = steady.analyse(T, sine() + 0.02 * T)
    assert 'mean drifting up' in v.failures


def test_period_change():
    phase = 2 * np.pi * (T + 0.004 * T ** 2)     # frequency rising
    v = steady.analyse(T, np.sin(phase))
    assert 'period shortening' in v.failures


def test_too_few_cycles():
    t = np.linspace(0, 6, 601)
    v = steady.analyse(t, sine(t=t))
    assert v.verdict == steady.TOO_SHORT and v.cycles == 4


def test_flat_signal():
    rng = np.random.default_rng(1)
    x = 1.2 + 1e-4 * rng.standard_normal(200)
    x = np.sort(x)                               # no crossings, tiny drift
    v = steady.analyse(np.arange(200.0), x)
    assert v.kind == 'flat' and v.steady


def test_flat_signal_drifting():
    t = np.arange(200.0)
    v = steady.analyse(t, 1.0 + 0.0005 * t)      # 10% rise, std ~3% of the mean
    assert v.kind == 'flat' and 'mean drifting up' in v.failures


def test_limits_are_taken():
    x = sine() * (1 + 0.03 * np.sin(2 * np.pi * T / 60))
    assert steady.analyse(T, x).steady
    assert not steady.analyse(T, x, tol=0.01).steady


def _othd(tsids, values):
    lines = []
    for i, v in zip(tsids, values):
        lines += [f"tsId {i}", f"time {i * 0.01:.10f}", "othId 0", "othFlag 1",
                  "aleDisp 3 1", f"0.0 {v:.10f} 0.0"]
    return "\n".join(lines) + "\n"


def args(**over):
    base = dict(case=None, verbose=False, help=False, examples=False, othd=False,
                oisd=False, var=None, t1=None, t2=None, node=None, group=None,
                last=None, othid=None, osgid=None, data_check_subcommand='steady',
                blocks=4, tol=0.05, mean_tol=0.1, min_cycles=10)
    base.update(over)
    return argparse.Namespace(**base)


@pytest.fixture
def case(tmp_path):
    d = tmp_path / "CS1"
    (d / "othd_files").mkdir(parents=True)
    tsids = np.arange(1, 6001)
    t = tsids * 0.01
    x = (1 - np.exp(-t / 4)) * np.sin(2 * np.pi * t)
    (d / "othd_files" / "riser1.othd").write_text(_othd(tsids, x))
    (d / "simflow.config").write_text("problem = riser\nnp = 1\n")
    return d


def plain(capsys):
    return ' '.join(capsys.readouterr().out.split())


def test_command_reports_the_verdict_and_start(case, capsys):
    execute_check(args(case=str(case), var=["dy"]))
    out = plain(capsys)
    assert "not steady" in out and "amplitude growing" in out
    start = int(out.split("not steady")[1].split()[0])
    assert 500 < start < 3000


def test_command_with_last(case, capsys):
    execute_check(args(case=str(case), var=["dy"], last=3000, verbose=True))
    out = plain(capsys)
    assert "tsId 3001..6000 (3000 steps)" in out and "steady" in out
    assert "aleDisp_y: blocks" in out


def test_bad_limits(case):
    with pytest.raises(SystemExit):
        execute_check(args(case=str(case), var=["dy"], blocks=1))
    with pytest.raises(SystemExit):
        execute_check(args(case=str(case), var=["dy"], min_cycles=2))
