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


def test_command_uses_the_remote_context(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_cmd, '_context_remote', lambda: 'cloud')
    assert init_cmd.execute_init(SimpleNamespace(force=False)) == 0
    assert 'remote     = cloud' in (tmp_path / '.auto.conf').read_text()
    out = capsys.readouterr().out
    assert 'set `path`' in out and 'No .cases here yet' in out
    assert init_cmd.execute_init(SimpleNamespace(force=False)) == 2      # exists now
