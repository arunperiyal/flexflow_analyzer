"""`auto init` sets a remote's folder and auto's settings in .cases.yml; the
cases file itself (src/core/cases_file.py) and auto's reading of it."""

from types import SimpleNamespace

import pytest

from src.commands.auto import init as init_cmd
from src.core import cases_file
from src.core.auto import conf

REMOTES = [{'name': 'cloud', 'user': 'sshd', 'ip': '10.0.0.1', 'path': '/shares/x/bare'},
           {'name': 'wsl', 'user': 'me', 'ip': '10.0.0.2', 'path': '/home/me/straight_grooves'},
           {'name': 'nas', 'user': 'me', 'ip': '10.0.0.3', 'path': ''}]


def run_init(tmp_path, monkeypatch, **flags):
    from src.utils.remote_config import RemoteConfig
    folder = tmp_path / 'bare'
    folder.mkdir(exist_ok=True)
    monkeypatch.chdir(folder)
    monkeypatch.setattr(RemoteConfig, 'get_all_remotes', lambda self: REMOTES)
    args = SimpleNamespace(remote=None, path=None, keep_rst=None, upload_rst=None,
                           disk_alert=None, force=False)
    for k, v in flags.items():
        setattr(args, k, v)
    return init_cmd.execute_init(args), folder


# --- the cases file --------------------------------------------------------------

def test_round_trip_keeps_every_section(tmp_path):
    cf = cases_file.CasesFile(cases_file.path_for(tmp_path),
                              cases=[{'name': 'c1', 'path': '/x/c1'}],
                              remotes={'cloud': '/shares/x', 'wsl': '/home/y'},
                              auto={'keep_rst': 500, 'disk_alert': '200G'})
    cases_file.write(cf)
    back = cases_file.read(tmp_path)
    assert (back.cases, back.remotes, back.auto) == (cf.cases, cf.remotes, cf.auto)
    assert (tmp_path / '.cases.yml').read_text().startswith('# flexflow:')


@pytest.mark.parametrize('text, message', [
    ('cases: 5\n', '`cases` should be a list'),
    ('remotes: [a]\n', '`remotes` should map'),
    ('auto: {speed: 1}\n', '`auto` takes'),
    ('other: 1\n', 'unknown section'),
    ('cases: [\n', 'not valid YAML'),
])
def test_bad_files_say_what_is_wrong(tmp_path, text, message):
    (tmp_path / '.cases.yml').write_text(text)
    with pytest.raises(cases_file.CasesFileError, match=message):
        cases_file.read(tmp_path)


def test_missing_file(tmp_path):
    with pytest.raises(cases_file.CasesFileError, match='no .cases.yml'):
        cases_file.read(tmp_path)


# --- auto's reading of it ----------------------------------------------------------

def test_auto_conf_for_a_remote(tmp_path):
    cases_file.write(cases_file.CasesFile(cases_file.path_for(tmp_path),
                                          remotes={'cloud': '/shares/x/bare', 'wsl': 'EDIT_ME'},
                                          auto={'keep_rst': 500, 'disk_alert': '200G'}))
    got = conf.read(tmp_path, 'cloud')
    assert (got.path, got.keep_rst, got.disk_alert) == ('/shares/x/bare', 500, 200 * 1024 ** 3)
    with pytest.raises(conf.AutoConfError, match='which remote'):
        conf.read(tmp_path, None)
    with pytest.raises(conf.AutoConfError, match="no folder for remote 'nas'"):
        conf.read(tmp_path, 'nas')
    with pytest.raises(conf.AutoConfError, match='still says EDIT_ME'):
        conf.read(tmp_path, 'wsl')


# --- auto init ---------------------------------------------------------------------

def test_path_comes_from_remote_set_path(tmp_path, monkeypatch, capsys):
    code, folder = run_init(tmp_path, monkeypatch, remote='cloud', keep_rst=500, disk_alert='200G')
    assert code == 0
    cf = cases_file.read(folder)
    assert cf.remotes == {'cloud': '/shares/x/bare'} and cf.cases == []
    assert cf.auto == {'keep_rst': 500, 'disk_alert': '200G'}
    out = ' '.join(capsys.readouterr().out.split())
    assert 'the folder is `remote set-path cloud`' in out and 'Check the path' not in out
    assert 'No cases listed yet' in out


def test_several_remotes_and_cases_kept(tmp_path, monkeypatch):
    folder = tmp_path / 'bare'
    folder.mkdir()
    cases_file.write(cases_file.CasesFile(cases_file.path_for(folder),
                                          cases=[{'name': 'c1', 'path': str(folder / 'c1')}]))
    run_init(tmp_path, monkeypatch, remote='cloud')
    run_init(tmp_path, monkeypatch, remote='wsl', path='/home/me/bare')
    cf = cases_file.read(folder)
    assert cf.remotes == {'cloud': '/shares/x/bare', 'wsl': '/home/me/bare'}
    assert [c['name'] for c in cf.cases] == ['c1']


