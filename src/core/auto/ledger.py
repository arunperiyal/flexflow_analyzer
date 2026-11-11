"""
What `auto` has sent to a remote and checked, per folder of cases:
<folder>/auto_logs/ledger.json

    {"cloud": {"BR0SG0U1P0": {"binary/riser.5740.plt":
        {"size": 155342168, "md5": "9e1f...", "verified": "md5", "when": "2026-11-12 09:31:05"}}}}

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
               verified: str):
        entry = {'size': size, 'md5': md5, 'verified': verified,
                 'when': time.strftime('%Y-%m-%d %H:%M:%S')}
        self.data.setdefault(remote, {}).setdefault(case, {})[rel] = entry
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + '.tmp')
        tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True))
        os.replace(tmp, self.path)
