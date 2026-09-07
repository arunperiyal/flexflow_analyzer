"""Tests for POST /api/settings/clear-cache -- Settings -> Clear Cache.

Flushes matplotlib's own installed-font list (stale once a font is added
to the system after that list was built -- see src/web/api/export.py's
font-substitution history) and the per-case data loader's cache.
"""

from pathlib import Path

import pytest

from src.web.server import create_app


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp('web_settings_workspace')
    return create_app(root).test_client()


def test_clear_cache_returns_ok_and_a_font_count(client):
    res = client.post('/api/settings/clear-cache')
    assert res.status_code == 200
    data = res.get_json()
    assert data['ok'] is True
    assert data['fonts'] > 0   # matplotlib always finds at least its own bundled fonts


def test_clear_cache_rebuilds_the_running_processs_font_manager():
    # Regression: the fix for the stale-font-cache bug this endpoint exists
    # to let a user re-trigger themselves -- re-initializing the *existing*
    # FontManager instance in place (not swapping in a new object) so
    # every module already holding a reference to it (export.py included)
    # sees the refreshed list without needing a process restart.
    from matplotlib import font_manager
    from src.web.api.settings import _rebuild_matplotlib_font_cache

    before = font_manager.fontManager
    count = _rebuild_matplotlib_font_cache()
    assert font_manager.fontManager is before   # same object, refreshed in place
    assert count == len(font_manager.fontManager.ttflist)


def test_clear_cache_writes_the_on_disk_font_cache():
    import matplotlib
    from matplotlib import font_manager
    from src.web.api.settings import _rebuild_matplotlib_font_cache

    _rebuild_matplotlib_font_cache()
    cache_path = Path(matplotlib.get_cachedir(), f'fontlist-v{font_manager.FontManager.__version__}.json')
    assert cache_path.is_file()


def test_clear_cache_empties_the_loader_cache(client):
    from src.web.services.loader import loader
    loader._cache['some/case'] = object()   # stand in for a real cached entry
    assert loader._cache

    res = client.post('/api/settings/clear-cache')
    assert res.status_code == 200
    assert not loader._cache
