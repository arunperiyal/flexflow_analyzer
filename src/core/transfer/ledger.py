"""
What `auto` and `case upload` have sent to a remote and checked, per folder
of cases: <folder>/auto_logs/ledger.json

    {"cloud": {"BR0SG0U1P0": {"binary/riser.5740.plt":
        {"size": 155342168, "md5": "9e1f...", "verified": "md5",
         "mtime": 1794475865.0, "path": "/nas/cases/BR0SG0U1P0/binary/riser.5740.plt",
         "when": "2026-11-12 09:31:05"}}}}

`mtime` is when the local file was last written, as it was when sent: a local
file written again since (a restart, a new conversion) no longer matches its
entry. `path` is where on the remote the copy is: `case upload --remote-path`
can send a case somewhere other than the folder `auto` uses.

A later stage deletes a local file only when its entry is `verified: md5` and
the size and md5 still match the file on the remote. Written after every file,
so a run cut short keeps what it had finished.
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

DIRNAME = 'auto_logs'
FILENAME = 'ledger.json'


def logs_dir(folder) -> Path:
    return Path(folder) / DIRNAME


class Ledger:
    def __init__(self, folder):
        self.path = logs_dir(folder) / FILENAME
        self.data = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text())
            except (OSError, ValueError):
                # unreadable: keep it aside, never overwrite what we cannot read
                self.path.rename(self.path.with_name(FILENAME + f".bad-{int(time.time())}"))
                self.data = {}

    def get(self, remote: str, case: str, rel: str) -> Optional[dict]:
        return self.data.get(remote, {}).get(case, {}).get(rel)

    def record(self, remote: str, case: str, rel: str, size: int, md5: Optional[str],
               verified: str, mtime: Optional[float] = None, path: Optional[str] = None):
        entry = {'size': size, 'md5': md5, 'verified': verified,
                 'when': time.strftime('%Y-%m-%d %H:%M:%S')}
        if mtime is not None:
            entry['mtime'] = mtime
        if path is not None:
            entry['path'] = path
        self.data.setdefault(remote, {}).setdefault(case, {})[rel] = entry
        self.save()

    def forget(self, remote: str, case: str, rel: str):
        """Take a file out: its copy was found missing or different."""
        if self.data.get(remote, {}).get(case, {}).pop(rel, None) is not None:
            self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + '.tmp')
        tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True))
        os.replace(tmp, self.path)
