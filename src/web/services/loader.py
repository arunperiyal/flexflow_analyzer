"""services/loader.py — scan()/load() cache: mtime-keyed, LRU-evicted, lock-guarded.

Per §9 of docs/WEBAPP_PLAN.md: SeriesMeta and loaded arrays are cached per
case, keyed additionally by (group, columns) for the arrays, bounded to a
handful of cases (panels pin two at once for a comparison), and re-read when
the mtime moves. The lock is held across the whole scan/load so two tabs
opening the same case cannot start the same parse twice.

`kind` ('othd' or 'oisd') is part of the cache key, not folded into one scan:
series.scan() assumes every path it is given is the same kind (SeriesMeta.kind
is read off the first path alone), and othId/osgId are both plain integers
starting at 0 -- scanning both kinds' files together would silently let an
outputSurface's group 0 collide with an outputTimeHistory's group 0. Every
case is really *two* independent series, read and cached separately.
"""

import threading
from collections import OrderedDict
from pathlib import Path
from typing import Optional

from src.core.readers import series

DEFAULT_MAX_CASES = 3

_GLOBS = {
    'othd': ('*.othd', 'othd_files/*.othd'),
    'oisd': ('*.oisd', 'oisd_files/*.oisd'),
}


class _CacheEntry:
    def __init__(self):
        self.mtime = None
        self.meta = None
        self.arrays = {}   # (group, (name, ...)) -> {name: ndarray}


class Loader:
    def __init__(self, max_cases: int = DEFAULT_MAX_CASES):
        self._max_cases = max_cases
        self._cache: "OrderedDict[tuple, _CacheEntry]" = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _paths(case_dir: Path, kind: str) -> list:
        case_dir = Path(case_dir)
        flat, archived = _GLOBS[kind]
        return sorted(case_dir.glob(flat)) + sorted(case_dir.glob(archived))

    @staticmethod
    def _newest_mtime(paths: list) -> float:
        return max((p.stat().st_mtime for p in paths), default=0.0)

    def _meta_locked(self, case_dir: Path, kind: str):
        paths = self._paths(case_dir, kind)
        if not paths:
            raise FileNotFoundError(f"no .{kind} files under {case_dir}")
        mtime = self._newest_mtime(paths)
        key = (str(case_dir), kind)
        entry = self._cache.get(key)
        if entry is None or entry.mtime != mtime:
            entry = _CacheEntry()
            entry.mtime = mtime
            entry.meta = series.scan(paths)
            self._cache[key] = entry
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_cases:
            self._cache.popitem(last=False)
        return entry

    def meta(self, case_dir, kind: str = 'othd'):
        with self._lock:
            return self._meta_locked(Path(case_dir), kind).meta

    def load(self, case_dir, names: list, group: Optional[int] = None, kind: str = 'othd'):
        """(SeriesMeta, {name: ndarray}) for `names` in `group` (default group if None)."""
        case_dir = Path(case_dir)
        with self._lock:
            entry = self._meta_locked(case_dir, kind)
            group = entry.meta.default_group if group is None else group
            cache_key = (group, tuple(sorted(names)))
            if cache_key not in entry.arrays:
                paths = self._paths(case_dir, kind)
                entry.arrays[cache_key] = series.load(paths, sorted(names), entry.meta, group)
            return entry.meta, entry.arrays[cache_key]

    def clear(self):
        """Drop every cached case -- the next meta()/load() call re-reads
        from disk regardless of mtime. The mtime check above only catches a
        rewrite that actually bumps the file's mtime; a case directory
        replaced wholesale by one that happens to preserve it (or system
        clock oddities) would otherwise keep serving stale arrays. Exposed
        for Settings -> Clear Cache."""
        with self._lock:
            self._cache.clear()


loader = Loader()
