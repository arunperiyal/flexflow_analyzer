"""`case upload|download binary --missing`: only the binary/ files the other
side lacks, or holds at another size (a copy cut short)."""

import argparse
import os
import shutil
from unittest.mock import patch

import pytest

from src.commands.case.download_impl import command as transfer
from src.commands.case.download_impl.command import CaseDownloadCommand, select_missing


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

    def remote_file_sizes(self, path):
        return {p.name: p.stat().st_size for p in self._local(path).iterdir() if p.is_file()}

    def make_remote_dir(self, path):
        self._local(path).mkdir(parents=True, exist_ok=True)
        return True

    def upload_file(self, local, path, callback=None):
        self.sent.append(os.path.basename(path))
        shutil.copy(local, self._local(path))

    def download_file(self, path, local, callback=None):
        self.sent.append(os.path.basename(path))
        os.makedirs(os.path.dirname(local), exist_ok=True)
        shutil.copy(self._local(path), local)


def binary(root, files):
    d = root / 'binary'
    d.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (d / name).write_text(text)
    return root


FULL = {'riser.100.plt': 'aaaa', 'riser.200.plt': 'bbbb', 'riser.300.plt': 'cccc',
        'main.py': 'print()'}


@pytest.fixture
def remote(tmp_path):
    root = binary(tmp_path / 'remote', FULL)
    (root / 'binary' / '__pycache__').mkdir()
    return root


def test_select_missing():
    here = {'a': 1, 'b': 2, 'c': 3}
    assert select_missing(['a', 'b', 'c'], here, {'a': 1, 'b': 5}) == (['c'], ['b'])


def test_download_missing_skips_what_is_here(remote, tmp_path, capsys):
    local = binary(tmp_path / 'local', {'riser.100.plt': 'aaaa', 'riser.200.plt': 'bb'})
    ssh = FakeRemote(remote)
    assert CaseDownloadCommand().download_binary_range(ssh, '/r/CS1', str(local), None,
                                                       missing=True)
    assert sorted(ssh.sent) == ['main.py', 'riser.200.plt', 'riser.300.plt']
    assert (local / 'binary/riser.200.plt').read_text() == 'bbbb'
    out = ' '.join(capsys.readouterr().out.split())
    assert '3 of 4 file(s)' in out and '1 at another size' in out and '1 already there' in out


def test_download_missing_within_a_window(remote, tmp_path):
    local = binary(tmp_path / 'local', {'riser.200.plt': 'bbbb'})
    ssh = FakeRemote(remote)
    assert CaseDownloadCommand().download_binary_range(ssh, '/r/CS1', str(local), (200, 300),
                                                       missing=True)
    assert ssh.sent == ['riser.300.plt']


def test_nothing_missing_sends_nothing(remote, tmp_path):
    local = binary(tmp_path / 'local', FULL)
    ssh = FakeRemote(remote)
    assert CaseDownloadCommand().download_binary_range(ssh, '/r/CS1', str(local), None,
                                                       missing=True)
    assert ssh.sent == []


def test_upload_missing(tmp_path):
    local = binary(tmp_path / 'local', FULL)
    there = binary(tmp_path / 'remote', {'riser.100.plt': 'aaaa'})
    ssh = FakeRemote(there)
    assert CaseDownloadCommand().upload_binary_range(ssh, '/r/CS1', str(local), None,
                                                     missing=True)
    assert sorted(ssh.sent) == ['main.py', 'riser.200.plt', 'riser.300.plt']


def test_upload_missing_to_a_remote_without_binary(tmp_path):
    local = binary(tmp_path / 'local', FULL)
    there = tmp_path / 'remote'
    there.mkdir()
    ssh = FakeRemote(there)
    assert CaseDownloadCommand().upload_binary_range(ssh, '/r/CS1', str(local), None,
                                                     force=True, missing=True)
    assert len(ssh.sent) == 4


def namespace(**kw):
    base = dict(what='binary', case=None, from_remote='srv', to=None, dir=None, files=None,
                t1=None, t2=None, freq=None, force=False, resume=False, help=False,
                examples=False, remote_path='/r', binary=False, missing=True)
    base.update(kw)
    return argparse.Namespace(**base)


def command(tmp_path):
    cmd = CaseDownloadCommand()
    cmd._get_transfer_state_file = lambda: tmp_path / 'state.json'
    cmd.validate_remote = lambda name: {'user': 'u', 'ip': 'h', 'port': 22,
                                        'password': None, 'path': '/r'}
    cmd.construct_remote_case_path = lambda base, path: '/r/CS1'
    return cmd


def test_case_download_binary_missing_end_to_end(remote, tmp_path):
    local = binary(tmp_path / 'CS1', {'riser.100.plt': 'aaaa'})
    ssh = FakeRemote(remote)
    with patch.object(transfer, 'SSHClientWrapper', return_value=ssh):
        assert command(tmp_path).execute_download(namespace(case=str(local))) == 0
    assert sorted(n for n in ssh.sent if n != 'simflow.config') == \
        ['main.py', 'riser.200.plt', 'riser.300.plt']


def test_missing_is_kept_for_resume(tmp_path):
    cmd = command(tmp_path)
    state = cmd._build_transfer_state('download', 'srv', '/r', 'CS1', [], ['binary'],
                                      False, False, missing=True)
    assert state['missing'] is True


def test_missing_needs_binary(tmp_path, capsys):
    ns = namespace(what='rst', case=str(tmp_path))
    assert command(tmp_path).execute_download(ns) == 1
    assert 'use `case download binary --missing`' in ' '.join(capsys.readouterr().out.split())
