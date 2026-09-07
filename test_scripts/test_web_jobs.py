"""Tests for background jobs (Phase 3): services/jobs.py, /api/jobs, and the
now-backgrounded POST /api/cases/<name>/maps ("Write map now").

The maps-writing integration test needs riser.crd (131 MB) -- the one file
the other web tests deliberately skip copying -- since that read is exactly
what backgrounding this endpoint exists to get off the request thread. It is
copied once into a module-scoped fixture, not per test.
"""

import json
import shutil
import time
from pathlib import Path

import pytest

from src.web.server import create_app
from src.web.services.jobs import JobRegistry

EXAMPLE = Path(__file__).resolve().parent.parent / 'examples' / 'BR0SG0U1P0'
_NEEDED_FILES = ('simflow.config', 'riser.def', 'riser.cyl_nodes.nbc', 'probe_dat.txt', 'riser.crd')


def _poll(client, job_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = client.get(f'/api/jobs/{job_id}')
        data = res.get_json()
        if data['status'] != 'running':
            return data
        time.sleep(0.05)
    raise TimeoutError(f"job {job_id} did not finish within {timeout}s")


# -- JobRegistry (unit) ------------------------------------------------------

def test_job_runs_on_a_thread_and_completes():
    reg = JobRegistry()
    job_id = reg.start(lambda: 42)
    deadline = time.time() + 5
    while reg.get(job_id).status == 'running' and time.time() < deadline:
        time.sleep(0.01)
    job = reg.get(job_id)
    assert job.status == 'done'
    assert job.result == 42
    assert job.error is None


def test_job_captures_an_exception_as_error():
    reg = JobRegistry()

    def boom():
        raise ValueError("nope")

    job_id = reg.start(boom)
    deadline = time.time() + 5
    while reg.get(job_id).status == 'running' and time.time() < deadline:
        time.sleep(0.01)
    job = reg.get(job_id)
    assert job.status == 'error'
    assert 'nope' in job.error


def test_unknown_job_returns_none():
    reg = JobRegistry()
    assert reg.get('does-not-exist') is None


# -- /api/jobs (blueprint) ---------------------------------------------------

@pytest.fixture
def client(tmp_path):
    return create_app(tmp_path).test_client()


def test_get_job_404_for_unknown_id(client):
    res = client.get('/api/jobs/no-such-job')
    assert res.status_code == 404


# -- POST /api/cases/<name>/maps is now backgrounded -------------------------

@pytest.fixture(scope='module')
def workspace(tmp_path_factory):
    root = tmp_path_factory.mktemp('web_jobs_workspace')
    case_dir = root / 'BR0SG0U1P0'
    case_dir.mkdir()
    for name in _NEEDED_FILES:
        shutil.copy(EXAMPLE / name, case_dir / name)
    (root / '.cases').write_text(json.dumps([{'name': 'BR0SG0U1P0', 'path': str(case_dir)}]))
    return root, case_dir


@pytest.fixture(scope='module')
def write_client(workspace):
    root, _ = workspace
    return create_app(root).test_client()


def test_write_maps_returns_a_job_id_and_eventually_completes(write_client):
    res = write_client.post('/api/cases/BR0SG0U1P0/maps', json={})
    assert res.status_code == 202
    job_id = res.get_json()['job_id']

    data = _poll(write_client, job_id)
    assert data['status'] == 'done'
    files = {row['file'] for row in data['result']}
    assert files == {'othd.riser_probe.map', 'othd.riser_probe1_field.map'}
