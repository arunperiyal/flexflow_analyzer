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


def _tstr(s):
    return b"".join(struct.pack("<i", ord(c)) for c in s) + struct.pack("<i", 0)


def write_plt(path, timestep, side=3):
    """Write a `side`^3 unit-cube brick mesh with variables X,Y,Z,U,P."""
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

    b = bytearray(b"#!TDV112")
    b += struct.pack("<ii", 1, 0)                       # byte-order check, filetype
    b += _tstr("test") + struct.pack("<i", len(names))
    for n in names:
        b += _tstr(n)
    b += struct.pack("<f", 299.0) + _tstr("FIELD")      # zone header
    b += struct.pack("<iid", -1, -1, float(timestep))   # parent, strand, solution time
    b += struct.pack("<iiiii", -1, 5, 0, 0, 0)          # colour, FEBRICK, no varloc/neighbours
    b += struct.pack("<ii", len(pts), len(conn))
    b += struct.pack("<iiii", 0, 0, 0, 0)               # i/j/k dims, no aux pairs
    b += struct.pack("<f", 357.0)                       # EOH
    b += struct.pack("<f", 299.0)                       # data section
    b += b"".join(struct.pack("<i", 1) for _ in names)  # every variable float32
    b += struct.pack("<iii", 0, 0, -1)                  # no passive/shared, own connectivity
    for c in cols:
        b += struct.pack("<dd", float(c.min()), float(c.max()))
    for c in cols:
        b += c.astype("<f4").tobytes()
    b += conn.astype("<i4").tobytes()
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
                    probe=None, probe_tol=None, no_progress=True)
    defaults.update(kw)
    return argparse.Namespace(**defaults)


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

    def test_writes_a_row_per_probe_per_step(self, case, capsys):
        out = case / "probes.csv"
        execute_extract(make_args(case, t1=1000, t2=3000, probe=["0.5,0.5,0.5", "0,0,0"],
                                  output_file=str(out)))
        lines = out.read_text().strip().split("\n")
        header = lines[0].split(",")
        assert header[:3] == ["timestep", "probe", "x_probe"]
        assert header[-2:] == ["U", "P"]
        assert len(lines) == 1 + 3 * 2                          # 3 steps x 2 probes

        rows = [dict(zip(header, ln.split(","))) for ln in lines[1:]]
        p1 = [r for r in rows if r["probe"] == "P1"]
        assert [int(r["timestep"]) for r in p1] == [1000, 2000, 3000]
        # U = 10x + step/1000 at the sampled node, which sits exactly on the probe
        assert [float(r["U"]) for r in p1] == [6.0, 7.0, 8.0]
        assert all(float(r["distance"]) == 0.0 for r in rows)

    def test_prints_a_table_when_no_output_is_given(self, case, capsys):
        execute_extract(make_args(case, timestep=1000, probe="0.5,0.5,0.5"))
        printed = capsys.readouterr().out
        assert "P1 (0.5, 0.5, 0.5)" in printed
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
