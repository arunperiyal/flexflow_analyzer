"""tools/make_dummy.py builds the dummy cases, and tools/fake_slurm.py answers
as SLURM did on PARAM Shakti. Built once per module into a temp folder."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.core import slurm
from src.core.plt_valid import check_plt
from src.core.settled import out_steps, settled_steps

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope='module')
def dummy(tmp_path_factory):
    root = tmp_path_factory.mktemp('dummy') / 'dummy'
    subprocess.run([sys.executable, str(REPO / 'tools' / 'make_dummy.py'), '--root', str(root)],
                   check=True, capture_output=True)
    return root


@pytest.fixture
def fake_path(dummy, monkeypatch):
    monkeypatch.setenv('PATH', f"{dummy / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv('FAKE_SLURM_DIR', str(dummy / 'slurm'))
    return dummy


def run(dummy, *cmd, cwd=None):
    return subprocess.run(list(cmd), capture_output=True, text=True, cwd=cwd,
                          env={**os.environ, 'PATH': f"{dummy / 'bin'}{os.pathsep}{os.environ['PATH']}",
                               'FAKE_SLURM_DIR': str(dummy / 'slurm')})


def test_eleven_cases_registered(dummy):
    from src.core import cases_file
    cf = cases_file.read(dummy / 'bare')
    assert [c['name'] for c in cf.cases] == [f'case{i}' for i in range(1, 12)]
    assert all(Path(c['path']).is_dir() for c in cf.cases)
    assert cf.remotes == {'local': str(dummy / 'cloud' / 'bare')}
    assert cf.auto == {'keep_rst': 200, 'disk_alert': '1M'}


def test_queue_read_through_the_real_reader(fake_path):
    jobs = slurm.read_queue()
    assert {(j.name, Path(j.workdir).name, j.state) for j in jobs} == {
        ('maincase2', 'case2', 'RUNNING'), ('maincase3', 'case3', 'PENDING'),
        ('postcase4', 'case4', 'RUNNING'), ('maincase1', 'case10', 'RUNNING')}
    bare = fake_path / 'bare'
    assert slurm.jobs_for_case(bare / 'case1', jobs) == []          # not case10's maincase1


def test_squeue_errors_like_the_cluster(dummy):
    bad_user = run(dummy, 'squeue', '-h', '-u', 'nobody_xyz')
    assert bad_user.returncode == 0 and 'Invalid user' in bad_user.stderr
    bad_job = run(dummy, 'squeue', '-h', '-j', '999')
    assert bad_job.returncode == 1 and 'Invalid job id' in bad_job.stderr


def test_fail_switch_makes_the_reader_raise(fake_path):
    run(fake_path, 'fake-slurm', 'fail', 'on')
    try:
        with pytest.raises(slurm.QueueError):
            slurm.read_queue()
    finally:
        run(fake_path, 'fake-slurm', 'fail', 'off')
    assert slurm.read_queue()


def test_sbatch_finish_and_sacct(dummy):
    case5 = dummy / 'bare' / 'case5'
    out = run(dummy, 'sbatch', '--export=ALL,START_TIME=350', 'postFlex.sh', cwd=case5)
    jobid = out.stdout.split()[-1]
    assert out.stdout.startswith('Submitted batch job')
    queue = run(dummy, 'squeue', '-h', '-u', os.environ.get('USER', 'user'), '-o', '%i|%j|%T|%Z').stdout
    assert f"{jobid}|postcase5|PENDING|{case5}" in queue
    run(dummy, 'fake-slurm', 'finish', jobid, 'TIMEOUT')
    assert jobid not in run(dummy, 'squeue', '-h', '-o', '%i').stdout
    acct = run(dummy, 'sacct', '-X', '-n', '-P', '--format=JobID,JobName%30,State,WorkDir').stdout
    assert f"{jobid}|postcase5|TIMEOUT|{case5}" in acct
    log = [json.loads(l) for l in (dummy / 'slurm' / 'submitted.log').read_text().splitlines()]
    assert log[-1]['options']['export'] == 'ALL,START_TIME=350'


def test_files_are_what_the_checks_expect(dummy):
    bare = dummy / 'bare'
    assert not check_plt(bare / 'case6' / 'binary' / 'riser.550.plt').ok      # cut short
    assert check_plt(bare / 'case6' / 'binary' / 'riser.450.plt').ok
    assert check_plt(dummy / 'cloud' / 'bare' / 'case1' / 'binary' / 'riser.1000.plt').ok
    # case2: solver at 652, step 650 has 3 of 4 parts
    ok, why = settled_steps(out_steps(bare / 'case2' / 'RUN_1', 'riser'), nsg=4,
                            running=True, solver_at=652, quiet_secs=0)
    assert ok == list(range(450, 601, 50)) and why[650] == '3 of 4 .out parts'
    # case8: archive/ pruned (the real --prune leaves the folder, empty), cleaned/ kept
    assert list((bare / 'case8' / 'othd_files' / 'archive').glob('*.othd')) == []
    assert (bare / 'case8' / 'othd_files' / 'cleaned' / 'riser1.othd').exists()
    from src.core.simflow_config import SimflowConfig
    assert SimflowConfig.find(bare / 'case9').problem is None
