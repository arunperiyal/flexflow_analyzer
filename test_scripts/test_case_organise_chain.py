"""`case organise plt` and `case organise output` delete along the chain
(src/core/chain.py): .out <- ASCII PLT <- binary PLT <- the copy on the
remote. A step with nothing to stand in for it is kept and reported; the
others go."""

import io
import os
import shutil
from argparse import Namespace
from types import SimpleNamespace

import pytest
import yaml
from rich.console import Console

from src.commands.case.organise_impl.organizer import CaseOrganizer
from src.core.transfer.ledger import Ledger
from test_scripts.plt_files import write_ascii_plt, write_plt

T0 = 1_700_000_000
STEPS = (100, 200, 300, 400)


class _Logger:
    def __getattr__(self, name):
        return lambda *a, **k: None


def at(path, seconds):
    os.utime(path, (T0 + seconds, T0 + seconds))
    return path


@pytest.fixture
def world(tmp_path):
    """cases/CS1: every step has .out (t=0), an ASCII PLT (t=10) and a binary
    PLT (t=20); r/CS1/binary holds a copy of each binary PLT."""
    case = tmp_path / 'cases' / 'CS1'
    run, binary = case / 'RUN_1', case / 'binary'
    run.mkdir(parents=True)
    binary.mkdir()
    for i, step in enumerate(STEPS):
        for k in range(2):
            (run / f'riser.{step}_{k}.out').write_text('o')
            at(run / f'riser.{step}_{k}.out', 0)
        at(write_ascii_plt(run / f'riser.{step}.plt', nodes=6 + i), 10)
        at(write_plt(binary / f'riser.{step}.plt', npts=8 + i), 20)
    there = tmp_path / 'r' / 'CS1' / 'binary'
    shutil.copytree(binary, there)
    (tmp_path / 'cases' / '.cases.yml').write_text(yaml.safe_dump(
        {'cases': [{'name': 'CS1', 'path': 'CS1'}], 'remotes': {'local': str(tmp_path / 'r')},
         'auto': {}}))
    return SimpleNamespace(case=case, run=run, binary=binary, there=there,
                           folder=tmp_path / 'cases')


def organise(world, subcommand, **flags):
    args = Namespace(delete_ascii=False, delete_binary=False, freq=None, keep_freq=None,
                     all_out=False, keep_out=False, dry_run=False, no_confirm=True, log=False,
                     verbose=False, t1=None, t2=None, remote='local')
    for key, value in flags.items():
        setattr(args, key, value)
    case = SimpleNamespace(case_directory=str(world.case), problem_name='riser',
                           config={'dir': './RUN_1'})
    out = io.StringIO()
    CaseOrganizer(case, args, _Logger(),
                  Console(file=out, width=200, color_system=None)).organize(subcommand)
    return ' '.join(out.getvalue().split())


def left(directory, suffix):
    return sorted({int(p.name.split('.')[1].split('_')[0]) for p in directory.glob(f'riser.*{suffix}')})


# --- plt --delete-binary -------------------------------------------------------------

def test_delete_binary_takes_only_what_the_remote_holds_with_the_same_md5(world):
    (world.there / 'riser.200.plt').unlink()                    # not on the remote
    copy = world.there / 'riser.300.plt'
    copy.write_bytes(copy.read_bytes()[:-1] + b'?')             # same size, another md5
    out = organise(world, 'plt', delete_binary=True)
    assert left(world.binary, '.plt') == [200, 300]             # kept and reported
    assert 'Keeping 2 file(s) with no verified copy on the remote' in out
    # what went is in the ledger as verified
    assert Ledger(world.folder).get('local', 'CS1', 'binary/riser.100.plt')['verified'] == 'md5'


def test_delete_binary_without_a_remote_deletes_nothing(world):
    out = organise(world, 'plt', delete_binary=True, remote=None)
    assert left(world.binary, '.plt') == list(STEPS)
    assert 'The remote could not be asked, so nothing in binary/ is deleted' in out
    out = organise(world, 'plt', delete_binary=True, remote='nowhere')
    assert left(world.binary, '.plt') == list(STEPS) and "'nowhere' is not set" in out


