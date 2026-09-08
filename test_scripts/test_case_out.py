"""Tests for `case out --list` and `case out --map`.

A nodal outputTimeHistory writes its records positionally, so the node file's
order is what indexes the othd. These check that the map preserves that order and
resolves coordinates against the file the .def actually names.
"""

import argparse
import json
import os

import pytest

from src.core.parsers.def_parser import (parse_output_time_history, parse_output_surfaces,
                                         parse_node_coordinates)
from src.commands.case.out_impl.command import (execute_out, WriteError,
                                                _read_coordinate_list,
                                                write_case_maps,
                                                survey_time_history,
                                                survey_output_surfaces)
from src.utils.logger import Logger

DEF_TEMPLATE = """
nodeCoordinates {{
    coordinates             = File( "{crd}" )
}}

# a commented-out block must not be picked up
#outputTimeHistory( "ghost" ) {{
#    type            = nodal
#    nodes           = File( "riser.ghost.nbc" )
#}}

outputTimeHistory( "riser_probe1_field" ) {{
    type            = coordinates
    coordinates     = File( "probe_dat.txt" )
    outputFrequency = 1
}}

outputTimeHistory( "riser_probe" ) {{
    type            = nodal
    nodes           = File( "riser.cyl_nodes.nbc" )
    outputFrequency = 1
}}

outputTimeHistory( "riser_tip" ) {{
    type            = nodal
    nodes           = File( "riser.tip_nodes.nbc" )
    outputFrequency = 5
}}

solve {{ }}
"""


DEF_NO_NODAL = """
nodeCoordinates {{
    coordinates     = File( "{crd}" )
}}
outputTimeHistory( "field_probe" ) {{
    type            = coordinates
    coordinates     = File( "probe_dat.txt" )
}}
"""

# a block whose type names no file to index its records by: nothing to map
DEF_UNMAPPABLE = """
nodeCoordinates {{
    coordinates     = File( "{crd}" )
}}
outputTimeHistory( "surface_probe" ) {{
    type            = surface
    outputFrequency = 1
}}
"""

# an outputSurface block alongside a nodal one, so oisd and othd handling can be
# checked side by side without either one masking a bug in the other
DEF_WITH_SURFACE = """
nodeCoordinates {{
    coordinates     = File( "{crd}" )
}}
outputSurface( "cylinder_body" ) {{
    surfaces        = File( "riser.cyl.srf" )
    elementGroup    = "interior"
    shape           = fourNodeQuad
    intgOutFreq     = 1
    nodalOutFreq    = 1
}}
outputTimeHistory( "riser_probe" ) {{
    type            = nodal
    nodes           = File( "riser.cyl_nodes.nbc" )
    outputFrequency = 1
}}
"""

# two outputSurface blocks, so osgId prediction (declaration order, shifted by a
# missing .srf) can be checked the same way _oth_ids already is
DEF_TWO_SURFACES = """
nodeCoordinates {{
    coordinates     = File( "{crd}" )
}}
outputSurface( "surf_a" ) {{
    surfaces        = File( "riser.a.srf" )
    elementGroup    = "interior"
    shape           = fourNodeQuad
}}
outputSurface( "surf_b" ) {{
    surfaces        = File( "riser.b.srf" )
    elementGroup    = "interior"
    shape           = fourNodeQuad
}}
"""


@pytest.fixture
def surface_case(tmp_path):
    """A case with one outputSurface block (3 quad elements) and one nodal block."""
    (tmp_path / "simflow.config").write_text("problem = riser\n")
    (tmp_path / "riser.def").write_text(DEF_WITH_SURFACE.format(crd="riser.crd"))
    (tmp_path / "riser.cyl_nodes.nbc").write_text("2\n18\n")
    (tmp_path / "riser.crd").write_text("".join(
        f"{n} {n / 10:.16e} {n / 100:.16e} {-n / 100:.16e}\n" for n in range(1, 20)))
    # parentId elemId node1 node2 node3 node4 -- a 3-element strip sharing edges,
    # matching gmshCnvt's writeSrf row layout
    (tmp_path / "riser.cyl.srf").write_text(
        "100 1 1 2 3 4\n"
        "102 2 4 3 5 6\n"
        "104 3 6 5 7 8\n"
    )
    # deliberately not sorted/contiguous, like the .nbc fixtures above
    (tmp_path / "riser.cyl.nbc").write_text("4\n1\n2\n3\n8\n5\n6\n7\n")
    return tmp_path


def read_surface_map(path):
    """An oisd map's two tables (nodes, then elements), split on the blank line
    between them."""
    comments = [ln for ln in path.read_text().splitlines() if ln.startswith("#")]
    sections, current = [], []
    for ln in path.read_text().splitlines():
        if ln.startswith("#"):
            continue
        if not ln.strip():
            if current:
                sections.append(current)
                current = []
            continue
        current.append(ln)
    if current:
        sections.append(current)
    node_header, node_rows = sections[0][0].split(","), [ln.split(",") for ln in sections[0][1:]]
    elem_header, elem_rows = sections[1][0].split(","), [ln.split(",") for ln in sections[1][1:]]
    return comments, (node_header, node_rows), (elem_header, elem_rows)


