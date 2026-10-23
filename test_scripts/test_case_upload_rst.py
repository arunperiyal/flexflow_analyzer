"""`case upload|download rst|sgd`: the restart files of some steps (every step
without --t1/--t2), and the new spelling `case upload|download binary` that
replaces --binary.

A restart from step T needs <problem>.T.sgd and one <problem>.T_<k>.rst per
subgrid (nsg in simflow.config). `sgd` carries the first, `rst` the second; a
step short of .rst files cannot restart and its .rst files are not sent.
"""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from src.commands.case.download_impl import command as transfer
from src.commands.case.download_impl.command import CaseDownloadCommand, select_restart

NAMES = (['riser.4000.sgd'] + [f'riser.4000_{k}.rst' for k in range(4)]
         + ['riser.4500.sgd'] + [f'riser.4500_{k}.rst' for k in range(3)]      # one .rst short
         + [f'riser.5000_{k}.rst' for k in range(4)]                            # no .sgd
         + ['riser.4000_0.out', 'riser.4000.plt', 'riser.othd', 'other.4000.sgd'])


RST_4000 = [f'riser.4000_{k}.rst' for k in range(4)]
RST_5000 = [f'riser.5000_{k}.rst' for k in range(4)]


def test_select_restart_keeps_only_complete_rst_steps():
    complete, incomplete = select_restart(NAMES, 'riser', (4000, 5000), nsg=4)
    assert complete == {4000: RST_4000, 5000: RST_5000}     # .rst alone: no .sgd needed
    assert list(incomplete) == [4500]
    # one step alone, and nsg unknown (any .rst will do)
    assert list(select_restart(NAMES, 'riser', (4500, 4500), nsg=None)[0]) == [4500]
    assert select_restart(NAMES, 'riser', (1, 10), nsg=4) == ({}, {})


def test_select_restart_without_a_window_takes_every_step():
    assert list(select_restart(NAMES, 'riser', None, nsg=4)[0]) == [4000, 5000]
    assert select_restart(NAMES, 'riser', None, nsg=4, kind='sgd') == \
        ({4000: ['riser.4000.sgd'], 4500: ['riser.4500.sgd']}, {})


def test_rst_files_sort_by_subgrid_number():
    names = ['riser.7.sgd'] + [f'riser.7_{k}.rst' for k in (10, 2, 1, 0)]
    complete, _ = select_restart(names, 'riser', (7, 7), nsg=4)
    assert complete[7] == ['riser.7_0.rst', 'riser.7_1.rst', 'riser.7_2.rst', 'riser.7_10.rst']


@pytest.fixture
def case(tmp_path):
    case = tmp_path / 'CS1'
    run = case / 'RUN_1'
    run.mkdir(parents=True)
    (case / 'simflow.config').write_text('problem = riser\nnsg \t= 4\ndir\t= ./RUN_1\n')
    for name in NAMES:
        (run / name).write_text('x' * 10)
    return case


def uploaded(ssh):
    return [(c.args[0].rsplit('/', 1)[1], c.args[1]) for c in ssh.upload_file.call_args_list]


def test_upload_restart_sends_the_complete_steps_into_the_remote_run_dir(case, capsys):
    ssh = MagicMock()
    ssh.remote_path_exists.return_value = True
    ok = CaseDownloadCommand().upload_restart(ssh, '/r/CS1', str(case), (4000.0, 5000.0))
    assert ok
    assert uploaded(ssh) == [(n, f'/r/CS1/RUN_1/{n}') for n in RST_4000 + RST_5000]
    out = capsys.readouterr().out
    assert 'skipping step 4500' in out and '3/4 .rst' in out


def test_upload_sgd_sends_only_the_sgd_files(case):
    ssh = MagicMock()
    ssh.remote_path_exists.return_value = True
    assert CaseDownloadCommand().upload_restart(ssh, '/r/CS1', str(case), None, kind='sgd')
    assert [n for n, _ in uploaded(ssh)] == ['riser.4000.sgd', 'riser.4500.sgd']


