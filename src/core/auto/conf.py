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
PLACEHOLDER = 'EDIT_ME'

TEMPLATE = """\
# Settings `auto` uses for the cases of this folder (.cases is next to this file).
# Edit what says {placeholder}, then run: auto show
#
# remote: a remote from `remote list`{known}, or `local` for a folder on this machine
remote     = {remote}
#
# path: the folder on the remote that holds these cases; case X goes to <path>/X
path       = {placeholder}
#
# keep_rst: when .rst files are thinned, keep the steps divisible by this.
# The restart point of a queued job and the newest complete set are always kept.
# Left commented out: .rst files are not thinned.
# keep_rst   = 500
#
# disk_alert: flag running cases whose run directory is bigger than this
# disk_alert = 200G
#
# Only when set, passed to the post jobs auto submits (else the script's own header):
# qos       =
# account   =
# partition =
"""
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
        if values[key] == PLACEHOLDER:
            raise AutoConfError(f"{FILENAME}: set `{key}` (it still says {PLACEHOLDER}); "
                                f"edit {source}")
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


def template(remote: str = None, known=()) -> str:
    """The text `auto init` writes: remote filled in when known, path left
    for the user."""
    names = f" ({', '.join(known)})" if known else ''
    return TEMPLATE.format(placeholder=PLACEHOLDER, known=names, remote=remote or PLACEHOLDER)


def write_template(folder, remote: str = None, known=(), force: bool = False) -> Path:
    """Write .auto.conf in folder; AutoConfError when one is there (unless force)."""
    path = Path(folder) / FILENAME
    if path.exists() and not force:
        raise AutoConfError(f"{path} exists; edit it, or `auto init --force` to start over")
    path.write_text(template(remote, known))
    return path
