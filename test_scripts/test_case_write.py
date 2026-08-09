"""Tests for `case write --othd-map`.

A nodal outputTimeHistory writes its records positionally, so the node file's
order is what indexes the othd. These check that the map preserves that order and
resolves coordinates against the file the .def actually names.
"""

import argparse
import json
import os

import pytest

from src.core.parsers.def_parser import parse_output_time_history, parse_node_coordinates
from src.commands.case.write_impl.command import (execute_write, WriteError,
                                                  _read_coordinate_list)

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
    defaults = dict(case=str(case), othd_map=True, verbose=False, help=False,
                    probe_type=None, closed=False)
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
        execute_write(make_args(case))
        assert (case / "othd.cyl_nodes.map").exists()
        assert (case / "othd.tip_nodes.map").exists()
        # a coordinates block is mapped too: its records are indexed by its own file
        assert (case / "othd.probe_dat.map").exists()

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

    def test_a_coordinates_block_maps_its_own_points(self, case):
        execute_write(make_args(case))
        comments, header, rows = read_map(case / "othd.probe_dat.map")
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
        execute_write(make_args(tmp_path))
        assert (tmp_path / "othd.probe_dat.map").exists()

    def test_header_records_where_it_came_from(self, case):
        execute_write(make_args(case))
        comments, _, _ = read_map(case / "othd.cyl_nodes.map")
        blob = "\n".join(comments)
        assert 'outputTimeHistory: "riser_probe"' in blob
        assert "nodes: riser.cyl_nodes.nbc (4)" in blob
        assert "undeformed (from riser.crd)" in blob

    def test_oth_id_follows_declaration_order_when_nothing_is_skipped(self, case):
        execute_write(make_args(case))
        # probe_dat.txt, cyl_nodes, tip_nodes -- all present, so 0, 1, 2
        assert "# othId: 0" in (case / "othd.probe_dat.map").read_text()
        assert "# othId: 1" in (case / "othd.cyl_nodes.map").read_text()
        assert "# othId: 2" in (case / "othd.tip_nodes.map").read_text()

    def test_a_missing_input_file_shifts_every_later_oth_id(self, case):
        """The solver writes no record for an output whose file is absent."""
        (case / "probe_dat.txt").unlink()
        execute_write(make_args(case))
        assert not (case / "othd.probe_dat.map").exists()
        # riser_probe was declared second but is written first
        assert "# othId: 0" in (case / "othd.cyl_nodes.map").read_text()
        assert "# othId: 1" in (case / "othd.tip_nodes.map").read_text()

    def test_an_empty_input_file_counts_as_missing(self, case):
        (case / "probe_dat.txt").write_text("")
        execute_write(make_args(case))
        assert not (case / "othd.probe_dat.map").exists()
        assert "# othId: 0" in (case / "othd.cyl_nodes.map").read_text()

    def test_the_basis_of_the_id_is_stated(self, case):
        (case / "probe_dat.txt").unlink()
        execute_write(make_args(case))
        header = (case / "othd.cyl_nodes.map").read_text()
        # the id is a prediction, so a reader must be able to see what it rests on
        assert "predicted from the .def" in header
        assert "1 earlier output(s) not written" in header

    def test_a_block_the_solver_skips_is_not_an_error(self, case):
        """Scanning every block, a missing input file is a skip -- it used to abort."""
        (case / "probe_dat.txt").unlink()
        execute_write(make_args(case))          # must not raise
        assert (case / "othd.cyl_nodes.map").exists()

    def test_naming_a_skipped_block_explicitly_does_error(self, case):
        (case / "probe_dat.txt").unlink()
        with pytest.raises(SystemExit):
            execute_write(make_args(case, othd_map="probe_dat"))

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

    def test_a_missing_node_file_is_skipped_like_the_solver_does(self, case):
        """The solver writes no record for it, so there is nothing to map onto."""
        (case / "riser.tip_nodes.nbc").unlink()
        execute_write(make_args(case))
        assert not (case / "othd.tip_nodes.map").exists()
        assert (case / "othd.cyl_nodes.map").exists()
        # tip_nodes was declared last, so the ids before it are untouched
        assert "# othId: 1" in (case / "othd.cyl_nodes.map").read_text()

    def test_naming_a_missing_node_file_explicitly_does_exit(self, case):
        (case / "riser.tip_nodes.nbc").unlink()
        with pytest.raises(SystemExit):
            execute_write(make_args(case, othd_map="tip_nodes"))

    def test_without_the_flag_it_writes_nothing(self, case):
        with pytest.raises(SystemExit):
            execute_write(make_args(case, othd_map=False))
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


