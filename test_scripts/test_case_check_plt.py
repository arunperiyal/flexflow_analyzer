"""`case check plt`: one check over binary/ and the run directory. Up to the
last step found, a step with no file is missing and a 0-byte one empty; the
steps after it are not written yet, shown apart from the gaps."""

import io

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
