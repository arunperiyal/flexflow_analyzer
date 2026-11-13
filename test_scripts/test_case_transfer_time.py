"""`case upload|download plt` against the session timeout: the selection's
size at `set transfer_speed` (Mbps) is set against rt.time_left(), and when
it does not fit the steps that do are offered as --t2."""

import os

import pytest

import shellkit
from src.commands.case.download_impl import budget
from src.commands.case.download_impl.command import CaseDownloadCommand, step_of
from test_scripts.test_case_transfer_missing import FakeRemote

MB = 1024 * 1024


# -- budget ---------------------------------------------------------------------------

def test_seconds_and_bytes_at_a_speed():
    assert budget.seconds_for(1_250_000, 10) == pytest.approx(1.0)      # 10 Mbps = 1.25 MB/s
    assert budget.bytes_in(60, 10) == 75_000_000
    assert budget.mbps_of(1_250_000, 1.0) == pytest.approx(10)


@pytest.mark.parametrize('seconds, text', [(40, '40 s'), (300, '5 min'), (5460, '1 h 31 min'),
                                           (7200, '2 h')])
def test_duration(seconds, text):
    assert budget.duration(seconds) == text


def sizes(steps, per_step, files_per_step=1):
    return {f'riser.{s}.p{k}.plt': per_step // files_per_step
            for s in steps for k in range(files_per_step)}


def test_fit_takes_whole_steps_in_step_order():
    sel = sizes([100, 20, 300, 4000], 10, files_per_step=2)    # name order != step order
    sel['notes.txt'] = 1                                       # no step: left out
    got = budget.fit(sel, 25, step_of)
    assert (got.first, got.last, got.files, got.nbytes) == (20, 100, 4, 20)
    assert budget.fit(sel, 5, step_of) is None


def test_plan_without_a_timeout_is_none():
    assert budget.plan(sizes([1, 2], 10), None, 10, step_of) is None


def test_plan_fits_within_the_safety_margin():
    sel = sizes(range(1, 11), 1_250_000)           # 10 s at 10 Mbps
    assert budget.plan(sel, 12, 10, step_of).fits
    p = budget.plan(sel, 10.5, 10, step_of)        # 90% of 10.5 s is 9.45 s
    assert not p.fits and p.cut.last == 9


# -- the command ------------------------------------------------------------------------

class Settings:
    def __init__(self, speed):
        self.specs = {'transfer_speed': None}
        self.speed = speed

    def get(self, name):
        return self.speed


class Runtime:
    def __init__(self, left, speed=10.0):
        self.left = left
        self.settings = Settings(speed)

    def time_left(self):
        return self.left


@pytest.fixture
def cases(tmp_path):
    """A local case with steps 1..10 of 1.25 MB each (1 s each at 10 Mbps)."""
    here = tmp_path / 'local'
    (here / 'binary').mkdir(parents=True)
    for s in range(1, 11):
        (here / 'binary' / f'riser.{s}.plt').write_bytes(b'x' * 1_250_000)
    there = tmp_path / 'remote'
    (there / 'binary').mkdir(parents=True)
    return here, there


def upload(cases, monkeypatch, left, policy='ask', answer=None, window=None):
    here, there = cases
    monkeypatch.setattr(shellkit, 'current_runtime', lambda: Runtime(left))
    cmd = CaseDownloadCommand()
    cmd._time_policy = policy
    if answer is not None:
        monkeypatch.setattr('sys.stdin.isatty', lambda: True)
        monkeypatch.setattr(cmd.console, 'input', lambda q: answer)
    ssh = FakeRemote(there)
    ok = cmd.upload_binary_range(ssh, '/r/CS1', str(here), window)
    return ok, sorted(ssh.sent, key=step_of)


def text(capsys):
    return ' '.join(capsys.readouterr().out.split())


def test_fits_goes_without_a_word(cases, monkeypatch, capsys):
    ok, sent = upload(cases, monkeypatch, left=600, window=(1, 10))
    assert ok and len(sent) == 10
    assert 'Session timeout' not in text(capsys)


def test_too_long_and_cut_to_what_fits(cases, monkeypatch, capsys):
    ok, sent = upload(cases, monkeypatch, left=5, answer='t', window=(1, 10))
    assert ok and sent == [f'riser.{s}.plt' for s in range(1, 5)]   # 4 s of 4.5
    out = text(capsys)
    assert 'about 10 s at 10 Mbps' in out and 'Up to --t2 4 fits' in out
    assert '--t1 5' in out


