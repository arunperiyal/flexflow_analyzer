"""
The record of one `auto apply` run: <folder>/auto_logs/auto_<date>_<time>.log,
plain text, one line per action or check, so a run can be read back later (or
pasted into a conversation). Also the lock that keeps two runs off one folder.

    with FolderLock(folder): ...        # AutoLockError when another run holds it
    log = RunLog(folder); log.line('case3', 'upload', 'sent 12 files'); log.path
"""

import os
import re
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import List, NamedTuple, Optional

from src.core.transfer.ledger import logs_dir

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
    def __init__(self, folder, stamp=None):
        self.dir = logs_dir(folder)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"auto_{stamp or time.strftime('%Y-%m-%d_%H%M%S')}.log"
        self._f = open(self.path, 'a', buffering=1)

    def line(self, case: str, kind: str, text: str):
        stamp = time.strftime('%H:%M:%S')
        for part in str(text).splitlines() or ['']:
            self._f.write(f"{stamp}  {case or '-':<12} {kind:<8} {part}\n")

    def close(self):
        self._f.close()


# -- reading the logs back (`auto log`) -------------------------------------------------

_LINE = re.compile(r'^(\d\d:\d\d:\d\d)  (\S+)\s+(\S+)\s*(.*)$')
_NAME = re.compile(r'^auto_(\d{4}-\d\d-\d\d)_(\d\d)(\d\d)(\d\d)\.log$')


class LogEntry(NamedTuple):
    time: str
    case: str           # '' for the lines of the run itself (start, end)
    kind: str           # history, upload, delete, post, problem, start, end
    text: str


def list_logs(folder) -> List[Path]:
    """The run logs of this folder of cases, newest first."""
    return sorted((p for p in logs_dir(folder).glob('auto_*.log') if _NAME.match(p.name)),
                  key=lambda p: p.name, reverse=True)


def started_at(path) -> Optional[datetime]:
    """When the run began, from the log's name."""
    m = _NAME.match(Path(path).name)
    if not m:
        return None
    return datetime.strptime(f"{m.group(1)} {m.group(2)}{m.group(3)}{m.group(4)}", '%Y-%m-%d %H%M%S')


def read_log(path) -> List[LogEntry]:
    """The lines of one log. A line that does not match the format is kept as text of the
    kind '' (a log written by hand or cut short)."""
    entries = []
    for raw in Path(path).read_text(errors='replace').splitlines():
        m = _LINE.match(raw)
        if not m:
            entries.append(LogEntry('', '', '', raw))
            continue
        when, case, kind, text = m.groups()
        entries.append(LogEntry(when, '' if case == '-' else case, kind, text))
    return entries


def is_failure(entry: LogEntry) -> bool:
    """A step that failed, or a case that could not be read."""
    return entry.kind == 'problem' or entry.text.startswith('FAILED')


def summarise(entries: List[LogEntry]) -> dict:
    """What one run did, for the list: its command, how it ended, the cases it touched."""
    start = next((e.text for e in entries if e.kind == 'start'), '')
    end = next((e.text for e in entries if e.kind == 'end'), None)
    cases = []
    for e in entries:
        if e.case and e.case not in cases:
            cases.append(e.case)
    steps = [e for e in entries if e.case and e.text.startswith(('ok:', 'FAILED'))]
    return dict(start=start, end=end, cases=cases, steps=len(steps),
                failed=sum(1 for e in entries if is_failure(e)))
