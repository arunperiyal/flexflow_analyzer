"""src/core/plt_valid.py (is a binary PLT whole?) and src/core/settled.py
(which steps' .out a post job may read)."""

import os
from pathlib import Path

import pytest

from plt_files import plt_bytes, write_plt
from src.core.plt_valid import check_plt, expected_size, plt_covers
from src.core.settled import out_steps, settled_steps

REAL = Path(__file__).resolve().parent.parent / 'examples' / 'BR0SG0U1P0' / 'binary' / 'riser.100.plt'


# --- plt_valid ---------------------------------------------------------------

def test_whole_file(tmp_path):
    check = check_plt(write_plt(tmp_path / 'a.plt'))
    assert check.ok and check.reason == '' and check.size == check.expected == len(plt_bytes())


@pytest.mark.parametrize('cut, reason', [
    (0, 'empty'),
    (5, 'not a binary PLT'),
    (40, 'header cut short'),
    (-4, 'cut short: '),
])
def test_cut_short(tmp_path, cut, reason):
    data = plt_bytes()
    path = tmp_path / 'b.plt'
    path.write_bytes(data[:cut] if cut >= 0 else data[:len(data) + cut])
    check = check_plt(path)
    assert not check.ok and check.reason.startswith(reason)


def test_too_long(tmp_path):
    path = tmp_path / 'c.plt'
    path.write_bytes(plt_bytes() + b'\0' * 12)
    assert check_plt(path).reason == '12 bytes past the end its header gives'


def test_missing_file(tmp_path):
    assert check_plt(tmp_path / 'none.plt').reason.startswith('cannot read')


@pytest.mark.skipif(not REAL.exists(), reason='no real PLT in examples/')
def test_real_flexflow_plt_is_whole():
    assert expected_size(REAL) == REAL.stat().st_size
    assert check_plt(REAL).ok


def test_plt_covers_needs_a_newer_whole_plt(tmp_path):
    outs = [tmp_path / f'riser.100_{k}.out' for k in range(2)]
    for p in outs:
        p.write_text('x')
    plt = write_plt(tmp_path / 'riser.100.plt')
    assert plt_covers(plt, outs) is None
    old = outs[0].stat().st_mtime - 100
    os.utime(plt, (old, old))
    assert plt_covers(plt, outs).startswith('older than its .out')
    write_plt(plt, cut=50)
    assert plt_covers(plt, outs) == 'header cut short or unreadable'


# --- settled -----------------------------------------------------------------

NSG = 3


@pytest.fixture
def run(tmp_path):
    run = tmp_path / 'RUN_1'
    run.mkdir()
    for step in (4450, 4500, 4550):
        for k in range(NSG):
            (run / f'riser.{step}_{k}.out').write_text('x')
    (run / 'riser.4600_0.out').write_text('x')            # being written: 1 of 3
    (run / 'riser.dbg.out').write_text('debug')           # not a step
    old = 1_000_000
    for p in run.iterdir():
        os.utime(p, (old, old))
    return run


def test_out_steps_ignores_other_names(run):
    steps = out_steps(run, 'riser')
    assert sorted(steps) == [4450, 4500, 4550, 4600]
    assert len(steps[4600]) == 1


def test_ended_case_needs_only_complete_parts(run):
    ok, why = settled_steps(out_steps(run, 'riser'), nsg=NSG, running=False)
    assert ok == [4450, 4500, 4550]
    assert why == {4600: '1 of 3 .out parts'}


def test_running_case_stops_before_the_solver(run):
    # BR0SG0U2P0: live .othd at 4571, so 4550 is done and 4600 is being computed
    ok, why = settled_steps(out_steps(run, 'riser'), nsg=NSG, running=True,
                            solver_at=4550, now=2_000_000)
    assert ok == [4450, 4500]
    assert why[4550] == 'the solver is at 4550, not past it yet'


def test_running_case_waits_for_quiet_parts(run):
    fresh = run / 'riser.4500_1.out'
    os.utime(fresh, (1_999_900, 1_999_900))
    ok, why = settled_steps(out_steps(run, 'riser'), nsg=NSG, running=True,
                            solver_at=4571, now=2_000_000)
    assert ok == [4450, 4550]
    assert why[4500] == 'a part changed 100 s ago'


def test_unknown_nsg_or_solver_settles_nothing(run):
    steps = out_steps(run, 'riser')
    assert settled_steps(steps, nsg=None, running=False)[0] == []
    assert settled_steps(steps, nsg=NSG, running=True, solver_at=None)[0] == []


def test_empty_part(run):
    (run / 'riser.4450_2.out').write_text('')
    ok, why = settled_steps(out_steps(run, 'riser'), nsg=NSG, running=False)
    assert 4450 not in ok and why[4450] == '1 empty .out part(s)'


def test_every_cut_point_is_caught_and_never_called_whole(tmp_path):
    data = plt_bytes()
    path = tmp_path / 'cut.plt'
    for n in range(len(data)):
        path.write_bytes(data[:n])
        check = check_plt(path)
        assert not check.ok, n
        # when a full length is given it is the real one, never a guess
        assert check.expected in (None, len(data)), (n, check.expected)
