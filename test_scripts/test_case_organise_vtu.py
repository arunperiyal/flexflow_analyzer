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
    args = Namespace(clean=False, dry_run=False, no_confirm=True, log=False,
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


def test_without_clean_only_lists(tmp_path, binary):
    organise(tmp_path)
    assert left(binary) == sorted(NAMES)


def test_clean_deletes_the_caches_only(tmp_path, binary):
    organise(tmp_path, clean=True)
    assert left(binary) == ['mine.vtu', 'riser.100.plt', 'riser.vtu']


def test_clean_within_the_window(tmp_path, binary):
    organise(tmp_path, clean=True, t1=200, t2=400)
    assert left(binary) == sorted(['riser.100.vtu', 'riser.100.z0.vtu', 'riser.500.vtu',
                                   'mine.vtu', 'riser.vtu', 'riser.100.plt'])


def test_dry_run_deletes_nothing(tmp_path, binary):
    organise(tmp_path, clean=True, dry_run=True)
    assert left(binary) == sorted(NAMES)


def test_parser():
    import argparse
    parser = argparse.ArgumentParser()
    CaseCommand().setup_parser(parser.add_subparsers(dest='command'))
    a = parser.parse_args(['case', 'organise', 'vtu', 'C1', '--clean', '--t2', '300'])
    assert (a.organise_subcommand, a.case, a.clean, a.t2) == ('vtu', 'C1', True, 300.0)
