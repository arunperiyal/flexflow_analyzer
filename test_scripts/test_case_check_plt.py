"""`case check plt`: one check over binary/ and the run directory. Up to the
last step found, a step with no file is missing and a 0-byte one empty; the
steps after it are not written yet, shown apart from the gaps."""

import io
import os

import pytest
from rich.console import Console

from src.commands.case.check_impl.command import _check_plt, _fmt_steps
from src.core.simflow_config import SimflowConfig


@pytest.fixture
def case(tmp_path):
    case = tmp_path / 'C1'
    (case / 'binary').mkdir(parents=True)
    (case / 'RUN_1').mkdir()
    (case / 'simflow.config').write_text('problem = riser\noutFreq = 50\ndir = RUN_1\n')
    (case / 'riser.def').write_text('timeSteppingControl{\n maxTimeSteps = 2000\n}\n')
    for t in range(50, 1501, 50):
        if t not in (300, 650, 700, 750, 1200):
            (case / 'binary' / f'riser.{t}.plt').write_text('x' * 10)
    (case / 'binary' / 'riser.900.plt').write_text('')            # empty
    (case / 'binary' / 'riser.825.plt').write_text('x')           # off the grid
    for t in (100, 1550, 1600):
        (case / 'RUN_1' / f'riser.{t}.plt').write_text('x')
    return case


def check(case, **kw):
    console = Console(file=io.StringIO(), width=120, color_system=None)
    _check_plt(SimflowConfig.find(case), case, console, **kw)
    return console.file.getvalue()


def rows(text):
    return {l.split()[0]: ' '.join(l.split()[1:]) for l in text.splitlines()
            if l.startswith('    ') and l.split()}


def test_one_check_over_both_places(case):
    text = check(case)
    assert '✗ 27 of 32 present up to 1600, the last step found · 5 missing, 1 empty' in text
    got = rows(text)
    assert got['missing'] == '300 · 650–750 (3) · 1200'
    assert got['empty'] == '900'
    assert got['extra'].startswith('825')
    assert got['in'].startswith('both 100')
    assert got['not'].startswith('yet 1650–2000 (8)')
    table = [l.split() for l in text.splitlines() if l.split()[:1] in (['binary/'], ['RUN_1/'])]
    assert [r[:5] for r in table] == [['binary/', '26', '50', '→', '1500'],
                                      ['RUN_1/', '3', '100', '→', '1600']]


def test_window_and_freq(case):
    text = check(case, t1=600, t2=1000)
    assert 'steps 600..1000' in text and '6 of 9 present up to 1000' in text
    assert rows(text)['missing'] == '650–750 (3)'
    assert 'not yet' not in text and 'in both' not in text
    assert '28 of 64 present' in check(case, freq=25)


def test_all_present(case):
    for t in (300, 650, 700, 750, 1200, 900):
        (case / 'binary' / f'riser.{t}.plt').write_text('x')
    text = check(case, t2=1500)
    assert '✓ 30 of 30 present up to 1500, the last step found · none missing' in text


def test_nothing_found(tmp_path, case):
    for d in ('binary', 'RUN_1'):
        for f in (case / d).iterdir():
            f.unlink()
    assert '✗ no riser.<step>.plt in binary/ or RUN_1/; 40 expected' in check(case)


def test_fmt_steps():
    assert _fmt_steps([50, 100, 150, 300], 50) == '50–150 (3) · 300'
    assert _fmt_steps([825, 875], None) == '825 · 875'
    long = _fmt_steps(list(range(10, 400, 20)), 10, limit=4)
    assert long == '10 · 30 · … 16 more … · 370 · 390'


def _age(path, when):
    os.utime(path, (when, when))


@pytest.fixture
def resumed(case):
    """Restarted from 1000; the resumed run has written .out for 1050..1600."""
    with open(case / 'simflow.config', 'a') as f:
        f.write('restartFlag = 1\nrestartTsId = 1000\n')
    for plt in (case / 'binary').glob('*.plt'):
        _age(plt, 1_000_000)                          # converted before the restart
    for i, t in enumerate(range(1050, 1601, 50)):
        for k in (0, 1):
            out = case / 'RUN_1' / f'riser.{t}_{k}.out'
            out.write_text('x')
            _age(out, 2_000_000 + i * 100)
    for t in (1050, 1100):                            # converted again since
        _age(case / 'binary' / f'riser.{t}.plt', 3_000_000)
    for t in (1550, 1600):
        _age(case / 'RUN_1' / f'riser.{t}.plt', 3_000_000)
    return case


def test_flags_the_plt_made_before_the_restart(resumed):
    text = check(resumed)
    assert '7 from before the restart' in text and '✗' in text
    assert rows(text)['stale'].startswith('1150 · 1250–1500 (6) (in binary/')


def test_converted_after_the_resumed_run_reached_it_is_not_stale(resumed):
    # 1300's PLT is newer than the resumed run's 1300 output: made from it
    _age(resumed / 'binary' / 'riser.1300.plt', 2_000_000 + 5 * 100 + 1)
    assert rows(check(resumed))['stale'].startswith('1150 · 1250 · 1350–1500 (4)')
    # ... but older than its 1350 output still counts for 1350 and on
    _age(resumed / 'binary' / 'riser.1350.plt', 2_000_000 + 5 * 100 + 1)
    assert rows(check(resumed))['stale'].startswith('1150 · 1250 · 1350–1500 (4)')


def test_restart_with_nothing_to_date_by(resumed):
    for f in (resumed / 'RUN_1').glob('*.out'):
        f.unlink()
    text = check(resumed)
    assert 'stale' not in text
    assert 'restart at 1000: no .out/.rst past it in the run directory' in ' '.join(text.split())


def test_restart_all_fresh(resumed):
    for t in range(1150, 1501, 50):
        plt = resumed / 'binary' / f'riser.{t}.plt'
        if plt.exists():
            _age(plt, 3_000_000)
    text = ' '.join(check(resumed).split())
    assert 'stale' not in text
    assert 'restart at 1000: none older than the resumed run (dated by its output from 1050 on)' in text


def test_no_restart_no_check(case):
    text = check(case)
    assert 'stale' not in text and 'restart' not in text