@pytest.fixture
def case(tmp_path):
    """A case with two nodal history blocks, one coordinates block, and a mesh."""
    (tmp_path / "simflow.config").write_text("problem = riser\nnp = 4\n")
    (tmp_path / "riser.def").write_text(DEF_TEMPLATE.format(crd="riser.crd"))
    # node ids deliberately out of order and non-contiguous
    (tmp_path / "riser.cyl_nodes.nbc").write_text("2\n18\n812\n813\n")
    (tmp_path / "riser.tip_nodes.nbc").write_text("18\n2\n")
    (tmp_path / "probe_dat.txt").write_text("1 0 0 3.0\n2 0 0 5.0\n3 0 0 10.0\n")
    (tmp_path / "riser.crd").write_text("".join(
        f"{n} {n / 10:.16e} {n / 100:.16e} {-n / 100:.16e}\n" for n in range(1, 1000)))
    return tmp_path


def make_args(case, **kw):
    defaults = dict(case=str(case), map=True, verbose=False, help=False,
                    probe_type=None, closed=False)
    defaults.setdefault("list", False)
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def flat(text):
    """Collapse whitespace: rich wraps console output at the terminal width."""
    return " ".join(text.split())


def read_map(path):
    lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
    comments = [ln for ln in lines if ln.startswith("#")]
    body = [ln for ln in lines if not ln.startswith("#")]
    return comments, body[0].split(","), [ln.split(",") for ln in body[1:]]


class TestDefParsing:
    """The .def is the source of truth for both the blocks and the mesh file."""

    def test_finds_every_output_time_history(self, case):
        blocks = parse_output_time_history(str(case / "riser.def"))
        assert [b["name"] for b in blocks] == [
            "riser_probe1_field", "riser_probe", "riser_tip"]      # 'ghost' is commented
        assert [b["type"] for b in blocks] == ["coordinates", "nodal", "nodal"]
        assert blocks[1]["nodes"] == "riser.cyl_nodes.nbc"
        assert blocks[2]["outputFrequency"] == 5

    def test_reads_the_coordinates_file_from_the_def(self, case):
        assert parse_node_coordinates(str(case / "riser.def")) == "riser.crd"

    def test_a_renamed_coordinates_file_is_followed(self, tmp_path):
        d = tmp_path / "other.def"
        d.write_text(DEF_TEMPLATE.format(crd="mesh_v2.crd"))
        assert parse_node_coordinates(str(d)) == "mesh_v2.crd"


