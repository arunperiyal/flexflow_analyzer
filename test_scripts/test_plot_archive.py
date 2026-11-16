"""`plot --archive RUNS`: read single runs of archive/ instead of the whole
history (the compiled file or every run, the later one winning)."""

from argparse import Namespace

import matplotlib
matplotlib.use('Agg')
import pytest

from src.commands.data import shared
from src.commands.visualization.plot_impl import command as plot
from test_case_organise_history import othd


class Log:
    def __init__(self):
        self.lines = []

    def info(self, msg):
        self.lines.append(msg)

    warning = success = info

    def error(self, msg):
        self.lines.append('ERROR ' + msg)


@pytest.fixture
def case(tmp_path):
    """Run 1 has steps 1-5, run 2 redoes 4-8 (value 2), run 6 is 7-9 (value 6)."""
    arch = tmp_path / 'othd_files' / 'archive'
    arch.mkdir(parents=True)
    (arch / 'riser1.othd').write_text(othd(range(1, 6), 1.0))
    (arch / 'riser2.othd').write_text(othd(range(4, 9), 2.0))
    (arch / 'riser6.othd').write_text(othd(range(7, 10), 6.0))
    return tmp_path


def args(**kw):
    base = dict(var=['aleDisp_x'], node=None, othid=None, osgid=None, group=None, othd=True,
                oisd=False, t1=None, t2=None, last=None, archive=None)
    base.update(kw)
    return Namespace(**base)


def read(case, **kw):
    return shared.select(case, args(**kw), Log(), ['aleDisp_x'])


def test_one_run(case):
    sel = read(case, archive='6')
    assert list(sel.tsids) == [7, 8, 9]
    assert set(sel.values['aleDisp_x']) == {6.0}


def test_a_list_joins_the_runs_in_order_and_the_later_wins(case):
    sel = read(case, archive='1,2')
    assert list(sel.tsids) == [1, 2, 3, 4, 5, 6, 7, 8]
    assert list(sel.values['aleDisp_x']) == [1, 1, 1, 2, 2, 2, 2, 2]


def test_a_range_and_a_bare_flag(case):
    assert list(read(case, archive='1-2').tsids) == list(range(1, 9))
    assert list(read(case, archive='all').tsids) == list(range(1, 10))


def test_without_the_flag_the_whole_history_is_read(case):
    assert list(read(case).tsids) == list(range(1, 10))


def test_a_missing_run_names_those_there(case):
    log = Log()
    with pytest.raises(SystemExit):
        shared.select(case, args(archive='3'), log, ['aleDisp_x'])
    assert any('run 3' in l and 'there: 1, 2, 6' in l for l in log.lines)


def test_descending_runs_are_refused(case):
    with pytest.raises(ValueError, match='ascending'):
        shared.find_files(case, 'othd', '2,1')


def test_the_title_says_which_runs(case):
    sel = read(case, archive='1,2')
    assert 'archive 1,2' in plot.describe(case, sel, ['dx'], '1,2')
    assert 'archive' not in plot.describe(case, sel, ['dx'])
