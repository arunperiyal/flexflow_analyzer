"""Ring buffer for the command window, and stdout capture for case operations.

Case operations (execute_add, write_case_maps, ...) print progress with
Rich/plain prints. capture() tees that stdout into the buffer instead of
adding a parallel set of log calls, so the command window shows exactly
what the CLI would have shown.
"""

import contextlib
import io
import re
import threading
from collections import deque

# Rich/Colors write ANSI SGR codes for a terminal; a browser has no use for
# them and would otherwise show the raw escape bytes.
_ANSI = re.compile(r'\x1b\[[0-9;]*m')


class LogBuffer:
    def __init__(self, maxlen: int = 2000):
        self._lines = deque(maxlen=maxlen)
        self._seq = 0
        self._lock = threading.Lock()

    def write(self, text: str) -> None:
        with self._lock:
            for line in text.splitlines():
                line = _ANSI.sub('', line)
                if not line.strip():
                    continue
                self._seq += 1
                self._lines.append({'seq': self._seq, 'line': line})

    def since(self, seq: int) -> list:
        with self._lock:
            return [entry for entry in self._lines if entry['seq'] > seq]

    @property
    def seq(self) -> int:
        with self._lock:
            return self._seq

    @contextlib.contextmanager
    def capture(self):
        """Redirect stdout and stderr into this buffer for the duration of the block."""
        tee = _Tee(self)
        with contextlib.redirect_stdout(tee), contextlib.redirect_stderr(tee):
            yield


class _Tee(io.TextIOBase):
    """A write-only stream that feeds every write into a LogBuffer."""

    def __init__(self, logbuf: LogBuffer):
        self._logbuf = logbuf

    def write(self, s: str) -> int:
        self._logbuf.write(s)
        return len(s)

    def flush(self) -> None:
        pass
