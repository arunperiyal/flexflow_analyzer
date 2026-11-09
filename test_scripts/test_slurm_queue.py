"""Reading the SLURM queue: failures are errors, jobs belong to cases by
working directory (src/core/slurm.py and the commands that use it)."""

import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core import slurm


def fake_squeue(tmp_path, monkeypatch, stdout='', stderr='', code=0):
    """Put an `squeue` on PATH that prints stdout/stderr and exits with code."""
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / 'out.txt').write_text(stdout)
    (bin_dir / 'err.txt').write_text(stderr)
    script = bin_dir / 'squeue'
    script.write_text(f"#!/bin/sh\ncat '{bin_dir}/out.txt'\ncat '{bin_dir}/err.txt' >&2\nexit {code}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv('PATH', f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv('USER', 'tester')


def line(jobid, name, state, workdir, partition='medium'):
    return f"{jobid}|{name}|{state}|{partition}|{workdir}\n"


@pytest.fixture
def cases(tmp_path):
    root = tmp_path / 'bare'
    for name in ('CS4', 'CS40', 'BR0SG0U2P0'):
        (root / name).mkdir(parents=True)
    return root


# --- failures are errors, never an empty queue --------------------------------

def test_exit_code_is_an_error(tmp_path, monkeypatch):
    fake_squeue(tmp_path, monkeypatch, stderr='slurm_load_jobs error: Invalid job id specified', code=1)
    with pytest.raises(slurm.QueueError, match='Invalid job id'):
        slurm.read_queue()


def test_stderr_with_exit_0_is_an_error(tmp_path, monkeypatch):
    # what squeue does for an unknown user on PARAM Shakti
    fake_squeue(tmp_path, monkeypatch, stderr='squeue: error: Invalid user: tester', code=0)
    with pytest.raises(slurm.QueueError, match='Invalid user'):
        slurm.read_queue()


def test_unreadable_line_is_an_error(tmp_path, monkeypatch):
    fake_squeue(tmp_path, monkeypatch, stdout='123|mainX|RUNNING\n')
    with pytest.raises(slurm.QueueError, match='unexpected squeue line'):
        slurm.read_queue()


def test_missing_squeue_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setenv('PATH', str(tmp_path))
    with pytest.raises(slurm.QueueError, match='not found'):
        slurm.read_queue()


def test_empty_queue_is_empty(tmp_path, monkeypatch):
    fake_squeue(tmp_path, monkeypatch, stdout='')
    assert slurm.read_queue() == []


# --- a job belongs to the case it was submitted from -------------------------

def test_jobs_match_by_workdir_not_name(cases):
    jobs = slurm.parse_queue(
        line(1, 'mainCS4', 'RUNNING', cases / 'CS4') +
        line(2, 'mainCS40', 'PENDING', cases / 'CS40') +
        # postFlex.sh copied from BR0SG0U1P0 into BR0SG0U2P0 without renaming
        line(3, 'postBR0SG0U1P0', 'RUNNING', cases / 'BR0SG0U2P0'))
    assert [j.jobid for j in slurm.jobs_for_case(cases / 'CS4', jobs)] == ['1']
    assert [j.jobid for j in slurm.jobs_for_case(cases / 'CS40', jobs)] == ['2']
    u2 = slurm.jobs_for_case(cases / 'BR0SG0U2P0', jobs)
    assert [j.jobid for j in u2] == ['3']
    assert u2[0].kind == 'post' and not u2[0].named_for('BR0SG0U2P0')


def test_workdir_through_a_symlink(cases, tmp_path):
    link = tmp_path / 'link_to_cs4'
    link.symlink_to(cases / 'CS4')
    jobs = slurm.parse_queue(line(7, 'mainCS4', 'RUNNING', link))
    assert slurm.jobs_for_case(cases / 'CS4', jobs)[0].jobid == '7'


def test_kind_active_and_name():
    job = slurm.parse_queue(line(9, 'mainBR0SG0U4P0', 'PENDING', '/x'))[0]
    assert (job.kind, job.active, job.pending) == ('main', True, True)
    assert job.named_for('BR0SG0U4P0')
    done = slurm.parse_queue(line(10, 'probeFlexflow', 'COMPLETED', '/x'))[0]
    assert (done.kind, done.active) == ('other', False)


def test_case_jobs_reads_and_filters(tmp_path, monkeypatch, cases):
    fake_squeue(tmp_path, monkeypatch, stdout=line(1, 'mainCS4', 'RUNNING', cases / 'CS4')
                + line(2, 'mainCS40', 'RUNNING', cases / 'CS40'))
    assert [j.jobid for j in slurm.case_jobs(cases / 'CS40')] == ['2']


# --- run sq ----------------------------------------------------------------

def test_run_sq_shows_error_not_empty_queue(tmp_path, monkeypatch, capsys):
    from src.commands.run.sq_impl import command as sq
    fake_squeue(tmp_path, monkeypatch, stderr='squeue: error: Invalid user: tester')
    sq.show_queue(SimpleNamespace(all=False, by_dir=False, sort=None))
    out = capsys.readouterr().out
    assert 'Invalid user' in out and 'No jobs in queue' not in out


def test_run_sq_reads_workdir_from_squeue(cases):
    from src.commands.run.sq_impl import command as sq
    row = f"12|mainCS4|RUNNING|01:00|1|medium|120|0|2026-11-09T10:00:00|None|(null)|{cases / 'CS4'}"
    job = sq.parse_queue_output(row)[0]
    assert job['workdir'] == str(cases / 'CS4')
    # without the %Z column the row still parses, workdir left for scontrol
    old = row.rsplit('|', 1)[0]
    assert sq.parse_queue_output(old)[0]['workdir'] is None


# --- case status and case run ------------------------------------------------

def test_case_status_flags_a_job_named_for_another_case(tmp_path, monkeypatch, cases):
    from src.commands.case.status_impl import command as status
    fake_squeue(tmp_path, monkeypatch,
                stdout=line(3, 'postBR0SG0U1P0', 'RUNNING', cases / 'BR0SG0U2P0'))
    shown = status._queued_jobs(cases / 'BR0SG0U2P0')
    assert shown == ['postBR0SG0U1P0 3 RUNNING (named for another case; expected postBR0SG0U2P0)']
    assert status._queued_jobs(cases / 'CS4') == []


def test_case_status_says_when_the_queue_failed(tmp_path, monkeypatch, cases):
    from src.commands.case.status_impl import command as status
    fake_squeue(tmp_path, monkeypatch, stderr='slurm_load_jobs error: timeout', code=1)
    assert status._queued_jobs(cases / 'CS4')[0].startswith('could not read the queue')


def test_case_run_counts_an_unreadable_queue_as_running(tmp_path, monkeypatch, cases):
    from src.commands.case.run import CaseRunCommand
    fake_squeue(tmp_path, monkeypatch, stderr='slurm_load_jobs error: timeout', code=1)
    runner = CaseRunCommand.__new__(CaseRunCommand)
    runner.case_dir = cases / 'CS4'
    assert runner.is_case_running() is True


def test_case_run_by_workdir(tmp_path, monkeypatch, cases):
    from src.commands.case.run import CaseRunCommand
    fake_squeue(tmp_path, monkeypatch, stdout=line(1, 'mainCS40', 'RUNNING', cases / 'CS40'))
    runner = CaseRunCommand.__new__(CaseRunCommand)
    runner.case_dir = cases / 'CS4'
    monkeypatch.setattr('subprocess.run', _no_ps(monkeypatch))
    assert runner.is_case_running() is False


def _no_ps(monkeypatch):
    """subprocess.run that serves squeue as usual but shows no mpiSimflow in ps."""
    import subprocess
    real = subprocess.run

    def run(cmd, *a, **k):
        if cmd and cmd[0] == 'ps':
            return SimpleNamespace(stdout='', stderr='', returncode=0)
        return real(cmd, *a, **k)
    return run