def test_existing_folder_kept_unless_force(tmp_path, monkeypatch, capsys):
    run_init(tmp_path, monkeypatch, remote='cloud', path='/a/bare')
    code, folder = run_init(tmp_path, monkeypatch, remote='cloud', path='/b/bare')
    assert cases_file.read(folder).remotes['cloud'] == '/a/bare'
    assert 'kept' in capsys.readouterr().out
    run_init(tmp_path, monkeypatch, remote='cloud', path='/b/bare', force=True)
    assert cases_file.read(folder).remotes['cloud'] == '/b/bare'


def test_path_of_another_folder_is_pointed_out(tmp_path, monkeypatch, capsys):
    code, folder = run_init(tmp_path, monkeypatch, remote='wsl')
    assert code == 0 and cases_file.read(folder).remotes['wsl'] == '/home/me/straight_grooves'
    assert "Check the path: it ends in 'straight_grooves', this folder is 'bare'" in \
        ' '.join(capsys.readouterr().out.split())


def test_no_set_path_leaves_edit_me(tmp_path, monkeypatch):
    code, folder = run_init(tmp_path, monkeypatch, remote='nas')
    assert cases_file.read(folder).remotes['nas'] == 'EDIT_ME'
    with pytest.raises(conf.AutoConfError, match='still says EDIT_ME'):
        conf.read(folder, 'nas')


def test_unknown_remote_and_bad_values_are_refused(tmp_path, monkeypatch):
    assert run_init(tmp_path, monkeypatch, remote='nope')[0] == 2
    assert run_init(tmp_path, monkeypatch, remote='cloud', disk_alert='lots')[0] == 2
    assert run_init(tmp_path, monkeypatch, remote='cloud', keep_rst=0)[0] == 2
    assert not (tmp_path / 'bare' / '.cases.yml').exists()


def test_flags_parse():
    import argparse
    from src.commands.auto import AutoCommand
    parser = argparse.ArgumentParser()
    AutoCommand().setup_parser(parser.add_subparsers(dest='command'))
    args = parser.parse_args(['auto', 'init', '--remote', 'cloud', '--keep-rst', '500',
                              '--disk-alert', '200G', '--path', '/x/bare'])
    assert (args.what, args.remote, args.keep_rst, args.disk_alert, args.path) == \
        ('init', 'cloud', 500, '200G', '/x/bare')
    args = parser.parse_args(['auto', 'show', 'case2', '--remote', 'local'])
    assert (args.what, args.case, args.remote) == ('show', 'case2', 'local')


# --- upload_rst ---------------------------------------------------------------------------

def test_upload_rst_is_read_and_must_be_a_multiple_of_keep_rst(tmp_path):
    cases_file.write(cases_file.CasesFile(cases_file.path_for(tmp_path),
                                          remotes={'cloud': '/shares/x/bare'},
                                          auto={'keep_rst': 500, 'upload_rst': 1000}))
    got = conf.read(tmp_path, 'cloud')
    assert (got.keep_rst, got.upload_rst) == (500, 1000)
    cases_file.write(cases_file.CasesFile(cases_file.path_for(tmp_path),
                                          remotes={'cloud': '/shares/x/bare'},
                                          auto={'keep_rst': 500, 'upload_rst': 750}))
    with pytest.raises(conf.AutoConfError, match=r'upload_rst \(750\) must be a multiple of '
                                                 r'auto.keep_rst \(500\)'):
        conf.read(tmp_path, 'cloud')
    # upload_rst alone is fine: nothing is thinned
    cases_file.write(cases_file.CasesFile(cases_file.path_for(tmp_path),
                                          remotes={'cloud': '/shares/x/bare'},
                                          auto={'upload_rst': 750}))
    assert conf.read(tmp_path, 'cloud').upload_rst == 750


def test_init_sets_upload_rst_and_refuses_a_mismatch(tmp_path, monkeypatch, capsys):
    code, folder = run_init(tmp_path, monkeypatch, remote='cloud', keep_rst=500, upload_rst=1000)
    assert code == 0 and cases_file.read(folder).auto == {'keep_rst': 500, 'upload_rst': 1000}
    before = (folder / '.cases.yml').read_text()
    # a new keep_rst that no longer divides the file's upload_rst is refused, nothing written
    assert run_init(tmp_path, monkeypatch, remote='cloud', keep_rst=300)[0] == 2
    assert 'must be a multiple of auto.keep_rst (300)' in capsys.readouterr().out
    assert (folder / '.cases.yml').read_text() == before
    assert run_init(tmp_path, monkeypatch, remote='cloud', upload_rst=750)[0] == 2
    assert run_init(tmp_path, monkeypatch, remote='cloud', upload_rst=0)[0] == 2


def test_init_flag_parses():
    import argparse
    from src.commands.auto import AutoCommand
    parser = argparse.ArgumentParser()
    AutoCommand().setup_parser(parser.add_subparsers(dest='command'))
    args = parser.parse_args(['auto', 'init', '--keep-rst', '500', '--upload-rst', '1000'])
    assert (args.keep_rst, args.upload_rst) == (500, 1000)
