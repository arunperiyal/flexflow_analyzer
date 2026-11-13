"""
The remote copy of the cases: what it holds, and the one way a file is sent
to it. `case upload` and `auto` both send through send_checked(), so a file
sent by hand and a file sent by `auto` are checked the same way.

What is already on the remote, case by case: {relative path: size}.

    cloud = open_cloud(conf)          # CloudError when it cannot be reached
    files = cloud.listing('case2')    # {'binary/riser.400.plt': 424, ...}
    cloud.close()

The remote `local` (remotes: {local: DIR} in .cases.yml) is a folder on this machine (the dummy cases,
tests). Any other name is a remote from `remote list`, reached over SFTP
with its password from ~/.flexflow/remotes.json -- the way `case upload`
connects, and what worked from both the login and a compute node in the
probe (the NAS may drop authorised keys, so key login is not relied on).

A listing goes as deep as a case's layout does (binary/, the history
folders, the run directory); a case not on the remote yet lists as empty.
"""

import hashlib
import os
import posixpath
import shlex
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

DEPTH = 3       # <case>/othd_files/archive/riserN.othd
CHUNK = 1 << 20


class Listing(dict):
    """{path: size} of what a remote holds, with `.mtimes` {path: seconds} when the remote
    says when each file was written."""

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.mtimes = {}


@dataclass(frozen=True)
class PutResult:
    """One file sent. verified: 'md5' (checked on the remote), 'size' (the remote
    has no md5sum, only the size was compared), 'snapshot' (a file that is still
    being written: not checked), or '' when it failed."""
    ok: bool
    size: int = 0
    md5: Optional[str] = None
    verified: str = ''
    detail: str = ''


def file_md5(path) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(CHUNK), b''):
            h.update(block)
    return h.hexdigest()


class CloudError(RuntimeError):
    pass


def remote_md5(ssh, path: str) -> Optional[str]:
    """md5 of a file on the remote `ssh` is connected to, or None when the
    remote cannot compute one (no md5sum, no such file)."""
    try:
        _, out, _ = ssh.ssh_client.exec_command(f"md5sum {shlex.quote(path)}", timeout=600)
        text = out.read().decode(errors='replace').strip()
        if out.channel.recv_exit_status() != 0 or not text:
            return None
        word = text.split()[0]
        return word if len(word) == 32 else None
    except Exception:
        return None


def _drop(ssh, path: str):
    try:
        ssh.sftp_client.remove(path)
    except Exception:
        pass


def send_checked(ssh, local, dest: str, snapshot: bool = False, callback=None,
                 where: str = 'the remote', mkdir: bool = True) -> PutResult:
    """Send `local` to the remote path `dest` over SFTP: to a temporary name,
    compared with the local file (size, and md5 when the remote has md5sum),
    then renamed over the real name. A failure leaves no file under the real
    name and removes the temporary one. `snapshot` is for a file that is
    still being written: it is sent and renamed, not checked. `mkdir=False`
    when the caller has already made sure the folder is there."""
    local = Path(local)
    parent = posixpath.dirname(dest)
    tmp = posixpath.join(parent, f".{posixpath.basename(dest)}.part")
    try:
        size = local.stat().st_size
        want = None if snapshot else file_md5(local)
        if mkdir and not ssh.make_remote_dir(parent):
            return PutResult(False, size, want, '', f"cannot create {parent}")
        if callback is None:
            ssh.upload_file(str(local), tmp)
        else:
            ssh.upload_file(str(local), tmp, callback)
        stat_ = ssh.remote_stat(tmp)
        if stat_ is None:
            return PutResult(False, size, want, '', "the sent file is not there")
        if not snapshot and stat_[0] != size:
            _drop(ssh, tmp)
            return PutResult(False, size, want, '',
                             f"sent {stat_[0]} of {size} bytes")
        level, got = 'snapshot', None
        if not snapshot:
            got = remote_md5(ssh, tmp)
            if got is None:
                level = 'size'                 # no md5sum there: the size matched
            elif got != want:
                _drop(ssh, tmp)
                return PutResult(False, size, want, '',
                                 f"md5 differs on {where} ({got} there, {want} sent)")
            else:
                level = 'md5'
        ssh.sftp_client.posix_rename(tmp, dest)
        return PutResult(True, size, want, level)
    except Exception as e:
        _drop(ssh, tmp)
        return PutResult(False, 0, None, '', f"{type(e).__name__}: {e}")


