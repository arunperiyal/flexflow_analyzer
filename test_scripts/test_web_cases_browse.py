"""Tests for GET /api/cases/browse -- the directory browser behind
Case -> Add, so finding the directory to scan doesn't require already
knowing (and typing) its exact absolute path.
"""

from pathlib import Path

import pytest

from src.web.server import create_app


@pytest.fixture(scope='module')
def workspace(tmp_path_factory):
    root = tmp_path_factory.mktemp('web_browse_workspace')
    (root / 'alpha').mkdir()
    (root / 'beta').mkdir()
    (root / 'alpha' / 'nested').mkdir()
    (root / '.hidden').mkdir()
    (root / 'not_a_dir.txt').write_text('x')
    return root


@pytest.fixture(scope='module')
def client(workspace):
    return create_app(workspace).test_client()


def test_browse_defaults_to_the_workspace_root(client, workspace):
    res = client.get('/api/cases/browse')
    assert res.status_code == 200
    data = res.get_json()
    assert data['dir'] == str(workspace)
    assert data['entries'] == ['alpha', 'beta']   # hidden dir and the plain file both excluded


def test_browse_lists_a_given_subdirectory(client, workspace):
    res = client.get(f'/api/cases/browse?dir={workspace / "alpha"}')
    assert res.status_code == 200
    data = res.get_json()
    assert data['dir'] == str(workspace / 'alpha')
    assert data['entries'] == ['nested']


def test_browse_reports_the_parent_directory(client, workspace):
    res = client.get(f'/api/cases/browse?dir={workspace / "alpha"}')
    data = res.get_json()
    assert data['parent'] == str(workspace)


def test_browse_reports_no_parent_at_the_filesystem_root(client):
    res = client.get('/api/cases/browse?dir=/')
    assert res.status_code == 200
    data = res.get_json()
    assert data['parent'] is None


def test_browse_excludes_hidden_and_non_directory_entries(client, workspace):
    res = client.get(f'/api/cases/browse?dir={workspace}')
    data = res.get_json()
    assert '.hidden' not in data['entries']
    assert 'not_a_dir.txt' not in data['entries']


def test_browse_404s_style_error_for_a_file_not_a_directory(client, workspace):
    res = client.get(f'/api/cases/browse?dir={workspace / "not_a_dir.txt"}')
    assert res.status_code == 400
    assert 'error' in res.get_json()


def test_browse_400s_for_a_path_that_does_not_exist(client, workspace):
    res = client.get(f'/api/cases/browse?dir={workspace / "does_not_exist"}')
    assert res.status_code == 400


def test_browse_expands_a_tilde_path(client, workspace, monkeypatch):
    # ~ resolves via Path.expanduser(), which reads $HOME -- pointed at the
    # workspace so this stays hermetic rather than touching the real home dir.
    monkeypatch.setenv('HOME', str(workspace))
    res = client.get('/api/cases/browse?dir=~')
    assert res.status_code == 200
    assert res.get_json()['dir'] == str(workspace)
