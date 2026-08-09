"""Tests for `field extract --probe` (point probes) against a synthetic PLT file.

The fixture writes a real TDV112 binary that src/plt/fxplt.py parses, so the whole
path -- header parse, zone load, probe validation, CSV output -- is exercised
without needing a case from a run.
"""

import argparse
import struct
import sys

import numpy as np
import pytest

from src.commands.field.extract_impl import probe as P
from src.commands.field.extract_impl.command import execute_extract
from src.commands.field.compute_impl.command import execute_compute


def _tstr(s):
    return b"".join(struct.pack("<i", ord(c)) for c in s) + struct.pack("<i", 0)


def write_plt(path, timestep, side=3):
    """Write a `side`^3 unit-cube brick mesh with variables X,Y,Z,U,P.

    A second zone 'surf' covers the z=0 face with quads and stores no data of its
    own: every variable is flagged as shared from zone 0, the way FlexFlow writes
    a cylinder-surface zone riding on the volume zone's node array.
    """
    g = np.linspace(0.0, 1.0, side)
    X, Y, Z = np.meshgrid(g, g, g, indexing="ij")
    pts = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()]).astype(np.float32)
    cols = [pts[:, 0], pts[:, 1], pts[:, 2],
            (pts[:, 0] * 10 + timestep / 1000.0).astype(np.float32),
            (pts[:, 1] * -5.0).astype(np.float32)]
    names = ["X", "Y", "Z", "U", "P"]

    at = lambda i, j, k: (i * side + j) * side + k
    conn = np.array([[at(i, j, k), at(i + 1, j, k), at(i + 1, j + 1, k), at(i, j + 1, k),
                      at(i, j, k + 1), at(i + 1, j, k + 1), at(i + 1, j + 1, k + 1),
                      at(i, j + 1, k + 1)]
                     for i in range(side - 1) for j in range(side - 1)
                     for k in range(side - 1)], dtype=np.int32)
    surf = np.array([[at(i, j, 0), at(i + 1, j, 0), at(i + 1, j + 1, 0), at(i, j + 1, 0)]
                     for i in range(side - 1) for j in range(side - 1)], dtype=np.int32)

    def zone_header(name, ztype, nelem):
        b = struct.pack("<f", 299.0) + _tstr(name)
        b += struct.pack("<iid", -1, -1, float(timestep))   # parent, strand, time
        b += struct.pack("<iiiii", -1, ztype, 0, 0, 0)      # colour, type, no varloc/neighbours
        b += struct.pack("<ii", len(pts), nelem)
        return b + struct.pack("<iiii", 0, 0, 0, 0)         # i/j/k dims, no aux pairs

    b = bytearray(b"#!TDV112")
    b += struct.pack("<ii", 1, 0)                       # byte-order check, filetype
    b += _tstr("test") + struct.pack("<i", len(names))
    for n in names:
        b += _tstr(n)
    b += zone_header("FIELD", 5, len(conn))             # FEBRICK
    b += zone_header("surf", 3, len(surf))              # FEQUADRILATERAL
    b += struct.pack("<f", 357.0)                       # EOH

    b += struct.pack("<f", 299.0)                       # zone 0 data
    b += b"".join(struct.pack("<i", 1) for _ in names)  # every variable float32
    b += struct.pack("<iii", 0, 0, -1)                  # no passive/shared, own connectivity
    for c in cols:
        b += struct.pack("<dd", float(c.min()), float(c.max()))
    for c in cols:
        b += c.astype("<f4").tobytes()
    b += conn.astype("<i4").tobytes()

    b += struct.pack("<f", 299.0)                       # zone 1 data
    b += b"".join(struct.pack("<i", 1) for _ in names)
    b += struct.pack("<i", 0)                           # no passive vars
    b += struct.pack("<i", 1)                           # variable sharing follows...
    b += b"".join(struct.pack("<i", 0) for _ in names)  # ...every one of them from zone 0
    b += struct.pack("<i", -1)                          # its own connectivity
    b += surf.astype("<i4").tobytes()                   # (no min/max: it stores nothing)
    path.write_bytes(bytes(b))


