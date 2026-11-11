"""
.cases.yml: one file per folder of cases, holding

    cases:          the cases of this folder (what `case add` finds)
      - name: BR0SG0U1P0
        path: /scratch/.../bare/BR0SG0U1P0
    remotes:        where these cases go on each remote: <path>/<case>
      cloud: /shares/arunperiyal/.../one_directional_cf/bare
    auto:           settings of the `auto` command
      keep_rst: 500
      disk_alert: 200G

The login of a remote (address, user, password) stays in
~/.flexflow/remotes.json; here is only the folder these cases have there.
Which remote a command uses is `--remote NAME` or `use remote:NAME`.

    cf = read(folder)            # CasesFileError when missing or malformed
    cf.cases, cf.remotes, cf.auto
    write(cf)                    # comments are rewritten, values kept

Every section is optional; a missing section reads as empty.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

FILENAME = '.cases.yml'
AUTO_KEYS = ('keep_rst', 'keep_newest_rst', 'upload_rst', 'disk_alert', 'qos', 'account',
             'partition')

HEADER = """\
# flexflow: the cases of this folder, where they go on each remote, and auto's
# settings. `case add` rewrites `cases`; `auto init` sets `remotes` and `auto`.
# Remote logins stay in ~/.flexflow/remotes.json; pick one with --remote NAME or
# `use remote:NAME`. A case goes to <remotes.NAME>/<case name> on that remote.
#
# auto:
#   keep_rst    .rst thinning keeps the steps divisible by this on this machine, for
#               resuming after a failure (unset: no thinning; a queued restart's set
#               and the newest complete set are always kept)
#   keep_newest_rst  thinning also keeps this many of the newest complete .rst sets
#               (default 2: if the newest was cut short when a job was killed, the one
#               before it restarts the run)
#   upload_rst  the .rst of steps divisible by this are uploaded, to resume the run
#               in the future (a multiple of keep_rst; unset: no restart sets are
#               uploaded). A finished run's final set is uploaded too
#   disk_alert  flag running cases whose run directory is bigger (e.g. 200G)
#   qos, account, partition   only if set: passed to the post jobs auto submits
"""


class CasesFileError(ValueError):
    pass


@dataclass
class CasesFile:
    path: Path
    cases: List[Dict[str, str]] = field(default_factory=list)
    remotes: Dict[str, str] = field(default_factory=dict)
    auto: Dict[str, object] = field(default_factory=dict)

    @property
    def folder(self) -> Path:
        return self.path.parent


def path_for(folder) -> Path:
    return Path(folder) / FILENAME


def exists(folder) -> bool:
    return path_for(folder).is_file()


def read(folder) -> CasesFile:
    """The folder's .cases.yml. CasesFileError when it is not there or not
    valid (with what is wrong)."""
    import yaml
    path = path_for(folder)
    if not path.is_file():
        raise CasesFileError(f"no {FILENAME} in {Path(folder)} (`case add` makes it)")
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        raise CasesFileError(f"{path} is not valid YAML: {e}")
    if not isinstance(data, dict):
        raise CasesFileError(f"{path} should hold `cases`, `remotes` and `auto`")
    unknown = set(data) - {'cases', 'remotes', 'auto'}
    if unknown:
        raise CasesFileError(f"{path}: unknown section(s) {', '.join(sorted(unknown))} "
                             f"(known: cases, remotes, auto)")
    cases = data.get('cases') or []
    if not isinstance(cases, list) or not all(isinstance(c, dict) and c.get('path')
                                              for c in cases):
        raise CasesFileError(f"{path}: `cases` should be a list of name/path entries")
    remotes = data.get('remotes') or {}
    if not isinstance(remotes, dict) or not all(isinstance(v, str) for v in remotes.values()):
        raise CasesFileError(f"{path}: `remotes` should map a remote name to its folder")
    auto = data.get('auto') or {}
    if not isinstance(auto, dict) or set(auto) - set(AUTO_KEYS):
        raise CasesFileError(f"{path}: `auto` takes {', '.join(AUTO_KEYS)}")
    return CasesFile(path=path,
                     cases=[{'name': str(c.get('name') or Path(c['path']).name),
                             'path': str(c['path'])} for c in cases],
                     remotes={str(k): v for k, v in remotes.items()}, auto=dict(auto))


def read_or_new(folder) -> CasesFile:
    """read(), or an empty one (not yet written) when there is none."""
    return read(folder) if exists(folder) else CasesFile(path=path_for(folder))


def write(cf: CasesFile) -> Path:
    import yaml
    data = {'cases': cf.cases, 'remotes': cf.remotes, 'auto': cf.auto}
    body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)
    tmp = cf.path.with_name(cf.path.name + '.tmp')
    tmp.write_text(HEADER + '\n' + body)
    tmp.replace(cf.path)
    return cf.path
