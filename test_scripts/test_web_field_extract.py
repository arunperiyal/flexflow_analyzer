"""Tests for POST /api/cases/<name>/field/extract (probe sampling, run as a
background job) and GET /api/cases/<name>/field/mesh.vtu (single-timestep
mesh download).

Copies exactly one PLT file into the fixture, same as test_web_field_info.py.
"""

import json
import shutil
import time
from pathlib import Path

import pytest

from src.web.server import create_app

EXAMPLE = Path(__file__).resolve().parent.parent / 'examples' / 'BR0SG0U1P0'
_NEEDED_FILES = ('simflow.config', 'riser.def')


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp('web_field_extract_workspace')
    case_dir = root / 'BR0SG0U1P0'
    case_dir.mkdir()
    for name in _NEEDED_FILES:
        shutil.copy(EXAMPLE / name, case_dir / name)
    (case_dir / 'binary').mkdir()
    shutil.copy(EXAMPLE / 'binary' / 'riser.100.plt', case_dir / 'binary' / 'riser.100.plt')
    (root / '.cases').write_text(json.dumps([{'name': 'BR0SG0U1P0', 'path': str(case_dir)}]))
    return create_app(root).test_client()


def _run_job(client, res):
    assert res.status_code == 202
    job_id = res.get_json()['job_id']
    for _ in range(60):
        r = client.get(f'/api/jobs/{job_id}')
        data = r.get_json()
        if data['status'] != 'running':
            return data
        time.sleep(0.2)
    raise AssertionError('job did not finish in time')


# -- extract ------------------------------------------------------------------

def test_extract_matches_a_direct_computation(client):
    from src.web.services.field_extract import run_probe_extract

    binary_dir = Path(client.application.config['WORKSPACE_ROOT']) / 'BR0SG0U1P0' / 'binary'
    expected_cols, expected_rows, _ = run_probe_extract(
        binary_dir, 'riser', 'FIELD', ['Pressure', 'U'], [[0, 0, 3]], [100])

    res = client.post('/api/cases/BR0SG0U1P0/field/extract', json={
        'zone': 'FIELD', 'columns': ['Pressure', 'U'],
        'points': [{'x': 0, 'y': 0, 'z': 3}], 'timestep': 100,
    })
    job = _run_job(client, res)
    assert job['status'] == 'done'
    assert job['result']['columns'] == expected_cols
    assert job['result']['rows'] == expected_rows


def test_extract_over_a_range_gets_one_row_per_probe_per_step(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/extract', json={
        'zone': 'FIELD', 'columns': ['Pressure'],
        'points': [{'x': 0, 'y': 0, 'z': 3}, {'x': 1, 'y': 0, 'z': 3}],
        't1': 100, 't2': 100,
    })
    job = _run_job(client, res)
    assert len(job['result']['rows']) == 2
    assert {r['probe'] for r in job['result']['rows']} == {1, 2}


def test_extract_surface_zone_reads_its_own_variables(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/extract', json={
        'zone': 'cyl', 'columns': ['Pressure'],
        'points': [{'x': 0, 'y': 0, 'z': 3}], 'timestep': 100,
    })
    job = _run_job(client, res)
    assert job['status'] == 'done'
    assert job['result']['rows'][0]['Pressure'] is not None


def test_extract_requires_zone(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/extract', json={
        'columns': ['Pressure'], 'points': [{'x': 0, 'y': 0, 'z': 3}], 'timestep': 100,
    })
    assert res.status_code == 400
    assert 'zone is required' in res.get_json()['error']


def test_extract_requires_columns(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/extract', json={
        'zone': 'FIELD', 'points': [{'x': 0, 'y': 0, 'z': 3}], 'timestep': 100,
    })
    assert res.status_code == 400
    assert 'columns is required' in res.get_json()['error']


def test_extract_requires_at_least_one_point(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/extract', json={
        'zone': 'FIELD', 'columns': ['Pressure'], 'points': [], 'timestep': 100,
    })
    assert res.status_code == 400
    assert 'point is required' in res.get_json()['error']


