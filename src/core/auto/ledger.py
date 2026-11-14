"""
What `auto` has sent to a remote and checked, per folder of cases:
<folder>/auto_logs/ledger.json

    {"cloud": {"BR0SG0U1P0": {"binary/riser.5740.plt":
        {"size": 155342168, "md5": "9e1f...", "verified": "md5", "when": "2026-11-12 09:31:05",
         "mtime": 1762940000.5, "deleted": "2026-11-14 10:02:11"}}}}

`mtime` is the local file's modification time when it was sent (the delete stage
compares it once the local file is gone); `deleted` is set when the delete stage
removed the local file. The delete stage clears a file only when its md5 is
computed on both sides at that moment; the ledger alone never clears one.
Written after every file, so a run cut short keeps what it had finished.
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
               verified: str, mtime: Optional[float] = None):
        entry = {'size': size, 'md5': md5, 'verified': verified,
                 'when': time.strftime('%Y-%m-%d %H:%M:%S')}
        if mtime is not None:
            entry['mtime'] = mtime
        self.data.setdefault(remote, {}).setdefault(case, {})[rel] = entry
        self.save()

    def mark_deleted(self, remote: str, case: str, rel: str):
        """The local file is gone: say when, and keep what the entry knew."""
        entry = self.get(remote, case, rel)
        if entry is not None:
            entry['deleted'] = time.strftime('%Y-%m-%d %H:%M:%S')
            self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + '.tmp')
        tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True))
        os.replace(tmp, self.path)
