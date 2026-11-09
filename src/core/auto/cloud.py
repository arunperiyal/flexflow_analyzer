"""
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

import os
import posixpath
import stat
from pathlib import Path
from typing import Dict

DEPTH = 3       # <case>/othd_files/archive/riserN.othd


class CloudError(RuntimeError):
    pass


class LocalCloud:
    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_dir():
            raise CloudError(f"{self.root} is not a folder")
        self.where = str(self.root)

    def listing(self, case_name: str) -> Dict[str, int]:
        base = self.root / case_name
        found = {}
        if not base.is_dir():
            return found
        for dirpath, dirnames, filenames in os.walk(base):
            rel = Path(dirpath).relative_to(base)
            if len(rel.parts) >= DEPTH:
                dirnames[:] = []
            for name in filenames:
                found[(rel / name).as_posix()] = (Path(dirpath) / name).stat().st_size
        return found

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

    def listing(self, case_name: str) -> Dict[str, int]:
        found = {}
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
        walk(posixpath.join(self.root, case_name), '', 0)
        return found

    def close(self):
        try:
            self.ssh.disconnect()
        except Exception:
            pass


def open_cloud(conf):
    """The remote conf names; CloudError when it cannot be used."""
    if conf.is_local:
        return LocalCloud(conf.path)
    from src.utils.remote_config import RemoteConfig
    remote = RemoteConfig().get_remote(conf.remote)
    if remote is None:
        raise CloudError(f"remote '{conf.remote}' is not set up (`remote list`)")
    return SftpCloud(remote, conf.path)
