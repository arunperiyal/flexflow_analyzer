"""/api/settings/clear-cache — flushes server-side caches that can go stale
independent of anything the user changes in the app itself: matplotlib's
own installed-font list (built once, from whatever was on the system at
the time -- installing a new font afterward, like the Microsoft core
fonts, does not get picked up until this runs) and the per-case data
loader's cache (see services/loader.py's own mtime-keyed invalidation for
what it does and doesn't already catch on its own).
"""

from pathlib import Path

import matplotlib
from flask import Blueprint, jsonify

from ..services.loader import loader

bp = Blueprint('settings', __name__, url_prefix='/api/settings')


def _rebuild_matplotlib_font_cache():
    """Rescans installed fonts and rewrites matplotlib's on-disk cache --
    the same fix applied by hand the first time this app hit a font that
    was installed after that cache already existed. Re-initializing the
    running process's own FontManager instance in place (rather than
    swapping in a new object) means every other module that already holds
    a reference to it -- e.g. this same process's own export.py, mid other
    requests -- sees the refreshed list immediately, no restart needed."""
    from matplotlib import font_manager
    font_manager.fontManager.__init__()
    cache_path = Path(matplotlib.get_cachedir(), f'fontlist-v{font_manager.FontManager.__version__}.json')
    font_manager.json_dump(font_manager.fontManager, cache_path)
    return len(font_manager.fontManager.ttflist)


@bp.post('/clear-cache')
def clear_cache():
    font_count = _rebuild_matplotlib_font_cache()
    loader.clear()
    return jsonify({'ok': True, 'fonts': font_count})