def test_delete_binary_leaves_a_plt_cut_short_here(world):
    local = world.binary / 'riser.100.plt'
    local.write_bytes(local.read_bytes()[:-10])
    shutil.copy(local, world.there / 'riser.100.plt')           # the same broken file there
    organise(world, 'plt', delete_binary=True)
    assert left(world.binary, '.plt') == [100]


def test_delete_binary_window_and_freq(world):
    organise(world, 'plt', delete_binary=True, t1=150, t2=400, freq=200)
    assert left(world.binary, '.plt') == [100, 300]


# --- plt --delete-ascii --------------------------------------------------------------

def test_delete_ascii_needs_a_whole_binary_written_after_it(world):
    write_plt(world.binary / 'riser.200.plt', cut=40)           # cut short
    at(world.binary / 'riser.300.plt', 5)                       # older than the ASCII PLT
    out = organise(world, 'plt', delete_ascii=True, remote=None)
    assert left(world.run, '.plt') == [200, 300]
    assert 'Keeping 2 ASCII PLT file(s) with no verified binary PLT' in out


def test_delete_ascii_stands_on_the_remote_when_binary_is_gone_here(world):
    organise(world, 'plt', delete_binary=True)                  # binary/ emptied, all verified
    assert left(world.binary, '.plt') == []
    (world.there / 'riser.400.plt').write_bytes(b'damaged since')
    out = organise(world, 'plt', delete_ascii=True)
    assert left(world.run, '.plt') == [400]                     # its copy is not as recorded
    # and with no remote to ask, none of them goes
    out = organise(world, 'plt', delete_ascii=True, remote=None)
    assert left(world.run, '.plt') == [400] and 'the remote was not asked' in out


def test_delete_ascii_freq_and_window(world):
    organise(world, 'plt', delete_ascii=True, t1=100, t2=300, freq=200)
    assert left(world.run, '.plt') == [100, 300, 400]


def test_both_flags_in_one_command_ascii_first(world):
    organise(world, 'plt', delete_ascii=True, delete_binary=True)
    assert left(world.run, '.plt') == [] and left(world.binary, '.plt') == []


# --- output --------------------------------------------------------------------------

def test_out_goes_on_a_whole_newer_ascii_plt_alone(world):
    shutil.rmtree(world.binary)
    shutil.rmtree(world.there)
    p = world.run / 'riser.300.plt'
    p.write_text(p.read_text()[:-30])                           # cut short
    at(p, 10)
    out = organise(world, 'output', keep_freq=1000, keep_out=False, remote=None)
    assert left(world.run, '.out') == [300]
    assert 'Keeping .out of 1 step(s) whose PLT cannot stand in for them' in out
    assert '300: the ASCII riser.300.plt is cut short' in out


def test_out_written_again_by_a_restart_stays(world):
    for k in range(2):
        at(world.run / f'riser.400_{k}.out', 50)                # after both PLTs
    organise(world, 'output', keep_freq=1000)
    assert left(world.run, '.out') == [400]


def test_out_falls_through_to_the_binary_and_then_the_remote(world):
    for step in STEPS:
        (world.run / f'riser.{step}.plt').unlink()              # no ASCII PLT at all
    organise(world, 'plt', delete_binary=True, t1=300)          # 300, 400: only on the remote
    (world.there / 'riser.400.plt').unlink()                    # ... and 400 lost there
    out = organise(world, 'output', keep_freq=1000)
    assert left(world.run, '.out') == [400]
    assert 'Keeping .out of 1 step(s) with no riser.<step>.plt yet: 400' in out


def test_out_with_no_plt_and_no_remote_says_the_remote_was_not_asked(world):
    for step in STEPS:
        (world.run / f'riser.{step}.plt').unlink()
    shutil.rmtree(world.binary)
    out = organise(world, 'output', keep_freq=1000, remote=None)
    assert left(world.run, '.out') == list(STEPS)
    assert 'The remote was not asked' in out


def test_the_whole_chain_in_order_leaves_only_the_remote_copies(world):
    organise(world, 'output', keep_freq=1000)
    organise(world, 'plt', delete_ascii=True)
    organise(world, 'plt', delete_binary=True)
    assert left(world.run, '.out') == [] and left(world.run, '.plt') == []
    assert left(world.binary, '.plt') == [] and left(world.there, '.plt') == list(STEPS)
