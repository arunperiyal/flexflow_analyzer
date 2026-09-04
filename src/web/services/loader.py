"""services/loader.py — scan()/load() cache: mtime-keyed, LRU-evicted, lock-guarded.

Per §9 of docs/WEBAPP_PLAN.md: SeriesMeta and loaded arrays are cached per
case, keyed additionally by (group, columns) for the arrays, bounded to a
handful of cases (panels pin two at once for a comparison), and re-read when
the othd mtime moves. The lock is held across the whole scan/load so two tabs
opening the same case cannot start the same parse twice.
"""

import threading
from collections import OrderedDict
from pathlib import Path
from typing import Optional

from src.core.readers import series

DEFAULT_MAX_CASES = 3


class _CacheEntry:
    def __init__(self):
        self.mtime = None
        self.meta = None
        self.arrays = {}   # (group, (name, ...)) -> {name: ndarray}


class Loader:
    def __init__(self, max_cases: int = DEFAULT_MAX_CASES):
        self._max_cases = max_cases
        self._cache: "OrderedDict[str, _CacheEntry]" = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _othd_paths(case_dir: Path) -> list:
        case_dir = Path(case_dir)
        return sorted(case_dir.glob('*.othd')) + sorted(case_dir.glob('othd_files/*.othd'))

    @staticmethod
    def _newest_mtime(paths: list) -> float:
        return max((p.stat().st_mtime for p in paths), default=0.0)

    def _meta_locked(self, case_dir: Path):
        paths = self._othd_paths(case_dir)
        if not paths:
            raise FileNotFoundError(f"no .othd files under {case_dir}")
        mtime = self._newest_mtime(paths)
        key = str(case_dir)
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

    def meta(self, case_dir):
        with self._lock:
            return self._meta_locked(Path(case_dir)).meta

    def load(self, case_dir, names: list, group: Optional[int] = None):
        """(SeriesMeta, {name: ndarray}) for `names` in `group` (default group if None)."""
        case_dir = Path(case_dir)
        with self._lock:
            entry = self._meta_locked(case_dir)
            group = entry.meta.default_group if group is None else group
            cache_key = (group, tuple(sorted(names)))
            if cache_key not in entry.arrays:
                paths = self._othd_paths(case_dir)
                entry.arrays[cache_key] = series.load(paths, sorted(names), entry.meta, group)
            return entry.meta, entry.arrays[cache_key]


loader = Loader()
