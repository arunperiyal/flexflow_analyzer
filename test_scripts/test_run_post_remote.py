"""`run post --remote`: postFlex.sh sends each binary PLT as soon as it is written.

The job runs simPlt2Bin in the background and sends a file once it has stopped
changing, then sends the rest when simPlt2Bin ends. These tests run the real
template end to end: a fake simPlt2Bin writes binary/riser.<step>.plt slowly,
and fake ssh/scp run the "remote" side in a local directory (rsync is the real
one, carried over the fake ssh). Also: the --t1/--t2 rename and how run post
builds the job's REMOTE_* variables.
"""

import argparse
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from src.commands.run import RunCommand
from src.commands.run.post_impl import command as post_cmd

TEMPLATE = Path(__file__).resolve().parent.parent / 'src' / 'templates' / 'scripts' / 'postFlex.sh'

FAKE_SIMPLT2BIN = r"""#!/bin/bash
# Writes each step in two halves with a pause, like preplot growing a file.
# Before the last step it waits for the first file to reach the "remote",
# which only happens if sending starts while conversion is still running.
while [ $# -gt 0 ]; do
    case "$1" in -f) FREQ=$2; shift 2;; -l) LAST=$2; shift 2;; -p) P=$2; shift 2;;
                 *) shift;; esac
done
mkdir -p binary
for step in $(seq "$FREQ" "$FREQ" 40); do
    if [ "$step" -eq "$LAST" ] && [ -n "$REMOTE_TARGET" ] && [ -z "$FAKE_DOWN" ]; then
        for i in $(seq 1 30); do
            [ -f "$FAKE_HOME/cases/Case/binary/$P.$FREQ.plt" ] && { echo yes > early_send; break; }
            sleep 1
        done
    fi
    printf 'first half of %s\n' "$step" > "binary/$P.$step.plt"
    sleep 1
    printf 'second half of %s\n' "$step" >> "binary/$P.$step.plt"
done
"""

FAKE_SSH = r"""#!/bin/bash
[ -n "$FAKE_DOWN" ] && { echo "ssh: connect to host: Connection refused" >&2; exit 255; }
while [ $# -gt 0 ]; do case "$1" in -o|-p|-l) shift 2;; -*) shift;; *) break;; esac; done
shift   # user@host
cmd="$*"
if [ -n "$FAKE_NO_RSYNC" ] && [ "$cmd" = "command -v rsync" ]; then exit 1; fi
cd "$FAKE_HOME" && exec bash -c "$cmd"
"""

FAKE_SCP = r"""#!/bin/bash
src="${@: -2:1}"; dest="${@: -1}"
cp "$src" "$FAKE_HOME/${dest#*:}"
"""


