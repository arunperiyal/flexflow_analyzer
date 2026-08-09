"""Tests for `case write --othd-map`.

A nodal outputTimeHistory writes its records positionally, so the node file's
order is what indexes the othd. These check that the map preserves that order and
resolves coordinates against the file the .def actually names.
"""

import argparse

import pytest

from src.core.parsers.def_parser import parse_output_time_history, parse_node_coordinates
from src.commands.case.write_impl.command import execute_write

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


@pytest.fixture
def case(tmp_path):
    """A case with two nodal history blocks, one coordinates block, and a mesh."""
    (tmp_path / "simflow.config").write_text("problem = riser\nnp = 4\n")
    (tmp_path / "riser.def").write_text(DEF_TEMPLATE.format(crd="riser.crd"))
    # node ids deliberately out of order and non-contiguous
    (tmp_path / "riser.cyl_nodes.nbc").write_text("2\n18\n812\n813\n")
    (tmp_path / "riser.tip_nodes.nbc").write_text("18\n2\n")
    (tmp_path / "riser.crd").write_text("".join(
        f"{n} {n / 10:.16e} {n / 100:.16e} {-n / 100:.16e}\n" for n in range(1, 1000)))
    return tmp_path


def make_args(case, **kw):
    defaults = dict(case=str(case), othd_map=True, verbose=False, help=False)
    defaults.update(kw)
    return argparse.Namespace(**defaults)


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

    def test_writes_one_map_per_nodal_block(self, case):
        execute_write(make_args(case))
        assert (case / "othd.cyl_nodes.map").exists()
        assert (case / "othd.tip_nodes.map").exists()
        # the coordinates-type block gets no map: it is not indexed by a node file
        assert not list(case.glob("othd.probe_dat*"))

    def test_rows_keep_the_node_file_order(self, case):
        execute_write(make_args(case))
        _, header, rows = read_map(case / "othd.cyl_nodes.map")
        assert header == ["row", "node", "x", "y", "z"]
        assert [r[0] for r in rows] == ["0", "1", "2", "3"]
        assert [r[1] for r in rows] == ["2", "18", "812", "813"]   # not sorted

        # the second block lists the same two nodes in the opposite order
        _, _, tip = read_map(case / "othd.tip_nodes.map")
        assert [r[1] for r in tip] == ["18", "2"]

    def test_coordinates_come_from_the_mesh_file(self, case):
        execute_write(make_args(case))
        _, _, rows = read_map(case / "othd.cyl_nodes.map")
        for row in rows:
            node = int(row[1])
            assert float(row[2]) == pytest.approx(node / 10)
            assert float(row[3]) == pytest.approx(node / 100)
            assert float(row[4]) == pytest.approx(-node / 100)

    def test_header_records_where_it_came_from(self, case):
        execute_write(make_args(case))
        comments, _, _ = read_map(case / "othd.cyl_nodes.map")
        blob = "\n".join(comments)
        assert 'outputTimeHistory: "riser_probe"' in blob
        assert "riser.cyl_nodes.nbc (4)" in blob
        assert "coordinates: riser.crd" in blob
        assert "undeformed" in blob

    def test_name_selects_a_single_block(self, case):
        execute_write(make_args(case, othd_map="tip_nodes"))
        assert (case / "othd.tip_nodes.map").exists()
        assert not (case / "othd.cyl_nodes.map").exists()

    def test_name_also_matches_the_block_name(self, case):
        execute_write(make_args(case, othd_map="riser_probe"))
        assert (case / "othd.cyl_nodes.map").exists()
        assert not (case / "othd.tip_nodes.map").exists()

    def test_unknown_name_exits(self, case):
        with pytest.raises(SystemExit):
            execute_write(make_args(case, othd_map="nope"))

    def test_missing_coordinates_file_exits(self, case):
        (case / "riser.crd").unlink()
        with pytest.raises(SystemExit):
            execute_write(make_args(case))

    def test_node_absent_from_the_mesh_exits(self, case):
        (case / "riser.cyl_nodes.nbc").write_text("2\n999999\n")
        with pytest.raises(SystemExit):
            execute_write(make_args(case))

    def test_missing_node_file_exits(self, case):
        (case / "riser.tip_nodes.nbc").unlink()
        with pytest.raises(SystemExit):
            execute_write(make_args(case))

    def test_without_the_flag_it_writes_nothing(self, case):
        with pytest.raises(SystemExit):
            execute_write(make_args(case, othd_map=False))
        assert not list(case.glob("othd.*.map"))
