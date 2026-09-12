"""Tests for POST /api/cases/<name>/field/render (iso/slice PNG rendering,
run as a background job) and GET .../field/render/<job_id>/<file>.

Copies exactly one PLT file into the fixture, same as test_web_field_info.py
and test_web_field_extract.py. Rendering is real (pyvista, off-screen) and
takes a couple of seconds per call even with the PLT->VTU sidecar cache warm,
so this file keeps the render count deliberately small.
"""

import base64
import json
import shutil
import time
from pathlib import Path

import pytest

from src.web.server import create_app

EXAMPLE = Path(__file__).resolve().parent.parent / 'examples' / 'BR0SG0U1P0'
_NEEDED_FILES = ('simflow.config', 'riser.def')
_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp('web_field_render_workspace')
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
    for _ in range(120):
        r = client.get(f'/api/jobs/{job_id}')
        data = r.get_json()
        if data['status'] != 'running':
            return job_id, data
        time.sleep(0.5)
    raise AssertionError('render job did not finish in time')


def test_render_iso_produces_a_real_png(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/render', json={
        'mode': 'iso', 'timestep': 100, 'views': ['iso'],
    })
    job_id, job = _run_job(client, res)
    assert job['status'] == 'done'
    assert job['result']['files'] == ['iso/iso_100.png']

    img = client.get(f'/api/cases/BR0SG0U1P0/field/render/{job_id}/iso/iso_100.png')
    assert img.status_code == 200
    assert img.mimetype == 'image/png'
    assert img.data[:8] == _PNG_MAGIC


def test_render_slice_produces_a_real_png(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/render', json={
        'mode': 'slice', 'timestep': 100, 'views': ['plane'],
    })
    job_id, job = _run_job(client, res)
    assert job['status'] == 'done'
    assert job['result']['files'] == ['plane/slice_100.png']

    img = client.get(f'/api/cases/BR0SG0U1P0/field/render/{job_id}/plane/slice_100.png')
    assert img.status_code == 200
    assert img.data[:8] == _PNG_MAGIC


def test_render_honors_a_custom_color_variable_and_range(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/render', json={
        'mode': 'iso', 'timestep': 100, 'views': ['iso'],
        'color': {'variable': 'Pressure', 'range': [80, 100]},
        'contour': {'variable': 'QCriterion'},
    })
    _, job = _run_job(client, res)
    assert job['status'] == 'done'


# -- validation ---------------------------------------------------------------

def test_rejects_an_unknown_mode(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/render', json={'mode': 'bogus', 'timestep': 100})
    assert res.status_code == 400
    assert 'mode must be' in res.get_json()['error']


def test_requires_a_timestep(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/render', json={'mode': 'iso'})
    assert res.status_code == 400
    assert 'timestep is required' in res.get_json()['error']


def test_rejects_a_color_range_with_min_above_max(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/render', json={
        'mode': 'iso', 'timestep': 100, 'color': {'range': [10, 5]},
    })
    assert res.status_code == 400
    assert 'min below max' in res.get_json()['error']


def test_rejects_a_malformed_color_range(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/render', json={
        'mode': 'iso', 'timestep': 100, 'color': {'range': [1, 2, 3]},
    })
    assert res.status_code == 400
    assert 'min, max' in res.get_json()['error']


def test_job_reports_an_unknown_timestep_as_an_error(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/render', json={'mode': 'iso', 'timestep': 999})
    _, job = _run_job(client, res)
    assert job['status'] == 'error'
    assert 'no PLT file' in job['error']


def test_404_for_unregistered_case(client):
    res = client.post('/api/cases/nope/field/render', json={'mode': 'iso', 'timestep': 100})
    assert res.status_code == 404


# -- image serving --------------------------------------------------------

def test_image_404_for_an_unknown_job(client):
    res = client.get('/api/cases/BR0SG0U1P0/field/render/nope/foo.png')
    assert res.status_code == 404


def test_image_404_for_a_filename_not_in_the_job(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/render', json={
        'mode': 'iso', 'timestep': 100, 'views': ['iso'],
    })
    job_id, job = _run_job(client, res)
    assert job['status'] == 'done'
    res2 = client.get(f'/api/cases/BR0SG0U1P0/field/render/{job_id}/not_a_real_file.png')
    assert res2.status_code == 404


# A 1x1 white PNG -- the exact bytes don't matter, only that field_snapshot_save
# decodes and stores whatever data:image/png;base64 payload the Render
# configuration window's client-side capture hands it.
_TINY_PNG_B64 = (
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
)


def test_snapshot_save_and_serve_round_trip(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/snapshot', json={
        'image': f'data:image/png;base64,{_TINY_PNG_B64}',
    })
    assert res.status_code == 200
    token = res.get_json()['token']
    assert token.endswith('.png')

    served = client.get(f'/api/cases/BR0SG0U1P0/field/render-file/{token}')
    assert served.status_code == 200
    assert served.data[:8] == _PNG_MAGIC
    assert served.data == base64.b64decode(_TINY_PNG_B64)


def test_snapshot_save_rejects_a_non_png_data_url(client):
    res = client.post('/api/cases/BR0SG0U1P0/field/snapshot', json={'image': 'not a data url'})
    assert res.status_code == 400


def test_snapshot_save_404_for_unregistered_case(client):
    res = client.post('/api/cases/NOPE/field/snapshot', json={
        'image': f'data:image/png;base64,{_TINY_PNG_B64}',
    })
    assert res.status_code == 404
