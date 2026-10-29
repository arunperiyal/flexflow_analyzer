"""`case upload|download history [--archive] [--cleaned] [--compiled]`: the
OTHD/OISD history of `case organise history`. The compiled file goes after
the runs, and is left newer than them on the other side (so the readers take
it) only when it holds all they do."""

import argparse
import os
import shutil
from unittest.mock import patch

import pytest

from src.commands.case.download_impl import command as transfer
from src.commands.case.download_impl.command import CaseDownloadCommand
from src.core import history


class FakeRemote:
    """An SSH stand-in over a local directory that plays the remote case /r/CS1."""

    def __init__(self, root):
        self.root = root
        self.sent = []

    def connect(self):
        return True

    def disconnect(self):
        pass

    def _local(self, path):
        return self.root / path.removeprefix('/r/CS1').lstrip('/')

    def remote_path_exists(self, path):
        return self._local(path).exists()

    def remote_is_dir(self, path):
        return self._local(path).is_dir()

    def list_remote_dir(self, path):
        return os.listdir(self._local(path))

    def remote_stat(self, path):
        p = self._local(path)
        return (p.stat().st_size, p.stat().st_mtime) if p.exists() else None

    def set_remote_mtime(self, path, mtime):
        os.utime(self._local(path), (mtime, mtime))

    def make_remote_dir(self, path):
        self._local(path).mkdir(parents=True, exist_ok=True)
        return True

    def upload_file(self, local, path, callback=None):
        self.sent.append(path)
        shutil.copy(local, self._local(path))

    def download_file(self, path, local, callback=None):
        self.sent.append(path)
        os.makedirs(os.path.dirname(local), exist_ok=True)
        shutil.copy(self._local(path), local)


