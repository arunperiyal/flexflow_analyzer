"""services/logbuf.py -- the read-only command window's lines (webapp.md §4, §8).

A ring buffer of what the server did: a case being read, a map being written, a
request that failed. `capture()` wraps code that already prints progress
(`FlexFlowCase`, `write_case_maps()`) and tees each finished line into the buffer
as well as to the real stdout, so the window is filled by code that exists
rather than by a parallel set of log calls. The buffer takes lines only; there
is no way to send one in from the browser.

    log.add("reading CS1 ...")
    lines, next_id = log.since(0)        # the browser asks again with next_id
"""

import contextlib
import io
import itertools
import sys
import threading
import time
from collections import deque
from typing import List, Tuple

MAX_LINES = 500


class LogBuffer:
    def __init__(self, max_lines: int = MAX_LINES):
        self._lines: deque = deque(maxlen=max_lines)    # (id, when, level, text)
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def add(self, text: str, level: str = 'info') -> None:
        text = str(text).rstrip()
        if not text:
            return
        with self._lock:
            self._lines.append((next(self._ids), time.strftime('%H:%M:%S'), level, text))

    def since(self, last: int = 0) -> Tuple[List[dict], int]:
        """The lines after id `last`, and the id to ask from next time. An id older than
        the buffer's oldest line returns all of it."""
        with self._lock:
            rows = [dict(id=i, time=t, level=lv, text=tx) for i, t, lv, tx in self._lines if i > last]
            newest = self._lines[-1][0] if self._lines else last
        return rows, max(newest, last)

    def clear(self) -> None:
        with self._lock:
            self._lines.clear()


class _Tee(io.TextIOBase):
    """Passes writes through, and adds each finished line to the buffer."""

    def __init__(self, buffer: LogBuffer, through):
        self._buffer, self._through, self._partial = buffer, through, ''

    def writable(self):
        return True

    def write(self, text):
        self._through.write(text)
        self._partial += text
        *done, self._partial = self._partial.split('\n')
        for line in done:
            self._buffer.add(line)
        return len(text)

    def flush(self):
        self._through.flush()

    def finish(self):
        if self._partial:
            self._buffer.add(self._partial)
            self._partial = ''


@contextlib.contextmanager
def capture(buffer: LogBuffer = None):
    """Tee this block's stdout into the buffer (process-wide while it runs: two
    requests reading at once may mix their lines, never lose them)."""
    tee = _Tee(buffer or log, sys.stdout)
    with contextlib.redirect_stdout(tee):
        try:
            yield
        finally:
            tee.finish()


log = LogBuffer()
