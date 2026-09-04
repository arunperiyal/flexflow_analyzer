"""Tests for src/web/services/mapfile.py against real `case out --map` output.

Writes a map with the same functions the CLI uses
(src/commands/case/out_impl/command.py) so the parser is checked against what
is actually on disk, not a hand-typed fixture that could drift from the format.
"""

from src.commands.case.out_impl.command import _write_node_map, _write_point_map
from src.web.services.mapfile import list_maps, parse_map


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
