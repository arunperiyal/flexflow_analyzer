"""Tests for src/web/services/mapfile.py against real `case out --map` output.

Writes a map with the same functions the CLI uses
(src/commands/case/out_impl/command.py) so the parser is checked against what
is actually on disk, not a hand-typed fixture that could drift from the format.
"""

from src.commands.case.out_impl.command import _write_node_map, _write_point_map, _write_surface_map
from src.web.services.mapfile import list_maps, parse_map, list_surface_maps, parse_surface_map


def test_parses_a_nodal_map_with_probe_and_othid(tmp_path):
    block = {'name': 'riser_probe', 'type': 'nodal', 'outputFrequency': 50}
    ids = [101, 205, 309]
    coords = {101: ('0.0', '0.0', '0.0'), 205: ('0.0', '0.0', '5.0'), 309: ('0.0', '0.0', '10.0')}
    out = tmp_path / 'othd.riser_probe.map'
    _write_node_map(out, block, 'riser.cyl_nodes.nbc', 'riser.crd', ids, coords,
                    'CS4SG1U1', 'riser', oth_id=0, skipped_before=0, stale=(),
                    probe='line', closed=False)

    parsed = parse_map(out)
    assert parsed.block == 'riser_probe'
    assert parsed.oth_id == 0
    assert parsed.probe == 'line'
    assert parsed.closed is False
    assert parsed.provenance_kind == 'nodes'
    assert parsed.provenance_file == 'riser.cyl_nodes.nbc'
    assert parsed.provenance_count == 3
    assert parsed.has_node_col is True
    assert [r['row'] for r in parsed.rows] == [0, 1, 2]
    assert [r['node'] for r in parsed.rows] == ids
    assert parsed.rows[2]['z'] == 10.0


def test_parses_a_coordinates_map_with_no_node_column(tmp_path):
    block = {'name': 'probe_dat', 'type': 'coordinates', 'outputFrequency': None}
    points = [('1.0', '2.0', '3.0'), ('4.0', '5.0', '6.0')]
    out = tmp_path / 'othd.probe_dat.map'
    _write_point_map(out, block, 'probe_dat.txt', points, 'CS4SG1U1', 'riser',
                     oth_id=1, skipped_before=1, stale=(), probe='cloud', closed=None)

    parsed = parse_map(out)
    assert parsed.block == 'probe_dat'
    assert parsed.probe == 'cloud'
    assert parsed.closed is None
    assert parsed.has_node_col is False
    assert parsed.provenance_kind == 'coordinates'
    assert 'node' not in parsed.rows[0]
    assert parsed.rows[1]['y'] == 5.0


def test_list_maps_sorted_by_name(tmp_path):
    for name in ('othd.b.map', 'othd.a.map', 'othd.c.map'):
        (tmp_path / name).write_text('# x\nrow,x,y,z\n0,0,0,0\n')
    found = [p.name for p in list_maps(tmp_path)]
    assert found == ['othd.a.map', 'othd.b.map', 'othd.c.map']


def test_map_with_no_probe_declared_reads_as_none(tmp_path):
    block = {'name': 'plain', 'type': 'nodal', 'outputFrequency': 10}
    out = tmp_path / 'othd.plain.map'
    _write_node_map(out, block, 'riser.nodes.nbc', 'riser.crd', [1], {1: ('0', '0', '0')},
                    'CS1', 'riser')
    parsed = parse_map(out)
    assert parsed.probe is None
    assert parsed.closed is None
    assert parsed.oth_id is None


def _surface_block(name='cylinder_body'):
    return {'name': name, 'elementGroup': 'interior', 'shape': 'fourNodeQuad',
            'intgOutFreq': 1, 'nodalOutFreq': 1}


def test_parses_a_surface_map(tmp_path):
    elements = [(100, 1, [1, 2, 3, 4]), (102, 2, [4, 3, 5, 6])]
    node_ids = [4, 1, 2, 3, 5, 6]
    coords = {n: (f'{n / 10:.1f}', f'{n / 100:.2f}', f'{-n / 100:.2f}') for n in node_ids}
    out = tmp_path / 'oisd.cylinder_body.map'
    _write_surface_map(out, _surface_block(), 'riser.cyl.srf', elements, 'riser.cyl.nbc',
                       node_ids, 'riser.crd', coords, 'BR0SG0U1P0', 'riser', osg_id=0,
                       skipped_before=0)

    parsed = parse_surface_map(out)
    assert parsed.block == 'cylinder_body'
    assert parsed.element_group == 'interior'
    assert parsed.shape == 'fourNodeQuad'
    assert parsed.osg_id == 0
    assert parsed.srf_file == 'riser.cyl.srf' and parsed.srf_count == 2
    assert parsed.nbc_file == 'riser.cyl.nbc' and parsed.nbc_count == 6

    assert [n['node'] for n in parsed.nodes] == node_ids       # .nbc order preserved
    assert parsed.nodes[0]['x'] == 0.4 and parsed.nodes[0]['y'] == 0.04

    assert [e['id'] for e in parsed.elements] == [1, 2]
    assert parsed.elements[0]['parent'] == 100
    assert parsed.elements[1]['nodes'] == [4, 3, 5, 6]


def test_surface_map_with_no_predicted_osgid(tmp_path):
    """osgId is None when the block's .srf was missing/empty at prediction
    time -- same as othId for an othd block (see _oth_ids)."""
    out = tmp_path / 'oisd.cylinder_body.map'
    _write_surface_map(out, _surface_block(), 'riser.cyl.srf', [(1, 1, [1, 2, 3, 4])],
                       'riser.cyl.nbc', [1, 2, 3, 4], 'riser.crd',
                       {n: ('0', '0', '0') for n in (1, 2, 3, 4)}, 'BR0', 'riser',
                       osg_id=None)
    parsed = parse_surface_map(out)
    assert parsed.osg_id is None


def test_list_surface_maps_sorted_by_name_and_not_confused_with_node_maps(tmp_path):
    for name in ('oisd.b.map', 'oisd.a.map', 'othd.z.map'):
        (tmp_path / name).write_text('# x\nrow,node,x,y,z\n0,1,0,0,0\n\nrow,parent,id,node1\n0,1,1,1\n')
    found = [p.name for p in list_surface_maps(tmp_path)]
    assert found == ['oisd.a.map', 'oisd.b.map']
