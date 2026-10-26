"""`case upload|download` carry .restarts: copied when the other side has
none; with both, the destination gains the restarts it lacks and keeps the
lines it has. Only the destination is written."""

import io

import pytest
from rich.console import Console

from src.core import restarts
from src.commands.case.download_impl.command import CaseUploadCommand as Transfer
from test_case_transfer_status import FakeSSH


def rows(*afters, recorded='2026-10-26 12:00'):
    return [dict(after=str(a), first=str(a + 1), time='-', reached=str(a + 50),
                 replaced='50', part='p', previous='q', recorded=recorded) for a in afters]


@pytest.fixture
def setup(tmp_path):
    t = Transfer()
    t.console = Console(file=io.StringIO(), width=120, color_system=None)
    case = tmp_path / 'C1'
    case.mkdir()
    return t, FakeSSH(), case


def remote_rows(ssh):
    return restarts.parse(ssh.files['/r/C1/.restarts'][0].decode())


def said(t):
    return t.console.file.getvalue()


def test_upload_copies(setup):
    t, ssh, case = setup
    restarts.write(case, rows(1000, 2050))
    t.sync_restarts(ssh, '/r/C1', str(case), is_upload=True)
    assert [r['after'] for r in remote_rows(ssh)] == ['1000', '2050']
    assert 'copied (2 restart(s))' in said(t)


def test_download_adds_what_is_missing_and_keeps_local_lines(setup):
    t, ssh, case = setup
    restarts.write(case, rows(1000, recorded='here'))
    ssh.files['/r/C1/.restarts'] = [restarts.render(rows(1000, 4000, recorded='there'),
                                                    'C1').encode(), 0]
    t.sync_restarts(ssh, '/r/C1', str(case), is_upload=False)
    got = restarts.read(case)
    assert [(r['after'], r['recorded']) for r in got] == [('1000', 'here'), ('4000', 'there')]
    assert 'merged (1 restart(s) added)' in said(t)
    assert ssh.files['/r/C1/.restarts'][1] == 0          # the source is not written


def test_up_to_date_and_nothing_to_send(setup):
    t, ssh, case = setup
    restarts.write(case, rows(1000))
    ssh.files['/r/C1/.restarts'] = [restarts.render(rows(1000, 2000), 'C1').encode(), 0]
    t.sync_restarts(ssh, '/r/C1', str(case), is_upload=True)
    assert 'already up to date' in said(t)
    t.sync_restarts(ssh, '/r/C2', str(case.parent / 'none'), is_upload=True)
    assert '/r/C2/.restarts' not in ssh.files


def test_a_failure_only_warns(setup, monkeypatch):
    t, ssh, case = setup
    restarts.write(case, rows(1000))
    monkeypatch.setattr(ssh, 'upload_file', lambda *a, **k: (_ for _ in ()).throw(OSError('disk full')))
    t.sync_restarts(ssh, '/r/C1', str(case), is_upload=True)
    assert '.restarts not carried: disk full' in said(t)