@pytest.fixture
def case(tmp_path):
    """A case directory holding three timesteps of the synthetic mesh."""
    binary = tmp_path / "binary"
    binary.mkdir()
    for ts in (1000, 2000, 3000):
        write_plt(binary / f"test.{ts}.plt", ts)
    return tmp_path


def make_args(case, **kw):
    defaults = dict(case=str(case), verbose=False, help=False, variables="U,P", zone="FIELD",
                    timestep=None, t1=None, t2=None, freq=None, output_file=None,
                    xmin=None, xmax=None, ymin=None, ymax=None, zmin=None, zmax=None,
                    probe=None, probe_tol=None, no_progress=True, interpolate=False, nen=None)
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def unit_cube_mesh(side=5):
    """(points, hex connectivity) for a side^3 node grid on the unit cube."""
    g = np.linspace(0.0, 1.0, side)
    X, Y, Z = np.meshgrid(g, g, g, indexing="ij")
    pts = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    at = lambda i, j, k: (i * side + j) * side + k
    conn = np.array([[at(i, j, k), at(i + 1, j, k), at(i + 1, j + 1, k), at(i, j + 1, k),
                      at(i, j, k + 1), at(i + 1, j, k + 1), at(i + 1, j + 1, k + 1),
                      at(i, j + 1, k + 1)]
                     for i in range(side - 1) for j in range(side - 1)
                     for k in range(side - 1)], dtype=np.int64)
    return pts, conn


def read_csv(path):
    """Split a probe CSV into its '#' block and its parsed rows."""
    lines = path.read_text().strip().split("\n")
    comments = [ln[2:] for ln in lines if ln.startswith("# ")]
    body = [ln for ln in lines if not ln.startswith("#")]
    header = body[0].split(",")
    return comments, header, [dict(zip(header, ln.split(","))) for ln in body[1:]]