class TestOthdMap:
    """End-to-end `case write --othd-map`."""

    def test_writes_one_map_per_mappable_block(self, case):
        execute_out(make_args(case))
        assert (case / "othd.riser_probe.map").exists()
        assert (case / "othd.riser_tip.map").exists()
        # a coordinates block is mapped too: its records are indexed by its own file
        assert (case / "othd.riser_probe1_field.map").exists()

    def test_rows_keep_the_node_file_order(self, case):
        execute_out(make_args(case))
        _, header, rows = read_map(case / "othd.riser_probe.map")
        assert header == ["row", "node", "x", "y", "z"]
        assert [r[0] for r in rows] == ["0", "1", "2", "3"]
        assert [r[1] for r in rows] == ["2", "18", "812", "813"]   # not sorted

        # the second block lists the same two nodes in the opposite order
        _, _, tip = read_map(case / "othd.riser_tip.map")
        assert [r[1] for r in tip] == ["18", "2"]

    def test_coordinates_come_from_the_mesh_file(self, case):
        execute_out(make_args(case))
        _, _, rows = read_map(case / "othd.riser_probe.map")
        for row in rows:
            node = int(row[1])
            assert float(row[2]) == pytest.approx(node / 10)
            assert float(row[3]) == pytest.approx(node / 100)
            assert float(row[4]) == pytest.approx(-node / 100)

    def test_a_coordinates_block_maps_its_own_points(self, case):
        execute_out(make_args(case))
        comments, header, rows = read_map(case / "othd.riser_probe1_field.map")
        assert header == ["row", "x", "y", "z"]        # no node: a point need not be one
        assert [r[0] for r in rows] == ["0", "1", "2"]
        assert [float(r[3]) for r in rows] == [3.0, 5.0, 10.0]
        blob = "\n".join(comments)
        assert 'outputTimeHistory: "riser_probe1_field"' in blob
        assert "coordinates: probe_dat.txt (3)" in blob

    def test_a_coordinates_only_case_needs_no_mesh(self, tmp_path):
        """The mesh is only read for nodal blocks."""
        (tmp_path / "simflow.config").write_text("problem = riser\n")
        (tmp_path / "riser.def").write_text(DEF_NO_NODAL.format(crd="riser.crd"))
        (tmp_path / "probe_dat.txt").write_text("1 1.0 2.0 3.0\n")
        # riser.crd deliberately absent
        execute_out(make_args(tmp_path))
        assert (tmp_path / "othd.field_probe.map").exists()

    def test_header_records_where_it_came_from(self, case):
        execute_out(make_args(case))
        comments, _, _ = read_map(case / "othd.riser_probe.map")
        blob = "\n".join(comments)
        assert 'outputTimeHistory: "riser_probe"' in blob
        assert "nodes: riser.cyl_nodes.nbc (4)" in blob
        assert "undeformed (from riser.crd)" in blob

    def test_oth_id_follows_declaration_order_when_nothing_is_skipped(self, case):
        execute_out(make_args(case))
        # probe_dat.txt, cyl_nodes, tip_nodes -- all present, so 0, 1, 2
        assert "# othId: 0" in (case / "othd.riser_probe1_field.map").read_text()
        assert "# othId: 1" in (case / "othd.riser_probe.map").read_text()
        assert "# othId: 2" in (case / "othd.riser_tip.map").read_text()

    def test_a_missing_input_file_shifts_every_later_oth_id(self, case):
        """The solver writes no record for an output whose file is absent."""
        (case / "probe_dat.txt").unlink()
        execute_out(make_args(case))
        assert not (case / "othd.riser_probe1_field.map").exists()
        # riser_probe was declared second but is written first
        assert "# othId: 0" in (case / "othd.riser_probe.map").read_text()
        assert "# othId: 1" in (case / "othd.riser_tip.map").read_text()

    def test_an_empty_input_file_counts_as_missing(self, case):
        (case / "probe_dat.txt").write_text("")
        execute_out(make_args(case))
        assert not (case / "othd.riser_probe1_field.map").exists()
        assert "# othId: 0" in (case / "othd.riser_probe.map").read_text()

    def test_the_basis_of_the_id_is_stated(self, case):
        (case / "probe_dat.txt").unlink()
        execute_out(make_args(case))
        header = (case / "othd.riser_probe.map").read_text()
        # the id is a prediction, so a reader must be able to see what it rests on
        assert "predicted from the .def" in header
        assert "1 earlier output(s) not written" in header

    def test_a_block_the_solver_skips_is_not_an_error(self, case):
        """Scanning every block, a missing input file is a skip -- it used to abort."""
        (case / "probe_dat.txt").unlink()
        execute_out(make_args(case))          # must not raise
        assert (case / "othd.riser_probe.map").exists()

    def test_naming_a_skipped_block_explicitly_does_error(self, case):
        (case / "probe_dat.txt").unlink()
        with pytest.raises(SystemExit):
            execute_out(make_args(case, map="probe_dat"))

    def test_name_selects_a_single_block(self, case):
        execute_out(make_args(case, map="tip_nodes"))
        assert (case / "othd.riser_tip.map").exists()
        assert not (case / "othd.riser_probe.map").exists()

    def test_name_also_matches_the_block_name(self, case):
        execute_out(make_args(case, map="riser_probe"))
        assert (case / "othd.riser_probe.map").exists()
        assert not (case / "othd.riser_tip.map").exists()

    def test_unknown_name_exits(self, case):
        with pytest.raises(SystemExit):
            execute_out(make_args(case, map="nope"))

    def test_missing_coordinates_file_exits(self, case):
        (case / "riser.crd").unlink()
        with pytest.raises(SystemExit):
            execute_out(make_args(case))

    def test_node_absent_from_the_mesh_exits(self, case):
        (case / "riser.cyl_nodes.nbc").write_text("2\n999999\n")
        with pytest.raises(SystemExit):
            execute_out(make_args(case))

    def test_a_missing_node_file_is_skipped_like_the_solver_does(self, case):
        """The solver writes no record for it, so there is nothing to map onto."""
        (case / "riser.tip_nodes.nbc").unlink()
        execute_out(make_args(case))
        assert not (case / "othd.riser_tip.map").exists()
        assert (case / "othd.riser_probe.map").exists()
        # tip_nodes was declared last, so the ids before it are untouched
        assert "# othId: 1" in (case / "othd.riser_probe.map").read_text()

    def test_naming_a_missing_node_file_explicitly_does_exit(self, case):
        (case / "riser.tip_nodes.nbc").unlink()
        with pytest.raises(SystemExit):
            execute_out(make_args(case, map="tip_nodes"))

    def test_without_the_flag_it_writes_nothing(self, case):
        with pytest.raises(SystemExit):
            execute_out(make_args(case, map=False))
        assert not list(case.glob("othd.*.map"))


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A .cases registry mixing cases that work, cases to skip, and cases that fail."""
    def build(name, template=DEF_TEMPLATE, crd=True, nbc=True):
        d = tmp_path / name
        d.mkdir()
        (d / "simflow.config").write_text("problem = riser\n")
        (d / "riser.def").write_text(template.format(crd="riser.crd"))
        (d / "probe_dat.txt").write_text("1 0 0 3.0\n")
        if nbc:
            (d / "riser.cyl_nodes.nbc").write_text("2\n18\n812\n")
            (d / "riser.tip_nodes.nbc").write_text("18\n2\n")
        if crd:
            (d / "riser.crd").write_text("".join(
                f"{n} {n / 10:.16e} {n / 100:.16e} {-n / 100:.16e}\n"
                for n in range(1, 1000)))
        return d

    build("Good1")
    build("Good2")
    build("Unmappable", template=DEF_UNMAPPABLE)  # no file to index by -> skip
    build("NoCrd", crd=False)                    # mesh gone       -> fail
    entries = [{"name": n, "path": str(tmp_path / n)}
               for n in ("Good1", "Good2", "Unmappable", "NoCrd")]
    entries.append({"name": "Gone", "path": str(tmp_path / "not_here")})
    (tmp_path / ".cases").write_text(json.dumps(entries))
    monkeypatch.chdir(tmp_path)                  # .cases is read from the cwd
    return tmp_path


DEF_SHARED_NODE_FILE = """
nodeCoordinates {{
    coordinates     = File( "{crd}" )
}}
outputTimeHistory( "probe_fast" ) {{
    type            = nodal
    nodes           = File( "riser.cyl_nodes.nbc" )
    outputFrequency = 1
}}
outputTimeHistory( "probe_slow" ) {{
    type            = nodal
    nodes           = File( "riser.cyl_nodes.nbc" )
    outputFrequency = 50
}}
"""


class TestMapNaming:
    """Maps are named after the block, which is what makes them distinct."""

    def test_named_after_the_block_not_its_input_file(self, case):
        execute_out(make_args(case))
        assert (case / "othd.riser_probe.map").exists()          # not othd.cyl_nodes.map
        assert (case / "othd.riser_probe1_field.map").exists()   # not othd.probe_dat.map

    def test_two_blocks_sharing_a_node_file_get_their_own_maps(self, tmp_path):
        """Naming after the file would put both on one path, the second winning."""
        (tmp_path / "simflow.config").write_text("problem = riser\n")
        (tmp_path / "riser.def").write_text(DEF_SHARED_NODE_FILE.format(crd="riser.crd"))
        (tmp_path / "riser.cyl_nodes.nbc").write_text("2\n18\n")
        (tmp_path / "riser.crd").write_text("".join(
            f"{n} {n / 10:.16e} {n / 100:.16e} {-n / 100:.16e}\n" for n in range(1, 100)))

        execute_out(make_args(tmp_path))
        fast, slow = tmp_path / "othd.probe_fast.map", tmp_path / "othd.probe_slow.map"
        assert fast.exists() and slow.exists()
        # each carries its own block and othId, so neither has been overwritten
        assert 'outputTimeHistory: "probe_fast"' in fast.read_text()
        assert "# othId: 0" in fast.read_text()
        assert 'outputTimeHistory: "probe_slow"' in slow.read_text()
        assert "# othId: 1" in slow.read_text()

    def test_a_name_needing_escaping_still_yields_one_file(self, tmp_path):
        (tmp_path / "simflow.config").write_text("problem = riser\n")
        (tmp_path / "riser.def").write_text(
            DEF_SHARED_NODE_FILE.format(crd="riser.crd").replace(
                '"probe_fast"', '"probe fast/slow"'))
        (tmp_path / "riser.cyl_nodes.nbc").write_text("2\n18\n")
        (tmp_path / "riser.crd").write_text("".join(
            f"{n} {n / 10:.16e} {n / 100:.16e} {-n / 100:.16e}\n" for n in range(1, 100)))
        execute_out(make_args(tmp_path))
        assert (tmp_path / "othd.probe_fast_slow.map").exists()   # no stray directory
        assert not (tmp_path / "probe fast").exists()

    def test_the_selector_still_accepts_the_node_set_name(self, case):
        """--map cyl_nodes reads naturally even though the file is block-named."""
        execute_out(make_args(case, map="cyl_nodes"))
        assert (case / "othd.riser_probe.map").exists()
        assert not (case / "othd.riser_tip.map").exists()


class TestOutputSurfaceParsing:
    """outputSurface writes an aggregate oisd record, not a positional one --
    there is no nodes/coordinates field to key records by."""

    def test_finds_every_output_surface(self, surface_case):
        blocks = parse_output_surfaces(str(surface_case / "riser.def"))
        assert [b["name"] for b in blocks] == ["cylinder_body"]
        block = blocks[0]
        assert block["surfaces"] == "riser.cyl.srf"
        assert block["elementGroup"] == "interior"
        assert block["shape"] == "fourNodeQuad"
        assert block["intgOutFreq"] == 1
        assert block["nodalOutFreq"] == 1

    def test_a_def_with_no_output_surface_gives_an_empty_list(self, case):
        assert parse_output_surfaces(str(case / "riser.def")) == []


class TestOisdMap:
    """oisd.<name>.map: not a row->node lookup like othd (an outputSurface's oisd
    holds one aggregate record per timestep for the whole surface), but the
    surface's mesh -- the .srf/.nbc it is built from -- since nothing else names
    it."""

    def test_writes_a_map_named_after_the_block(self, surface_case):
        execute_out(make_args(surface_case))
        assert (surface_case / "oisd.cylinder_body.map").exists()
        assert (surface_case / "othd.riser_probe.map").exists()   # othd unaffected

    def test_node_table_preserves_the_nbc_order(self, surface_case):
        execute_out(make_args(surface_case))
        _, (node_header, node_rows), _ = read_surface_map(surface_case / "oisd.cylinder_body.map")
        assert node_header == ["row", "node", "x", "y", "z"]
        assert [r[1] for r in node_rows] == ["4", "1", "2", "3", "8", "5", "6", "7"]

    def test_node_table_coordinates_come_from_the_mesh_file(self, surface_case):
        execute_out(make_args(surface_case))
        _, (_, node_rows), _ = read_surface_map(surface_case / "oisd.cylinder_body.map")
        for row in node_rows:
            node = int(row[1])
            assert float(row[2]) == pytest.approx(node / 10)
            assert float(row[3]) == pytest.approx(node / 100)
            assert float(row[4]) == pytest.approx(-node / 100)

    def test_element_table_preserves_the_srf_order_and_ids(self, surface_case):
        execute_out(make_args(surface_case))
        _, _, (elem_header, elem_rows) = read_surface_map(surface_case / "oisd.cylinder_body.map")
        assert elem_header == ["row", "parent", "id", "node1", "node2", "node3", "node4"]
        assert elem_rows[0] == ["0", "100", "1", "1", "2", "3", "4"]
        assert elem_rows[1] == ["1", "102", "2", "4", "3", "5", "6"]
        assert elem_rows[2] == ["2", "104", "3", "6", "5", "7", "8"]

    def test_header_records_the_block_and_its_files(self, surface_case):
        execute_out(make_args(surface_case))
        comments, _, _ = read_surface_map(surface_case / "oisd.cylinder_body.map")
        blob = "\n".join(comments)
        assert 'outputSurface: "cylinder_body"' in blob
        assert "elementGroup: interior" in blob
        assert "shape: fourNodeQuad" in blob
        assert "intgOutFreq: 1" in blob and "nodalOutFreq: 1" in blob
        assert "osgId: 0" in blob
        assert "surfaces: riser.cyl.srf (3 element(s))" in blob
        assert "nodes: riser.cyl.nbc (8 node(s))" in blob
        assert "coordinates are undeformed (from riser.crd)" in blob

    def test_a_surface_only_case_still_needs_the_mesh(self, tmp_path):
        """Unlike a coordinates-type othd block, a surface's map carries node
        coordinates, so the mesh is not optional just because there is no
        nodal othd block in the case."""
        (tmp_path / "simflow.config").write_text("problem = riser\n")
        (tmp_path / "riser.def").write_text("""
