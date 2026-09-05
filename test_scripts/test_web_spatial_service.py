"""Unit tests for services/spatial.py's reductions, isolated from Flask/loader."""

import numpy as np

from src.web.services.spatial import STATS, nearest_time_index, window_mask


def test_rms():
    assert STATS['rms'](np.array([3.0, 4.0])) == np.sqrt(12.5)  # sqrt(mean(9, 16))


def test_mean():
    assert STATS['mean'](np.array([1.0, 2.0, 3.0])) == 2.0


def test_peak_abs():
    assert STATS['peak_abs'](np.array([-5.0, 2.0, 3.0])) == 5.0


def test_peak_to_peak():
    assert STATS['peak_to_peak'](np.array([-5.0, 2.0, 3.0])) == 8.0


def test_nearest_time_index_picks_the_closest():
    times = np.array([0.0, 0.1, 0.2, 0.3])
    assert nearest_time_index(times, 0.24) == 2
    assert nearest_time_index(times, 0.26) == 3
    assert nearest_time_index(times, -1.0) == 0
    assert nearest_time_index(times, 10.0) == 3


def test_window_mask_both_ends_given():
    times = np.array([0.0, 0.1, 0.2, 0.3, 0.4])
    mask = window_mask(times, 0.1, 0.3)
    assert list(mask) == [False, True, True, True, False]


def test_window_mask_none_means_the_whole_range():
    times = np.array([0.0, 0.1, 0.2])
    assert list(window_mask(times, None, None)) == [True, True, True]


def test_window_mask_one_sided():
    times = np.array([0.0, 0.1, 0.2, 0.3])
    assert list(window_mask(times, 0.2, None)) == [False, False, True, True]
    assert list(window_mask(times, None, 0.1)) == [True, True, False, False]
