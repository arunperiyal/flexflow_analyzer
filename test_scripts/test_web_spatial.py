"""Tests for /api/cases/<name>/spatial -- per-node snapshots and time-window
statistics for the spatial plot (value/statistic vs. position along the
probe, rather than vs. time).

Reuses the same trimmed BR0SG0U1P0 fixture as test_web_api.py (no
riser.crd, no binary/ -- this only reads othd_files/ through the loader).
"""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from src.web.server import create_app

EXAMPLE = Path(__file__).resolve().parent.parent / 'examples' / 'BR0SG0U1P0'
_NEEDED_FILES = ('simflow.config', 'riser.def', 'riser.cyl_nodes.nbc', 'probe_dat.txt',
                 'othd.riser_probe.map', 'othd.riser_probe1_field.map')


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp('web_spatial_workspace')
    case_dir = root / 'BR0SG0U1P0'
    case_dir.mkdir()
    for name in _NEEDED_FILES:
        shutil.copy(EXAMPLE / name, case_dir / name)
    shutil.copytree(EXAMPLE / 'othd_files', case_dir / 'othd_files')
    (root / '.cases').write_text(json.dumps([{'name': 'BR0SG0U1P0', 'path': str(case_dir)}]))
    return create_app(root).test_client()


def _reference_series(client, row, column):
    """The row's raw time series via /history, to check spatial reductions against."""
    res = client.get(f'/api/cases/BR0SG0U1P0/history?group=0&columns={column}&rows={row}')
    data = res.get_json()
    return np.array(data['times']), np.array(data['series'][0]['values'])


# -- snapshot mode ------------------------------------------------------------

def test_snapshot_returns_the_value_at_the_nearest_time(client):
    times, values = _reference_series(client, 0, 'aleDisp_y')
    target_time = float(times[10])

    res = client.get(f'/api/cases/BR0SG0U1P0/spatial'
                     f'?group=0&columns=aleDisp_y&rows=0,12&mode=snapshot&time={target_time}')
    assert res.status_code == 200
    data = res.get_json()
    assert data['mode'] == 'snapshot'
    assert data['time'] == pytest.approx(target_time)
    assert len(data['values']) == 2   # 1 column x 2 rows

    row0 = next(v for v in data['values'] if v['row'] == 0)
    assert row0['value'] == pytest.approx(float(values[10]))


def test_snapshot_snaps_to_the_nearest_available_time(client):
    times, values = _reference_series(client, 0, 'aleDisp_y')
    nudged = float(times[5]) + 1e-6   # not an exact time, but close to index 5

    res = client.get(f'/api/cases/BR0SG0U1P0/spatial'
                     f'?group=0&columns=aleDisp_y&rows=0&mode=snapshot&time={nudged}')
    data = res.get_json()
    assert data['time'] == pytest.approx(float(times[5]))
    assert data['values'][0]['value'] == pytest.approx(float(values[5]))


def test_snapshot_requires_a_time(client):
    res = client.get('/api/cases/BR0SG0U1P0/spatial?columns=aleDisp_y&rows=0&mode=snapshot')
    assert res.status_code == 400
    assert 'requires' in res.get_json()['error']


# -- stat mode ----------------------------------------------------------------

@pytest.mark.parametrize("stat,reducer", [
    ('rms', lambda v: np.sqrt(np.mean(v ** 2))),
    ('mean', lambda v: np.mean(v)),
    ('peak_abs', lambda v: np.max(np.abs(v))),
    ('peak_to_peak', lambda v: np.max(v) - np.min(v)),
])
def test_each_stat_matches_a_direct_numpy_reduction(client, stat, reducer):
    _, values = _reference_series(client, 12, 'aleDisp_y')

    res = client.get(f'/api/cases/BR0SG0U1P0/spatial'
                     f'?group=0&columns=aleDisp_y&rows=12&mode=stat&stats={stat}')
    assert res.status_code == 200
    data = res.get_json()
    assert data['values'][0]['stat'] == stat
    assert data['values'][0]['value'] == pytest.approx(float(reducer(values)))


def test_stat_windowed_by_t1_t2_only_reduces_that_range(client):
    times, values = _reference_series(client, 12, 'aleDisp_y')
    t1, t2 = float(times[5]), float(times[15])

    res = client.get(f'/api/cases/BR0SG0U1P0/spatial'
                     f'?group=0&columns=aleDisp_y&rows=12&mode=stat&stats=rms&t1={t1}&t2={t2}')
    data = res.get_json()
    mask = (times >= t1) & (times <= t2)
    expected = np.sqrt(np.mean(values[mask] ** 2))
    assert data['values'][0]['value'] == pytest.approx(float(expected))
    assert data['t1'] == pytest.approx(float(times[mask][0]))
    assert data['t2'] == pytest.approx(float(times[mask][-1]))


def test_stat_multiple_stats_and_columns_cross_product(client):
    res = client.get('/api/cases/BR0SG0U1P0/spatial'
                     '?group=0&columns=aleDisp_y,aleDisp_z&rows=0,12'
                     '&mode=stat&stats=rms,mean')
    data = res.get_json()
    assert len(data['values']) == 2 * 2 * 2   # 2 cols x 2 rows x 2 stats
    seen = {(v['row'], v['column'], v['stat']) for v in data['values']}
    assert (0, 'aleDisp_y', 'rms') in seen
    assert (12, 'aleDisp_z', 'mean') in seen


def test_stat_requires_at_least_one_stat(client):
    res = client.get('/api/cases/BR0SG0U1P0/spatial?columns=aleDisp_y&rows=0&mode=stat')
    assert res.status_code == 400
    assert 'requires' in res.get_json()['error']


def test_stat_rejects_an_unknown_stat_name(client):
    res = client.get('/api/cases/BR0SG0U1P0/spatial'
                     '?columns=aleDisp_y&rows=0&mode=stat&stats=bogus')
    assert res.status_code == 400
    assert 'unknown stat' in res.get_json()['error']


# -- shared validation (mirrors /history) --------------------------------------

def test_rejects_an_unknown_mode(client):
    res = client.get('/api/cases/BR0SG0U1P0/spatial?columns=aleDisp_y&rows=0&mode=bogus')
    assert res.status_code == 400
    assert 'mode must be' in res.get_json()['error']


def test_rejects_unknown_column(client):
    res = client.get('/api/cases/BR0SG0U1P0/spatial'
                     '?columns=notAThing&rows=0&mode=snapshot&time=0')
    assert res.status_code == 400
    assert 'unknown column' in res.get_json()['error']


def test_rejects_out_of_range_row(client):
    res = client.get('/api/cases/BR0SG0U1P0/spatial'
                     '?columns=aleDisp_y&rows=99999&mode=snapshot&time=0')
    assert res.status_code == 400
    assert 'out of range' in res.get_json()['error']


def test_caps_rows_at_256(client):
    rows = ','.join(str(i) for i in range(300))
    res = client.get(f'/api/cases/BR0SG0U1P0/spatial'
                     f'?columns=aleDisp_y&rows={rows}&mode=snapshot&time=0')
    assert res.status_code == 400
    assert 'at most' in res.get_json()['error']


def test_404_for_unregistered_case(client):
    res = client.get('/api/cases/nope/spatial?columns=aleDisp_y&rows=0&mode=snapshot&time=0')
    assert res.status_code == 404