def test_send_all_anyway(cases, monkeypatch):
    ok, sent = upload(cases, monkeypatch, left=5, answer='y', window=(1, 10))
    assert ok and len(sent) == 10


def test_stop(cases, monkeypatch, capsys):
    ok, sent = upload(cases, monkeypatch, left=5, answer='', window=(1, 10))
    assert not ok and sent == []
    assert 'Nothing sent' in text(capsys)


def test_fit_flag_cuts_without_asking(cases, monkeypatch, capsys):
    ok, sent = upload(cases, monkeypatch, left=5, policy='fit', window=(3, 10))
    assert ok and sent == [f'riser.{s}.plt' for s in range(3, 7)]
    assert '--fit: sending steps 3..6' in text(capsys)


def test_no_time_check(cases, monkeypatch, capsys):
    ok, sent = upload(cases, monkeypatch, left=1, policy='ignore', window=(1, 10))
    assert ok and len(sent) == 10
    assert 'Session timeout' not in text(capsys)


def test_without_a_terminal_it_warns_and_sends(cases, monkeypatch, capsys):
    monkeypatch.setattr('sys.stdin.isatty', lambda: False)
    ok, sent = upload(cases, monkeypatch, left=5, window=(1, 10))
    assert ok and len(sent) == 10
    assert 'no terminal to ask at' in text(capsys)


def test_not_even_one_step_fits(cases, monkeypatch, capsys):
    ok, sent = upload(cases, monkeypatch, left=0.5, policy='fit', window=(1, 10))
    assert not ok and sent == []
    assert 'Not even the first step fits' in text(capsys)


def test_no_runtime_no_check(cases, monkeypatch):
    here, there = cases
    monkeypatch.setattr(shellkit, 'current_runtime', lambda: None)
    ssh = FakeRemote(there)
    assert CaseDownloadCommand().upload_binary_range(ssh, '/r/CS1', str(here), (1, 10))
    assert len(ssh.sent) == 10


def test_download_is_checked_too(cases, monkeypatch, capsys, tmp_path):
    here, there = cases
    remote_side = here                       # the files to fetch live on the "remote"
    local = tmp_path / 'fresh'
    monkeypatch.setattr(shellkit, 'current_runtime', lambda: Runtime(5))
    cmd = CaseDownloadCommand()
    cmd._time_policy = 'fit'
    ssh = FakeRemote(remote_side)
    assert cmd.download_binary_range(ssh, '/r/CS1', str(local), (1, 10))
    assert sorted(os.listdir(local / 'binary'), key=step_of) == \
        [f'riser.{s}.plt' for s in range(1, 5)]


def test_whole_directory_is_cut_to_a_window(cases, monkeypatch):
    here, there = cases
    monkeypatch.setattr(shellkit, 'current_runtime', lambda: Runtime(5))
    cmd = CaseDownloadCommand()
    cmd._time_policy = 'fit'
    ssh = FakeRemote(there)
    target = {'case_path': str(here), 'remote_case_path': '/r/CS1'}
    cut = cmd._whole_binary_check(ssh, target, True)
    assert cut == (1, 4)
    assert cmd._send_cut(ssh, target, True, cut, force=False)
    assert len(ssh.sent) == 4 and cmd._time_policy == 'fit'


def test_rate_is_reported_against_the_setting(monkeypatch, capsys):
    monkeypatch.setattr(shellkit, 'current_runtime', lambda: Runtime(600, speed=10))
    cmd = CaseDownloadCommand()
    cmd._report_rate(100 * MB, 100 * MB * 8 / 6e6)          # 6 Mbps
    assert 'set transfer_speed 6' in text(capsys)
    cmd._report_rate(100 * MB, 100 * MB * 8 / 9.5e6)        # close enough
    out = text(capsys)
    assert '9.5 Mbps' in out and 'set transfer_speed' not in out
    cmd._report_rate(MB, 1)                                 # too small to say
    assert text(capsys) == ''



def test_a_shellkit_without_time_left_just_sends(cases, monkeypatch, capsys):
    """The cluster's shellkit may be older than the one with the session timeout
    (`'Runtime' object has no attribute 'time_left'`): the check is skipped."""
    class OldRuntime:
        def __init__(self):
            self.settings = Settings(10.0)
    here, there = cases
    monkeypatch.setattr(shellkit, 'current_runtime', lambda: OldRuntime())
    cmd = CaseDownloadCommand()
    cmd._time_policy = 'ask'
    ssh = FakeRemote(there)
    assert cmd.upload_binary_range(ssh, '/r/CS1', str(here), (1, 10))
    assert len(ssh.sent) == 10
