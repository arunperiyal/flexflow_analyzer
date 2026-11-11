"""
The record of one `auto apply` run: <folder>/auto_logs/auto_<date>_<time>.log,
plain text, one line per action or check, so a run can be read back later (or
pasted into a conversation). Also the lock that keeps two runs off one folder.

    with FolderLock(folder): ...        # AutoLockError when another run holds it
    log = RunLog(folder); log.line('case3', 'upload', 'sent 12 files'); log.path
"""

import os
import socket
import time
from pathlib import Path

from .ledger import logs_dir

STALE_SECS = 12 * 3600


class AutoLockError(RuntimeError):
    pass


class FolderLock:
    """auto_logs/apply.lock, created with O_EXCL and holding host, pid and time.
    A lock older than STALE_SECS is taken over (a run that was killed)."""

    def __init__(self, folder):
        self.path = logs_dir(folder) / 'apply.lock'
        self.held = False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in (1, 2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                    holder = self.path.read_text().strip()
                except OSError:
                    continue
                if age > STALE_SECS and attempt == 1:
                    self.path.unlink(missing_ok=True)
                    continue
                raise AutoLockError(f"another auto apply holds {self.path} ({holder}, "
                                    f"{int(age // 60)} min ago); if it is gone, delete the file")
            with os.fdopen(fd, 'w') as f:
                f.write(f"{socket.gethostname()} pid {os.getpid()} "
                        f"{time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.held = True
            return self
        raise AutoLockError(f"could not take {self.path}")

    def __exit__(self, *exc):
        if self.held:
            self.path.unlink(missing_ok=True)
            self.held = False


class RunLog:
    def __init__(self, folder):
        self.dir = logs_dir(folder)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"auto_{time.strftime('%Y-%m-%d_%H%M%S')}.log"
        self._f = open(self.path, 'a', buffering=1)

    def line(self, case: str, kind: str, text: str):
        stamp = time.strftime('%H:%M:%S')
        for part in str(text).splitlines() or ['']:
            self._f.write(f"{stamp}  {case or '-':<12} {kind:<8} {part}\n")

    def close(self):
        self._f.close()