def test_upload_restart_with_nothing_complete_fails(case):
    ssh = MagicMock()
    assert not CaseDownloadCommand().upload_restart(ssh, '/r/CS1', str(case), (4500.0, 4500.0))
    ssh.upload_file.assert_not_called()


def test_upload_restart_needs_force_for_a_missing_remote_dir(case):
    ssh = MagicMock()
    ssh.remote_path_exists.return_value = False
    assert not CaseDownloadCommand().upload_restart(ssh, '/r/CS1', str(case), (4000.0, 4000.0))
    ssh.make_remote_dir.return_value = True
    assert CaseDownloadCommand().upload_restart(ssh, '/r/CS1', str(case), (4000.0, 4000.0),
                                                force=True)
    ssh.make_remote_dir.assert_called_with('/r/CS1/RUN_1')


REMOTE = {'user': 'u', 'ip': 'h', 'port': 22, 'password': None, 'path': '/r'}


def args(**kw):
    ns = dict(what=None, case=None, to='srv', dir=None, files=None, t1=None, t2=None,
              force=False, resume=False, help=False, examples=False, remote_path='/r',
              binary=False)
    ns.update(kw)
    return argparse.Namespace(**ns)


@pytest.fixture
def cmd(tmp_path):
    cmd = CaseDownloadCommand()
    cmd._get_transfer_state_file = lambda: tmp_path / 'state.json'
    cmd.validate_remote = lambda name: REMOTE
    return cmd


def test_case_upload_rst_end_to_end(cmd, case):
    with patch.object(transfer, 'SSHClientWrapper') as ssh_class:
        ssh = ssh_class.return_value
        ssh.remote_path_exists.return_value = True
        assert cmd.execute_upload(args(what='rst', case=str(case), t1=4000.0)) == 0
    assert [n for n, _ in uploaded(ssh)] == RST_4000


@pytest.mark.parametrize('what, names', [('rst', RST_4000 + RST_5000),
                                         ('sgd', ['riser.4000.sgd', 'riser.4500.sgd'])])
def test_case_upload_rst_sgd_without_steps_sends_every_step(cmd, case, what, names):
    with patch.object(transfer, 'SSHClientWrapper') as ssh_class:
        ssh = ssh_class.return_value
        ssh.remote_path_exists.return_value = True
        assert cmd.execute_upload(args(what=what, case=str(case))) == 0
    assert [n for n, _ in uploaded(ssh)] == names


@pytest.mark.parametrize('kw, message', [
    (dict(what='rst', t1=4000.0, dir='binary'), 'carries the .rst files only'),
    (dict(what='sgd', files=True), 'carries the .sgd files only'),
    (dict(t1=4000.0), 'need `case upload binary`, `rst` or `sgd`'),
    (dict(binary=True), '--binary is now a word'),
    (dict(what='CS1', case='CS2'), "'CS1' is not binary, rst or sgd"),
])
def test_case_upload_errors(cmd, case, capsys, kw, message):
    kw.setdefault('case', str(case))
    assert cmd.execute_upload(args(**kw)) == 1
    assert message in ' '.join(capsys.readouterr().out.split())


def test_the_case_may_come_first(cmd, case):
    """`case upload CS1` (no binary/rst): the first word is the case."""
    with patch.object(cmd, 'upload_directory', return_value=True) as up, \
            patch.object(transfer, 'SSHClientWrapper'):
        assert cmd.execute_upload(args(what=str(case), dir='othd_files')) == 0
    assert up.call_args.args[2] == str(case)


