"""`case upload` sends each file the way `auto` does (src/core/transfer): to a
temporary name, compared with the local file by size and md5, then renamed;
and writes what it sent to the ledger of the case's folder. A copy that
differs or is cut short is never left under the real name."""

import argparse
import os
import shutil
from unittest.mock import patch

import pytest

from src.commands.case.download_impl import command as transfer
from src.commands.case.download_impl.command import CaseUploadCommand
from src.core.transfer.cloud import file_md5
from src.core.transfer.ledger import Ledger
from test_scripts.checked_remote import CheckedRemote


class Remote(CheckedRemote):
    """The remote folder /r, played by a local one. `damage` changes what
    arrives: 'flip' a byte of the same length, 'cut' the last byte off."""

    def __init__(self, root, md5sum=True, damage=None, only=None):
        self.root, self.md5sum, self.damage, self.only = root, md5sum, damage, only

    def connect(self):
        return True

    def disconnect(self):
        pass

    def _local(self, path):
        return self.root / path.removeprefix('/r').lstrip('/')

    def remote_path_exists(self, path):
        return self._local(path).exists()

    def remote_is_dir(self, path):
        return self._local(path).is_dir()

    def remote_file_sizes(self, path):
        return {p.name: p.stat().st_size for p in self._local(path).iterdir() if p.is_file()}

    def make_remote_dir(self, path):
        self._local(path).mkdir(parents=True, exist_ok=True)
        return True

    def upload_file(self, local, path, callback=None):
        data = open(local, 'rb').read()
        if self.damage and (self.only is None or self.only in path):
            data = data[:-1] + (b'?' if self.damage == 'flip' else b'')
        self._local(path).write_bytes(data)


PLTS = {'riser.100.plt': b'aaaa', 'riser.200.plt': b'bbbbbb', 'riser.300.plt': b'cc'}


@pytest.fixture
def case(tmp_path):
    case = tmp_path / 'cases' / 'CS1'
    (case / 'binary').mkdir(parents=True)
    for name, data in PLTS.items():
        (case / 'binary' / name).write_bytes(data)
    (case / 'simflow.config').write_text('problem = riser\n')
    return case


@pytest.fixture
def there(tmp_path):
    (tmp_path / 'r' / 'CS1' / 'binary').mkdir(parents=True)
    return tmp_path / 'r'


def send_binary(case, ssh, **kw):
    cmd = CaseUploadCommand()
    cmd._sending = ('srv', str(case))
    ok = cmd.upload_binary_range(ssh, '/r/CS1', str(case), None, **kw)
    return cmd, ok


def on_remote(there):
    return sorted(p.name for p in (there / 'CS1' / 'binary').iterdir())


def test_a_sent_file_is_checked_renamed_and_written_to_the_ledger(case, there):
    cmd, ok = send_binary(case, Remote(there))
    assert ok and on_remote(there) == sorted(PLTS)            # no .part left
    assert cmd._sent == {'md5': 3}
    entries = Ledger(case.parent).data['srv']['CS1']
    assert sorted(entries) == sorted(f'binary/{n}' for n in PLTS)
    for rel, entry in entries.items():
        local = case / rel
        assert entry['verified'] == 'md5' and entry['md5'] == file_md5(local)
        assert entry['size'] == local.stat().st_size and entry['mtime'] == local.stat().st_mtime
        assert entry['path'] == f'/r/CS1/{rel}'


def test_a_copy_that_differs_is_not_left_and_not_recorded(case, there, capsys):
    (there / 'CS1' / 'binary' / 'riser.200.plt').write_bytes(b'old copy')
    cmd, ok = send_binary(case, Remote(there, damage='flip', only='riser.200'))
    assert not ok
    out = ' '.join(capsys.readouterr().out.split())
    assert 'riser.200.plt: md5 differs' in out
    # the older copy still stands under the real name; nothing temporary is left
    assert (there / 'CS1' / 'binary' / 'riser.200.plt').read_bytes() == b'old copy'
    assert on_remote(there) == ['riser.100.plt', 'riser.200.plt']
    # what went before it is recorded, the bad one and what came after are not
    assert list(Ledger(case.parent).data['srv']['CS1']) == ['binary/riser.100.plt']


def test_a_transfer_cut_short_is_removed(case, there, capsys):
    cmd, ok = send_binary(case, Remote(there, damage='cut'))
    assert not ok and on_remote(there) == []
    assert 'sent 3 of 4 bytes' in ' '.join(capsys.readouterr().out.split())
    assert not (case.parent / 'auto_logs').exists()


def test_a_remote_without_md5sum_is_checked_by_size_and_says_so(case, there, capsys):
    cmd, ok = send_binary(case, Remote(there, md5sum=False))
    assert ok and on_remote(there) == sorted(PLTS) and cmd._sent == {'size': 3}
    entries = Ledger(case.parent).data['srv']['CS1']
    assert {e['verified'] for e in entries.values()} == {'size'}
    cmd._report_checks()
    assert '3 by size only (no md5sum on the remote)' in ' '.join(capsys.readouterr().out.split())


def test_a_whole_folder_goes_file_by_file_checked(case, there):
    (case / 'binary' / 'sub').mkdir()
    (case / 'binary' / 'sub' / 'note.txt').write_text('n')
    cmd = CaseUploadCommand()
    cmd._sending = ('srv', str(case))
    assert cmd.upload_directory(Remote(there), '/r/CS1', str(case), 'binary')
    assert (there / 'CS1' / 'binary' / 'sub' / 'note.txt').read_text() == 'n'
    assert not list(there.rglob('.*.part'))
    assert 'binary/sub/note.txt' in Ledger(case.parent).data['srv']['CS1']
    assert cmd._sent == {'md5': 4}


def test_a_folder_stops_at_the_first_bad_copy(case, there):
    cmd = CaseUploadCommand()
    assert not cmd.upload_directory(Remote(there, damage='flip', only='riser.200'),
                                    '/r/CS1', str(case), 'binary')
    assert on_remote(there) == ['riser.100.plt']


def test_a_file_outside_the_case_in_hand_is_sent_but_not_recorded(case, there, tmp_path):
    other = tmp_path / 'loose.txt'
    other.write_text('x')
    cmd = CaseUploadCommand()
    cmd._sending = ('srv', str(case))
    cmd._send(Remote(there), str(other), '/r/CS1/loose.txt')
    assert (there / 'CS1' / 'loose.txt').read_text() == 'x'
    assert not (case.parent / 'auto_logs').exists()


def test_case_upload_files_end_to_end_writes_the_ledger(case, there, tmp_path, capsys):
    cmd = CaseUploadCommand()
    cmd._get_transfer_state_file = lambda: tmp_path / 'state.json'
    cmd.validate_remote = lambda name: {'user': 'u', 'ip': 'h', 'port': 22,
                                        'password': None, 'path': '/r'}
    ns = argparse.Namespace(what=None, case=str(case), to='srv', dir=None,
                            files='simflow.config', t1=None, t2=None, force=False,
                            resume=False, help=False, examples=False, remote_path='/r',
                            binary=False)
    with patch.object(transfer, 'SSHClientWrapper', return_value=Remote(there)):
        assert cmd.execute_upload(ns) == 0
    assert (there / 'CS1' / 'simflow.config').read_text() == 'problem = riser\n'
    entry = Ledger(case.parent).data['srv']['CS1']['simflow.config']
    assert entry['verified'] == 'md5' and entry['path'] == '/r/CS1/simflow.config'
    assert 'Checked on the remote: 1 by md5' in ' '.join(capsys.readouterr().out.split())
