"""`case organise output --keep-freq N` never deletes a restart point off the
keep grid: restartTsId from simflow.config (where a queued restart resumes),
the newest complete .rst set, and a newest set that is still incomplete."""

from argparse import Namespace
from types import SimpleNamespace

import pytest
from rich.console import Console

from src.commands.case.organise_impl.organizer import CaseOrganizer

NSG = 4


class _Logger:
    def __getattr__(self, name):
        return lambda *a, **k: None


def organise(case_dir, config, **flags):
    args = Namespace(delete_ascii=False, delete_binary=False, freq=None, keep_freq=500,
                     all_out=False, keep_out=False, dry_run=False, no_confirm=True,
                     log=False, verbose=False, t1=None, t2=None)
    for key, value in flags.items():
        setattr(args, key, value)
    case = SimpleNamespace(case_directory=str(case_dir), problem_name='riser',
                           config={'dir': './RUN_1', 'nsg': str(NSG), **config})
    CaseOrganizer(case, args, _Logger(), Console(file=open('/dev/null', 'w'))).organize('output')


def write_rst(run, step, parts=NSG):
    for k in range(parts):
        (run / f'riser.{step}_{k}.rst').write_text('r')


def rst_steps(run):
    return sorted({int(p.name.split('.')[1].split('_')[0]) for p in run.glob('*.rst')})


@pytest.fixture
def run(tmp_path):
    run = tmp_path / 'RUN_1'
    run.mkdir()
    for step in range(6000, 8301, 50):
        write_rst(run, step)
    return run


def test_queued_restart_point_off_the_grid_stays(tmp_path, run):
    # BR0SG0U4P0: a main job is queued to resume from 8250
    organise(tmp_path, {'restartTsId': '8250', 'restartFlag': '1'})
    assert rst_steps(run) == [6000, 6500, 7000, 7500, 8000, 8250, 8300]
    assert len(list(run.glob('riser.8250_*.rst'))) == NSG


def test_newest_complete_set_stays_without_a_restart(tmp_path, run):
    organise(tmp_path, {})
    assert rst_steps(run) == [6000, 6500, 7000, 7500, 8000, 8300]


def test_newest_set_still_being_written_stays_with_the_last_complete_one(tmp_path, run):
    write_rst(run, 8350, parts=2)
    organise(tmp_path, {})
    left = rst_steps(run)
    assert 8350 in left and 8300 in left
    assert len(list(run.glob('riser.8350_*.rst'))) == 2


def test_restart_point_kept_even_outside_the_window(tmp_path, run):
    organise(tmp_path, {'restartTsId': '7250'}, t1=7000, t2=8000)
    left = rst_steps(run)
    assert 7250 in left
    assert 7100 not in left              # inside the window, off the grid
    assert 6050 in left                  # outside the window: untouched


def test_dry_run_deletes_nothing(tmp_path, run):
    before = rst_steps(run)
    organise(tmp_path, {'restartTsId': '8250'}, dry_run=True)
    assert rst_steps(run) == before