outputSurface( "surf_a" ) {
    surfaces        = File( "riser.a.srf" )
    elementGroup    = "interior"
    shape           = fourNodeQuad
}
""")
        (tmp_path / "riser.a.srf").write_text("100 1 1 2 3 4\n")
        (tmp_path / "riser.a.nbc").write_text("1\n2\n3\n4\n")
        # riser.crd deliberately absent, and no nodeCoordinates block either
        with pytest.raises(WriteError, match="no nodeCoordinates"):
            write_case_maps(str(tmp_path), None, Logger())

    def test_a_missing_srf_is_skipped_without_breaking_othd(self, tmp_path):
        (tmp_path / "simflow.config").write_text("problem = riser\n")
        (tmp_path / "riser.def").write_text(DEF_WITH_SURFACE.format(crd="riser.crd"))
        (tmp_path / "riser.cyl_nodes.nbc").write_text("2\n18\n")
        (tmp_path / "riser.crd").write_text("".join(
            f"{n} {n / 10:.16e} {n / 100:.16e} {-n / 100:.16e}\n" for n in range(1, 20)))
        # riser.cyl.srf deliberately absent
        execute_out(make_args(tmp_path))
        assert (tmp_path / "othd.riser_probe.map").exists()
        assert not (tmp_path / "oisd.cylinder_body.map").exists()

    def test_a_missing_sibling_nbc_raises(self, surface_case):
        (surface_case / "riser.cyl.nbc").unlink()
        with pytest.raises(WriteError, match="Node file not found"):
            write_case_maps(str(surface_case), None, Logger())

    def test_mismatched_element_node_counts_raise(self, surface_case):
        (surface_case / "riser.cyl.srf").write_text(
            "100 1 1 2 3 4\n"
            "102 2 4 3 5\n"          # one node short
        )
        with pytest.raises(WriteError, match="mixes element node counts"):
            write_case_maps(str(surface_case), None, Logger())

    def test_the_selector_matches_the_block_name(self, surface_case):
        execute_out(make_args(surface_case, map="cylinder_body"))
        assert (surface_case / "oisd.cylinder_body.map").exists()
        assert not (surface_case / "othd.riser_probe.map").exists()

    def test_the_selector_also_matches_the_srf_derived_set_name(self, surface_case):
        """--map cyl reads naturally even though the file is block-named."""
        execute_out(make_args(surface_case, map="cyl"))
        assert (surface_case / "oisd.cylinder_body.map").exists()
        assert not (surface_case / "othd.riser_probe.map").exists()

    def test_an_unmatched_selector_mentions_both_kinds_of_block(self, surface_case, capsys):
        with pytest.raises(SystemExit):
            execute_out(make_args(surface_case, map="nonexistent_thing"))
        captured = capsys.readouterr()
        message = flat(captured.err + captured.out)
        assert "outputTimeHistory or outputSurface matches" in message



class TestOsgIdPrediction:
    """Mirrors TestStalePrediction/_oth_ids: nothing in a .def or an oisd file
    states which osgId a block writes to, so it is predicted from declaration
    order, shifted by any block whose .srf is missing."""

    @staticmethod
    def _write_two_surfaces(tmp_path, skip_a=False, skip_b=False):
        (tmp_path / "simflow.config").write_text("problem = riser\n")
        (tmp_path / "riser.def").write_text(DEF_TWO_SURFACES.format(crd="riser.crd"))
        (tmp_path / "riser.crd").write_text("".join(
            f"{n} {n / 10:.16e} {n / 100:.16e} {-n / 100:.16e}\n" for n in range(1, 10)))
        srf = "100 1 1 2 3 4\n"
        if not skip_a:
            (tmp_path / "riser.a.srf").write_text(srf)
            (tmp_path / "riser.a.nbc").write_text("1\n2\n3\n4\n")
        if not skip_b:
            (tmp_path / "riser.b.srf").write_text(srf)
            (tmp_path / "riser.b.nbc").write_text("1\n2\n3\n4\n")

    def test_both_present_get_sequential_ids(self, tmp_path):
        self._write_two_surfaces(tmp_path)
        execute_out(make_args(tmp_path))
        assert "# osgId: 0" in (tmp_path / "oisd.surf_a.map").read_text()
        assert "# osgId: 1" in (tmp_path / "oisd.surf_b.map").read_text()

    def test_a_missing_earlier_srf_shifts_the_later_id_down(self, tmp_path):
        self._write_two_surfaces(tmp_path, skip_a=True)
        execute_out(make_args(tmp_path))
        assert not (tmp_path / "oisd.surf_a.map").exists()
        assert "# osgId: 0" in (tmp_path / "oisd.surf_b.map").read_text()
        assert "1 earlier outputSurface(s) not written" in (tmp_path / "oisd.surf_b.map").read_text()


class TestList:
    """`case out --list` answers: is it mapped, and what does each othId hold."""

    @staticmethod
    def by_name(rows):
        return {r["name"]: r for r in rows}

    def test_reports_every_block_in_declaration_order(self, case):
        rows = survey_time_history(case, None)
        assert [r["name"] for r in rows] == [
            "riser_probe1_field", "riser_probe", "riser_tip"]
        assert [r["type"] for r in rows] == ["coordinates", "nodal", "nodal"]
        assert [r["file"] for r in rows] == [
            "probe_dat.txt", "riser.cyl_nodes.nbc", "riser.tip_nodes.nbc"]

    def test_says_whether_a_map_exists(self, case):
        before = self.by_name(survey_time_history(case, None))
        assert not any(r["map_exists"] for r in before.values())
        assert before["riser_probe"]["map"] == "othd.riser_probe.map"

        execute_out(make_args(case))
        after = self.by_name(survey_time_history(case, None))
        assert all(r["map_exists"] for r in after.values())

    def test_reports_the_declared_probe_read_back_from_the_map(self, case):
        execute_out(make_args(case, map="cyl_nodes", probe_type="helix", closed=True))
        row = self.by_name(survey_time_history(case, None))["riser_probe"]
        assert row["probe"] == "helix" and row["closed"] == "yes"
        # a block with no map yet has nothing to report
        assert self.by_name(survey_time_history(case, None))["riser_tip"]["probe"] is None

    def test_a_block_the_solver_skips_has_no_oth_id(self, case):
        (case / "probe_dat.txt").unlink()
        rows = self.by_name(survey_time_history(case, None))
        assert rows["riser_probe1_field"]["oth_id"] is None      # not written
        assert rows["riser_probe1_field"]["file_exists"] is False
        assert rows["riser_probe"]["oth_id"] == 0                # shifted down
        assert rows["riser_tip"]["oth_id"] == 1

    def test_listing_needs_no_mesh(self, case):
        """It reads declarations, so a case stripped of its mesh still lists."""
        (case / "riser.crd").unlink()
        rows = survey_time_history(case, None)
        assert len(rows) == 3

    def test_a_case_without_a_def_is_a_skip(self, tmp_path):
        with pytest.raises(WriteError) as exc:
            survey_time_history(tmp_path, None)
        assert exc.value.skip is True

    def test_the_table_prints(self, case, capsys):
        execute_out(make_args(case, list=True))
        out = flat(capsys.readouterr().out)
        assert "Name" in out and "OthId" in out and "MapFile" in out and "Probe" in out
        assert "riser_probe" in out
        assert "predicted from the .def" in out       # never shown as measured


class TestSurfaceList:
    """`case out --list` also surveys outputSurface blocks, in a separate
    table -- OsgId/ElementGroup/Shape have no counterpart in the
    outputTimeHistory table, and Type/Probe have none here."""

    def test_reports_the_declared_surface(self, surface_case):
        rows = survey_output_surfaces(surface_case, None)
        assert [r["name"] for r in rows] == ["cylinder_body"]
        row = rows[0]
        assert row["file"] == "riser.cyl.srf"
        assert row["elementGroup"] == "interior"
        assert row["shape"] == "fourNodeQuad"
        assert row["osg_id"] == 0
        assert row["map"] == "oisd.cylinder_body.map"

    def test_says_whether_a_map_exists(self, surface_case):
        before = survey_output_surfaces(surface_case, None)[0]
        assert not before["map_exists"]

        execute_out(make_args(surface_case))
        after = survey_output_surfaces(surface_case, None)[0]
        assert after["map_exists"]

    def test_a_case_with_no_output_surface_is_a_skip(self, case):
        with pytest.raises(WriteError) as exc:
            survey_output_surfaces(case, None)
        assert exc.value.skip is True

    def test_a_surface_only_case_can_still_be_listed(self, tmp_path):
        """The bug this fixes: --list used to error out entirely ('declares no
        outputTimeHistory block') on a case whose only declared output is an
        outputSurface block."""
        (tmp_path / "simflow.config").write_text("problem = riser\n")
        (tmp_path / "riser.def").write_text("""
outputSurface( "surf_a" ) {
    surfaces        = File( "riser.a.srf" )
    elementGroup    = "interior"
    shape           = fourNodeQuad
}
""")
        (tmp_path / "riser.a.srf").write_text("100 1 1 2 3 4\n")
        execute_out(make_args(tmp_path, list=True))   # must not exit/raise
        with pytest.raises(WriteError) as exc:
            survey_time_history(tmp_path, None)
        assert exc.value.skip is True                 # the other side is still a skip

    def test_both_tables_print_for_a_case_with_both(self, surface_case, capsys):
        # Row/header content (e.g. "cylinder_body", "ElementGroup") is checked
        # against the returned data above, not the rendered table -- rich
        # truncates a narrow test console's cells with an ellipsis rather than
        # wrapping, which a plain substring check cannot survive.
        execute_out(make_args(surface_case, list=True))
        out = flat(capsys.readouterr().out)
        assert "outputTimeHistory in" in out
        assert "outputSurface in" in out
        assert "OsgId" in out

    def test_no_surface_section_for_a_case_with_none(self, case, capsys):
        execute_out(make_args(case, list=True))
        out = flat(capsys.readouterr().out)
        assert "outputSurface in" not in out


class TestProbeDeclaration:
    """Probe geometry is declared, never derived -- the coordinates cannot give it."""

    def test_absent_by_default(self, case):
        execute_out(make_args(case))
        assert "# probe:" not in (case / "othd.riser_probe.map").read_text()

    def test_declared_type_is_recorded(self, case):
        execute_out(make_args(case, probe_type="line"))
        header = (case / "othd.riser_probe.map").read_text()
        assert "# probe: line" in header
        # a reader must never mistake a declaration for a measurement
        assert "declared with --probe-type" in header
        assert "not derived from the coordinates" in header

    def test_closed_marks_a_ring(self, case):
        execute_out(make_args(case, probe_type="line", closed=True))
        assert "# closed: yes" in (case / "othd.riser_probe.map").read_text()

    def test_an_open_line_says_so(self, case):
        execute_out(make_args(case, probe_type="line"))
        assert "# closed: no" in (case / "othd.riser_probe.map").read_text()

    def test_a_helix_is_its_own_type(self, case):
        """A helix wraps a body: axial position and angle, not arc length alone."""
        execute_out(make_args(case, probe_type="helix", closed=True))
        header = (case / "othd.riser_probe.map").read_text()
        assert "# probe: helix" in header and "# closed: yes" in header

    def test_closed_is_only_meaningful_for_a_curve(self, case):
        execute_out(make_args(case, probe_type="surface"))
        assert "# closed:" not in (case / "othd.riser_probe.map").read_text()

    def test_closed_without_a_line_exits(self, case):
        with pytest.raises(SystemExit):
            execute_out(make_args(case, probe_type="surface", closed=True))
        with pytest.raises(SystemExit):
            execute_out(make_args(case, closed=True))

    def test_an_unknown_type_exits(self, case):
        with pytest.raises(SystemExit):
            execute_out(make_args(case, probe_type="spiral"))

    def test_it_applies_to_coordinates_blocks_too(self, case):
        """Three collinear points are a line or three points; only a human knows."""
        execute_out(make_args(case, map="probe_dat", probe_type="point"))
        assert "# probe: point" in (case / "othd.riser_probe1_field.map").read_text()

    def test_selecting_one_block_lets_sets_differ(self, case):
        execute_out(make_args(case, map="cyl_nodes", probe_type="line"))
        execute_out(make_args(case, map="probe_dat", probe_type="point"))
        assert "# probe: line" in (case / "othd.riser_probe.map").read_text()
        assert "# probe: point" in (case / "othd.riser_probe1_field.map").read_text()


class TestCoordinateFileLayout:
    """The column layout is established, not assumed: guessing here is silent."""

    @staticmethod
    def parse(tmp_path, text):
        path = tmp_path / "probe.txt"
        path.write_text(text)
        return _read_coordinate_list(str(path))

    def test_four_columns_are_index_x_y_z(self, tmp_path):
        """The real probe_dat.txt shape. Taking fields 0-2 would give (1, 0, 0)."""
        points, _ = self.parse(tmp_path, "1 0.0 0.0 3.0\n2 0.0 0.0 6.0\n3 0.0 0.0 9.0\n")
        assert [tuple(round(float(v), 1) for v in p) for p in points] == [
            (0.0, 0.0, 3.0), (0.0, 0.0, 6.0), (0.0, 0.0, 9.0)]

    def test_three_columns_are_x_y_z(self, tmp_path):
        points, _ = self.parse(tmp_path, "0.0 0.0 3.0\n0.0 0.0 6.0\n")
        assert [tuple(round(float(v), 1) for v in p) for p in points] == [
            (0.0, 0.0, 3.0), (0.0, 0.0, 6.0)]

    def test_a_leading_index_may_be_any_increasing_integers(self, tmp_path):
        points, _ = self.parse(tmp_path, "812 1.0 2.0 3.0\n813 4.0 5.0 6.0\n")
        assert [tuple(round(float(v), 1) for v in p) for p in points] == [
            (1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]

    def test_four_columns_without_an_index_raises(self, tmp_path):
        # which three of the four are the coordinates is genuinely unclear
        with pytest.raises(WriteError, match="does not read as a row index"):
            self.parse(tmp_path, "0.5 0.0 0.0 3.0\n0.5 0.0 0.0 6.0\n")

    def test_mixed_column_counts_raise(self, tmp_path):
        with pytest.raises(WriteError, match="mixes"):
            self.parse(tmp_path, "1 0.0 0.0 3.0\n0.0 0.0 6.0\n")

    def test_comments_and_blanks_are_ignored(self, tmp_path):
        points, skipped = self.parse(tmp_path, "# probes\n\n1 0.0 0.0 3.0\n")
        assert len(points) == 1 and skipped == 0


class TestStalePrediction:
    """A predicted id cannot describe othd files written before the input existed."""

    def test_an_input_newer_than_the_othd_is_flagged(self, case):
        othd = case / "othd_files"
        othd.mkdir()
        (othd / "riser.othd").write_text("data")
        os.utime(othd / "riser.othd", (1_600_000_000, 1_600_000_000))   # long ago
        execute_out(make_args(case))
        header = (case / "othd.riser_probe.map").read_text()
        assert "WARNING" in header and "newer than this case's othd files" in header

    def test_no_othd_files_means_no_warning(self, case):
        execute_out(make_args(case))
        assert "WARNING" not in (case / "othd.riser_probe.map").read_text()

    def test_an_othd_newer_than_the_inputs_is_not_flagged(self, case):
        othd = case / "othd_files"
        othd.mkdir()
        (othd / "riser.othd").write_text("data")                        # written just now
        execute_out(make_args(case))
        assert "WARNING" not in (case / "othd.riser_probe.map").read_text()


class TestWildcardList:
    """`case out * --list` surveys the whole registry in one table."""

    def test_lists_every_case_it_can_read(self, registry, capsys):
        execute_out(make_args("*", map=False, list=True))
        out = flat(capsys.readouterr().out)
        assert "Good1" in out and "Good2" in out
        assert "4 of 5 case(s)" in out          # only the missing directory fails

    def test_a_case_that_cannot_be_mapped_can_still_be_listed(self, registry, capsys):
        """Listing reads the .def only; mapping also needs the mesh and the
        node files, so the two sets are different and the table is the wider."""
        execute_out(make_args("*", map=False, list=True))
        out = flat(capsys.readouterr().out)
        assert "NoCrd" in out          # no mesh: unmappable, but declared blocks
        assert "Unmappable" in out     # nothing to index by, but still declared

    def test_a_case_it_cannot_read_is_reported_not_fatal(self, registry, capsys):
        execute_out(make_args("*", map=False, list=True))
        out = flat(capsys.readouterr().out)
        assert "Gone" in out                    # named under the table
        assert "Good1" in out                   # and the good ones still listed

    def test_it_reads_the_registry_not_a_directory_called_star(self, registry, capsys):
        """The bug: --list ran before the wildcard check and took '*' as a path."""
        execute_out(make_args("*", map=False, list=True))
        out = flat(capsys.readouterr().out)
        assert "Case directory not found: *" not in out

    def test_blocks_are_counted_across_cases(self, registry, capsys):
        execute_out(make_args("*", map=False, list=True))
        out = flat(capsys.readouterr().out)
        assert "output block(s)" in out

    def test_exits_non_zero_when_nothing_could_be_listed(self, tmp_path, monkeypatch):
        (tmp_path / ".cases").write_text(json.dumps(
            [{"name": "Gone", "path": str(tmp_path / "not_here")}]))
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc:
            execute_out(make_args("*", map=False, list=True))
        assert exc.value.code == 1

    def test_a_single_case_still_gets_its_own_table(self, registry, capsys):
        """The wildcard path must not have changed the ordinary one."""
        execute_out(make_args(registry / "Good1", map=False, list=True))
        out = flat(capsys.readouterr().out)
        assert "outputTimeHistory in Good1" in out
        assert "Case" not in out.split("Name")[0]   # no Case column for one case


class TestWildcard:
    """`case write * --othd-map` over the .cases registry."""

    def test_maps_every_case_it_can(self, registry):
        execute_out(make_args("*"))
        assert (registry / "Good1" / "othd.riser_probe.map").exists()
        assert (registry / "Good2" / "othd.riser_tip.map").exists()

    def test_one_bad_case_does_not_end_the_batch(self, registry, capsys):
        execute_out(make_args("*"))
        out = flat(capsys.readouterr().out)
        # Unmappable is skipped, NoCrd and Gone fail, yet both good cases are written
        assert "2 case(s) mapped" in out
        assert "1 skipped" in out and "2 failed" in out
        assert (registry / "Good1" / "othd.riser_probe.map").exists()

    def test_nothing_to_map_is_a_skip_not_a_failure(self, registry, capsys):
        execute_out(make_args("*"))
        out = flat(capsys.readouterr().out)
        assert "Unmappable" in out and "records can be mapped" in out
        assert not list((registry / "Unmappable").glob("othd.*.map"))

    def test_a_coordinates_block_counts_as_mappable(self, registry):
        """A case with only a coordinates block is mapped, not skipped."""
        execute_out(make_args("*"))
        assert (registry / "Good1" / "othd.riser_probe1_field.map").exists()

    def test_the_selector_still_applies(self, registry):
        execute_out(make_args("*", map="tip_nodes"))
        assert (registry / "Good1" / "othd.riser_tip.map").exists()
        assert not (registry / "Good1" / "othd.riser_probe.map").exists()

    def test_exits_non_zero_when_no_case_could_be_mapped(self, tmp_path, monkeypatch):
        (tmp_path / ".cases").write_text(json.dumps(
            [{"name": "Gone", "path": str(tmp_path / "not_here")}]))
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            execute_out(make_args("*"))

    def test_missing_registry_is_reported(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            execute_out(make_args("*"))
