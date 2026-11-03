"""On a login node a transfer is held under `login_cpu_limit` of a core:
paramiko's SFTP holds a core at ~100%, and Param Shakti kills (and threatens
to lock the account for) >90% for >30 min on a login node."""

import time

import pytest

from src.utils import cpu_cap
from src.utils.cpu_cap import CpuCap, on_login_node


class Clock:
    def __init__(self):
        self.wall = self.cpu = 0.0
        self.slept = []

    def sleep(self, s):
        self.slept.append(s)
        self.wall += s

    def busy(self, s):            # s seconds of work at 100% of a core
        self.wall += s
        self.cpu += s


def cap(clock, limit=0.7):
    notes = []
    c = CpuCap(limit, clock=lambda: clock.wall, cpu=lambda: clock.cpu,
               sleep=clock.sleep, notify=notes.append)
    return c, notes


def test_full_speed_work_is_paused_to_the_limit():
    clock = Clock()
    c, notes = cap(clock)
    for _ in range(100):
        clock.busy(0.1)
        c.tick()
    assert clock.cpu / clock.wall == pytest.approx(0.7, abs=0.02)
    assert len(notes) == 1 and '70%' in notes[0]


def test_work_under_the_limit_is_left_alone():
    clock = Clock()
    c, notes = cap(clock)
    for _ in range(100):
        clock.busy(0.05)
        clock.wall += 0.1            # waiting on the network
        c.tick()
    assert clock.slept == [] and notes == []


def test_no_look_before_a_second():
    clock = Clock()
    c, _ = cap(clock)
    clock.busy(0.5)
    c.tick()
    assert clock.slept == []


def test_pauses_are_bounded():
    clock = Clock()
    c, _ = cap(clock, limit=0.01)
    clock.busy(10)
    c.tick()
    assert clock.slept == [cpu_cap.LONGEST_PAUSE]


def test_the_cap_holds_a_real_busy_loop():
    """CPU time measured, not simulated: a loop at 100% held to 50%."""
    c = CpuCap(0.5, every=0.2)
    w0, c0 = time.monotonic(), time.process_time()
    while time.monotonic() - w0 < 3:
        t = time.monotonic()
        while time.monotonic() - t < 0.01:
            pass
        c.tick()
    share = (time.process_time() - c0) / (time.monotonic() - w0)
    assert 0.35 < share < 0.6


@pytest.mark.parametrize('host, job, forced, expected', [
    ('login08.iitkgp.ac.in', None, None, True),
    ('login08', '12345', None, False),          # inside a Slurm job
    ('arun-workstation', None, None, False),
    ('arun-workstation', None, '1', True),
    ('login08', None, '0', False),
])
def test_on_login_node(monkeypatch, host, job, forced, expected):
    monkeypatch.setattr(cpu_cap.socket, 'gethostname', lambda: host)
    for name, value in (('SLURM_JOB_ID', job), ('FLEXFLOW_LOGIN_NODE', forced)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    assert on_login_node() is expected


class Settings:
    def __init__(self, limit):
        self.specs = {'login_cpu_limit': None}
        self.limit = limit

    def get(self, name):
        return self.limit


@pytest.mark.parametrize('login, limit, expected', [(True, 70, 0.7), (True, 50, 0.5),
                                                    (True, 0, None), (False, 70, None)])
def test_for_transfers(monkeypatch, login, limit, expected):
    import shellkit
    monkeypatch.setattr(cpu_cap, 'on_login_node', lambda: login)
    monkeypatch.setattr(shellkit, 'current_runtime',
                        lambda: type('RT', (), {'settings': Settings(limit)})())
    got = cpu_cap.for_transfers()
    assert (got.limit if got else None) == expected


def test_the_ssh_wrapper_ticks_the_cap_in_every_callback(monkeypatch):
    from src.utils.ssh_client import SSHClientWrapper
    ticks, seen = [], []
    monkeypatch.setattr(cpu_cap, 'for_transfers',
                        lambda: type('Cap', (), {'tick': lambda self: ticks.append(1)})())
    ssh = SSHClientWrapper('h', 'u', 'p')
    cb = ssh._capped(lambda done, total: seen.append(done))
    cb(1, 2), cb(2, 2)
    assert ticks == [1, 1] and seen == [1, 2]
    assert ssh._capped(None) is not None          # ticks even with no progress bar


def test_off_a_login_node_the_callback_is_untouched(monkeypatch):
    from src.utils.ssh_client import SSHClientWrapper
    monkeypatch.setattr(cpu_cap, 'for_transfers', lambda: None)
    ssh = SSHClientWrapper('h', 'u', 'p')
    f = lambda d, t: None
    assert ssh._capped(f) is f and ssh._capped(None) is None


def test_a_capped_download_bounds_the_prefetch(monkeypatch, tmp_path):
    from src.utils import ssh_client
    calls = []

    class SFTP:
        def get(self, remote, local, callback=None, **kw):
            calls.append(kw)

    for cap in (object(), None):
        ssh = ssh_client.SSHClientWrapper('h', 'u', 'p')
        ssh.connected, ssh.sftp_client = True, SFTP()
        ssh.remote_path_exists = lambda path: True
        monkeypatch.setattr(cpu_cap, 'for_transfers',
                            lambda cap=cap: cap and type('Cap', (), {'tick': lambda s: None})())
        ssh.download_file('/r/x', str(tmp_path / 'x'))
    assert calls == [{'max_concurrent_prefetch_requests': ssh_client.PREFETCH_UNDER_CAP}, {}]
