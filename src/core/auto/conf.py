"""
.auto.conf: the settings `auto` uses for one folder of cases, next to .cases.

    remote     = cloud          # a remote from `remote list`, or `local`
    path       = /shares/.../one_directional_cf/bare   # the folder there
    keep_rst   = 500            # .rst grid kept when thinning (unset: no thinning)
    disk_alert = 200G           # flag running cases whose run dir is bigger
    qos        = ...            # only when set: passed to post jobs
    account    = ...
    partition  = ...

A case goes to <path>/<case name>. Lines are `key = value`; `#` starts a
comment. Unknown keys are an error, so a typo does not silently do nothing.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

FILENAME = '.auto.conf'
KEYS = ('remote', 'path', 'keep_rst', 'disk_alert', 'qos', 'account', 'partition')
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


def parse_size(text: str) -> int:
    m = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*([KMGT]?)B?\s*', text, re.IGNORECASE)
    if not m:
        raise AutoConfError(f"not a size: {text!r} (e.g. 200G, 500M)")
    return int(float(m.group(1)) * _UNITS[m.group(2).upper()])


def read(folder) -> AutoConf:
    """The folder's .auto.conf; AutoConfError says what is missing or wrong."""
    source = Path(folder) / FILENAME
    if not source.exists():
        raise AutoConfError(f"no {FILENAME} in {Path(folder)} -- it names the remote and "
                            f"the folder there (see `auto --help`)")
    values = {}
    for n, raw in enumerate(source.read_text().splitlines(), 1):
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        key, eq, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if not eq or not key:
            raise AutoConfError(f"{FILENAME} line {n}: expected `key = value`, got {raw.strip()!r}")
        if key not in KEYS:
            raise AutoConfError(f"{FILENAME} line {n}: unknown key {key!r} "
                                f"(known: {', '.join(KEYS)})")
        values[key] = value
    for key in ('remote', 'path'):
        if not values.get(key):
            raise AutoConfError(f"{FILENAME}: `{key}` is not set")
    keep = values.get('keep_rst')
    if keep is not None:
        if not keep.isdigit() or int(keep) <= 0:
            raise AutoConfError(f"{FILENAME}: keep_rst must be a positive whole number, got {keep!r}")
        keep = int(keep)
    alert = values.get('disk_alert')
    return AutoConf(source=source, remote=values['remote'], path=values['path'],
                    keep_rst=keep, disk_alert=parse_size(alert) if alert else None,
                    qos=values.get('qos') or None, account=values.get('account') or None,
                    partition=values.get('partition') or None)
