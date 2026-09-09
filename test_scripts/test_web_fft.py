"""Tests for /api/cases/<name>/fft -- one-sided amplitude spectra for the
FFT plot panel.

Same shape as /history's own tests (test_web_api.py): reads othd columns by
default, oisd columns via kind=oisd, shares validation (unknown column,
out-of-range row, row cap, unregistered case, unknown kind). The one thing
unique to this endpoint is the non-uniform-sampling error path, exercised by
monkeypatching a cached SeriesMeta's times after the fixture data loads.
"""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from src.web.server import create_app
from src.web.services.fft import compute_fft
from src.web.services.loader import loader

EXAMPLE = Path(__file__).resolve().parent.parent / 'examples' / 'BR0SG0U1P0'
_NEEDED_FILES = ('simflow.config', 'riser.def', 'riser.cyl_nodes.nbc', 'probe_dat.txt',
                 'othd.riser_probe.map', 'othd.riser_probe1_field.map',
                 'riser.cyl.srf', 'riser.cyl.nbc', 'oisd.cylinder_body.map')


@pytest.fixture(scope='module')
def workspace(tmp_path_factory):
    root = tmp_path_factory.mktemp('web_fft_workspace')
    case_dir = root / 'BR0SG0U1P0'
    case_dir.mkdir()
    for name in _NEEDED_FILES:
        shutil.copy(EXAMPLE / name, case_dir / name)
    shutil.copytree(EXAMPLE / 'othd_files', case_dir / 'othd_files')
    shutil.copytree(EXAMPLE / 'oisd_files', case_dir / 'oisd_files')
    (root / '.cases').write_text(json.dumps([{'name': 'BR0SG0U1P0', 'path': str(case_dir)}]))
    return root, case_dir


@pytest.fixture(scope='module')
def client(workspace):
    root, _ = workspace
    return create_app(root).test_client()


def _reference_series(client, row, column, kind='othd'):
    """The row's raw time series via /history, to check the FFT against."""
    res = client.get(f'/api/cases/BR0SG0U1P0/history'
                      f'?kind={kind}&group=0&columns={column}&rows={row}')
    data = res.get_json()
    return np.array(data['times']), np.array(data['series'][0]['values'])


# -- successful retrieval -------------------------------------------------

def test_fft_matches_a_direct_computation_from_the_raw_series(client):
    times, values = _reference_series(client, 0, 'aleDisp_y')
    expected_freqs, expected_amplitude = compute_fft(times, values)

    res = client.get('/api/cases/BR0SG0U1P0/fft?group=0&columns=aleDisp_y&rows=0')
    assert res.status_code == 200
    data = res.get_json()
    assert data['case'] == 'BR0SG0U1P0'
    assert data['group'] == 0
    assert len(data['series']) == 1
    s = data['series'][0]
    assert s['row'] == 0
    assert s['column'] == 'aleDisp_y'
    assert np.allclose(data['frequencies'], expected_freqs)
    assert np.allclose(s['amplitude'], expected_amplitude)


def test_fft_multiple_columns_and_rows_share_one_frequency_axis(client):
    res = client.get('/api/cases/BR0SG0U1P0/fft'
                      '?group=0&columns=aleDisp_y,aleDisp_z&rows=0,12')
    assert res.status_code == 200
    data = res.get_json()
    assert len(data['series']) == 2 * 2   # 2 columns x 2 rows
    seen = {(v['row'], v['column']) for v in data['series']}
    assert (0, 'aleDisp_y') in seen
    assert (12, 'aleDisp_z') in seen
    n = len(data['frequencies'])
    for s in data['series']:
        assert len(s['amplitude']) == n


def test_fft_kind_oisd_reads_the_surface_series(client):
    times, values = _reference_series(client, 0, 'totTrac_x', kind='oisd')
    expected_freqs, expected_amplitude = compute_fft(times, values)

    res = client.get('/api/cases/BR0SG0U1P0/fft?kind=oisd&group=0&columns=totTrac_x&rows=0')
    assert res.status_code == 200
    data = res.get_json()
    s = data['series'][0]
    assert np.allclose(data['frequencies'], expected_freqs)
    assert np.allclose(s['amplitude'], expected_amplitude)


# -- non-uniform sampling --------------------------------------------------

def test_rejects_non_uniformly_spaced_times(client, workspace, monkeypatch):
    _, case_dir = workspace
    meta = loader.meta(case_dir, kind='othd')
    broken = meta.times.copy()
    broken[len(broken) // 2] += 10.0   # one displaced sample breaks uniform spacing
    monkeypatch.setattr(meta, 'times', broken)

    res = client.get('/api/cases/BR0SG0U1P0/fft?columns=aleDisp_y&rows=0')
    assert res.status_code == 400
    assert 'evenly spaced' in res.get_json()['error']


# -- shared validation (mirrors /history and /spatial) ----------------------

def test_rejects_unknown_column(client):
    res = client.get('/api/cases/BR0SG0U1P0/fft?columns=notAThing&rows=0')
    assert res.status_code == 400
    assert 'unknown column' in res.get_json()['error']


def test_rejects_out_of_range_row(client):
    res = client.get('/api/cases/BR0SG0U1P0/fft?columns=aleDisp_y&rows=99999')
    assert res.status_code == 400
    assert 'out of range' in res.get_json()['error']


def test_caps_rows_at_32(client):
    rows = ','.join(str(i) for i in range(40))
    res = client.get(f'/api/cases/BR0SG0U1P0/fft?columns=aleDisp_y&rows={rows}')
    assert res.status_code == 400
    assert 'at most' in res.get_json()['error']


def test_kind_oisd_row_1_is_out_of_range(client):
    """A surface has exactly one row -- 0 -- since nodes_of() for an oisd
    group is always 1."""
    res = client.get('/api/cases/BR0SG0U1P0/fft?kind=oisd&columns=totArea&rows=1')
    assert res.status_code == 400
    assert 'out of range' in res.get_json()['error']


def test_kind_oisd_does_not_see_othd_columns(client):
    res = client.get('/api/cases/BR0SG0U1P0/fft?kind=oisd&columns=aleDisp_y&rows=0')
    assert res.status_code == 400
    assert 'unknown column' in res.get_json()['error']


def test_rejects_unknown_kind(client):
    res = client.get('/api/cases/BR0SG0U1P0/fft?kind=nope&columns=aleDisp_y&rows=0')
    assert res.status_code == 400


def test_requires_columns_and_rows(client):
    res = client.get('/api/cases/BR0SG0U1P0/fft?columns=aleDisp_y')
    assert res.status_code == 400
    assert 'required' in res.get_json()['error']


def test_404_for_unregistered_case(client):
    res = client.get('/api/cases/nope/fft?columns=aleDisp_y&rows=0')
    assert res.status_code == 404
