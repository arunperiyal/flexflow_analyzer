"""
Keep a transfer's CPU use under a limit on a cluster login node.

paramiko does SFTP's packet work and encryption in Python, so an upload on a
fast link holds a core at ~100% for as long as it runs -- and a login node's
watchdog (Param Shakti: >90% of a core for >30 min) kills it and threatens
the account. CpuCap is ticked from the transfer's progress callback, after
each chunk; when the process has used more than `limit` of a core since the
last look, it sleeps until the share is back at the limit. Process CPU time
counts every thread, paramiko's transport thread included, and while the
caller sleeps nothing feeds that thread either.

Only on a login node (on_login_node): a workstation or a Slurm job runs
the transfer at full speed.
"""

import os
import re
import socket
import time
from typing import Callable, Optional

DEFAULT_LIMIT = 70          # percent of one core
EVERY = 1.0                 # seconds between looks
LONGEST_PAUSE = 5.0

_LOGIN_HOST = re.compile(r'^login', re.IGNORECASE)


def on_login_node() -> bool:
    """A cluster login node: a host named login* outside any Slurm job.
    FLEXFLOW_LOGIN_NODE=1/0 says so outright, for a cluster named otherwise."""
    forced = os.environ.get('FLEXFLOW_LOGIN_NODE')
    if forced in ('0', '1'):
        return forced == '1'
    if os.environ.get('SLURM_JOB_ID'):
        return False
    return bool(_LOGIN_HOST.match(socket.gethostname()))


class CpuCap:
    """Pause the caller so the process stays under `limit` (0..1) of a core."""

    def __init__(self, limit: float, every: float = EVERY,
                 clock: Callable[[], float] = time.monotonic,
                 cpu: Callable[[], float] = time.process_time,
                 sleep: Callable[[float], None] = time.sleep,
                 notify: Optional[Callable[[str], None]] = None):
        self.limit, self.every = limit, every
        self._clock, self._cpu, self._sleep = clock, cpu, sleep
        self._notify = notify
        self.paused = 0.0
        self._t0, self._c0 = clock(), cpu()

    def tick(self) -> None:
        now = self._clock()
        wall = now - self._t0
        if wall < self.every:
            return
        used = self._cpu() - self._c0
        pause = used / self.limit - wall
        if pause > 0:
            if not self.paused and self._notify:
                self._notify(f"login node: holding the transfer under "
                             f"{self.limit * 100:.0f}% of a core (set login_cpu_limit)")
            pause = min(pause, LONGEST_PAUSE)
            self._sleep(pause)
            self.paused += pause
        self._t0, self._c0 = self._clock(), self._cpu()


def for_transfers() -> Optional[CpuCap]:
    """The cap for this process's transfers, or None: not a login node, or
    `set login_cpu_limit 0`."""
    if not on_login_node():
        return None
    limit = DEFAULT_LIMIT
    try:
        from shellkit import current_runtime
        rt = current_runtime()
        if rt is not None and 'login_cpu_limit' in rt.settings.specs:
            limit = rt.settings.get('login_cpu_limit')
    except Exception:
        pass
    if not limit:
        return None

    def notify(message):
        from rich.console import Console
        Console(stderr=True).print(f"[dim]    {message}[/dim]")
    return CpuCap(limit / 100.0, notify=notify)