def test_extract_requires_a_timestep_or_range(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/extract', json={
        'zone': 'FIELD', 'columns': ['Pressure'], 'points': [{'x': 0, 'y': 0, 'z': 3}],
    })
    assert res.status_code == 400
    assert 'timestep' in res.get_json()['error']


def test_extract_rejects_a_point_missing_a_coordinate(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/extract', json={
        'zone': 'FIELD', 'columns': ['Pressure'], 'points': [{'x': 0, 'y': 0}], 'timestep': 100,
    })
    assert res.status_code == 400
    assert 'numeric x, y, z' in res.get_json()['error']


def test_extract_job_reports_an_unknown_zone_as_an_error(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/extract', json={
        'zone': 'nope', 'columns': ['Pressure'], 'points': [{'x': 0, 'y': 0, 'z': 3}], 'timestep': 100,
    })
    job = _run_job(client, res)
    assert job['status'] == 'error'
    assert "zone 'nope' not found" in job['error']


def test_extract_job_reports_an_unknown_variable_as_an_error(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/extract', json={
        'zone': 'FIELD', 'columns': ['bogus'], 'points': [{'x': 0, 'y': 0, 'z': 3}], 'timestep': 100,
    })
    job = _run_job(client, res)
    assert job['status'] == 'error'
    assert "'bogus'" in job['error']


def test_extract_caps_the_number_of_timesteps(client, tmp_path_factory):
    # resolve_steps only globs filenames (list_steps), so 51 empty touched
    # files trip the cap before any real PLT content is ever read.
    root = tmp_path_factory.mktemp('web_field_extract_capped')
    case_dir = root / 'BR0SG0U1P0'
    case_dir.mkdir()
    for name in _NEEDED_FILES:
        shutil.copy(EXAMPLE / name, case_dir / name)
    binary_dir = case_dir / 'binary'
    binary_dir.mkdir()
    for ts in range(0, 5100, 100):
        (binary_dir / f'riser.{ts}.plt').touch()
    (root / '.cases').write_text(json.dumps([{'name': 'BR0SG0U1P0', 'path': str(case_dir)}]))
    capped_client = create_app(root).test_client()

    res = capped_client.post('/api/cases/BR0SG0U1P0/field/extract', json={
        'zone': 'FIELD', 'columns': ['Pressure'], 'points': [{'x': 0, 'y': 0, 'z': 3}],
        't1': 0, 't2': 100000,
    })
    assert res.status_code == 400
    assert 'at most 50' in res.get_json()['error']


def test_extract_404_for_unregistered_case(client):
    res = client.post('/api/cases/nope/field/extract', json={
        'zone': 'FIELD', 'columns': ['Pressure'], 'points': [{'x': 0, 'y': 0, 'z': 3}], 'timestep': 100,
    })
    assert res.status_code == 404


# -- mesh.vtu -------------------------------------------------------------

def test_mesh_download_returns_a_vtu_file(client):
    res = client.get('/api/cases/BR0SG0U1P0/field/mesh.vtu?zone=cyl&timestep=100')
    assert res.status_code == 200
    assert res.mimetype == 'application/octet-stream'
    assert len(res.data) > 0
    assert 'BR0SG0U1P0_cyl_100.vtu' in res.headers.get('Content-Disposition', '')


def test_mesh_download_requires_zone(client):
    res = client.get('/api/cases/BR0SG0U1P0/field/mesh.vtu?timestep=100')
    assert res.status_code == 400
    assert 'zone is required' in res.get_json()['error']


def test_mesh_download_rejects_an_unknown_zone(client):
    res = client.get('/api/cases/BR0SG0U1P0/field/mesh.vtu?zone=nope&timestep=100')
    assert res.status_code == 400
    assert "zone 'nope' not found" in res.get_json()['error']


def test_mesh_download_404_for_an_unknown_timestep(client):
    res = client.get('/api/cases/BR0SG0U1P0/field/mesh.vtu?zone=cyl&timestep=999')
    assert res.status_code == 404


def test_mesh_download_404_for_unregistered_case(client):
    res = client.get('/api/cases/nope/field/mesh.vtu?zone=cyl&timestep=100')
    assert res.status_code == 404