class TestProbeDeclaration:
    """Probe geometry is declared, never derived -- the coordinates cannot give it."""

    def test_absent_by_default(self, case):
        execute_write(make_args(case))
        assert "# probe:" not in (case / "othd.cyl_nodes.map").read_text()

    def test_declared_type_is_recorded(self, case):
        execute_write(make_args(case, probe_type="line"))
        header = (case / "othd.cyl_nodes.map").read_text()
        assert "# probe: line" in header
        # a reader must never mistake a declaration for a measurement
        assert "declared with --probe-type" in header
        assert "not derived from the coordinates" in header

    def test_closed_marks_a_ring(self, case):
        execute_write(make_args(case, probe_type="line", closed=True))
        assert "# closed: yes" in (case / "othd.cyl_nodes.map").read_text()

    def test_an_open_line_says_so(self, case):
        execute_write(make_args(case, probe_type="line"))
        assert "# closed: no" in (case / "othd.cyl_nodes.map").read_text()

    def test_closed_is_only_meaningful_for_a_line(self, case):
        execute_write(make_args(case, probe_type="surface"))
        assert "# closed:" not in (case / "othd.cyl_nodes.map").read_text()

    def test_closed_without_a_line_exits(self, case):
        with pytest.raises(SystemExit):
            execute_write(make_args(case, probe_type="surface", closed=True))
        with pytest.raises(SystemExit):
            execute_write(make_args(case, closed=True))

    def test_an_unknown_type_exits(self, case):
        with pytest.raises(SystemExit):
            execute_write(make_args(case, probe_type="helix"))

    def test_it_applies_to_coordinates_blocks_too(self, case):
        """Three collinear points are a line or three points; only a human knows."""
        execute_write(make_args(case, othd_map="probe_dat", probe_type="point"))
        assert "# probe: point" in (case / "othd.probe_dat.map").read_text()

    def test_selecting_one_block_lets_sets_differ(self, case):
        execute_write(make_args(case, othd_map="cyl_nodes", probe_type="line"))
        execute_write(make_args(case, othd_map="probe_dat", probe_type="point"))
        assert "# probe: line" in (case / "othd.cyl_nodes.map").read_text()
        assert "# probe: point" in (case / "othd.probe_dat.map").read_text()


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
        execute_write(make_args(case))
        header = (case / "othd.cyl_nodes.map").read_text()
        assert "WARNING" in header and "newer than this case's othd files" in header

    def test_no_othd_files_means_no_warning(self, case):
        execute_write(make_args(case))
        assert "WARNING" not in (case / "othd.cyl_nodes.map").read_text()

    def test_an_othd_newer_than_the_inputs_is_not_flagged(self, case):
        othd = case / "othd_files"
        othd.mkdir()
        (othd / "riser.othd").write_text("data")                        # written just now
        execute_write(make_args(case))
        assert "WARNING" not in (case / "othd.cyl_nodes.map").read_text()


class TestWildcard:
    """`case write * --othd-map` over the .cases registry."""

    def test_maps_every_case_it_can(self, registry):
        execute_write(make_args("*"))
        assert (registry / "Good1" / "othd.cyl_nodes.map").exists()
        assert (registry / "Good2" / "othd.tip_nodes.map").exists()

    def test_one_bad_case_does_not_end_the_batch(self, registry, capsys):
        execute_write(make_args("*"))
        out = flat(capsys.readouterr().out)
        # Unmappable is skipped, NoCrd and Gone fail, yet both good cases are written
        assert "2 case(s) mapped" in out
        assert "1 skipped" in out and "2 failed" in out
        assert (registry / "Good1" / "othd.cyl_nodes.map").exists()

    def test_nothing_to_map_is_a_skip_not_a_failure(self, registry, capsys):
        execute_write(make_args("*"))
        out = flat(capsys.readouterr().out)
        assert "Unmappable" in out and "records can be mapped" in out
        assert not list((registry / "Unmappable").glob("othd.*.map"))

    def test_a_coordinates_block_counts_as_mappable(self, registry):
        """A case with only a coordinates block is mapped, not skipped."""
        execute_write(make_args("*"))
        assert (registry / "Good1" / "othd.probe_dat.map").exists()

    def test_the_selector_still_applies(self, registry):
        execute_write(make_args("*", othd_map="tip_nodes"))
        assert (registry / "Good1" / "othd.tip_nodes.map").exists()
        assert not (registry / "Good1" / "othd.cyl_nodes.map").exists()

    def test_exits_non_zero_when_no_case_could_be_mapped(self, tmp_path, monkeypatch):
        (tmp_path / ".cases").write_text(json.dumps(
            [{"name": "Gone", "path": str(tmp_path / "not_here")}]))
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            execute_write(make_args("*"))

    def test_missing_registry_is_reported(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            execute_write(make_args("*"))
