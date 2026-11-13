"""`case check plt --verify`: each binary PLT against its copy on the remote, by
size and md5 read now on both sides. What matches goes in the ledger as
verified; what does not comes out of it. Exit code 0 only when all match."""

import os
import shutil
from types import SimpleNamespace

import pytest
import yaml

from src.commands.case.check_impl.command import execute_case_check
from src.core.transfer.cloud import LocalCloud, SftpCloud, file_md5
from src.core.transfer.ledger import Ledger
from src.core.transfer.verify import verify_plts
from test_scripts.plt_files import write_plt
from test_scripts.test_auto_apply import FakeSsh

STEPS = (100, 200, 300)


@pytest.fixture
def world(tmp_path):
    """cases/CS1 with three whole binary PLTs, and r/CS1 holding the same."""
    case = tmp_path / 'cases' / 'CS1'
    (case / 'binary').mkdir(parents=True)
    (case / 'simflow.config').write_text('problem = riser\n')
    for i, step in enumerate(STEPS):
        write_plt(case / 'binary' / f'riser.{step}.plt', npts=8 + i)
    there = tmp_path / 'r' / 'CS1' / 'binary'
    shutil.copytree(case / 'binary', there)
    (tmp_path / 'cases' / '.cases.yml').write_text(yaml.safe_dump(
        {'cases': [{'name': 'CS1', 'path': 'CS1'}], 'remotes': {'local': str(tmp_path / 'r')}, 'auto': {}}))
    return SimpleNamespace(case=case, there=there, folder=tmp_path / 'cases',
                           cloud=LocalCloud(tmp_path / 'r'))


def verify(world, **kw):
    ledger = Ledger(world.folder)
    return verify_plts(world.case, 'riser', world.cloud, 'local', ledger, **kw), ledger


def names(steps):
    return [f'riser.{s}.plt' for s in steps]


def test_all_match_and_are_written_to_the_ledger(world):
    result, ledger = verify(world)
    assert result.ok and result.verified == names(STEPS)
    assert result.summary() == 'PLT verify: 3 of 3 verified'
    for step in STEPS:
        local = world.case / 'binary' / f'riser.{step}.plt'
        entry = ledger.get('local', 'CS1', f'binary/riser.{step}.plt')
        assert entry['verified'] == 'md5' and entry['md5'] == file_md5(local)
        assert entry['mtime'] == local.stat().st_mtime
        assert entry['path'] == str(world.there / local.name)


def test_one_that_differs_at_the_same_size_comes_out_of_the_ledger(world):
    verify(world)                                               # all three recorded
    copy = world.there / 'riser.200.plt'
    data = bytearray(copy.read_bytes())
    data[-1] ^= 0xFF
    copy.write_bytes(bytes(data))
    result, ledger = verify(world)
    assert not result.ok and result.verified == names((100, 300))
    assert 'md5' in result.differs['riser.200.plt']
    assert ledger.get('local', 'CS1', 'binary/riser.200.plt') is None
    assert ledger.get('local', 'CS1', 'binary/riser.100.plt')['verified'] == 'md5'
    assert result.summary() == 'PLT verify: 2 of 3 verified, 1 differ'


def test_another_size_is_told_without_reading_the_file(world):
    (world.there / 'riser.300.plt').write_bytes(b'short')
    result, _ = verify(world)
    assert 'bytes here, 5 there' in result.differs['riser.300.plt']


def test_one_missing_there_and_one_only_there(world):
    (world.there / 'riser.100.plt').unlink()
    shutil.copy(world.there / 'riser.200.plt', world.there / 'riser.400.plt')
    result, ledger = verify(world)
    assert not result.ok
    assert result.not_there == ['riser.100.plt'] and result.only_there == ['riser.400.plt']
    assert ledger.get('local', 'CS1', 'binary/riser.100.plt') is None


def test_a_local_plt_cut_short_is_never_verified_even_with_the_same_copy(world):
    local = world.case / 'binary' / 'riser.200.plt'
    local.write_bytes(local.read_bytes()[:-10])
    shutil.copy(local, world.there / 'riser.200.plt')           # the same bad file there
    result, ledger = verify(world)
    assert not result.ok and 'cut short' in result.broken['riser.200.plt']
    assert ledger.get('local', 'CS1', 'binary/riser.200.plt') is None


def test_a_broken_plt_says_how_to_make_it_again(world):
    run = world.case / 'RUN_1'
    run.mkdir()
    for step in (100, 200, 300):
        local = world.case / 'binary' / f'riser.{step}.plt'
        local.write_bytes(local.read_bytes()[:-10])
    (run / 'riser.100.plt').write_text('ascii')                 # 100: its ASCII PLT is there
    (run / 'riser.200_0.out').write_text('out')                 # 200: only its .out
    result = verify_plts(world.case, 'riser', world.cloud, 'local', run_dir=run)
    assert result.rebuild == {
        'riser.100.plt': 'run post convert CS1 --t1 100 --t2 100',
        'riser.200.plt': 'run post full CS1 --t1 200 --t2 200',
        'riser.300.plt': 'no ASCII PLT and no .out of this step are left to make it from'}


def test_a_restart_that_wrote_the_local_plt_again(world):
    verify(world)
    write_plt(world.case / 'binary' / 'riser.300.plt', npts=20)  # computed again, another size
    result, ledger = verify(world)
    assert list(result.differs) == ['riser.300.plt']
    assert ledger.get('local', 'CS1', 'binary/riser.300.plt') is None


