"""Unit tests for services/data_stats.py -- reductions and PLT-frame locators,
isolated from Flask/loader. Values match a hand-checked synthetic signal
(tsId 0..20, freq=5, a triangle wave hitting +/-3)."""

import numpy as np
import pytest

from src.web.services.data_stats import FUNCS, locate, plt_rows, zeroloc

TSIDS = np.arange(21)
TIMES = TSIDS * 0.1
VALUES = np.array([0, 1, 2, 3, 2, 1, 0, -1, -2, -3, -2, -1, 0, 1, 2, 3, 2, 1, 0, -1, -2],
                   dtype=float)
FREQ = 5


def test_min_max():
    assert FUNCS['min'](VALUES) == -3.0
    assert FUNCS['max'](VALUES) == 3.0


def test_mean_and_rms():
    assert FUNCS['mean'](VALUES) == np.mean(VALUES)
    assert FUNCS['rms'](VALUES) == np.sqrt(np.mean(VALUES ** 2))


def test_std_and_range():
    assert FUNCS['std'](VALUES) == np.std(VALUES)
    assert FUNCS['range'](VALUES) == 6.0


def test_plt_rows_marks_every_freq_th_step():
    mask = plt_rows(TSIDS, FREQ)
    assert list(TSIDS[mask]) == [0, 5, 10, 15, 20]


def test_plt_rows_with_no_freq_marks_nothing():
    mask = plt_rows(TSIDS, None)
    assert not mask.any()


def test_locate_max_points_at_the_strongest_plt_frame():
    found = locate(VALUES, TSIDS, TIMES, FREQ, 'max')
    assert found['value'] == 3.0
    assert found['tsId'] == 3          # the true peak, off the PLT grid
    assert found['plt_tsId'] == 15     # the PLT frame closest in *value*, not time
    assert found['plt_value'] == 3.0
    assert found['plt_ranked'][0] == (15, 3.0)
    assert len(found['plt_ranked']) == 4   # 1 + default 3 runners-up


def test_locate_min_breaks_ties_by_earlier_tsid():
    found = locate(VALUES, TSIDS, TIMES, FREQ, 'min')
    assert found['value'] == -3.0
    assert found['tsId'] == 9
    # tsId 10 and 20 both hold -2.0 (the best available); 10 wins the tie.
    assert found['plt_tsId'] == 10
    assert found['plt_value'] == -2.0


def test_locate_with_no_plt_frequency_still_reports_the_value():
    found = locate(VALUES, TSIDS, TIMES, None, 'max')
    assert found['value'] == 3.0
    assert found['plt_tsId'] is None
    assert found['plt_ranked'] == []


def test_zeroloc_descending_finds_the_nearest_plt_on_its_way_down():
    found = zeroloc(VALUES, TSIDS, TIMES, FREQ, 'descending')
    assert found['count'] == 2
    assert found['plt_tsId'] == 5
    assert found['plt_value'] == 1.0
    assert found['plt_offset'] == pytest.approx(1.0 / 3.0)


def test_zeroloc_ascending_finds_an_exact_zero_plt_frame():
    found = zeroloc(VALUES, TSIDS, TIMES, FREQ, 'ascending')
    assert found['count'] == 1
    assert found['plt_tsId'] == 0
    assert found['plt_value'] == 0.0
    assert found['plt_offset'] == 0.0


def test_zeroloc_returns_zero_count_when_the_signal_never_crosses():
    flat = np.ones_like(VALUES)
    found = zeroloc(flat, TSIDS, TIMES, FREQ, 'descending')
    assert found['count'] == 0
    assert found['tsId'] is None
