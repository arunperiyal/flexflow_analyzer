"""`plot --run`: read the run directory's .othd/.oisd (what a job is writing
now, before `case organise history --update` archives it) instead of the
history. A last step still being written is left out."""

from argparse import Namespace

import matplotlib
matplotlib.use('Agg')
import pytest

from src.commands.data import shared
from src.commands.visualization.plot_impl import command as plot
from test_case_organise_history import archive, othd


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
    """History: run 1 = steps 1-5 (value 1). Run directory: a job at steps 6-9 (value 9)."""
    (tmp_path / 'simflow.config').write_text('problem = riser\ndir = ./RUN_1\n')
    archive(tmp_path, {'riser1.othd': othd(range(1, 6), 1.0)})
    run_dir = tmp_path / 'RUN_1'
    run_dir.mkdir()
    (run_dir / 'riser.othd').write_text(othd(range(6, 10), 9.0))
    return tmp_path


def args(**kw):
    base = dict(var=['aleDisp_x'], node=None, othid=None, osgid=None, group=None, othd=True,
                oisd=False, t1=None, t2=None, last=None, archive=None, run=False)
    base.update(kw)
    return Namespace(**base)


def read(case, log=None, **kw):
    return shared.select(case, args(**kw), log or Log(), ['aleDisp_x'])


def test_run_reads_the_run_directory_only(case):
    sel = read(case, run=True)
    assert list(sel.tsids) == [6, 7, 8, 9]
    assert set(sel.values['aleDisp_x']) == {9.0}


def test_without_the_flag_the_history_is_read(case):
    assert list(read(case).tsids) == [1, 2, 3, 4, 5]


def test_a_step_still_being_written_is_left_out(case):
    path = case / 'RUN_1' / 'riser.othd'
    path.write_text(othd(range(6, 11), 9.0)[:-9])          # the job is in the middle of step 10
    log = Log()
    sel = read(case, log, run=True)
    assert list(sel.tsids) == [6, 7, 8, 9]
    assert any('still being written' in l for l in log.lines)
    assert path.read_text() == othd(range(6, 11), 9.0)[:-9]     # the job's file is not touched


def test_a_file_with_no_whole_step_is_an_error(case):
    (case / 'RUN_1' / 'riser.othd').write_text(othd([6], 9.0)[:-9])
    with pytest.raises(SystemExit):
        read(case, run=True)


def test_a_kind_the_run_directory_lacks_is_an_error(case):
    log = Log()
    with pytest.raises(SystemExit):
        shared.scan_kinds(case, ('oisd',), log, None, True)
    assert any('no oisd' in l for l in log.lines)


def test_no_run_directory_is_an_error(tmp_path):
    (tmp_path / 'simflow.config').write_text('problem = riser\n')
    with pytest.raises(ValueError, match='no run directory'):
        shared.find_files(tmp_path, 'othd', run=True)


def test_the_title_says_run_directory(case):
    sel = read(case, run=True)
    assert 'run directory' in plot.describe(case, sel, ['dx'], None, True)
    assert 'run directory' not in plot.describe(case, sel, ['dx'])


def test_run_and_archive_exclude_each_other(case, capsys):
    with pytest.raises(SystemExit):
        plot.execute_plot(Namespace(
            input_file=None, case=str(case), var=['aleDisp_x'], run=True, archive='1', verbose=False,
            no_display=True, output=None, gnu=False, othd=True, oisd=False, node=None, othid=None,
            osgid=None, group=None, t1=None, t2=None, last=None, plot_type='time', plot_style=None,
            legend_style=None, title=None, fontname=None, restart=False))
    captured = capsys.readouterr()
    assert 'give one' in captured.out + captured.err