class LocalCloud:
    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_dir():
            raise CloudError(f"{self.root} is not a folder")
        self.where = str(self.root)

    def listing(self, case_name: str) -> 'Listing':
        base = self.root / case_name
        found = Listing()
        if not base.is_dir():
            return found
        for dirpath, dirnames, filenames in os.walk(base):
            rel = Path(dirpath).relative_to(base)
            if len(rel.parts) >= DEPTH:
                dirnames[:] = []
            for name in filenames:
                st = (Path(dirpath) / name).stat()
                found[(rel / name).as_posix()] = st.st_size
                found.mtimes[(rel / name).as_posix()] = st.st_mtime
        return found

    def path_of(self, case_name: str, rel: str) -> str:
        return str(self.root / case_name / rel)

    def md5(self, case_name: str, rel: str) -> Optional[str]:
        """md5 of <root>/<case>/<rel> as it is now, or None when it is not there."""
        try:
            return file_md5(self.root / case_name / rel)
        except OSError:
            return None

    def put(self, local, case_name: str, rel: str, snapshot: bool = False) -> PutResult:
        """Copy `local` to <root>/<case>/<rel>: to a temporary name first, checked
        (md5 of both), then renamed, so the real name never holds a half file."""
        local = Path(local)
        dest = self.root / case_name / rel
        tmp = dest.with_name(f".{dest.name}.part")
        try:
            size = local.stat().st_size
            want = None if snapshot else file_md5(local)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(local, 'rb') as src, open(tmp, 'wb') as out:
                for block in iter(lambda: src.read(CHUNK), b''):
                    out.write(block)
            if snapshot:
                os.replace(tmp, dest)
                return PutResult(True, size, None, 'snapshot')
            got = file_md5(tmp)
            if got != want:
                tmp.unlink(missing_ok=True)
                return PutResult(False, size, want, '', f"md5 differs after the copy "
                                                        f"({got} here, {want} sent)")
            os.replace(tmp, dest)
            return PutResult(True, size, want, 'md5')
        except OSError as e:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            return PutResult(False, 0, None, '', f"{e.strerror or e}")

    def close(self):
        pass


class SftpCloud:
    def __init__(self, remote: dict, root: str):
        from src.utils.ssh_client import SSHClientWrapper
        self.root = root
        self.where = f"{remote.get('name')} ({remote.get('user')}@{remote.get('ip')}:{root})"
        if not remote.get('password'):
            raise CloudError(f"remote '{remote.get('name')}' has no password in remotes.json")
        self.ssh = SSHClientWrapper(host=remote['ip'], username=remote['user'],
                                    password=remote['password'], port=remote.get('port') or 22)
        try:
            self.ssh.connect()
        except Exception as e:
            raise CloudError(f"cannot log in to {self.where}: {e}")
        if not self.ssh.remote_is_dir(root):
            self.close()
            raise CloudError(f"{root} is not a folder on {remote.get('name')}")

    def listing(self, case_name: str) -> 'Listing':
        found = Listing()
        sftp = self.ssh.sftp_client

        def walk(path, rel, depth):
            try:
                entries = sftp.listdir_attr(path)
            except FileNotFoundError:
                return
            except Exception as e:
                raise CloudError(f"cannot list {path}: {e}")
            for a in entries:
                child_rel = posixpath.join(rel, a.filename) if rel else a.filename
                if a.st_mode is not None and stat.S_ISDIR(a.st_mode):
                    if depth < DEPTH:
                        walk(posixpath.join(path, a.filename), child_rel, depth + 1)
                else:
                    found[child_rel] = a.st_size
                    if a.st_mtime is not None:
                        found.mtimes[child_rel] = float(a.st_mtime)
        walk(posixpath.join(self.root, case_name), '', 0)
        return found

    def path_of(self, case_name: str, rel: str) -> str:
        return posixpath.join(self.root, case_name, rel)

    def md5(self, case_name: str, rel: str) -> Optional[str]:
        """md5 of <root>/<case>/<rel> as it is now, or None when the remote
        cannot compute one (no md5sum there, or no such file)."""
        return remote_md5(self.ssh, posixpath.join(self.root, case_name, rel))

    def put(self, local, case_name: str, rel: str, snapshot: bool = False) -> PutResult:
        """Send `local` to <root>/<case>/<rel>, checked (send_checked)."""
        return send_checked(self.ssh, local, posixpath.join(self.root, case_name, rel),
                            snapshot=snapshot, where=self.where)

    def close(self):
        try:
            self.ssh.disconnect()
        except Exception:
            pass


def open_for_folder(folder, remote: Optional[str]):
    """The remote named `remote` as the folder of cases `folder` uses it (the
    folder in its .cases.yml `remotes:`); CloudError when it cannot be used."""
    from types import SimpleNamespace
    from src.core import cases_file
    try:
        cf = cases_file.read(folder)
    except cases_file.CasesFileError as e:
        raise CloudError(str(e))
    listed = ', '.join(cf.remotes) or 'none yet'
    if not remote:
        raise CloudError(f"which remote? --remote NAME or `use remote:NAME` "
                         f"({cases_file.FILENAME} lists: {listed})")
    path = cf.remotes.get(remote)
    if not path:
        raise CloudError(f"{cf.path} has no folder for remote '{remote}' (lists: {listed}); "
                         f"`auto init --remote {remote} --path DIR` adds it")
    if path == 'EDIT_ME':
        raise CloudError(f"set the folder of remote '{remote}' in {cf.path} (it still says EDIT_ME)")
    return open_cloud(SimpleNamespace(remote=remote, path=path, is_local=remote == 'local'))


def open_cloud(conf):
    """The remote conf names; CloudError when it cannot be used."""
    if conf.is_local:
        return LocalCloud(conf.path)
    from src.utils.remote_config import RemoteConfig
    remote = RemoteConfig().get_remote(conf.remote)
    if remote is None:
        raise CloudError(f"remote '{conf.remote}' is not set up (`remote list`)")
    return SftpCloud(remote, conf.path)
