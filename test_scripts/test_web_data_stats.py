"""Tests for /api/cases/<name>/data/stats -- reductions and PLT-frame
locators over a time-history window.

Reuses the same trimmed BR0SG0U1P0 fixture as test_web_data_info.py.
"""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from src.web.server import create_app
from src.web.services.data_stats import FUNCS, locate, zeroloc

EXAMPLE = Path(__file__).resolve().parent.parent / 'examples' / 'BR0SG0U1P0'
_NEEDED_FILES = ('simflow.config', 'riser.def', 'riser.cyl_nodes.nbc', 'probe_dat.txt',
                 'othd.riser_probe.map', 'othd.riser_probe1_field.map',
                 'riser.cyl.srf', 'riser.cyl.nbc', 'oisd.cylinder_body.map')


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp('web_data_stats_workspace')
    case_dir = root / 'BR0SG0U1P0'
    case_dir.mkdir()
    for name in _NEEDED_FILES:
        shutil.copy(EXAMPLE / name, case_dir / name)
    shutil.copytree(EXAMPLE / 'othd_files', case_dir / 'othd_files')
    shutil.copytree(EXAMPLE / 'oisd_files', case_dir / 'oisd_files')
    (root / '.cases').write_text(json.dumps([{'name': 'BR0SG0U1P0', 'path': str(case_dir)}]))
    return create_app(root).test_client()


def _reference_series(client, row, column):
    res = client.get(f'/api/cases/BR0SG0U1P0/history?group=0&columns={column}&rows={row}')
    data = res.get_json()
    return np.array(data['times']), np.array(data['series'][0]['values'])


# -- value functions --------------------------------------------------------

def test_value_funcs_match_a_direct_computation(client):
    _, values = _reference_series(client, 7, 'aleDisp_y')
    res = client.get('/api/cases/BR0SG0U1P0/data/stats'
                     '?group=0&columns=aleDisp_y&node=7&funcs=min,max,mean,rms,std,range')
    assert res.status_code == 200
    data = res.get_json()
    row = data['values'][0]
    assert row['column'] == 'aleDisp_y'
    for name, fn in FUNCS.items():
        assert row[name] == pytest.approx(fn(values))


def test_multiple_columns_each_get_their_own_row(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/stats'
                     '?group=0&columns=aleDisp_y,aleDisp_z&node=7&funcs=max')
    data = res.get_json()
    assert {r['column'] for r in data['values']} == {'aleDisp_y', 'aleDisp_z'}


# -- locators -----------------------------------------------------------------

def test_maxloc_matches_a_direct_computation(client):
    from src.commands.data.shared import out_freq
    from src.web.services.loader import loader

    root = Path(client.application.config['WORKSPACE_ROOT']) / 'BR0SG0U1P0'
    meta = loader.meta(root, kind='othd')
    freq = out_freq(root)

    times, values = _reference_series(client, 7, 'aleDisp_y')
    expected = locate(values, meta.tsids, times, freq, 'max')

    res = client.get('/api/cases/BR0SG0U1P0/data/stats'
                     '?group=0&columns=aleDisp_y&node=7&funcs=maxloc')
    row = res.get_json()['maxloc'][0]
    assert row['value'] == pytest.approx(expected['value'])
    assert row['tsId'] == expected['tsId']
    assert row['plt_tsId'] == expected['plt_tsId']
    assert row['plt_ranked'] == [list(t) for t in expected['plt_ranked']]


def test_zeroloc_matches_a_direct_computation(client):
    from src.commands.data.shared import out_freq
    from src.web.services.loader import loader

    root = Path(client.application.config['WORKSPACE_ROOT']) / 'BR0SG0U1P0'
    meta = loader.meta(root, kind='othd')
    freq = out_freq(root)

    times, values = _reference_series(client, 7, 'aleDisp_y')
    expected = zeroloc(values, meta.tsids, times, freq, 'descending')

    res = client.get('/api/cases/BR0SG0U1P0/data/stats'
                     '?group=0&columns=aleDisp_y&node=7&funcs=zeroloc')
    rows = res.get_json()['zeroloc']
    row = next(r for r in rows if r['direction'] == 'descending')
    assert row['count'] == expected['count']
    assert row['plt_tsId'] == expected['plt_tsId']


def test_only_requested_funcs_appear_in_the_response(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/stats'
                     '?group=0&columns=aleDisp_y&node=7&funcs=max')
    data = res.get_json()
    assert 'maxloc' not in data
    assert 'minloc' not in data
    assert 'zeroloc' not in data
    assert set(data['values'][0].keys()) == {'column', 'max'}


# -- t1/t2 window (tsId-based) -----------------------------------------------

def test_t1_t2_window_narrows_to_that_tsid_range(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/stats'
                     '?group=0&columns=aleDisp_y&node=7&funcs=max&t1=1&t2=100')
    data = res.get_json()
    assert data['tsid_min'] == 1
    assert data['tsid_max'] == 100
    assert data['steps'] == 100


def test_rejects_a_window_with_no_timesteps_in_it(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/stats'
                     '?group=0&columns=aleDisp_y&node=7&funcs=max&t1=999999&t2=999999')
    assert res.status_code == 400
    assert 'no timesteps' in res.get_json()['error']


# -- shared validation --------------------------------------------------------

def test_requires_columns(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/stats?funcs=max')
    assert res.status_code == 400
    assert 'columns is required' in res.get_json()['error']


def test_requires_funcs(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/stats?columns=aleDisp_y')
    assert res.status_code == 400
    assert 'funcs is required' in res.get_json()['error']


def test_rejects_an_unknown_func(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/stats?columns=aleDisp_y&funcs=bogus')
    assert res.status_code == 400
    assert 'unknown func' in res.get_json()['error']


def test_rejects_an_unknown_column(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/stats?columns=notAThing&funcs=max')
    assert res.status_code == 400
    assert 'unknown column' in res.get_json()['error']


def test_rejects_an_out_of_range_node(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/stats?columns=aleDisp_y&funcs=max&node=99999')
    assert res.status_code == 400
    assert 'out of range' in res.get_json()['error']


def test_404_for_unregistered_case(client):
    res = client.get('/api/cases/nope/data/stats?columns=aleDisp_y&funcs=max')
    assert res.status_code == 404
