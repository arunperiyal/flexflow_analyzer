"""Tests for `field render iso` and `field render slice`.

`field render` carries two modes on one parser, which is what makes it worth
testing: argparse cannot tell that `--values` is meaningless to a slice, that a
missing mode word has bound the case to `mode`, or that `--output cut.vtp` means
"do not render anything at all". All three are decided in the impl, and all
three are here.

The geometry maths (plane placement, normal parsing) is tested against
`src/plt/render.py` directly, since that is where it lives.
"""

import argparse
import sys

import numpy as np
import pytest

from src.commands.field.render_impl import command as render_cmd
from src.plt import render


def args(**over):
    """A render Namespace with every flag the parser defines."""
    base = dict(mode="iso", case=None, verbose=False, help=False, vtu="m.vtu",
                config=None, write_template=None, timestep=None, zone=None,
                nen=None, color=None, output=None, contour=None, values=None,
                normal=None, origin=None, slices=None)
    base.update(over)
    return argparse.Namespace(**base)


class TestModeValidation:
    """The mode word is the first positional and both positionals are optional."""

    def test_bare_render_prints_help_and_exits_clean(self, capsys):
        with pytest.raises(SystemExit) as exc:
            render_cmd.execute_render(args(mode=None))
        assert exc.value.code == 0
        assert "MODES:" in capsys.readouterr().out

    def test_unknown_mode_is_an_error(self, capsys):
        with pytest.raises(SystemExit) as exc:
            render_cmd.execute_render(args(mode="contour"))
        assert exc.value.code == 1
        # Logger.error writes to stderr; the help text below uses plain print.
        assert "Unknown render mode 'contour'" in capsys.readouterr().err

    def test_a_case_in_the_mode_slot_is_named_as_such(self, capsys, tmp_path):
        """`field render myCase` binds myCase to mode -- say so."""
        case = tmp_path / "BR0SG0U1P0"
        case.mkdir()
        with pytest.raises(SystemExit):
            render_cmd.execute_render(args(mode=str(case)))
        err = capsys.readouterr().err
        assert "looks like a case" in err
        assert "field render iso" in err

    @pytest.mark.parametrize("mode, heading", [
        ("iso", "Field Render Iso"), ("slice", "Field Render Slice"),
    ])
    def test_help_is_per_mode(self, capsys, mode, heading):
        render_cmd.execute_render(args(mode=mode, help=True))
        assert heading in capsys.readouterr().out


class TestModeOnlyFlags:
    """A flag belonging to the other mode is an error, never a silent no-op."""

    @pytest.mark.parametrize("mode, flag, value", [
        ("slice", "values", [20.0]),
        ("slice", "contour", "QCriterion"),
        ("iso", "normal", "z"),
        ("iso", "slices", 5),
        ("iso", "origin", "0,0,3"),
    ])
    def test_rejected(self, capsys, mode, flag, value):
        with pytest.raises(SystemExit) as exc:
            render_cmd.execute_render(args(mode=mode, **{flag: value}))
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert f"--{flag}" in err
        assert f"field render {'iso' if mode == 'slice' else 'slice'}" in err

    def test_shared_flags_pass_for_both(self):
        """--color/--zone/--nen belong to neither mode alone."""
        for mode in ("iso", "slice"):
            render_cmd._check_mode_flags(args(mode=mode, color="W", nen=8), mode, _Logger())


class TestOutputResolution:
    """--output picks the format by extension; a bare NAME stays a prefix."""

    @pytest.mark.parametrize("value, kind", [
        (None, "prefix"), ("wake", "prefix"), ("out/wake", "prefix"),
        ("wake.png", "image"),
        ("cut.vtp", "geometry"), ("cut.vtu", "geometry"),
        ("cut.vtk", "geometry"), ("cut.csv", "geometry"),
    ])
    def test_kind(self, value, kind):
        got, _ = render_cmd._resolve_output(args(output=value), "slice", _Logger())
        assert got == kind

    def test_unknown_extension_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            render_cmd._resolve_output(args(output="cut.stl"), "slice", _Logger())
        assert exc.value.code == 1
        assert "Unsupported --output extension" in capsys.readouterr().err


class TestVectorParsing:
    """--normal/--origin take an axis name or three comma-separated numbers."""

    def test_axis_names_pass_through(self):
        assert render_cmd._parse_vector("z", "normal", _Logger()) == "z"
        assert render_cmd._parse_vector("-x", "normal", _Logger()) == "-x"

    def test_vectors_become_floats(self):
        assert render_cmd._parse_vector("1,1,0", "normal", _Logger()) == [1.0, 1.0, 0.0]

    @pytest.mark.parametrize("bad", ["1,2", "1,2,3,4", "a,b,c"])
    def test_bad_vectors_error(self, bad):
        with pytest.raises(SystemExit):
            render_cmd._parse_vector(bad, "normal", _Logger())


class TestRenderConfig:
    """The engine's own geometry decisions, independent of any CLI."""

    def test_normals(self):
        assert render._normal_vector("z") == [0, 0, 1]
        assert render._normal_vector("-x") == [-1, 0, 0]
        assert render._normal_vector([1, 1, 0]) == [1, 1, 0]

    @pytest.mark.parametrize("bad", ["q", [0, 0, 0], [1, 2]])
    def test_bad_normals_raise(self, bad):
        with pytest.raises(ValueError):
            render._normal_vector(bad)

    def test_slice_gets_its_own_views(self):
        """Four views suit an isosurface; a plane is invisible from three of them."""
        assert len(render.default_config("iso")["views"]) == 4
        assert len(render.default_config("slice")["views"]) == 1
        assert render.default_config("slice")["views"][0]["parallel"] is True

    def test_camera_aims_down_the_normal(self):
        assert render.view_direction_for("z") == "+z"
        assert render.view_direction_for("-y") == "-y"
        assert render.view_direction_for([1, 1, 0]) is None   # oblique: leave it

    def test_planes_land_strictly_inside_the_mesh(self):
        """A plane exactly on a bounding face cuts nothing, so the ends are trimmed."""
        mesh = _Bounds((0, 1, 0, 2, 0, 3))
        got = [float(o[2]) for o in
               render._plane_origins(mesh, np.array([0.0, 0.0, 1.0]), 3)]
        assert got == pytest.approx([0.75, 1.5, 2.25])
        assert all(0 < z < 3 for z in got)


class _Bounds:
    def __init__(self, bounds):
        self.bounds = bounds


class _Logger:
    """Stands in for utils.Logger, matching where the real one writes.

    error/warning go to stderr; info/success are silent without --verbose, which
    is why the "did you mean a case?" hint lives in the error rather than beside
    it.
    """

    def error(self, msg):
        print(msg, file=sys.stderr)

    def warning(self, msg):
        print(msg, file=sys.stderr)

    def info(self, msg):
        pass

    def success(self, msg):
        pass