class TestParseProbes:
    """Parsing of the --probe flag."""

    def test_single_point(self):
        points, axes = P.parse_probes(["0.5,0.25,0.75"], Logger())
        assert points.tolist() == [[0.5, 0.25, 0.75]]
        assert axes[0].tolist() == [0, 1, 2]

    def test_repeated_and_semicolon_separated(self):
        points, axes = P.parse_probes(["1,2,3", "4,5,6;7,8,9"], Logger())
        assert points.tolist() == [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

    def test_two_values_leave_z_unspecified(self):
        points, axes = P.parse_probes(["0.5,0.5"], Logger())
        assert axes[0].tolist() == [0, 1]
        assert np.isnan(points[0][2])
        assert P.label(points[0], axes[0]) == "(0.5, 0.5, -)"

    def test_bare_string_is_not_split_per_character(self):
        points, _ = P.parse_probes("0.5,0.5,0.5", Logger())
        assert points.tolist() == [[0.5, 0.5, 0.5]]

    @pytest.mark.parametrize("spec", ["0.5,0.5,junk", "0.5", "1,2,3,4"])
    def test_malformed_exits(self, spec):
        with pytest.raises(SystemExit):
            P.parse_probes([spec], Logger())


class TestNearestNode:
    """Nearest-node lookup must agree with brute force, chunked or not."""

    @pytest.fixture
    def pts(self):
        return np.random.RandomState(0).rand(5000, 3).astype("f4")

    def test_matches_brute_force(self, pts):
        point = np.array([0.3, 0.4, 0.5])
        idx, dist = P.nearest_node(pts, point, np.arange(3))
        brute = np.linalg.norm(pts - point, axis=1)
        assert idx == int(brute.argmin())
        assert dist == pytest.approx(brute.min(), abs=1e-6)

    def test_chunking_does_not_change_the_answer(self, pts):
        point = np.array([0.3, 0.4, 0.5])
        assert P.nearest_node(pts, point, np.arange(3), chunk=97) == \
               P.nearest_node(pts, point, np.arange(3))

    def test_two_dimensional_probe_ignores_z(self, pts):
        point = np.array([0.3, 0.4, np.nan])
        idx, dist = P.nearest_node(pts, point, np.arange(2))
        brute = np.linalg.norm(pts[:, :2] - point[:2], axis=1)
        assert idx == int(brute.argmin())
        assert dist == pytest.approx(brute.min(), abs=1e-6)


class TestDomainChecks:
    """Inside-domain validation and the far-from-any-node warning."""

    def test_inside_passes(self):
        points, axes = P.parse_probes(["0.5,0.5,0.5"], Logger())
        P.check_inside(points, axes, np.zeros(3), np.ones(3), "FIELD", Logger())

    def test_outside_exits(self):
        points, axes = P.parse_probes(["5,0,0"], Logger())
        with pytest.raises(SystemExit):
            P.check_inside(points, axes, np.zeros(3), np.ones(3), "FIELD", Logger())

    def test_tolerance_admits_a_boundary_probe(self):
        points, axes = P.parse_probes(["1.05,0.5,0.5"], Logger())
        with pytest.raises(SystemExit):
            P.check_inside(points, axes, np.zeros(3), np.ones(3), "FIELD", Logger())
        P.check_inside(points, axes, np.zeros(3), np.ones(3), "FIELD", Logger(), tol=0.1)

    def test_unspecified_axis_is_not_checked(self):
        points, axes = P.parse_probes(["0.5,0.5"], Logger())   # z unspecified -> nan
        P.check_inside(points, axes, np.zeros(3), np.ones(3), "FIELD", Logger())

    def test_quiet_for_a_node_within_the_mesh(self):
        assert P.far_probe_warning(0.05, np.zeros(3), np.ones(3), 1000) is None

    def test_warns_when_the_probe_sits_in_a_hole(self):
        pts = np.random.RandomState(0).rand(20000, 3)
        pts = pts[np.linalg.norm(pts - 0.5, axis=1) > 0.4]     # spherical hole in the middle
        dist = np.linalg.norm(pts - 0.5, axis=1).min()
        assert "hole of the mesh" in P.far_probe_warning(dist, pts.min(0), pts.max(0), len(pts))


class TestExtractProbe:
    """End-to-end `field extract --probe` against the synthetic case."""

    def test_writes_a_row_per_probe_per_step(self, case):
        out = case / "probes.csv"
        execute_extract(make_args(case, t1=1000, t2=3000, probe=["0.5,0.5,0.5", "0,0,0"],
                                  output_file=str(out)))
        _, header, rows = read_csv(out)
        assert header == ["timestep", "probe", "node", "x_node", "y_node", "z_node",
                          "distance", "U", "P"]
        assert len(rows) == 3 * 2                               # 3 steps x 2 probes

        p1 = [r for r in rows if r["probe"] == "1"]
        assert [int(r["timestep"]) for r in p1] == [1000, 2000, 3000]
        # U = 10x + step/1000 at the sampled node, which sits exactly on the probe
        assert [float(r["U"]) for r in p1] == [6.0, 7.0, 8.0]
        assert all(float(r["distance"]) == 0.0 for r in rows)

    def test_probe_details_head_the_file_as_comments(self, case):
        out = case / "probes.csv"
        execute_extract(make_args(case, timestep=1000, probe=["0.5,0.5,0.5", "0,0,0"],
                                  output_file=str(out)))
        comments, header, rows = read_csv(out)
        assert "zone: FIELD" in comments[1]
        assert "sampling: nearest node" in comments
        assert "probe 1: (0.5, 0.5, 0.5)" in comments
        assert "probe 2: (0, 0, 0)" in comments
        # the coordinates are in the block, not repeated on every row
        assert not [name for name in header if name.endswith("_probe")]

    def test_comment_block_survives_a_pandas_round_trip(self, case):
        pd = pytest.importorskip("pandas")
        out = case / "probes.csv"
        execute_extract(make_args(case, t1=1000, t2=3000, probe="0.5,0.5,0.5",
                                  output_file=str(out)))
        df = pd.read_csv(out, comment="#")
        assert list(df.columns)[:2] == ["timestep", "probe"]
        assert df["U"].tolist() == [6.0, 7.0, 8.0]

    def test_prints_a_table_when_no_output_is_given(self, case, capsys):
        execute_extract(make_args(case, timestep=1000, probe="0.5,0.5,0.5"))
        printed = capsys.readouterr().out
        assert "probe 1: (0.5, 0.5, 0.5)" in printed
        assert "distance" in printed

    def test_probe_outside_the_domain_exits(self, case):
        with pytest.raises(SystemExit):
            execute_extract(make_args(case, timestep=1000, probe="5,0,0"))

    def test_unknown_variable_exits(self, case):
        with pytest.raises(SystemExit):
            execute_extract(make_args(case, timestep=1000, variables="Nope", probe="0,0,0"))

    def test_unknown_zone_exits(self, case):
        with pytest.raises(SystemExit):
            execute_extract(make_args(case, timestep=1000, zone="NOZONE", probe="0,0,0"))

    def test_mesh_output_is_rejected_for_probes(self, case):
        with pytest.raises(SystemExit):
            execute_extract(make_args(case, timestep=1000, probe="0,0,0",
                                      output_file=str(case / "probes.vtu")))

    def test_interpolate_without_a_probe_exits(self, case):
        with pytest.raises(SystemExit):
            execute_extract(make_args(case, timestep=1000, interpolate=True))


class TestSharedZone:
    """A zone storing nothing of its own, riding on the volume zone's arrays."""

    def test_reader_follows_the_share_to_the_owning_zone(self, case):
        from src.plt.fxplt import PltFile
        plt = PltFile(str(case / "binary" / "test.1000.plt"))
        assert [z["name"] for z in plt.zones] == ["FIELD", "surf"]
        assert plt.shared_from(0) == []                  # FIELD stores its own
        assert plt.shared_from(1) == [0]                 # surf borrows all of them
        assert [plt.variable_owner(1, v) for v in range(len(plt.vars))] == [0] * 5

    def test_surface_zone_keeps_only_the_nodes_its_elements_use(self, case):
        from src.plt.fxplt import PltFile
        plt = PltFile(str(case / "binary" / "test.1000.plt"))
        volume_pts, _, volume_data, _ = plt.load_zone(0)
        pts, conn, pdata, info = plt.load_zone(1)

        assert info["shared_from"] == [0]
        assert info["npts_shared"] == len(volume_pts)    # what the header claimed
        assert len(pts) == 9 and len(conn) == 4          # the 3x3 z=0 face
        assert set(pdata) == {"U", "P"}                  # data arrived despite sharing
        assert np.all(pts[:, 2] == 0.0)

        # the compacted arrays must still be the parent's values at those nodes
        on_face = np.flatnonzero(volume_pts[:, 2] == 0.0)
        assert np.array_equal(pts, volume_pts[on_face])
        assert np.array_equal(pdata["U"], volume_data["U"][on_face])
        assert conn.max() == len(pts) - 1                # renumbered, not parent indices

    def test_extracts_the_surface_to_csv(self, case):
        out = case / "surface.csv"
        execute_extract(make_args(case, zone="surf", variables="X,Y,Z,U",
                                  t1=1000, t2=3000, output_file=str(out)))
        rows = np.loadtxt(out, delimiter=",", skiprows=1)
        assert len(rows) == 3 * 9                        # 3 steps x 9 surface nodes
        assert set(rows[:, 0].astype(int)) == {1000, 2000, 3000}
        assert np.all(rows[:, 3] == 0.0)                 # every row is on the z=0 face

    def test_warns_when_rows_carry_no_coordinates(self, case, capsys):
        out = case / "surface.csv"
        execute_extract(make_args(case, zone="surf", variables="U",
                                  t1=1000, t2=3000, output_file=str(out)))
        assert "carry no coordinates" in capsys.readouterr().err

    def test_no_such_warning_once_coordinates_are_asked_for(self, case, capsys):
        out = case / "surface.csv"
        execute_extract(make_args(case, zone="surf", variables="X,Y,Z,U",
                                  t1=1000, t2=3000, output_file=str(out)))
        assert "carry no coordinates" not in capsys.readouterr().err

    def test_probes_the_surface_zone(self, case):
        execute_extract(make_args(case, zone="surf", variables="U", timestep=1000,
                                  probe="0.5,0.5,0.0"))

    def test_writes_the_surface_as_a_quad_mesh(self, case):
        meshio = pytest.importorskip("meshio")
        out = case / "surface.vtu"
        execute_extract(make_args(case, zone="surf", variables="U", timestep=1000,
                                  output_file=str(out)))
        mesh = meshio.read(out)
        assert [c.type for c in mesh.cells] == ["quad"]
        assert len(mesh.points) == 9 and len(mesh.cells[0].data) == 4


class TestComputeForce:
    """`field compute force` over the shared surface zone (the cube's z=0 face)."""

    @staticmethod
    def compute_args(case, **kw):
        defaults = dict(quantity="force", case=str(case), verbose=False, help=False,
                        zone="surf", timestep=None, t1=None, t2=None, freq=None,
                        output_file=None, pressure="P", nen=None, no_progress=True)
        defaults.update(kw)
        return argparse.Namespace(**defaults)

    def test_areas_and_normals_come_from_the_mesh(self, case):
        from src.plt.fxplt import PltFile
        from src.plt import surface
        plt = PltFile(str(case / "binary" / "test.1000.plt"))
        pts, vol_conn, _, _ = plt.load_zone(0)
        surf_conn = plt.load_connectivity(1)
        centroid, area, normal = surface.element_geometry(pts, surf_conn)

        assert len(surf_conn) == 4                       # 2x2 quads on the z=0 face
        assert area == pytest.approx(0.25)               # each 0.5 x 0.5
        assert area.sum() == pytest.approx(1.0)
        assert np.all(centroid[:, 2] == 0.0)
        assert np.abs(normal[:, 2]) == pytest.approx(1.0)   # face normal is +/- z

    def test_normals_are_oriented_by_the_adjacent_volume_cell(self, case):
        from src.plt.fxplt import PltFile
        from src.plt import surface
        plt = PltFile(str(case / "binary" / "test.1000.plt"))
        pts, vol_conn, _, _ = plt.load_zone(0)
        surf_conn = plt.load_connectivity(1)
        centroid, area, normal = surface.element_geometry(pts, surf_conn)
        owners = surface.adjacent_cells(surf_conn, vol_conn)
        assert np.all(owners >= 0)                       # every face found its cell

        anchors = pts[vol_conn[owners]].mean(axis=1)
        out = surface.orient_outward(normal, centroid, anchors)
        # the mesh lies at z > 0, so "out of the body" is +z for this face
        assert np.all(out[:, 2] > 0)

    def test_force_matches_the_analytic_integral(self, case, capsys):
        out = case / "forces.csv"
        # P = -5y over the z=0 face, area 1, outward normal +z
        #   Fz = -integral p dA = 5 * mean(y) * area = 5 * 0.5 * 1 = 2.5
        execute_compute(self.compute_args(case, timestep=1000, output_file=str(out)))
        rows = [ln for ln in out.read_text().splitlines() if not ln.startswith("#")]
        header = rows[0].split(",")
        assert header == ["element", "x", "y", "z", "area", "nx", "ny", "nz",
                          "P", "Fx", "Fy", "Fz"]
        data = np.array([[float(v) for v in ln.split(",")] for ln in rows[1:]])
        assert len(data) == 4
        col = {n: data[:, i] for i, n in enumerate(header)}
        assert col["Fz"].sum() == pytest.approx(2.5)
        assert col["Fx"].sum() == pytest.approx(0.0)
        assert col["Fy"].sum() == pytest.approx(0.0)
        assert col["area"].sum() == pytest.approx(1.0)

    def test_element_ids_are_stable_across_timesteps(self, case):
        out = case / "forces.csv"
        execute_compute(self.compute_args(case, t1=1000, t2=3000, output_file=str(out)))
        rows = [ln.split(",") for ln in out.read_text().splitlines()
                if not ln.startswith("#")][1:]
        by_step = {}
        for r in rows:
            by_step.setdefault(int(r[0]), []).append(int(r[1]))
        assert sorted(by_step) == [1000, 2000, 3000]
        assert all(v == [0, 1, 2, 3] for v in by_step.values())

    def test_refuses_a_volume_zone(self, case):
        with pytest.raises(SystemExit):
            execute_compute(self.compute_args(case, zone="FIELD", timestep=1000))

    def test_refuses_an_unknown_quantity(self, case):
        with pytest.raises(SystemExit):
            execute_compute(self.compute_args(case, quantity="lift", timestep=1000))

    def test_missing_pressure_variable_exits(self, case):
        with pytest.raises(SystemExit):
            execute_compute(self.compute_args(case, pressure="Nope", timestep=1000))

    def test_writes_the_surface_with_force_as_cell_data(self, case):
        meshio = pytest.importorskip("meshio")
        out = case / "forces.vtu"
        execute_compute(self.compute_args(case, timestep=1000, output_file=str(out)))
        mesh = meshio.read(out)
        assert len(mesh.points) == 9 and mesh.cells[0].type == "quad"
        assert set(mesh.cell_data) == {"area", "Pressure", "nx", "ny", "nz",
                                       "Fx", "Fy", "Fz"}
        assert float(np.sum(mesh.cell_data["Fz"][0])) == pytest.approx(2.5)

    def test_bare_output_name_splits_the_run_into_one_file_per_step(self, case):
        out = case / "loads"
        execute_compute(self.compute_args(case, t1=1000, t2=3000, output_file=str(out)))
        assert sorted(p.name for p in out.iterdir()) == [
            "elements_1000.csv", "elements_2000.csv", "elements_3000.csv", "summary.csv"]

        comments, header, rows = read_csv(out / "elements_2000.csv")
        assert header == ["element", "x", "y", "z", "area", "nx", "ny", "nz",
                          "P", "Fx", "Fy", "Fz"]          # no timestep: it is the name
        assert "timestep: 2000" in comments[-1]
        assert len(rows) == 4
        assert sum(float(r["Fz"]) for r in rows) == pytest.approx(2.5)

    def test_summary_carries_one_row_per_timestep(self, case):
        out = case / "loads"
        execute_compute(self.compute_args(case, t1=1000, t2=3000, output_file=str(out)))
        _, header, rows = read_csv(out / "summary.csv")
        assert header == ["timestep", "elements", "area", "Fx", "Fy", "Fz"]
        assert [r["timestep"] for r in rows] == ["1000", "2000", "3000"]
        assert all(r["elements"] == "4" for r in rows)     # integers, not 4.0e+00
        assert all(float(r["Fz"]) == pytest.approx(2.5) for r in rows)

    def test_prints_totals_without_an_output_file(self, case, capsys):
        execute_compute(self.compute_args(case, timestep=1000))
        printed = capsys.readouterr().out
        assert "Fz" in printed and "elements" in printed


class TestInterpolate:
    """--interpolate must reproduce a linear field exactly, off-node included."""

    def test_reproduces_the_linear_field_between_nodes(self, case):
        pytest.importorskip("pyvista")
        out = case / "probes.csv"
        # U = 10x + step/1000 and P = -5y are linear, so interpolation is exact.
        # (0.25, 0.75, 0.5) sits inside a cell, not on any node.
        execute_extract(make_args(case, t1=1000, t2=3000, probe="0.25,0.75,0.5",
                                  interpolate=True, output_file=str(out)))
        comments, header, rows = read_csv(out)
        assert header == ["timestep", "probe", "source", "U", "P"]   # no node columns
        assert "sampling: linear interpolation inside the containing cell" in comments
        assert [r["source"] for r in rows] == ["cell"] * 3
        assert [float(r["U"]) for r in rows] == pytest.approx([3.5, 4.5, 5.5])
        assert [float(r["P"]) for r in rows] == pytest.approx([-3.75] * 3)

    def test_differs_from_the_nearest_node_off_node(self, case):
        pytest.importorskip("pyvista")
        near, interp_out = case / "near.csv", case / "interp.csv"
        args = dict(timestep=1000, probe="0.25,0.75,0.5")
        execute_extract(make_args(case, output_file=str(near), **args))
        execute_extract(make_args(case, output_file=str(interp_out), interpolate=True, **args))
        near_u = float(read_csv(near)[2][0]["U"])
        interp_u = float(read_csv(interp_out)[2][0]["U"])
        assert near_u == pytest.approx(1.0)                  # snapped to the node at x=0
        assert interp_u == pytest.approx(3.5)                # the value at x=0.25

    def test_reports_where_each_value_came_from(self, case):
        pytest.importorskip("pyvista")
        from src.commands.field.extract_impl import interp
        pts, conn = unit_cube_mesh()
        data = {"U": (10 * pts[:, 0]).copy()}

        def probe_at(point):
            target = np.array([point], dtype=float)
            node = [int(np.argmin(np.linalg.norm(pts - target[0], axis=1)))]
            return interp.sample(pts, conn, "hexahedron", data, target, pad=0.5,
                                 anchor_nodes=node)

        values, source, moved = probe_at([0.3, 0.5, 0.5])           # inside an element
        assert source == [interp.FOUND] and moved[0] == 0
        assert values["U"][0] == pytest.approx(3.0)

        values, source, moved = probe_at([0.0, 0.5, 0.5])           # exactly on the wall
        assert source == [interp.FOUND]
        assert values["U"][0] == pytest.approx(0.0)

        values, source, moved = probe_at([-1e-9, 0.5, 0.5])         # a hair outside it
        assert source == [interp.NUDGED]                             # stepped inward...
        assert 0 < moved[0] < 1e-3                                   # ...but barely
        assert values["U"][0] == pytest.approx(0.0, abs=1e-3)

        values, source, moved = probe_at([-0.5, 0.5, 0.5])          # in a hole
        assert source == [interp.MISSING] and moved[0] == 0

    def test_falls_back_to_the_nearest_node_in_a_hole(self, case, capsys):
        pytest.importorskip("pyvista")
        # A cube of cells with the middle removed: the probe passes the bounding-box
        # check but lies in no element, so the nearest node's value must be used.
        from src.commands.field.extract_impl import interp
        pts, conn = unit_cube_mesh(side=7)
        middle = np.linalg.norm(pts[conn].mean(axis=1) - 0.5, axis=1) < 0.25
        conn = conn[~middle]
        data = {"U": (10 * pts[:, 0]).copy()}
        target = np.array([[0.5, 0.5, 0.5]])
        node = [int(np.argmin(np.linalg.norm(pts - target[0], axis=1)))]
        _, source, _ = interp.sample(pts, conn, "hexahedron", data, target, pad=0.5,
                                     anchor_nodes=node)
        assert source == [interp.MISSING]

    def test_flags_an_interpolant_outside_its_element_range(self, case):
        pytest.importorskip("pyvista")
        from src.commands.field.extract_impl import interp
        pts, conn = unit_cube_mesh()
        data = {"U": (10 * pts[:, 0]).copy()}
        target = np.array([[0.3, 0.5, 0.5]])
        values, _, _ = interp.sample(pts, conn, "hexahedron", data, target, pad=0.5)
        assert interp.check_cells(pts, conn, "hexahedron", data, target, values) == []
        # a value no convex combination of the element's nodes could produce
        broken = interp.check_cells(pts, conn, "hexahedron", data, target,
                                    {"U": np.array([999.0])})
        assert len(broken) == 1 and "outside its element's nodal range" in broken[0]


class Logger:
    """Quiet stand-in for src.utils.logger.Logger (errors go to stderr as usual)."""

    verbose = False

    def info(self, message):
        pass

    def success(self, message):
        pass

    def warning(self, message):
        print(f"[WARNING] {message}", file=sys.stderr)

    def error(self, message):
        print(f"[ERROR] {message}", file=sys.stderr)

    def debug(self, message):
        pass
