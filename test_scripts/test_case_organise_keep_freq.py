"""`case organise plt --delete-binary --freq/--keep-freq` and `output --keep-freq`.

--freq picks the binary/ steps that may go, --keep-freq spares the steps it
divides; `output --keep-freq N` keeps the .rst steps divisible by N with no
need to know outFreq; without it, 10 * freq. `output` deletes a step's .out
once its .plt exists -- keep-freq steps too, since a restart reads only .rst
-- and keeps the .out of steps with no .plt.
"""

import argparse
from argparse import Namespace
from types import SimpleNamespace

import pytest
from rich.console import Console

from src.commands.case import CaseCommand
from src.commands.case.organise_impl.command import _check_keep_flags
from src.commands.case.organise_impl.organizer import CaseOrganizer


class _Logger:
    def __getattr__(self, name):
        return lambda *a, **k: None


def organise(case_dir, subcommand, config=None, **flags):
    args = Namespace(delete_ascii=False, delete_binary=False, freq=None, keep_freq=None,
                     all_out=False,
                     dry_run=False, no_confirm=True, log=False,
                     verbose=False, t1=None, t2=None)
    for key, value in flags.items():
        setattr(args, key, value)
    case = SimpleNamespace(case_directory=str(case_dir), problem_name='riser',
                           config=config or {'dir': './RUN_1'})
    CaseOrganizer(case, args, _Logger(), Console(file=open('/dev/null', 'w'))).organize(subcommand)


def steps(directory, suffix):
    return sorted(int(p.name.split('.')[1].split('_')[0]) for p in directory.glob(f'*{suffix}'))


@pytest.fixture
def binary(tmp_path):
    binary = tmp_path / 'binary'
    binary.mkdir()
    for t in range(3990, 5011):
        (binary / f'riser.{t}.plt').write_text('x')
    return binary


def test_delete_binary_keeps_every_fifth_step(tmp_path, binary):
    organise(tmp_path, 'plt', delete_binary=True, t1=4000, t2=5000, freq=1, keep_freq=5)
    left = steps(binary, '.plt')
    assert [t for t in left if 4000 <= t <= 5000] == list(range(4000, 5001, 5))
    assert 3990 in left and 5010 in left and 3999 in left          # outside the window


def test_delete_binary_freq_only_touches_its_multiples(tmp_path, binary):
    organise(tmp_path, 'plt', delete_binary=True, t1=4000, t2=4100, freq=10, keep_freq=50)
    gone = set(range(3990, 5011)) - set(steps(binary, '.plt'))
    assert gone == {4010, 4020, 4030, 4040, 4060, 4070, 4080, 4090}


def test_delete_binary_dry_run_deletes_nothing(tmp_path, binary):
    organise(tmp_path, 'plt', delete_binary=True, keep_freq=5, dry_run=True)
    assert len(steps(binary, '.plt')) == 1021


@pytest.fixture
def run_dir(tmp_path):
    run = tmp_path / 'RUN_1'
    run.mkdir()
    for t in range(50, 2001, 50):
        (run / f'riser.{t}_1.out').write_text('x')
        (run / f'riser.{t}_1.rst').write_text('x')
    return run


@pytest.fixture
def converted(tmp_path, run_dir):
    """Steps up to 1000 have their .plt: 50..500 in binary/, 550..1000 still in
    the run directory."""
    binary = tmp_path / 'binary'
    binary.mkdir()
    for t in range(50, 501, 50):
        (binary / f'riser.{t}.plt').write_text('x')
    for t in range(550, 1001, 50):
        (run_dir / f'riser.{t}.plt').write_text('x')
    return run_dir


def test_output_keep_freq_needs_no_outfreq(tmp_path, run_dir):
    organise(tmp_path, 'output', keep_freq=300, t2=1500)
    assert steps(run_dir, '.rst') == [300, 600, 900, 1200, 1500] + list(range(1550, 2001, 50))


def test_output_default_is_ten_times_freq(tmp_path, run_dir):
    organise(tmp_path, 'output', config={'dir': './RUN_1', 'outFreq': '50'})
    assert steps(run_dir, '.rst') == [500, 1000, 1500, 2000]


def test_output_deletes_out_once_its_plt_exists_keep_freq_steps_too(tmp_path, converted):
    organise(tmp_path, 'output', keep_freq=500)
    assert steps(converted, '.out') == list(range(1050, 2001, 50))     # no .plt for these
    assert steps(converted, '.rst') == [500, 1000, 1500, 2000]


def test_output_without_any_plt_keeps_every_out(tmp_path, run_dir):
    organise(tmp_path, 'output', keep_freq=500)
    assert len(steps(run_dir, '.out')) == 40


def test_output_all_out_deletes_unconverted_out_too(tmp_path, converted):
    organise(tmp_path, 'output', keep_freq=500, all_out=True, t2=1500)
    assert steps(converted, '.out') == list(range(1550, 2001, 50))     # outside --t2 only
    assert steps(converted, '.rst') == [500, 1000, 1500] + list(range(1550, 2001, 50))


def test_output_out_respects_the_time_window(tmp_path, converted):
    organise(tmp_path, 'output', keep_freq=500, t1=300, t2=700)
    assert steps(converted, '.out') == [50, 100, 150, 200, 250] + list(range(750, 2001, 50))


@pytest.fixture
def parse():
    parser = argparse.ArgumentParser()
    CaseCommand().setup_parser(parser.add_subparsers(dest='command'))
    return lambda *words: parser.parse_args(['case', 'organise', *words])


def test_parse_and_check(parse):
    args = parse('plt', 'C1', '--delete-binary', '--t1', '4000', '--t2', '5000',
                 '--freq', '1', '--keep-freq', '5')
    assert (args.freq, args.keep_freq) == (1, 5) and _check_keep_flags(args, 'plt') is None
    assert 'only applies with --delete-binary' in \
        _check_keep_flags(parse('plt', 'C1', '--delete-ascii', '--keep-freq', '5'), 'plt')
    assert 'must be 1 or more' in \
        _check_keep_flags(parse('plt', 'C1', '--delete-binary', '--freq', '0'), 'plt')
    with pytest.raises(SystemExit):
        parse('output', 'C1', '--keep-every', '2')
    assert parse('output', 'C1', '--keep-freq', '500').keep_freq == 500
    assert parse('output', 'C1', '--all-out').all_out is True
