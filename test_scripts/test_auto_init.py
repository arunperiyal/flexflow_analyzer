"""`auto init` writes .auto.conf for the user to edit; `auto show` will not
run on it until the placeholders are replaced."""

from types import SimpleNamespace

import pytest

from src.commands.auto import init as init_cmd
from src.core.auto import conf


def test_template_leaves_path_to_the_user(tmp_path):
    path = conf.write_template(tmp_path, remote='cloud', known=['cloud', 'wsl'])
    text = path.read_text()
    assert 'remote     = cloud' in text and 'path       = EDIT_ME' in text
    assert '`remote list` (cloud, wsl)' in text
    assert '# keep_rst   = 500' in text                     # optional, off until set
    with pytest.raises(conf.AutoConfError, match='set `path` .*EDIT_ME'):
        conf.read(tmp_path)


def test_edited_template_reads(tmp_path):
    path = conf.write_template(tmp_path, remote='cloud')
    path.write_text(path.read_text().replace('path       = EDIT_ME', 'path       = /shares/x/bare')
                    .replace('# keep_rst   = 500', 'keep_rst   = 500'))
    got = conf.read(tmp_path)
    assert (got.remote, got.path, got.keep_rst, got.disk_alert) == ('cloud', '/shares/x/bare', 500, None)


def test_no_remote_known_is_left_to_edit_too(tmp_path):
    conf.write_template(tmp_path)
    with pytest.raises(conf.AutoConfError, match='set `remote`'):
        conf.read(tmp_path)


def test_does_not_overwrite_without_force(tmp_path):
    conf.write_template(tmp_path, remote='cloud')
    (tmp_path / '.auto.conf').write_text('remote = cloud\npath = /mine\n')
    with pytest.raises(conf.AutoConfError, match='exists'):
        conf.write_template(tmp_path, remote='cloud')
    assert conf.read(tmp_path).path == '/mine'
    conf.write_template(tmp_path, remote='cloud', force=True)
    assert 'EDIT_ME' in (tmp_path / '.auto.conf').read_text()


REMOTES = [{'name': 'cloud', 'user': 'sshd', 'ip': '10.0.0.1', 'path': '/shares/x/bare'},
           {'name': 'wsl', 'user': 'me', 'ip': '10.0.0.2', 'path': '/home/me/straight_grooves'},
           {'name': 'nas', 'user': 'me', 'ip': '10.0.0.3', 'path': ''}]


def run_init(tmp_path, monkeypatch, **flags):
    from src.utils.remote_config import RemoteConfig
    folder = tmp_path / 'bare'
    folder.mkdir(exist_ok=True)
    monkeypatch.chdir(folder)
    monkeypatch.setattr(RemoteConfig, 'get_all_remotes', lambda self: REMOTES)
    args = SimpleNamespace(remote=None, path=None, keep_rst=None, disk_alert=None, force=False)
    for k, v in flags.items():
        setattr(args, k, v)
    return init_cmd.execute_init(args), folder


def test_path_comes_from_remote_set_path(tmp_path, monkeypatch, capsys):
    code, folder = run_init(tmp_path, monkeypatch, remote='cloud', keep_rst=500, disk_alert='200G')
    assert code == 0
    got = conf.read(folder)
    assert (got.remote, got.path, got.keep_rst, got.disk_alert) == ('cloud', '/shares/x/bare', 500,
                                                                    200 * 1024 ** 3)
    text = (folder / '.auto.conf').read_text()
    assert '# from `remote set-path cloud`: check it' in text
    out = capsys.readouterr().out
    assert 'from `remote set-path cloud`' in out and 'Check the path' not in out
    assert init_cmd.execute_init(SimpleNamespace(remote='cloud', path=None, keep_rst=None,
                                                 disk_alert=None, force=False)) == 2   # exists


def test_path_of_another_folder_is_pointed_out(tmp_path, monkeypatch, capsys):
    code, folder = run_init(tmp_path, monkeypatch, remote='wsl')
    assert code == 0 and conf.read(folder).path == '/home/me/straight_grooves'
    assert "Check the path: it ends in 'straight_grooves', this folder is 'bare'" in \
        ' '.join(capsys.readouterr().out.split())


def test_path_flag_wins_and_no_set_path_leaves_edit_me(tmp_path, monkeypatch):
    code, folder = run_init(tmp_path, monkeypatch, remote='wsl', path='/data/bare')
    assert conf.read(folder).path == '/data/bare'
    code, folder = run_init(tmp_path, monkeypatch, remote='nas', force=True)
    with pytest.raises(conf.AutoConfError, match='set `path`'):
        conf.read(folder)


def test_unknown_remote_and_bad_values_are_refused(tmp_path, monkeypatch):
    assert run_init(tmp_path, monkeypatch, remote='nope')[0] == 2
    assert run_init(tmp_path, monkeypatch, remote='cloud', disk_alert='lots')[0] == 2
    assert run_init(tmp_path, monkeypatch, remote='cloud', keep_rst=0)[0] == 2
    assert not (tmp_path / 'bare' / '.auto.conf').exists()


def test_flags_parse(tmp_path):
    import argparse
    from src.commands.auto import AutoCommand
    parser = argparse.ArgumentParser()
    AutoCommand().setup_parser(parser.add_subparsers(dest='command'))
    args = parser.parse_args(['auto', 'init', '--remote', 'cloud', '--keep-rst', '500',
                              '--disk-alert', '200G', '--path', '/x/bare'])
    assert (args.what, args.remote, args.keep_rst, args.disk_alert, args.path) == \
        ('init', 'cloud', 500, '200G', '/x/bare')
