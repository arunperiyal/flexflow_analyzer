"""`case check plt --remote --adopt`: PLTs only on the remote, with no record, are judged
where they lie (header read there, write time against the .out, md5 on the remote) and
recorded, so `case organise out` can count them. Nothing is downloaded. The remote is a folder."""

import io
import os
import shutil
from types import SimpleNamespace

import pytest
import yaml
from rich.console import Console
from shellkit import Runtime

from src.cli.app import create_app
from test_scripts.plt_files import write_plt

T0 = 1_700_000_000


def at(path, seconds):
    os.utime(path, (T0 + seconds, T0 + seconds))
    return path


@pytest.fixture
def world(tmp_path, monkeypatch):
    """.out of steps 100, 300, 400 here (t=0, 0, 100). On the remote, with no record: 100 cut
    short, 300 whole and newer (t=50), 400 whole but older than its .out (t=50), 500 whole
    with no .out left here."""
    folder = tmp_path / 'cases'
    case = folder / 'CS1'
    run = case / 'RUN_1'
    run.mkdir(parents=True)
    (case / 'binary').mkdir()
    (case / 'simflow.config').write_text('problem = riser\nnp = 1\ndir = ./RUN_1\n')
    for step, t in ((100, 0), (300, 0), (400, 100)):
        (run / f'riser.{step}_0.out').write_text('o')
        at(run / f'riser.{step}_0.out', t)
    there = tmp_path / 'r' / 'CS1' / 'binary'
    there.mkdir(parents=True)
    at(write_plt(there / 'riser.100.plt', cut=40), 50)
    for step in (300, 400, 500):
        at(write_plt(there / f'riser.{step}.plt', npts=8), 50)
    (folder / '.cases.yml').write_text(yaml.safe_dump(
        {'cases': [{'name': 'CS1', 'path': 'CS1'}], 'remotes': {'local': str(tmp_path / 'r')},
         'auto': {}}))
    monkeypatch.chdir(folder)
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    return SimpleNamespace(folder=folder, case=case, there=there, root=tmp_path)


@pytest.fixture
def shell(world):
    out = io.StringIO()
    rt = Runtime(create_app(), console=Console(file=out, width=200, color_system=None),
                 err_console=Console(file=out, width=200, color_system=None))

    def run(line, capsys):
        status = rt.execute_line(line)
        text = out.getvalue() + capsys.readouterr().out
        out.truncate(0)
        out.seek(0)
        return status, ' '.join(text.split())
    return run


def ledger(world):
    from src.core.transfer.ledger import Ledger
    return Ledger(world.folder)


def test_adopt_records_the_whole_newer_copies_and_refuses_the_rest(shell, world, capsys):
    status, text = shell("case check plt --case CS1 --remote local --adopt", capsys)
    assert 'adopted 300, 500' in text
    assert 'riser.100.plt: not whole on the remote' in text
    assert 'riser.400.plt: written on the remote at or before its .out' in text
    got = ledger(world).get('local', 'CS1', 'binary/riser.300.plt')
    assert got['verified'] == 'adopted' and got['md5'] and got['mtime'] == T0 + 50
    assert ledger(world).get('local', 'CS1', 'binary/riser.100.plt') is None
    assert ledger(world).get('local', 'CS1', 'binary/riser.400.plt') is None


def test_an_adopted_copy_stands_in_for_its_out(shell, world, capsys):
    shell("case check plt --case CS1 --remote local --adopt", capsys)
    _, text = shell("case check out --case CS1 --remote local", capsys)
    assert '300 ✓ — ✓ remote' in text
    assert '100 ✓ — ✗ on the remote, not recorded' in text
    from src.core.chain import Chain, remote_copies
    chain = Chain(world.case, 'riser', world.case / 'RUN_1',
                  remote=remote_copies(world.case, 'riser', 'local'))
    outs = [world.case / 'RUN_1' / 'riser.300_0.out']
    assert chain.for_out(300, outs).ok and chain.for_out(300, outs).by == 'remote'
    assert not chain.for_out(400, [world.case / 'RUN_1' / 'riser.400_0.out']).ok


def test_nothing_is_downloaded(shell, world, capsys):
    shell("case check plt --case CS1 --remote local --adopt", capsys)
    assert os.listdir(world.case / 'binary') == []


def test_a_second_adopt_leaves_the_recorded_ones_alone(shell, world, capsys):
    shell("case check plt --case CS1 --remote local --adopt", capsys)
    _, text = shell("case check plt --case CS1 --remote local --adopt", capsys)
    assert 'already recorded 300, 500' in text and 'adopted 300' not in text


def test_an_adopted_copy_that_changes_is_reported(shell, world, capsys):
    shell("case check plt --case CS1 --remote local --adopt", capsys)
    write_plt(world.there / 'riser.300.plt', npts=16)
    _, text = shell("case check plt --case CS1 --remote local", capsys)
    assert 'changed on the remote' in text and 'riser.300.plt' in text


def test_window_picks_the_steps(shell, world, capsys):
    _, text = shell("case check plt --case CS1 --remote local --adopt --t1 300 --t2 300", capsys)
    assert ledger(world).get('local', 'CS1', 'binary/riser.300.plt')
    assert ledger(world).get('local', 'CS1', 'binary/riser.500.plt') is None


def test_adopt_without_remote_is_refused(shell, capsys):
    status, text = shell("case check plt --case CS1 --adopt", capsys)
    assert status != 0 and '--remote' in text


def test_the_organise_message_names_adopt(shell, world, capsys):
    status, text = shell("case organise out --case CS1 --remote local --dry-run", capsys)
    assert 'on the remote, not recorded' in text and '--adopt' in text
    assert 'Keeping .out of 3 step(s)' in text



def test_check_out_names_the_unrecorded_copy(shell, capsys):
    _, text = shell("case check out --case CS1 --remote local", capsys)
    assert '400 ✓ — ✗ on the remote, not recorded' in text