def nas(world, tmp_path, **kw):
    cloud = object.__new__(SftpCloud)
    cloud.root, cloud.where, cloud.ssh = str(tmp_path / 'r'), 'nas', FakeSsh(md5sum=False)
    cloud.listing = world.cloud.listing
    for k, v in kw.items():
        setattr(cloud.ssh, k, v)
    return cloud


def test_a_remote_without_md5sum_is_read_back_and_verified_by_md5(world, tmp_path):
    ledger = Ledger(world.folder)
    result = verify_plts(world.case, 'riser', nas(world, tmp_path, open=open), 'nas', ledger)
    assert result.ok and result.verified == names(STEPS)
    assert ledger.get('nas', 'CS1', 'binary/riser.100.plt')['verified'] == 'md5'
    # and a copy that differs is caught the same way
    copy = world.there / 'riser.200.plt'
    copy.write_bytes(copy.read_bytes()[:-1] + b'?')
    result = verify_plts(world.case, 'riser', nas(world, tmp_path, open=open), 'nas', ledger)
    assert list(result.differs) == ['riser.200.plt']


def test_a_copy_that_cannot_be_read_back_is_size_only_and_not_ok(world, tmp_path):
    ledger = Ledger(world.folder)
    result = verify_plts(world.case, 'riser', nas(world, tmp_path), 'nas', ledger)
    assert not result.ok and result.size_only == names(STEPS)
    assert ledger.get('nas', 'CS1', 'binary/riser.100.plt')['verified'] == 'size'
    assert result.summary() == 'PLT verify: 0 of 3 verified, 3 by size only'


def test_window_and_freq_pick_the_steps(world):
    result, _ = verify(world, window=(150, None))
    assert result.verified == names((200, 300))
    result, _ = verify(world, window=(None, 250), freq=200)
    assert result.verified == names((200,))


def test_an_emptied_binary_is_fine_when_the_remote_is_as_recorded(world):
    verify(world)                                               # verified, in the ledger
    shutil.rmtree(world.case / 'binary')                        # deleted here to save space
    result, ledger = verify(world)
    assert result.ok and result.kept_there == names(STEPS) and not result.only_there
    assert result.summary() == ('PLT verify: binary/ is empty here, '
                                '3 only on the remote, as recorded')
    assert ledger.get('local', 'CS1', 'binary/riser.100.plt')['verified'] == 'md5'   # kept


def test_a_remote_only_copy_that_changed_since_it_was_verified(world):
    verify(world)
    shutil.rmtree(world.case / 'binary')
    copy = world.there / 'riser.200.plt'
    copy.write_bytes(copy.read_bytes()[:-1] + b'?')             # same size, another md5
    (world.there / 'riser.300.plt').write_bytes(b'short')
    result, _ = verify(world)
    assert not result.ok and result.kept_there == names((100,))
    assert result.changed_there == {'riser.200.plt': 'another md5 than when verified',
                                    'riser.300.plt': '5 bytes there, '
                                    f"{len(world_plt(2)):,} when verified"}


def world_plt(i):
    from test_scripts.plt_files import plt_bytes
    return plt_bytes(npts=8 + i)


def test_remote_only_with_no_record_is_listed_apart(world):
    shutil.rmtree(world.case / 'binary')                        # never verified from here
    result, _ = verify(world)
    assert result.ok and result.only_there == names(STEPS) and not result.kept_there
    assert 'not recorded' in result.summary()


def test_nothing_here_and_nothing_there_is_not_ok(world):
    shutil.rmtree(world.case / 'binary')
    shutil.rmtree(world.there)
    result, _ = verify(world)
    assert not result.ok and result.summary() == 'PLT verify: no binary PLT here or on the remote'


def test_steps_of_the_series_in_neither_place(world):
    (world.case / 'binary' / 'riser.200.plt').unlink()          # 200: only on the remote
    result, _ = verify(world, window=(100, 500), freq=100)
    assert result.nowhere == [400, 500] and not result.ok
    assert result.verified == names((100, 300)) and result.only_there == names((200,))
    assert result.summary().endswith('2 in neither place')
    # an open window names no series, so nothing is called lost
    result, _ = verify(world, window=(100, None), freq=100)
    assert result.nowhere == [] and result.ok


# --- the command -----------------------------------------------------------------

def run(world, **kw):
    ns = dict(check_subcommand='plt', case=str(world.case), verify=True, remote='local',
              t1=None, t2=None, freq=None, verbose=False, help=False, examples=False)
    ns.update(kw)
    return execute_case_check(SimpleNamespace(**ns))


def test_the_command_exits_0_when_all_are_verified(world, capsys):
    assert run(world) == 0
    out = ' '.join(capsys.readouterr().out.split())
    assert 'PLT verify: 3 of 3 verified' in out and '100, 200, 300' in out
    assert Ledger(world.folder).get('local', 'CS1', 'binary/riser.100.plt')


def test_the_command_exits_1_and_names_what_is_wrong(world, capsys):
    (world.there / 'riser.100.plt').unlink()
    assert run(world, verbose=True) == 1
    out = ' '.join(capsys.readouterr().out.split())
    assert 'not on the remote 100' in out and '2 of 3 verified, 1 not on the remote' in out
    assert 'riser.200.plt verified' in out                       # -v: a line per file


def test_the_command_needs_a_remote_it_knows(world, capsys):
    assert run(world, remote=None) == 1
    assert 'which remote?' in capsys.readouterr().out
    assert run(world, remote='nowhere') == 1
    assert "no folder for remote 'nowhere'" in ' '.join(capsys.readouterr().out.split())


def test_without_verify_the_plain_check_still_runs(world, capsys):
    assert run(world, verify=False) is None
    assert 'PLT file check' in capsys.readouterr().out
