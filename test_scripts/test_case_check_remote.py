"""`case check history --remote` and `case check out --remote`: what the case holds here
against what the remote holds, read-only. The remote is a folder (`local`)."""

import io
import os
import shutil
from types import SimpleNamespace

import pytest
import yaml
from rich.console import Console
from shellkit import Runtime

from src.cli.app import create_app
from test_scripts.plt_files import write_ascii_plt, write_plt

T0 = 1_700_000_000
STEPS = (100, 200, 300)


def at(path, seconds):
    os.utime(path, (T0 + seconds, T0 + seconds))
    return path


@pytest.fixture
def world(tmp_path, monkeypatch):
    """cases/CS1 with .out of steps 100, 200, 300 (t=0). Step 100 has an ASCII PLT here (t=10),
    step 200 only a verified binary PLT on the remote (t=20), step 300 no PLT anywhere."""
    folder = tmp_path / 'cases'
    case = folder / 'CS1'
    run, binary = case / 'RUN_1', case / 'binary'
    run.mkdir(parents=True)
    binary.mkdir()
    (case / 'simflow.config').write_text('problem = riser\nnp = 1\ndir = ./RUN_1\n')
    for step in STEPS:
        (run / f'riser.{step}_0.out').write_text('o')
        at(run / f'riser.{step}_0.out', 0)
    at(write_ascii_plt(run / 'riser.100.plt', nodes=6), 10)
    there = tmp_path / 'r' / 'CS1'
    (there / 'binary').mkdir(parents=True)
    at(write_plt(binary / 'riser.200.plt', npts=8), 20)
    shutil.copy2(binary / 'riser.200.plt', there / 'binary' / 'riser.200.plt')
    (folder / '.cases.yml').write_text(yaml.safe_dump(
        {'cases': [{'name': 'CS1', 'path': 'CS1'}], 'remotes': {'local': str(tmp_path / 'r')},
         'auto': {}}))
    # the copy is verified once (the ledger records it), then deleted here, as `organise` does
    from src.core.transfer.cloud import LocalCloud
    from src.core.transfer.ledger import Ledger
    from src.core.transfer.verify import verify_plts
    cloud = LocalCloud(tmp_path / 'r')
    assert verify_plts(case, 'riser', cloud, 'local', Ledger(folder)).verified == ['riser.200.plt']
    (binary / 'riser.200.plt').unlink()
    monkeypatch.chdir(folder)
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    return SimpleNamespace(folder=folder, case=case, run=run, there=there, root=tmp_path)


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


# --- case check out --remote ---------------------------------------------------------------

def test_out_without_remote_does_not_look_at_plts(shell, capsys):
    status, text = shell('case check out --case CS1', capsys)
    assert status == 0 and 'PLT' not in text.split('Out/Rst file check')[1].split('3 .out')[0]


def test_out_with_remote_says_what_stands_in_for_each_out(shell, capsys):
    status, text = shell('case check out --case CS1 --remote local', capsys)
    assert status == 0, text
    assert '100 ✓ — ✓ ascii' in text                      # the ASCII PLT here
    assert '200 ✓ — ✓ remote' in text                     # only a copy on the remote
    assert '300 ✓ — ✗ none' in text                       # nowhere
    assert '1 step(s) with a .out and no PLT that stands in for it, here or on the remote: 300' in text
    assert 'Convert them first: run post full --case CS1 --t1 300 --t2 300' in text


def test_out_every_step_covered_says_so(shell, world, capsys):
    (world.run / 'riser.300_0.out').unlink()
    status, text = shell('case check out --case CS1 --remote local', capsys)
    assert 'every .out has a PLT that stands in for it' in text


def test_out_with_a_remote_that_cannot_be_asked_says_so(shell, world, capsys):
    cf = yaml.safe_load((world.folder / '.cases.yml').read_text())
    cf['remotes']['other'] = str(world.root / 'o')
    (world.folder / '.cases.yml').write_text(yaml.safe_dump(cf))    # two remotes: none chosen
    status, text = shell('case check out --case CS1 --remote', capsys)
    assert 'The remote was not asked' in text and '300 ✓ — ✗ none' in text


# --- case check history --remote -----------------------------------------------------------

@pytest.fixture
def history(world):
    for sub, name, body in (('archive', 'riser1.othd', 'aaaa'), ('archive', 'riser2.othd', 'bbbb'),
                            ('cleaned', 'riser1.othd', 'cccc')):
        here = world.case / 'othd_files' / sub
        here.mkdir(parents=True, exist_ok=True)
        (here / name).write_text(body)
    there = world.there / 'othd_files'
    (there / 'archive').mkdir(parents=True)
    (there / 'cleaned').mkdir()
    (there / 'archive' / 'riser1.othd').write_text('aaaa')          # identical
    (there / 'archive' / 'riser2.othd').write_text('BBBB')          # same size, other md5
    (there / 'archive' / 'riser3.othd').write_text('dddd')          # only there
    # cleaned/riser1.othd is not on the remote
    return world


def test_history_remote_tells_identical_differing_missing_and_only_there(shell, history, capsys):
    status, text = shell('case check history --case CS1 --remote local', capsys)
    assert 'identical riser1.othd' in text
    assert 'differs othd_files/archive/riser2.othd: same size, different md5' in text
    assert 'not on the remote riser1.othd' in text                    # cleaned/riser1
    assert 'only on the remote riser3.othd' in text
    assert '1 of 3 identical, 1 differ, 1 not on the remote, 1 only on the remote' in text


def test_history_remote_picks_the_parts_like_the_plain_check(shell, history, capsys):
    status, text = shell('case check history --case CS1 --archive --remote local', capsys)
    assert '1 of 2 identical, 1 differ, 1 only on the remote' in text and 'not on the remote' not in text


def test_history_remote_all_identical_is_a_pass(shell, history, world, capsys):
    shutil.rmtree(world.there / 'othd_files')
    shutil.copytree(world.case / 'othd_files', world.there / 'othd_files')
    status, text = shell('case check history --case CS1 --remote local', capsys)
    assert '✓ History vs remote: 3 of 3 identical' in text


def test_history_without_remote_does_not_look_there(shell, history, capsys):
    status, text = shell('case check history --case CS1', capsys)
    assert 'History vs remote' not in text


def test_history_remote_that_cannot_be_asked_says_it_was_not_looked_at(shell, history, world, capsys):
    cf = yaml.safe_load((world.folder / '.cases.yml').read_text())
    cf['remotes']['other'] = str(world.root / 'o')
    (world.folder / '.cases.yml').write_text(yaml.safe_dump(cf))
    status, text = shell('case check history --case CS1 --remote', capsys)
    assert 'The remote was not looked at' in text
