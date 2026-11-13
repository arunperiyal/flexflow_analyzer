"""Stand-ins for the remote side of send_checked (src/core/transfer/cloud.py),
for the `case upload` tests: a file goes to `.<name>.part`, its size and md5
are read back, and it is renamed to its real name.

    ssh = checked_mock()                 # a MagicMock that passes the check
    class FakeRemote(CheckedRemote): ... # a fake over a local folder (_local(path))
    final(path)                          # the real name of a `.part` path
"""

import hashlib
import os
import posixpath
import shlex
from pathlib import Path
from unittest.mock import MagicMock


def final(path: str) -> str:
    """'/r/c/.a.plt.part' -> '/r/c/a.plt'; any other path as it is."""
    head, name = posixpath.split(path)
    if name.startswith('.') and name.endswith('.part'):
        name = name[1:-len('.part')]
    return posixpath.join(head, name) if head else name


def _md5(path) -> str:
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def checked_mock(ssh=None, md5sum=True):
    """A MagicMock (or the one given) whose remote reports what was sent to it."""
    ssh = MagicMock() if ssh is None else ssh
    there = {}                                   # remote path -> (size, md5)

    def upload(local, remote, callback=None):
        there[remote] = (os.path.getsize(local), _md5(local))

    def exec_command(cmd, timeout=None):
        path = shlex.split(cmd)[1]
        out = MagicMock()
        ok = md5sum and path in there
        out.read.return_value = f"{there[path][1]}  {path}\n".encode() if ok else b''
        out.channel.recv_exit_status.return_value = 0 if ok else 1
        return None, out, None

    def rename(a, b):
        there[b] = there.pop(a)

    ssh.upload_file.side_effect = upload
    ssh.remote_stat.side_effect = lambda p: (there[p][0], 0) if p in there else None
    ssh.ssh_client.exec_command.side_effect = exec_command
    ssh.sftp_client.posix_rename.side_effect = rename
    ssh.there = there
    return ssh


class CheckedRemote:
    """The calls send_checked makes beyond upload_file, for a fake that maps a
    remote path to a local one with _local(path)."""

    md5sum = True

    @property
    def ssh_client(self):
        return self

    @property
    def sftp_client(self):
        return self

    @property
    def channel(self):
        return self

    def remote_stat(self, path):
        p = self._local(path)
        return (p.stat().st_size, p.stat().st_mtime) if p.exists() else None

    def exec_command(self, cmd, timeout=None):
        p = self._local(shlex.split(cmd)[1])
        ok = self.md5sum and p.is_file()
        self._rc, self._out = (0, f"{_md5(p)}  {p}\n".encode()) if ok else (1, b'')
        return None, self, None

    def read(self):
        return self._out

    def recv_exit_status(self):
        return self._rc

    def posix_rename(self, a, b):
        os.replace(self._local(a), self._local(b))

    def remove(self, path):
        os.remove(self._local(path))
