"""Tests for /api/cases/<name>/data/info -- the web equivalent of `data show`.

Reuses the same trimmed BR0SG0U1P0 fixture as test_web_api.py (othd_files/ and
oisd_files/, no riser.crd, no binary/).
"""

import json
import shutil
from pathlib import Path

import pytest

from src.web.server import create_app

EXAMPLE = Path(__file__).resolve().parent.parent / 'examples' / 'BR0SG0U1P0'
_NEEDED_FILES = ('simflow.config', 'riser.def', 'riser.cyl_nodes.nbc', 'probe_dat.txt',
                 'othd.riser_probe.map', 'othd.riser_probe1_field.map',
                 'riser.cyl.srf', 'riser.cyl.nbc', 'oisd.cylinder_body.map')


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp('web_data_info_workspace')
    case_dir = root / 'BR0SG0U1P0'
    case_dir.mkdir()
    for name in _NEEDED_FILES:
        shutil.copy(EXAMPLE / name, case_dir / name)
    shutil.copytree(EXAMPLE / 'othd_files', case_dir / 'othd_files')
    shutil.copytree(EXAMPLE / 'oisd_files', case_dir / 'oisd_files')
    (root / '.cases').write_text(json.dumps([{'name': 'BR0SG0U1P0', 'path': str(case_dir)}]))
    return create_app(root).test_client()


def test_default_kind_returns_both_othd_and_oisd(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/info')
    assert res.status_code == 200
    data = res.get_json()
    assert data['case'] == 'BR0SG0U1P0'
    assert 'othd' in data and 'oisd' in data


def test_othd_summary_matches_a_direct_scan(client):
    from src.core.readers import series
    from src.commands.data.shared import find_files

    paths = find_files(Path(client.application.config['WORKSPACE_ROOT']) / 'BR0SG0U1P0', 'othd')
    meta = series.scan(paths)

    res = client.get('/api/cases/BR0SG0U1P0/data/info?kind=othd')
    data = res.get_json()['othd']
    assert data['kind'] == 'othd'
    assert data['files'] == len(meta.files)
    assert data['group_label'] == 'othId'
    assert data['timesteps'] == len(meta.times)
    assert data['tsid_min'] == int(meta.tsids.min())
    assert data['tsid_max'] == int(meta.tsids.max())
    assert data['time_min'] == pytest.approx(float(meta.times.min()))
    assert data['time_max'] == pytest.approx(float(meta.times.max()))
    group_ids = {g['group'] for g in data['groups']}
    assert group_ids == set(meta.groups)


def test_othd_variable_table_carries_names_components_and_short_names(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/info?kind=othd')
    groups = res.get_json()['othd']['groups']
    variables = {v['name']: v for g in groups for v in g['variables']}
    assert 'aleDisp' in variables
    assert variables['aleDisp']['ncomp'] == 3
    assert variables['aleDisp']['columns'] == ['aleDisp_x', 'aleDisp_y', 'aleDisp_z']
    assert variables['aleDisp']['short'] == 'dx, dy, dz'


def test_oisd_summary_uses_osgid_as_the_group_label(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/info?kind=oisd')
    data = res.get_json()['oisd']
    assert data['kind'] == 'oisd'
    assert data['group_label'] == 'osgId'
    assert any(v['name'] == 'totTrac' for g in data['groups'] for v in g['variables'])


def test_plt_alignment_reflects_simflow_configs_out_freq(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/info?kind=othd')
    alignment = res.get_json()['othd']['plt_alignment']
    assert alignment is not None
    assert alignment['freq'] > 0
    assert alignment['count'] > 0
    assert alignment['min'] % alignment['freq'] == 0
    assert alignment['max'] % alignment['freq'] == 0


def test_rejects_an_unknown_kind(client):
    res = client.get('/api/cases/BR0SG0U1P0/data/info?kind=nope')
    assert res.status_code == 400
    assert 'kind must be' in res.get_json()['error']


def test_404_for_unregistered_case(client):
    res = client.get('/api/cases/nope/data/info')
    assert res.status_code == 404
