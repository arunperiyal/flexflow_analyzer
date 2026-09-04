"""Tests for src/web/services/loader.py: the scan/load cache, mtime, LRU."""

import time

import numpy as np
import pytest

from src.web.services.loader import Loader

_OTHD = """tsId 1
time 0.0
othId 0
othFlag 1
vel 3 2
1.0 2.0 3.0
4.0 5.0 6.0
tsId 2
time 0.1
othId 0
othFlag 1
vel 3 2
1.1 2.1 3.1
4.1 5.1 6.1
"""


def _write_case(tmp_path, name='case1', content=_OTHD):
    case_dir = tmp_path / name
    case_dir.mkdir()
    (case_dir / f'{name}.othd').write_text(content)
    return case_dir


def test_meta_reads_the_group_and_variable(tmp_path):
    case_dir = _write_case(tmp_path)
    loader = Loader()
    meta = loader.meta(case_dir)
    assert meta.groups == [0]
    assert 'vel' in meta.variables_of(0)
    assert len(meta.times) == 2


def test_meta_raises_when_no_othd_present(tmp_path):
    empty = tmp_path / 'empty_case'
    empty.mkdir()
    loader = Loader()
    with pytest.raises(FileNotFoundError):
        loader.meta(empty)


def test_load_caches_arrays_for_the_same_columns(tmp_path):
    case_dir = _write_case(tmp_path)
    loader = Loader()
    meta1, arr1 = loader.load(case_dir, ['vel'])
    meta2, arr2 = loader.load(case_dir, ['vel'])
    assert arr1 is arr2   # same cache entry, not re-parsed
    assert np.allclose(arr1['vel'][0, 0], [1.0, 2.0, 3.0])


def test_load_reloads_when_othd_mtime_changes(tmp_path):
    case_dir = _write_case(tmp_path)
    loader = Loader()
    meta1, arr1 = loader.load(case_dir, ['vel'])

    # Rewrite with a third timestep and force the mtime forward.
    othd = case_dir / 'case1.othd'
    othd.write_text(_OTHD + "tsId 3\ntime 0.2\nothId 0\nothFlag 1\nvel 3 2\n1.2 2.2 3.2\n4.2 5.2 6.2\n")
    new_time = time.time() + 5
    import os
    os.utime(othd, (new_time, new_time))

    meta2, arr2 = loader.load(case_dir, ['vel'])
    assert len(meta2.times) == 3
    assert arr1 is not arr2


def test_lru_evicts_the_oldest_case_beyond_max(tmp_path):
    loader = Loader(max_cases=2)
    dirs = [_write_case(tmp_path, name=f'case{i}') for i in range(3)]
    for d in dirs:
        loader.meta(d)
    # case0 was evicted when case2 pushed the cache over its limit of 2
    assert str(dirs[0]) not in loader._cache
    assert str(dirs[1]) in loader._cache
    assert str(dirs[2]) in loader._cache