def test_in_the_shell_the_case_context_fills_only_a_mode(tmp_path, monkeypatch):
    import io
    from rich.console import Console
    from shellkit import Runtime
    from shellkit.context import fill_context
    from src.cli.app import create_app
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    (tmp_path / 'CaseA').mkdir()
    monkeypatch.chdir(tmp_path)
    rt = Runtime(create_app(), console=Console(file=io.StringIO()),
                 err_console=Console(file=io.StringIO()))
    assert rt.execute_line('use case:CaseA') == 0

    def parsed(line):
        ns = rt.parser.parse_args(line.split())
        fill_context(ns, rt.context)
        return ns
    ns = parsed('case upload rst --t1 5')
    assert (ns.what, ns.case.endswith('CaseA')) == ('rst', True)
    ns = parsed('case upload CS9')
    assert (ns.what, ns.case) == ('CS9', None)        # moved to case by the command


# --- case download rst ---------------------------------------------------------

class FakeRemote:
    """An SSH stand-in over a local directory that plays the remote case."""

    def __init__(self, root):
        self.root = root
        self.fetched = []

    def connect(self):
        return True

    def disconnect(self):
        pass

    def _local(self, path):
        return self.root / path.removeprefix('/r/CS1').lstrip('/')

    def remote_path_exists(self, path):
        return self._local(path).exists()

    def list_remote_dir(self, path):
        return sorted(p.name for p in self._local(path).iterdir())

    def download_file(self, path, local, callback=None):
        self.fetched.append(path)
        import shutil
        shutil.copy(self._local(path), local)


def test_download_restart_reads_the_remote_config(case, tmp_path):
    here = tmp_path / 'local'
    here.mkdir()
    remote = FakeRemote(case)
    assert CaseDownloadCommand().download_restart(remote, '/r/CS1', str(here), (4000.0, 5000.0))
    assert sorted(p.name for p in (here / 'RUN_1').iterdir()) == RST_4000 + RST_5000
    assert remote.fetched[0] == '/r/CS1/simflow.config'


def test_download_sgd_of_every_step(case, tmp_path):
    here = tmp_path / 'local'
    here.mkdir()
    assert CaseDownloadCommand().download_restart(FakeRemote(case), '/r/CS1', str(here),
                                                  None, kind='sgd')
    assert sorted(p.name for p in (here / 'RUN_1').iterdir()) == \
        ['riser.4000.sgd', 'riser.4500.sgd']


def test_download_restart_falls_back_to_the_local_config(case, tmp_path):
    here = tmp_path / 'local'
    here.mkdir()
    (here / 'simflow.config').write_text((case / 'simflow.config').read_text())
    (case / 'simflow.config').unlink()
    assert CaseDownloadCommand().download_restart(FakeRemote(case), '/r/CS1', str(here),
                                                  (4000.0, 4000.0))
    assert len(list((here / 'RUN_1').iterdir())) == 4


def test_download_restart_with_nothing_complete_fails(case, tmp_path):
    remote = FakeRemote(case)
    assert not CaseDownloadCommand().download_restart(remote, '/r/CS1', str(tmp_path),
                                                      (4500.0, 4500.0))
    assert remote.fetched == ['/r/CS1/simflow.config']


def test_case_download_rst_end_to_end(cmd, case, tmp_path):
    here = tmp_path / 'local' / 'CS1'          # remote case path: /r/CS1
    here.mkdir(parents=True)
    remote = FakeRemote(case)
    with patch.object(transfer, 'SSHClientWrapper', return_value=remote):
        ns = args(what='rst', case=str(here), t1=4000.0, from_remote='srv', freq=None)
        assert cmd.execute_download(ns) == 0
    assert len(list((here / 'RUN_1').iterdir())) == 4


def test_case_download_rst_without_steps_fetches_every_step(cmd, case, tmp_path):
    here = tmp_path / 'local' / 'CS1'
    here.mkdir(parents=True)
    with patch.object(transfer, 'SSHClientWrapper', return_value=FakeRemote(case)):
        ns = args(what='rst', case=str(here), from_remote='srv', freq=None)
        assert cmd.execute_download(ns) == 0
    assert sorted(p.name for p in (here / 'RUN_1').iterdir()) == RST_4000 + RST_5000
