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
    CaseOrganizer(case, args, _Logger(), Console(file=open('/dev/null', 'w'))).organize('rst')


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


def test_the_two_newest_complete_sets_stay_without_a_restart(tmp_path, run):
    organise(tmp_path, {})                      # --keep-newest defaults to 2
    assert rst_steps(run) == [6000, 6500, 7000, 7500, 8000, 8250, 8300]


def test_keep_newest_one_keeps_only_the_newest(tmp_path, run):
    organise(tmp_path, {}, keep_newest=1)
    assert rst_steps(run) == [6000, 6500, 7000, 7500, 8000, 8300]


def test_keep_newest_three(tmp_path, run):
    organise(tmp_path, {}, keep_newest=3)
    assert rst_steps(run) == [6000, 6500, 7000, 7500, 8000, 8200, 8250, 8300]


def test_a_stop_at_5020_keeps_5000_and_4950(tmp_path):
    """output every 50, stopped at 5020: the last two sets stay with the 500 grid."""
    run = tmp_path / 'RUN_1'
    run.mkdir()
    for step in range(4000, 5001, 50):
        write_rst(run, step)
    organise(tmp_path, {})
    assert rst_steps(run) == [4000, 4500, 4950, 5000]


def test_a_cut_short_newest_set_leaves_the_two_newest_complete_ones(tmp_path):
    run = tmp_path / 'RUN_1'
    run.mkdir()
    for step in range(6000, 6301, 50):
        write_rst(run, step)
    write_rst(run, 6350, parts=2)                # the job was killed while writing it
    organise(tmp_path, {})
    # the grid (6000), the two newest COMPLETE sets (6250, 6300), the set being written (6350)
    assert rst_steps(run) == [6000, 6250, 6300, 6350]
