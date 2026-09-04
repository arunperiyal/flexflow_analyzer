"""Integration tests for the phase-2 web API against the real example case.

examples/BR0SG0U1P0 already carries two written maps and real othd files, and
is exactly the case docs/WEBAPP_PLAN.md §6 describes: `riser_probe.map`
predicts othId 1, but the othd only ever wrote othId 0 -- so the cross-check
this endpoint exists for should actually catch something.

Only the small files plus othd_files/ (~65 MB) are copied -- the example
directory also carries a 131 MB riser.crd and a 1.3 GB binary/ (PLT/VTU
render output) that these read-only API tests never touch. Session-scoped so
that copy happens once, not once per test.
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
def workspace(tmp_path_factory):
    """A trimmed copy of the example case, registered in a fresh workspace's .cases."""
    root = tmp_path_factory.mktemp('web_api_workspace')
    case_dir = root / 'BR0SG0U1P0'
    case_dir.mkdir()
    for name in _NEEDED_FILES:
        shutil.copy(EXAMPLE / name, case_dir / name)
    shutil.copytree(EXAMPLE / 'othd_files', case_dir / 'othd_files')
    (root / '.cases').write_text(json.dumps([{'name': 'BR0SG0U1P0', 'path': str(case_dir)}]))
    return root, case_dir


@pytest.fixture(scope='module')
def client(workspace):
    root, _ = workspace
    app = create_app(root)
    return app.test_client()


def test_meta_reports_the_real_group_and_variables(client):
    res = client.get('/api/cases/BR0SG0U1P0/meta')
    assert res.status_code == 200
    data = res.get_json()
    assert data['problem'] == 'riser'
    assert len(data['groups']) == 1
    group = data['groups'][0]
    assert group['othId'] == 0
    assert 'aleDisp' in group['variables']
    assert 'aleDisp_y' in group['columns']
    assert group['nodes'] == 49
    assert data['times']['n'] > 0


def test_meta_404_for_unregistered_case(client):
    res = client.get('/api/cases/no-such-case/meta')
    assert res.status_code == 404


def test_maps_list_flags_the_wrong_predicted_othid(client):
    res = client.get('/api/cases/BR0SG0U1P0/maps')
    assert res.status_code == 200
    rows = {r['file']: r for r in res.get_json()}

    riser_probe = rows['othd.riser_probe.map']
    assert riser_probe['oth_id'] == 1          # predicted from the .def
    assert riser_probe['oth_id_ok'] is False    # but the real othd only wrote othId 0
    assert riser_probe['body'] is None          # no domain.yml in this example

    field_probe = rows['othd.riser_probe1_field.map']
    assert field_probe['oth_id'] == 0
    assert field_probe['oth_id_ok'] is True
    assert field_probe['has_node_col'] is False   # a coordinates block


def test_get_map_projects_points_with_no_frame(client):
    res = client.get('/api/cases/BR0SG0U1P0/maps/othd.riser_probe.map')
    assert res.status_code == 200
    data = res.get_json()
    assert data['header']['block'] == 'riser_probe'
    assert len(data['rows']) == 49
    # No domain.yml -> falls back to the largest-range coordinate pair.
    view_ids = [v['id'] for v in data['views']]
    assert view_ids[0] == 'largest_pair'
    assert data['projection']['view'] == 'largest_pair'
    assert len(data['projection']['pts']) == 49


def test_get_map_honors_the_requested_view(client):
    res = client.get('/api/cases/BR0SG0U1P0/maps/othd.riser_probe.map?view=xy')
    assert res.status_code == 200
    data = res.get_json()
    assert data['projection']['view'] == 'xy'
    assert data['projection']['ax'] == 'x [m]'
    assert data['projection']['ay'] == 'y [m]'


def test_get_map_404_for_missing_file(client):
    res = client.get('/api/cases/BR0SG0U1P0/maps/othd.nope.map')
    assert res.status_code == 404


def test_history_returns_times_and_series_for_the_real_group(client):
    res = client.get('/api/cases/BR0SG0U1P0/history'
                     '?group=0&columns=aleDisp_y,aleDisp_z&rows=0,12')
    assert res.status_code == 200
    data = res.get_json()
    assert data['case'] == 'BR0SG0U1P0'
    assert data['group'] == 0
    n = len(data['times'])
    assert n > 0
    assert len(data['series']) == 4   # 2 columns x 2 rows
    for s in data['series']:
        assert s['row'] in (0, 12)
        assert s['column'] in ('aleDisp_y', 'aleDisp_z')
        assert len(s['values']) == n


def test_history_rejects_unknown_column(client):
    res = client.get('/api/cases/BR0SG0U1P0/history?columns=notAThing&rows=0')
    assert res.status_code == 400
    assert 'unknown column' in res.get_json()['error']


def test_history_rejects_out_of_range_row(client):
    res = client.get('/api/cases/BR0SG0U1P0/history?columns=aleDisp_y&rows=99999')
    assert res.status_code == 400
    assert 'out of range' in res.get_json()['error']


def test_history_caps_rows_at_32(client):
    rows = ','.join(str(i) for i in range(40))
    res = client.get(f'/api/cases/BR0SG0U1P0/history?columns=aleDisp_y&rows={rows}')
    assert res.status_code == 400
    assert 'at most' in res.get_json()['error']
