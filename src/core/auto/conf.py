"""
What `auto` uses for a folder of cases, from its .cases.yml (src/core/cases_file.py):
the chosen remote's folder (`remotes:`) and the `auto:` settings.

    conf = read(folder, remote='cloud')     # AutoConfError says what is missing
    conf.remote, conf.path, conf.keep_rst, conf.disk_alert, ...

The remote is named by --remote or `use remote:`; `local` is a folder on this
machine (remotes: {local: /some/folder}), for the dummy cases and tests.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .. import cases_file

PLACEHOLDER = 'EDIT_ME'
_UNITS = {'': 1, 'K': 1024, 'M': 1024 ** 2, 'G': 1024 ** 3, 'T': 1024 ** 4}


class AutoConfError(ValueError):
    pass


@dataclass(frozen=True)
class AutoConf:
    source: Path
    remote: str
    path: str
    keep_rst: Optional[int] = None
    disk_alert: Optional[int] = None    # bytes
    qos: Optional[str] = None
    account: Optional[str] = None
    partition: Optional[str] = None

    @property
    def is_local(self) -> bool:
        return self.remote == 'local'


def parse_size(text) -> int:
    m = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*([KMGT]?)B?\s*', str(text), re.IGNORECASE)
    if not m:
        raise AutoConfError(f"not a size: {text!r} (e.g. 200G, 500M)")
    return int(float(m.group(1)) * _UNITS[m.group(2).upper()])


def check_keep_rst(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
        raise AutoConfError(f"keep_rst must be a positive whole number, got {value!r}")
    return int(value)


def read(folder, remote: Optional[str]) -> AutoConf:
    """auto's settings for this folder with this remote."""
    try:
        cf = cases_file.read(folder)
    except cases_file.CasesFileError as e:
        raise AutoConfError(str(e))
    listed = ', '.join(cf.remotes) or 'none yet'
    if not remote:
        raise AutoConfError(f"which remote? --remote NAME or `use remote:NAME` "
                            f"({cases_file.FILENAME} lists: {listed})")
    path = cf.remotes.get(remote)
    if not path:
        raise AutoConfError(f"{cf.path} has no folder for remote '{remote}' (lists: {listed}); "
                            f"`auto init --remote {remote} --path DIR` adds it")
    if path == PLACEHOLDER:
        raise AutoConfError(f"set the folder of remote '{remote}' in {cf.path} "
                            f"(it still says {PLACEHOLDER})")
    a = cf.auto
    return AutoConf(source=cf.path, remote=remote, path=path,
                    keep_rst=check_keep_rst(a.get('keep_rst')),
                    disk_alert=parse_size(a['disk_alert']) if a.get('disk_alert') else None,
                    qos=a.get('qos') or None, account=a.get('account') or None,
                    partition=a.get('partition') or None)


def set_up(folder, remote: Optional[str] = None, path: Optional[str] = None,
           keep_rst=None, disk_alert=None, replace: bool = False):
    """Add or change auto's entries in the folder's .cases.yml (made, with no
    cases yet, when missing): the remote's folder and the given settings.
    An existing remote folder is changed only with replace. Returns
    (cases file, what changed, what was kept)."""
    check_keep_rst(keep_rst)
    if disk_alert is not None:
        parse_size(disk_alert)
    try:
        cf = cases_file.read_or_new(folder)
    except cases_file.CasesFileError as e:
        raise AutoConfError(str(e))
    changed, kept = [], []
    if remote:
        old = cf.remotes.get(remote)
        new = path or PLACEHOLDER
        if old and old != PLACEHOLDER and old != new and not replace:
            kept.append(f"remotes.{remote}: {old} (--force to replace it)")
        elif old != new:
            cf.remotes[remote] = new
            changed.append(f"remotes.{remote}: {new}")
    for key, value in (('keep_rst', keep_rst), ('disk_alert', disk_alert)):
        if value is not None and cf.auto.get(key) != value:
            cf.auto[key] = value
            changed.append(f"auto.{key}: {value}")
    cases_file.write(cf)
    return cf, changed, kept
