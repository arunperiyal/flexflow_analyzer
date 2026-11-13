"""`auto apply`: history, checked uploads, post jobs -- on freshly built dummy
cases with the fake SLURM and the folder remote. Nothing is ever deleted."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.commands.auto.apply import execute_apply
from src.core.transfer import cloud as cloud_mod
from src.core.transfer.cloud import LocalCloud, PutResult, SftpCloud, file_md5
from src.core.transfer.ledger import Ledger
from src.core.auto.runlog import AutoLockError, FolderLock

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def dummy(tmp_path, monkeypatch):
    root = tmp_path / 'dummy'
    subprocess.run([sys.executable, str(REPO / 'tools' / 'make_dummy.py'), '--root', str(root)],
                   check=True, capture_output=True)
    monkeypatch.setenv('PATH', f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv('FAKE_SLURM_DIR', str(root / 'slurm'))
    monkeypatch.chdir(root / 'bare')
    return root


def apply(case, **kw):
    args = SimpleNamespace(case=case, remote='local', only=None, dry_run=False, yes=True)
    for k, v in kw.items():
        setattr(args, k, v)
    return execute_apply(args)


def submitted(dummy):
    path = dummy / 'slurm' / 'submitted.log'
    return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []


def tree(root):
    return sorted((str(p.relative_to(root)), p.stat().st_size, p.stat().st_mtime)
                  for p in Path(root).rglob('*') if p.is_file())


def last_log(dummy):
    return sorted((dummy / 'bare' / 'auto_logs').glob('auto_*.log'))[-1].read_text()


# --- what it does ----------------------------------------------------------------------

def test_dry_run_changes_nothing_and_writes_no_log(dummy, capsys):
    before = tree(dummy)
    assert apply('*', dry_run=True) == 0
    out = capsys.readouterr().out
    assert 'organise history --update --clean --compile' in out and 'run post full --t1 350' in out
    assert 'nothing was done' in out
    assert tree(dummy) == before and not (dummy / 'bare' / 'auto_logs').exists()


def test_one_case_history_upload_and_post_in_that_order(dummy):
    assert apply('case5') == 0
    case, remote = dummy / 'bare' / 'case5', dummy / 'cloud' / 'bare' / 'case5'
    # history moved into archive/ as run 2, cleaned and compiled
    assert (case / 'othd_files' / 'archive' / 'riser2.othd').exists()
    assert not (case / 'RUN_1' / 'riser.othd').exists()
    assert (case / 'othd_files' / 'cleaned' / 'riser2.othd').exists()
    # every uploaded file is on the remote, byte for byte, as the ledger says
    ledger = Ledger(dummy / 'bare').data['local']['case5']
    assert 'othd_files/archive/riser2.othd' in ledger and 'RUN_1/riser.600_0.rst' not in ledger
    for rel, entry in ledger.items():
        assert entry['mtime'] == (case / rel).stat().st_mtime or rel == '.casestatus.md'
        assert file_md5(remote / rel) == entry['md5'] == file_md5(case / rel) or rel == '.casestatus.md'
        assert entry['verified'] == 'md5'
        assert entry['path'] == str(remote / rel)
    assert not list(remote.rglob('.*.part'))                    # no temporary file left
    # the post job went in with the window of the plan
    job = submitted(dummy)[-1]
    assert job['name'] == 'postcase5' and job['workdir'] == str(case)
    assert job['options']['export'] == 'ALL,START_TIME=350,END_TIME=500,FREQ=50'
    log = last_log(dummy)
    assert 'history  ok: moved RUN_1/riser.othd and .oisd into archive/ as run 2' in log
    assert 'post     ok: post job' in log and log.index(' history ') < log.index(' upload ') \
        < log.index(' post ')


def test_a_second_run_finds_nothing_to_do(dummy, capsys):
    assert apply('*') == 0
    capsys.readouterr()
    jobs = len(submitted(dummy))
    assert apply('*') == 0
    assert 'nothing to do' in capsys.readouterr().out and len(submitted(dummy)) == jobs


def test_only_limits_the_steps(dummy):
    assert apply('case5', only='upload') == 0
    assert (dummy / 'bare' / 'case5' / 'RUN_1' / 'riser.othd').exists()      # not organised
    assert not any(j['name'] == 'postcase5' for j in submitted(dummy))        # not posted
    assert Ledger(dummy / 'bare').data['local']['case5']
    assert apply('case5', only='nonsense') == 2


def test_nothing_is_deleted_anywhere(dummy):
    def names():
        return {p.relative_to(dummy / 'bare') for p in (dummy / 'bare').rglob('*')
                if p.is_file() and 'auto_logs' not in p.parts}
    before = names()
    apply('*')
    gone = before - names()
    # the only files that leave a place are the run directory's history, moved to archive/
    assert {g.name for g in gone} <= {'riser.othd', 'riser.oisd'}
    assert all('RUN_1' in g.parts for g in gone)


def test_a_running_cases_live_history_is_a_snapshot_not_moved(dummy):
    apply('case2')
    assert (dummy / 'bare' / 'case2' / 'RUN_1' / 'riser.othd').exists()
    ledger = Ledger(dummy / 'bare').data['local']['case2']
    assert ledger['RUN_1/riser.othd']['verified'] == 'snapshot'
    assert 'mtime' not in ledger['RUN_1/riser.othd']      # still being written


# --- when something goes wrong ------------------------------------------------------------

def test_a_failed_step_stops_that_case_and_the_others_go_on(dummy, monkeypatch, capsys):
    from src.core.auto import executor
    real = executor.do_upload

    def flaky(snap, plan, conf, cloud, ledger, say, **kw):
        if snap.name == 'case2':
            return executor.Step('upload', False, 'sent 0 of 16 files; 16 failed', 'x: boom')
        return real(snap, plan, conf, cloud, ledger, say, **kw)
    monkeypatch.setattr(executor, 'do_upload', flaky)
    assert apply('*') == 1
    jobs = {j['name'] for j in submitted(dummy)}
    assert 'postcase2' not in jobs and 'postcase3' in jobs      # case2 stopped before its post
    out = capsys.readouterr().out
    assert '✗ upload: sent 0 of 16 files; 16 failed' in out and '1 step(s) failed' in out
    assert 'upload   FAILED: sent 0 of 16 files' in last_log(dummy)


def test_a_post_the_script_name_refuses_is_reported(dummy, capsys):
    script = dummy / 'bare' / 'case3' / 'postFlex.sh'
    script.write_text(script.read_text().replace('-J postcase3', '-J postsomethingelse'))
    assert apply('case3', only='post') == 1
    out = capsys.readouterr().out
    assert ('✗ post: postFlex.sh names its job postsomethingelse, it should be postcase3' in
            ' '.join(out.split()))
    assert not any(j['name'] == 'postcase3' for j in submitted(dummy))


def test_an_unreadable_queue_does_nothing(dummy, capsys):
    subprocess.run([str(dummy / 'bin' / 'fake-slurm'), 'fail', 'on'], check=True,
                   env={**os.environ, 'FAKE_SLURM_DIR': str(dummy / 'slurm')})
    before = tree(dummy)
    assert apply('*') == 1
    assert 'the queue could not be read' in capsys.readouterr().out
    assert tree(dummy) == before


def test_declining_the_question_does_nothing(dummy, monkeypatch, capsys):
    monkeypatch.setattr('builtins.input', lambda prompt='': 'n')
    before = tree(dummy)
    assert apply('*', yes=False) == 1
    assert 'Cancelled' in capsys.readouterr().out and tree(dummy) == before


def test_another_run_holding_the_folder_stops_this_one(dummy, capsys):
    logs = dummy / 'bare' / 'auto_logs'
    logs.mkdir()
    (logs / 'apply.lock').write_text('login03 pid 4242 2026-11-11 10:00:00')
    before = tree(dummy)
    assert apply('case5') == 1
    assert 'another auto apply holds' in capsys.readouterr().out and tree(dummy) == before
    # a lock left by a run that died long ago is taken over
    old = time.time() - 13 * 3600
    os.utime(logs / 'apply.lock', (old, old))
    assert apply('case5') == 0 and not (logs / 'apply.lock').exists()


def test_the_lock_is_released_after_a_failure(dummy, monkeypatch):
    from src.core.auto import executor
    monkeypatch.setattr(executor, 'do_upload', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('x')))
    with pytest.raises(RuntimeError):
        apply('case5')
    assert not (dummy / 'bare' / 'auto_logs' / 'apply.lock').exists()


# --- a checked copy ------------------------------------------------------------------------

def test_local_put_leaves_nothing_under_the_real_name_when_the_md5_differs(tmp_path, monkeypatch):
    src = tmp_path / 'a.plt'
    src.write_bytes(b'x' * 1000)
    (tmp_path / 'remote').mkdir(exist_ok=True)
    cloud = LocalCloud(tmp_path / 'remote')
    calls = iter(['aaaa', 'bbbb'])                              # the file, then its copy
    monkeypatch.setattr(cloud_mod, 'file_md5', lambda p: next(calls))
    res = cloud.put(src, 'c1', 'binary/a.plt')
    assert not res.ok and 'md5 differs after the copy' in res.detail
    assert not list((tmp_path / 'remote').rglob('*a.plt*'))     # neither the file nor a .part


def test_local_put_replaces_an_older_copy_only_once_the_new_one_is_checked(tmp_path):
    (tmp_path / 'remote' / 'c1' / 'binary').mkdir(parents=True)
    old = tmp_path / 'remote' / 'c1' / 'binary' / 'a.plt'
    old.write_bytes(b'old')
    src = tmp_path / 'a.plt'
    src.write_bytes(b'new data')
    res = LocalCloud(tmp_path / 'remote').put(src, 'c1', 'binary/a.plt')
    assert res == PutResult(True, 8, file_md5(src), 'md5') and old.read_bytes() == b'new data'


class FakeSsh:
    """The few paramiko calls SftpCloud.put makes, on a local folder."""

    def __init__(self, md5sum=True, corrupt=False):
        self.md5sum, self.corrupt = md5sum, corrupt
        self.ssh_client = self
        self.sftp_client = self
        self.channel = self

    def make_remote_dir(self, path):
        os.makedirs(path, exist_ok=True)
        return True

    def upload_file(self, local, remote):
        data = Path(local).read_bytes()
        Path(remote).write_bytes(data[:-1] if self.corrupt else data)

    def remote_stat(self, path):
        return (os.path.getsize(path), 0) if os.path.exists(path) else None

    def exec_command(self, cmd, timeout=None):
        import shlex
        self._rc, self._out = 1, b''
        if self.md5sum:
            path = shlex.split(cmd)[1]
            self._rc, self._out = 0, f"{file_md5(path)}  {path}\n".encode()
        return None, self, None

    def read(self):
        return self._out

    def recv_exit_status(self):
        return self._rc

    def posix_rename(self, a, b):
        os.replace(a, b)

    def remove(self, path):
        os.remove(path)


def sftp_cloud(tmp_path, **kw):
    cloud = object.__new__(SftpCloud)
    cloud.root, cloud.where, cloud.ssh = str(tmp_path / 'nas'), 'nas', FakeSsh(**kw)
    return cloud


def test_sftp_put_checks_the_md5_on_the_remote(tmp_path):
    src = tmp_path / 'a.plt'
    src.write_bytes(os.urandom(5000))
    res = sftp_cloud(tmp_path).put(src, 'c1', 'binary/a.plt')
    assert res.ok and res.verified == 'md5'
    assert (tmp_path / 'nas' / 'c1' / 'binary' / 'a.plt').read_bytes() == src.read_bytes()


def test_md5_of_a_named_remote_file(tmp_path):
    (tmp_path / 'c1' / 'binary').mkdir(parents=True)
    there = tmp_path / 'c1' / 'binary' / 'a.plt'
    there.write_bytes(b'abc')
    local = LocalCloud(tmp_path)
    assert local.md5('c1', 'binary/a.plt') == file_md5(there)
    assert local.md5('c1', 'binary/none.plt') is None
    cloud = SftpCloud.__new__(SftpCloud)
    cloud.ssh, cloud.root, cloud.where = FakeSsh(), str(tmp_path), 'fake'
    assert cloud.md5('c1', 'binary/a.plt') == file_md5(there)
    # no md5sum there: the file is read back and hashed here
    cloud.ssh = FakeSsh(md5sum=False)
    cloud.ssh.open = open
    assert cloud.md5('c1', 'binary/a.plt') == file_md5(there)
    assert cloud.md5('c1', 'binary/none.plt') is None


def test_sftp_put_without_md5sum_says_it_only_compared_sizes(tmp_path):
    src = tmp_path / 'a.plt'
    src.write_bytes(b'abc' * 100)
    res = sftp_cloud(tmp_path, md5sum=False).put(src, 'c1', 'a.plt')
    assert res.ok and res.verified == 'size'


def test_sftp_put_removes_a_cut_short_copy(tmp_path):
    src = tmp_path / 'a.plt'
    src.write_bytes(b'abc' * 100)
    res = sftp_cloud(tmp_path, corrupt=True).put(src, 'c1', 'a.plt')
    assert not res.ok and 'sent 299 of 300 bytes' in res.detail
    assert not list((tmp_path / 'nas').rglob('*a.plt*'))


# --- the ledger and the lock -------------------------------------------------------------

def test_ledger_keeps_each_file_and_survives_an_unreadable_file(tmp_path):
    led = Ledger(tmp_path)
    led.record('cloud', 'c1', 'binary/a.plt', 10, 'abc', 'md5')
    assert Ledger(tmp_path).get('cloud', 'c1', 'binary/a.plt')['md5'] == 'abc'
    (tmp_path / 'auto_logs' / 'ledger.json').write_text('{not json')
    fresh = Ledger(tmp_path)
    assert fresh.data == {} and list((tmp_path / 'auto_logs').glob('ledger.json.bad-*'))


def test_the_lock_is_exclusive(tmp_path):
    with FolderLock(tmp_path):
        with pytest.raises(AutoLockError):
            FolderLock(tmp_path).__enter__()
    with FolderLock(tmp_path):
        pass


def test_apply_never_waits_for_an_answer(dummy, monkeypatch):
    """run post and organise history ask questions in some situations; apply must not
    reach one (its output is hidden, so a question would hang it)."""
    def no_input(prompt=''):
        raise AssertionError(f"apply asked a question: {prompt!r}")
    monkeypatch.setattr('builtins.input', no_input)
    script = dummy / 'bare' / 'case3' / 'postFlex.sh'
    script.write_text(script.read_text().replace('#SBATCH -J postcase3', '# no job name here'))
    assert apply('*') == 1                       # case3's post fails; nothing was asked


def test_apply_sends_the_grid_sets_and_not_the_newest(dummy):
    # case3 holds restart sets 200, 400, 550-750; upload_rst is 400 (dummy settings)
    assert apply('case3', only='upload') == 0
    remote = dummy / 'cloud' / 'bare' / 'case3' / 'RUN_1'
    sent = sorted({p.name.split('.')[1].split('_')[0] for p in remote.glob('riser.*_*.rst')})
    assert sent == ['400']                                      # not 700, not 750
    led = Ledger(dummy / 'bare').data['local']['case3']
    assert {k for k in led if k.endswith('.rst')} == {f'RUN_1/riser.400_{k}.rst' for k in range(4)}


def test_dry_run_says_which_binary_plts_replace_old_run_files_on_the_remote():
    from src.commands.auto.apply import _upload_breakdown
    from src.core.auto.decide import CasePlan
    plan = CasePlan('c1', 'running', ctx={'stale_plt': [5745, 5750]})
    plan.step('plt', 'upload', 'upload-plt', 'case upload plt c1',
              files={f'binary/riser.{t}.plt': 100 for t in (5745, 5750, 5760)})
    text = ' '.join(_upload_breakdown(plan))
    assert 'binary PLTs: 3 files' in text
    assert 'replaces 2 on the remote (5745, 5750, from before the restart)' in text
    plan.ctx = {}
    assert 'replaces' not in ' '.join(_upload_breakdown(plan))


def test_predate_agrees_with_the_number_of_steps():
    from src.core.auto.report import _predate
    assert _predate([8300]) == 'predates' and _predate([4950, 5000]) == 'predate'
