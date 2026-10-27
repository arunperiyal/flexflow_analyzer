"""`case upload|download input`: <problem>.def and every file it names with
File(...). Every launch of mpiSimflow runs the preprocessor again from these
(solStart.c) and rewrites the .sgd/.cas, so a restart needs the inputs
unchanged, not the .sgd. Nothing is sent when one of them is missing."""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from src.commands.case.download_impl import command as transfer
from src.commands.case.download_impl.command import CaseDownloadCommand, def_inputs

DEF = '''\
COORDINATE{ coordinates = File( "riser.crd" ) }
ELEMENT_SET{ elements = File("riser.fluid.cnn") }
#   nodes = File( "old.nbc" )
SURFACE{ surfaces = File( "bc/riser.cyl.srf" ) nodes = File( "riser.cyl.nbc" ) }
NODAL_BC{ nodes = File( "riser.cyl.nbc" ) }
'''
INPUTS = ['riser.crd', 'riser.fluid.cnn', 'bc/riser.cyl.srf', 'riser.cyl.nbc']


@pytest.fixture
def case(tmp_path):
    case = tmp_path / 'CS1'
    (case / 'bc').mkdir(parents=True)
    (case / 'simflow.config').write_text('problem = riser\nnsg = 4\ndir = ./RUN_1\n')
    (case / 'riser.def').write_text(DEF)
    for name in INPUTS + ['riser.0.sgd', 'riser.geo']:
        (case / name).write_text('x')
    return case


def test_def_inputs_skips_comments_and_repeats(case):
    assert def_inputs(case / 'riser.def') == INPUTS


def sent(ssh):
    return sorted(c.args[1] for c in ssh.upload_file.call_args_list)


def test_upload_input_sends_the_def_and_its_files(case):
    ssh = MagicMock()
    ssh.remote_path_exists.return_value = True
    assert CaseDownloadCommand().upload_input(ssh, '/r/CS1', str(case))
    assert sent(ssh) == sorted(f'/r/CS1/{n}' for n in ['riser.def'] + INPUTS)


def test_upload_input_with_one_missing_sends_nothing(case, capsys):
    (case / 'riser.crd').unlink()
    ssh = MagicMock()
    assert not CaseDownloadCommand().upload_input(ssh, '/r/CS1', str(case))
    ssh.upload_file.assert_not_called()
    assert '1 of them missing' in capsys.readouterr().out


def test_upload_input_refuses_paths_outside_the_case(case, capsys):
    (case / 'riser.def').write_text(DEF + 'X{ nodes = File( "../shared/a.nbc" ) }\n')
    ssh = MagicMock()
    assert not CaseDownloadCommand().upload_input(ssh, '/r/CS1', str(case))
    assert 'outside the case' in ' '.join(capsys.readouterr().out.split())


class FakeRemote:
    """An SSH stand-in over a local directory that plays the remote case."""

    def __init__(self, root):
        self.root = root

    def connect(self):
        return True

    def disconnect(self):
        pass

    def _local(self, path):
        return self.root / path.removeprefix('/r/CS1').lstrip('/')

    def remote_path_exists(self, path):
        return self._local(path).exists()

    def download_file(self, path, local, callback=None):
        import shutil
        shutil.copy(self._local(path), local)


def test_download_input_reads_the_remote_def(case, tmp_path):
    here = tmp_path / 'local'
    here.mkdir()
    assert CaseDownloadCommand().download_input(FakeRemote(case), '/r/CS1', str(here))
    got = sorted(str(p.relative_to(here)) for p in here.rglob('*') if p.is_file())
    assert got == sorted(['riser.def'] + INPUTS)


def test_case_upload_input_end_to_end(tmp_path, case):
    cmd = CaseDownloadCommand()
    cmd._get_transfer_state_file = lambda: tmp_path / 'state.json'
    cmd.validate_remote = lambda name: {'user': 'u', 'ip': 'h', 'port': 22,
                                        'password': None, 'path': '/r'}
    ns = argparse.Namespace(what='input', case=str(case), to='srv', dir=None, files=None,
                            t1=None, t2=None, force=False, resume=False, help=False,
                            examples=False, remote_path='/r', binary=False)
    with patch.object(transfer, 'SSHClientWrapper') as ssh_class:
        ssh = ssh_class.return_value
        ssh.remote_path_exists.return_value = True
        assert cmd.execute_upload(ns) == 0
    assert len(ssh.upload_file.call_args_list) == 5
