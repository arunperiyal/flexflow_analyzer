"""Tests for /api/cases/<name>/field/steps and /field/info -- PLT field-data
metadata, the web equivalent of `field list`'s step discovery and
`field info`.

Copies exactly one PLT file into the fixture -- examples/BR0SG0U1P0/binary/
holds 5 files at ~162 MB each, so copying the whole directory (as history/fft
tests do for othd_files/) is not worth it here; every test in this file reads
only riser.100.plt.
"""

import json
import shutil
from pathlib import Path

import pytest

from src.web.server import create_app

EXAMPLE = Path(__file__).resolve().parent.parent / 'examples' / 'BR0SG0U1P0'
_NEEDED_FILES = ('simflow.config', 'riser.def')


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp('web_field_info_workspace')
    case_dir = root / 'BR0SG0U1P0'
    case_dir.mkdir()
    for name in _NEEDED_FILES:
        shutil.copy(EXAMPLE / name, case_dir / name)
    (case_dir / 'binary').mkdir()
    shutil.copy(EXAMPLE / 'binary' / 'riser.100.plt', case_dir / 'binary' / 'riser.100.plt')
    (root / '.cases').write_text(json.dumps([{'name': 'BR0SG0U1P0', 'path': str(case_dir)}]))
    return create_app(root).test_client()


# -- steps --------------------------------------------------------------------

def test_steps_lists_the_one_plt_file_present(client):
    res = client.get('/api/cases/BR0SG0U1P0/field/steps')
    assert res.status_code == 200
    assert res.get_json()['steps'] == [100]


def test_steps_404_for_unregistered_case(client):
    res = client.get('/api/cases/nope/field/steps')
    assert res.status_code == 404


# -- info -----------------------------------------------------------------

def test_info_defaults_to_the_only_step_present(client):
    res = client.get('/api/cases/BR0SG0U1P0/field/info')
    assert res.status_code == 200
    data = res.get_json()
    assert data['case'] == 'BR0SG0U1P0'
    assert data['basic']['timestep'] == 100
    assert data['basic']['file'] == 'riser.100.plt'
    assert data['basic']['problem'] == 'riser'
    assert data['basic']['plt_count'] == 1
    assert data['basic']['nvars'] > 0
    assert data['basic']['nzones'] > 0


def test_info_honors_an_explicit_timestep(client):
    res = client.get('/api/cases/BR0SG0U1P0/field/info?timestep=100')
    assert res.status_code == 200
    assert res.get_json()['basic']['timestep'] == 100


def test_info_404_for_an_unknown_timestep(client):
    res = client.get('/api/cases/BR0SG0U1P0/field/info?timestep=999')
    assert res.status_code == 404
    assert '999' in res.get_json()['error']


def test_info_zones_include_type_and_element_counts(client):
    res = client.get('/api/cases/BR0SG0U1P0/field/info')
    zones = res.get_json()['zones']
    assert len(zones) > 0
    volume = zones[0]
    assert volume['name']
    assert volume['type'] in ('hexahedron', 'tetra', 'quad', 'triangle')
    assert volume['npts'] > 0
    assert volume['nelem'] > 0
    assert volume['nodes_per_elem'] > 0


def test_info_checks_confirm_naming_and_no_truncation(client):
    res = client.get('/api/cases/BR0SG0U1P0/field/info')
    checks = res.get_json()['checks']
    assert checks['naming_ok'] is True
    assert checks['naming_bad_files'] == []
    assert checks['truncated'] is False
    assert checks['short_by_mb'] == 0.0


def test_info_stats_carries_coordinate_ranges(client):
    res = client.get('/api/cases/BR0SG0U1P0/field/info')
    stats = res.get_json()['stats']
    assert stats is not None
    by_name = {s['variable']: s for s in stats}
    assert 'X' in by_name
    assert by_name['X']['min'] is not None
    assert by_name['X']['max'] is not None
    assert by_name['X']['max'] > by_name['X']['min']


def test_info_404_for_a_case_with_no_binary_directory(client, tmp_path_factory):
    root = tmp_path_factory.mktemp('web_field_info_no_binary')
    case_dir = root / 'BareCase'
    case_dir.mkdir()
    (root / '.cases').write_text(json.dumps([{'name': 'BareCase', 'path': str(case_dir)}]))
    bare_client = create_app(root).test_client()
    res = bare_client.get('/api/cases/BareCase/field/info')
    assert res.status_code == 404


def test_info_404_for_unregistered_case(client):
    res = client.get('/api/cases/nope/field/info')
    assert res.status_code == 404
