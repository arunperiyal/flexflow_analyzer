"""case upload/download and run post --remote: where a case goes on a remote.
--remote-path, else the remote's folder in the case's own .cases.yml, else
the remote's `remote set-path`, else ~; then /<case name>."""

from registry_files import write_registry
from src.commands.case.download_impl.command import CaseUploadCommand

CLOUD = {'name': 'cloud', 'user': 'u', 'ip': '1.2.3.4', 'password': 'p',
         'path': '/shares/set-path'}


def test_order_of_the_base_folder(tmp_path):
    cmd = CaseUploadCommand()
    write_registry(tmp_path, [], remotes={'cloud': '/shares/x/bare', 'wsl': 'EDIT_ME'})
    assert cmd.get_remote_base_path(CLOUD, '/given', tmp_path) == '/given'
    assert cmd.get_remote_base_path(CLOUD, None, tmp_path) == '/shares/x/bare'
    assert cmd.get_remote_base_path(dict(CLOUD, name='wsl'), None, tmp_path) == '/shares/set-path'
    assert cmd.get_remote_base_path(dict(CLOUD, name='nas'), None, tmp_path) == '/shares/set-path'
    assert cmd.get_remote_base_path(CLOUD, None, tmp_path / 'nothing') == '/shares/set-path'
    assert cmd.get_remote_base_path(dict(CLOUD, path=''), None, None) == '~'


def test_each_case_goes_to_its_own_folders_place(tmp_path):
    cmd = CaseUploadCommand()
    bare, helical = tmp_path / 'bare', tmp_path / 'helical'
    for folder, there in ((bare, '/shares/x/bare'), (helical, '/shares/x/helical')):
        (folder / 'c1').mkdir(parents=True)
        write_registry(folder, [{'name': 'c1', 'path': str(folder / 'c1')}],
                       remotes={'cloud': there})
    base = cmd.get_remote_base_path(CLOUD, None, bare)
    assert cmd.construct_remote_case_path(base, str(bare / 'c1'), CLOUD, None) == '/shares/x/bare/c1'
    assert cmd.construct_remote_case_path(base, str(helical / 'c1'), CLOUD, None) == \
        '/shares/x/helical/c1'
    # --remote-path wins for every case
    assert cmd.construct_remote_case_path('/given', str(helical / 'c1'), CLOUD, '/given') == '/given/c1'
    # without the remote, the base is used as it is (the old behaviour)
    assert cmd.construct_remote_case_path('/b', str(helical / 'c1')) == '/b/c1'
