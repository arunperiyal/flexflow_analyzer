"""Tests for POST /api/export -- the workspace rendered via matplotlib at 300 dpi.

Reuses the same trimmed BR0SG0U1P0 fixture as test_web_api.py (no riser.crd,
no binary/ -- this only reads othd_files/ through the loader).
"""

import json
import shutil
from pathlib import Path

import pytest

from src.web.server import create_app

EXAMPLE = Path(__file__).resolve().parent.parent / 'examples' / 'BR0SG0U1P0'
_NEEDED_FILES = ('simflow.config', 'riser.def', 'riser.cyl_nodes.nbc', 'probe_dat.txt',
                 'othd.riser_probe.map', 'othd.riser_probe1_field.map')


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp('web_export_workspace')
    case_dir = root / 'BR0SG0U1P0'
    case_dir.mkdir()
    for name in _NEEDED_FILES:
        shutil.copy(EXAMPLE / name, case_dir / name)
    shutil.copytree(EXAMPLE / 'othd_files', case_dir / 'othd_files')
    (root / '.cases').write_text(json.dumps([{'name': 'BR0SG0U1P0', 'path': str(case_dir)}]))
    return create_app(root).test_client()


def _panels():
    return [{
        'id': 'p1', 'title': 'BR0SG0U1P0',
        'traces': [
            {'case': 'BR0SG0U1P0', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'color': '#dc2626'},
            {'case': 'BR0SG0U1P0', 'group': 0, 'row': 12, 'col': 'aleDisp_y', 'color': '#f59e0b'},
        ],
    }]


def test_export_returns_a_png(client):
    res = client.post('/api/export', json={'panels': _panels(), 'linkX': True})
    assert res.status_code == 200
    assert res.mimetype == 'image/png'
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'
    assert 'flexflow_plot.png' in res.headers.get('Content-Disposition', '')


def test_export_with_no_panels_is_a_400(client):
    res = client.post('/api/export', json={'panels': []})
    assert res.status_code == 400


def test_export_skips_a_trace_from_an_unregistered_case(client):
    panels = [{
        'id': 'p1', 'title': 'ghost',
        'traces': [{'case': 'no-such-case', 'group': 0, 'row': 0, 'col': 'aleDisp_y', 'color': '#000'}],
    }]
    res = client.post('/api/export', json={'panels': panels})
    # Renders an (empty) panel rather than erroring the whole export.
    assert res.status_code == 200
    assert res.mimetype == 'image/png'


def test_export_renders_multiple_panels(client):
    panels = _panels() + [{'id': 'p2', 'title': 'second', 'traces': _panels()[0]['traces']}]
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_does_not_crash_on_a_spatial_panel(client):
    # A spatial trace has no `row` (it carries `points` instead) -- naively
    # reusing the time-domain _trace_values() path on it used to misindex
    # the array (row=None shifted `comp` onto the node axis) and raise
    # inside matplotlib's plot() rather than being skipped cleanly.
    panels = [{
        'id': 'p1', 'title': 'spatial rms', 'kind': 'spatial',
        'traces': [{
            'case': 'BR0SG0U1P0', 'group': 0, 'col': 'aleDisp_y', 'mode': 'stat', 'stat': 'rms',
            'points': [{'row': 0, 'x': 0.0}, {'row': 12, 'x': 1.0}], 'color': '#000',
        }],
    }]
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.mimetype == 'image/png'


def test_export_mixed_time_and_spatial_panels(client):
    panels = _panels() + [{
        'id': 'p2', 'title': 'spatial', 'kind': 'spatial',
        'traces': [{'case': 'BR0SG0U1P0', 'group': 0, 'col': 'aleDisp_y', 'mode': 'snapshot',
                    'time': 1.0, 'points': [{'row': 0, 'x': 0.0}], 'color': '#000'}],
    }]
    res = client.post('/api/export', json={'panels': panels})
    assert res.status_code == 200
    assert res.data[:8] == b'\x89PNG\r\n\x1a\n'