def _executable(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def job(tmp_path):
    case = tmp_path / 'Case'
    (case / 'binary').mkdir(parents=True)
    (case / 'simflow.config').write_text('problem = riser\ndir = ./RUN_1\noutFreq = 10\n')
    (case / 'riser.def').write_text('maxTimeSteps = 30\n')
    shutil.copy(TEMPLATE, case / 'postFlex.sh')

    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    _executable(fake_bin / 'simPlt2Bin', FAKE_SIMPLT2BIN)
    _executable(fake_bin / 'ssh', FAKE_SSH)
    _executable(fake_bin / 'scp', FAKE_SCP)
    (case / 'simflow_env.sh').write_text(
        f'export SIMPLT=/bin/true\nexport SIMPLT2BIN={fake_bin / "simPlt2Bin"}\n')

    # an old binary for step 0: in the window, but not written by this job
    old = case / 'binary' / 'riser.0.plt'
    old.write_text('from an earlier post job\n')
    os.utime(old, (1, 1))

    home = tmp_path / 'remote_home'
    home.mkdir()

    def run(**extra):
        env = dict(os.environ,
                   PATH=f"{fake_bin}:{os.environ['PATH']}",
                   SLURM_SUBMIT_DIR=str(case), SLURM_NTASKS='2', SLURM_CPUS_PER_TASK='1',
                   SLURM_JOB_ID='7', CONVERT_ONLY='1', FAKE_HOME=str(home),
                   REMOTE_TARGET='me@ws', REMOTE_DIR='~/cases/Case/binary',
                   SEND_STABLE_SECS='1', SEND_POLL_SECS='1')
        env.update(extra)
        result = subprocess.run(['bash', 'postFlex.sh'], cwd=case, env=env,
                                capture_output=True, text=True, timeout=180)
        return result, case, home / 'cases' / 'Case' / 'binary'

    return run


def _check_sent(result, case, remote):
    assert result.returncode == 0, result.stdout + result.stderr
    # the window is [0, 30]: step 40 is outside it, step 0 predates the job
    assert sorted(p.name for p in remote.iterdir()) == ['riser.10.plt', 'riser.20.plt',
                                                        'riser.30.plt']
    for p in remote.iterdir():
        assert p.read_bytes() == (case / 'binary' / p.name).read_bytes()
    assert (case / 'early_send').exists(), "nothing was sent while simPlt2Bin was running"
    assert (case / 'post_sent_7.log').read_text().count(' sent ') == 3
    assert not (case / '.post_start_7').exists()


def test_sends_each_file_as_it_is_written_with_rsync(job):
    result, case, remote = job()
    _check_sent(result, case, remote)
    assert '(rsync)' in result.stdout


def test_sends_with_scp_when_the_remote_has_no_rsync(job):
    result, case, remote = job(FAKE_NO_RSYNC='1')
    _check_sent(result, case, remote)
    assert '(scp)' in result.stdout
    assert not list(remote.glob('.*.part'))


def test_unreachable_remote_does_not_fail_the_job(job):
    result, case, remote = job(FAKE_DOWN='1')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'will NOT be sent' in result.stdout
    assert 'case upload --binary --t1 0 --t2 30' in result.stdout
    assert not remote.exists()
    assert (case / 'binary' / 'riser.30.plt').exists()


def test_no_remote_sends_nothing(job):
    result, case, remote = job(REMOTE_TARGET='')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Send to:' not in result.stdout
    assert not remote.exists()


# --- run post: parsing and the job's variables -------------------------------

@pytest.fixture
def parse():
    parser = argparse.ArgumentParser()
    RunCommand().setup_parser(parser.add_subparsers(dest='command'))
    return lambda *words: parser.parse_args(['run', 'post', *words])


def test_t1_t2_replace_start_upto(parse):
    args = parse('full', 'Case001', '--t1', '100', '--t2', '500')
    assert (args.t1, args.t2) == (100, 500)
    with pytest.raises(SystemExit):
        parse('full', 'Case001', '--upto', '500')


@pytest.fixture
def case_with_script(tmp_path, monkeypatch):
    case = tmp_path / 'Case001'
    case.mkdir()
    (case / 'simflow.config').write_text('problem = riser\noutFreq = 50\n')
    shutil.copy(TEMPLATE, case / 'postFlex.sh')
    remotes = {'ws': {'name': 'ws', 'user': 'me', 'ip': '10.0.0.5', 'port': 2222,
                      'password': '', 'path': '~/cases'}}
    from src.utils import remote_config
    monkeypatch.setattr(remote_config.RemoteConfig, 'get_remote',
                        lambda self, name: remotes.get(name))
    return case


def _exports(case, check=False, **kw):
    from rich.console import Console
    args = argparse.Namespace(**{'t1': None, 't2': None, 'freq': None, 'convert': False,
                                 'remote': None, 'no_remote': False, **kw})
    return post_cmd._job_exports(args, case, case / 'postFlex.sh',
                                 Console(file=open(os.devnull, 'w')), check_remote=check)


def test_remote_becomes_the_jobs_variables(case_with_script):
    exports, rows = _exports(case_with_script, remote='ws', t1=100.0, t2=500.0)
    assert exports == ['START_TIME=100', 'END_TIME=500', 'REMOTE_TARGET=me@10.0.0.5',
                       'REMOTE_PORT=2222', 'REMOTE_DIR=~/cases/Case001/binary']
    assert ('Send binary PLT to', 'ws  (me@10.0.0.5:~/cases/Case001/binary)') in rows


def test_no_remote_wins_over_the_context(case_with_script):
    exports, _ = _exports(case_with_script, remote='ws', no_remote=True)
    assert not any(e.startswith('REMOTE_') for e in exports)


def test_unknown_remote_and_old_script_are_refused(case_with_script):
    assert _exports(case_with_script, remote='nope') is None
    (case_with_script / 'postFlex.sh').write_text('#!/bin/bash\nsimPlt2Bin\n')
    assert _exports(case_with_script, remote='ws') is None


def test_submit_refuses_when_key_login_fails(case_with_script, monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 255, '', 'Permission denied (publickey).')

    monkeypatch.setattr(post_cmd.subprocess, 'run', fake_run)
    assert _exports(case_with_script, check=True, remote='ws') is None
    assert calls[0][:3] == ['ssh', '-o', 'BatchMode=yes']
    assert calls[0][-2:] == ['me@10.0.0.5', 'true']


def test_fractional_t1_is_refused(case_with_script):
    assert _exports(case_with_script, t1=10.5) is None