def write(path, text, mtime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    os.utime(path, (mtime, mtime))


def make_case(root, runs=(1, 2), compiled_at=300):
    """A case with runs in archive/ and cleaned/ (mtime 100+N) and a compiled
    file at `compiled_at`, for both types."""
    (root / 'simflow.config').parent.mkdir(parents=True, exist_ok=True)
    (root / 'simflow.config').write_text('problem = riser\n')
    for ext in history.TYPES:
        for n in runs:
            write(root / f'{ext}_files/archive/riser{n}.{ext}', f'raw {n}', 100 + n)
            write(root / f'{ext}_files/cleaned/riser{n}.{ext}', f'{n}', 100 + n)
        for d in ('archive', 'cleaned'):
            os.utime(root / f'{ext}_files/{d}', (200, 200))
        if compiled_at:
            write(root / f'{ext}_files/riser.{ext}', 'joined', compiled_at)
    return root


def files(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob('*')
                  if p.is_file() and p.name != 'simflow.config')


@pytest.fixture
def remote(tmp_path):
    return make_case(tmp_path / 'remote')


@pytest.fixture
def local(tmp_path):
    here = tmp_path / 'local'
    here.mkdir()
    (here / 'simflow.config').write_text('problem = riser\n')
    return here


def test_download_history_carries_all_three_and_keeps_compiled_fresh(remote, local):
    ssh = FakeRemote(remote)
    assert CaseDownloadCommand().download_history(ssh, '/r/CS1', str(local),
                                                   ['archive', 'cleaned', 'compiled'])
    assert files(local) == files(remote)
    for ext in history.TYPES:
        assert history.compiled_is_fresh(local, ext, 'riser')
        assert history.read_files(local, ext, 'riser') == [local / f'{ext}_files/riser.{ext}']
    # the compiled file is sent after the runs of its type
    othd = [p for p in ssh.sent if 'othd_files' in p]
    assert othd[-1].endswith('othd_files/riser.othd')


def test_download_only_the_named_sets(remote, local):
    assert CaseDownloadCommand().download_history(FakeRemote(remote), '/r/CS1', str(local),
                                                   ['cleaned'])
    assert files(local) == sorted(f'{e}_files/cleaned/riser{n}.{e}'
                                  for e in history.TYPES for n in (1, 2))


def test_a_stale_compiled_file_stays_stale(tmp_path, local):
    remote = make_case(tmp_path / 'remote', compiled_at=150)   # older than archive/
    assert CaseDownloadCommand().download_history(FakeRemote(remote), '/r/CS1', str(local),
                                                   ['archive', 'cleaned', 'compiled'])
    assert not history.compiled_is_fresh(local, 'othd', 'riser')
    assert len(history.read_files(local, 'othd', 'riser')) == 2


def test_compiled_older_than_runs_only_here(remote, local, capsys):
    write(local / 'othd_files/archive/riser3.othd', 'raw 3', 100)
    assert CaseDownloadCommand().download_history(FakeRemote(remote), '/r/CS1', str(local),
                                                   ['compiled'])
    assert not history.compiled_is_fresh(local, 'othd', 'riser')
    assert history.compiled_is_fresh(local, 'oisd', 'riser')
    assert 'run(s) 3 only in' in ' '.join(capsys.readouterr().out.split())


def test_archived_runs_already_there_are_not_sent_again(remote, local, capsys):
    write(local / 'othd_files/archive/riser1.othd', 'raw 1', 100)
    ssh = FakeRemote(remote)
    assert CaseDownloadCommand().download_history(ssh, '/r/CS1', str(local), ['archive'])
    assert '/r/CS1/othd_files/archive/riser1.othd' not in ssh.sent
    assert len(ssh.sent) == 4 - 1 + 1      # 3 archived files plus simflow.config
    assert '1 archived run(s) already' in capsys.readouterr().out


def test_flat_parts_go_with_archive(remote, local):
    write(remote / 'othd_files/riser3.othd', 'raw 3', 400)
    assert CaseDownloadCommand().download_history(FakeRemote(remote), '/r/CS1', str(local),
                                                   ['archive'])
    assert (local / 'othd_files/riser3.othd').read_text() == 'raw 3'


def test_upload_history(tmp_path):
    here = make_case(tmp_path / 'local')
    there = tmp_path / 'remote'
    there.mkdir()
    ssh = FakeRemote(there)
    assert CaseDownloadCommand().upload_history(ssh, '/r/CS1', str(here),
                                                ['cleaned', 'compiled'])
    assert files(there) == sorted([f'{e}_files/cleaned/riser{n}.{e}' for e in history.TYPES
                                   for n in (1, 2)] +
                                  [f'{e}_files/riser.{e}' for e in history.TYPES])
    assert history.compiled_is_fresh(there, 'oisd', 'riser')


def test_nothing_to_send(tmp_path, local, capsys):
    bare = tmp_path / 'remote'
    bare.mkdir()
    (bare / 'simflow.config').write_text('problem = riser\n')
    assert not CaseDownloadCommand().download_history(FakeRemote(bare), '/r/CS1', str(local),
                                                       ['archive'])
    assert 'No archive history' in capsys.readouterr().out


def namespace(**kw):
    base = dict(what='history', case=None, to='srv', dir=None, files=None, t1=None, t2=None,
                force=False, resume=False, help=False, examples=False, remote_path='/r',
                binary=False, archive=False, cleaned=False, compiled=False)
    base.update(kw)
    return argparse.Namespace(**base)


def command(tmp_path):
    cmd = CaseDownloadCommand()
    cmd._get_transfer_state_file = lambda: tmp_path / 'state.json'
    cmd.validate_remote = lambda name: {'user': 'u', 'ip': 'h', 'port': 22,
                                        'password': None, 'path': '/r'}
    cmd.construct_remote_case_path = lambda base, path: '/r/CS1'
    return cmd


def test_case_upload_history_end_to_end(tmp_path):
    here = make_case(tmp_path / 'CS1')
    there = tmp_path / 'remote'
    there.mkdir()
    with patch.object(transfer, 'SSHClientWrapper', return_value=FakeRemote(there)):
        assert command(tmp_path).execute_upload(namespace(case=str(here), compiled=True)) == 0
    assert files(there) == ['oisd_files/riser.oisd', 'othd_files/riser.othd']


def test_set_flags_need_history(tmp_path, capsys):
    ns = namespace(what='binary', case=str(tmp_path), cleaned=True)
    assert command(tmp_path).execute_upload(ns) == 1
    assert 'use `case upload history`' in capsys.readouterr().out


def test_history_takes_no_step_window(tmp_path, capsys):
    assert command(tmp_path).execute_upload(namespace(case=str(tmp_path), t1=10)) == 1
    assert 'drop --t1/--t2/--freq' in capsys.readouterr().out
