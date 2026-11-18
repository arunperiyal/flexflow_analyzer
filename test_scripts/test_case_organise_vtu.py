"""`case organise vtu [--clean]`: the .vtu caches field render keeps beside
the PLTs in binary/ -- listed without --clean, deleted with it (within
--t1/--t2). Only the cache names are touched."""

from argparse import Namespace
from types import SimpleNamespace

import pytest
from rich.console import Console

from src.commands.case import CaseCommand
from src.commands.case.organise_impl.organizer import CaseOrganizer


class _Logger:
    def __getattr__(self, name):
        return lambda *a, **k: None


def organise(case_dir, **flags):
    args = Namespace(leftovers=False, orphans=False, dry_run=False, yes=True, log=False,
                     verbose=False, t1=None, t2=None)
    for key, value in flags.items():
        setattr(args, key, value)
    case = SimpleNamespace(case_directory=str(case_dir), problem_name='riser',
                           config={'dir': './RUN_1'})
    CaseOrganizer(case, args, _Logger(), Console(file=open('/dev/null', 'w'))).organize('vtu')


NAMES = ['riser.100.vtu', 'riser.100.z0.vtu', 'riser.200.vtu', 'riser.300.partial.vtu',
         'riser.400.deriving.vtu', 'riser.500.vtu', 'mine.vtu', 'riser.vtu', 'riser.100.plt']


@pytest.fixture
def binary(tmp_path):
    binary = tmp_path / 'binary'
    binary.mkdir()
    for name in NAMES:
        (binary / name).write_text('x')
    return binary


def left(binary):
    return sorted(p.name for p in binary.iterdir())


def test_dry_run_deletes_nothing(tmp_path, binary):
    organise(tmp_path, dry_run=True)
    assert left(binary) == sorted(NAMES)


def test_it_deletes_the_caches_and_leftovers_but_keeps_those_with_no_plt(tmp_path, binary):
    organise(tmp_path)
    # only riser.100.plt is there: riser.200/.500 have none, so they stay
    assert left(binary) == ['mine.vtu', 'riser.100.plt', 'riser.200.vtu', 'riser.500.vtu',
                            'riser.vtu']


def test_orphans_go_with_the_flag(tmp_path, binary):
    organise(tmp_path, orphans=True)
    assert left(binary) == ['mine.vtu', 'riser.100.plt', 'riser.vtu']


def test_leftovers_only(tmp_path, binary):
    organise(tmp_path, leftovers=True)
    assert 'riser.300.partial.vtu' not in left(binary) and 'riser.400.deriving.vtu' not in left(binary)
    assert {'riser.100.vtu', 'riser.100.z0.vtu', 'riser.200.vtu', 'riser.500.vtu'} <= set(left(binary))


def test_within_the_window(tmp_path, binary):
    organise(tmp_path, orphans=True, t1=200, t2=400)
    assert left(binary) == sorted(['riser.100.vtu', 'riser.100.z0.vtu', 'riser.500.vtu',
                                   'mine.vtu', 'riser.vtu', 'riser.100.plt'])


def test_parser():
    import argparse
    parser = argparse.ArgumentParser()
    CaseCommand().setup_parser(parser.add_subparsers(dest='command'))
    a = parser.parse_args(['case', 'organise', 'vtu', 'C1', '--orphans', '--yes', '--t2', '300'])
    assert (a.organise_subcommand, a.case, a.orphans, a.yes, a.t2) == ('vtu', 'C1', True, True, 300.0)
