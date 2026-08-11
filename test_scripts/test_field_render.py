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
import pathlib
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
                normal=None, origin=None, slices=None, color_range=None,
                t1=None, t2=None, freq=None, camera=None, pick_camera=None,
                no_vtp=False)
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

    @pytest.mark.parametrize("mode, heading", [
        ("iso", "Field Render Iso"), ("slice", "Field Render Slice"),
    ])
    def test_no_input_shows_the_mode_help(self, capsys, mode, heading):
        """Nothing to render is someone finding their way, not a typo."""
        with pytest.raises(SystemExit) as exc:
            render_cmd.execute_render(args(mode=mode, vtu=None))
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "nothing to render" in captured.err
        assert heading in captured.out


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
    """--output names a directory; its extension picks what goes inside."""

    @pytest.mark.parametrize("value, name, ext", [
        (None, "render_slice", None),          # the default directory
        ("wake", "wake", None),
        ("out/wake", "out/wake", None),
        ("wake.png", "wake", ".png"),
        ("cut.vtp", "cut", ".vtp"),
        ("cut.vtu", "cut", ".vtu"),
        ("cut.vtk", "cut", ".vtk"),
        ("cut.csv", "cut", ".csv"),
    ])
    def test_directory_and_format(self, value, name, ext):
        got_name, got_ext = render_cmd._resolve_output(
            args(output=value), "slice", _Logger())
        assert (got_name, got_ext) == (name, ext)

    def test_default_names_the_mode(self):
        assert render_cmd._resolve_output(args(), "iso", _Logger())[0] == "render_iso"

    def test_unknown_extension_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            render_cmd._resolve_output(args(output="cut.stl"), "slice", _Logger())
        assert exc.value.code == 1
        assert "Unsupported --output extension" in capsys.readouterr().err

    def test_directory_goes_under_the_case(self, tmp_path):
        """Figures belong with the case, not loose beside the PLTs in binary/."""
        case = tmp_path / "C"
        case.mkdir()
        got = render_cmd._output_dir(args(case=str(case)), "render_iso")
        assert got == case / "render_iso"
        assert got.is_dir()

    def test_a_vtu_input_keeps_the_directory_beside_it(self, tmp_path):
        vtu = tmp_path / "field.vtu"
        vtu.write_text("")
        got = render_cmd._output_dir(args(case=None, vtu=str(vtu)), "render_iso")
        assert got == tmp_path / "render_iso"


class TestColourRange:
    """--color-range fixes the colour scale so frames can be compared."""

    def test_ordered_range_passes(self):
        assert render_cmd._check_range([-0.5, 0.5], _Logger()) == [-0.5, 0.5]

    def test_absent_is_none(self):
        """None means auto, computed per surface inside render_surface."""
        assert render_cmd._check_range(None, _Logger()) is None

    @pytest.mark.parametrize("pair", [[1.0, 1.0], [5.0, 1.0]])
    def test_min_must_be_below_max(self, capsys, pair):
        with pytest.raises(SystemExit) as exc:
            render_cmd._check_range(pair, _Logger())
        assert exc.value.code == 1
        assert "MIN below MAX" in capsys.readouterr().err

    def test_it_reaches_the_config(self):
        """The whole point: the value must land on color.range."""
        cfg = render.default_config("iso")
        render_cmd._apply_overrides(args(color_range=[-2.0, 3.0]), cfg, "iso")
        assert cfg["color"]["range"] == [-2.0, 3.0]

    def test_it_applies_to_slice_too(self):
        """Colouring is shared, so --color-range is not an iso-only flag."""
        cfg = render.default_config("slice")
        render_cmd._apply_overrides(args(mode="slice", color_range=[0.0, 1.0]), cfg, "slice")
        assert cfg["color"]["range"] == [0.0, 1.0]


class TestCamera:
    """A saved view is this repo's answer to a Tecplot .sty: set it once, reuse it."""

    def test_camera_replaces_the_default_views(self, tmp_path):
        """A chosen camera answers "which view", so the mode's defaults go."""
        cam = tmp_path / "cam.yml"
        cam.write_text("position: [1, 2, 3]\nfocal: [0, 0, 0]\nup: [0, 0, 1]\n")
        cfg = render.default_config("iso")
        assert len(cfg["views"]) == 4
        render_cmd._apply_camera(args(camera=str(cam)), cfg, _Logger())
        assert cfg["views"] == [{"name": "view", "camera_file": str(cam)}]

    def test_missing_camera_file_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            render_cmd._apply_camera(args(camera="/nope/cam.yml"),
                                     render.default_config("iso"), _Logger())
        assert exc.value.code == 1
        assert "camera file not found" in capsys.readouterr().err

    def test_reading_and_writing_a_frame_round_trips(self, tmp_path):
        """save_camera writes exactly what load_camera reads -- one format."""
        from src.plt.camera import save_camera, load_camera
        path = tmp_path / "cam.yml"
        saved = save_camera(str(path), _Camera())
        assert load_camera(str(path)) == saved
        assert saved["position"] == [3.0, -2.0, 1.5]
        assert saved["parallel"] is True

    def test_the_frame_is_what_setup_camera_consumes(self, tmp_path):
        """The written keys must be the ones _setup_camera looks for."""
        from src.plt.camera import save_camera
        saved = save_camera(str(tmp_path / "cam.yml"), _Camera())
        assert set(saved) == {"position", "focal", "up", "parallel",
                              "parallel_scale", "view_angle"}


class TestConfigValidation:
    """Config values that would otherwise fail deep inside pyvista."""

    def test_a_good_range_passes(self):
        cfg = render.default_config("iso")
        cfg["color"]["range"] = [-0.5, 0.5]
        render_cmd._check_config(cfg, _Logger())          # no exit

    def test_none_is_auto(self):
        render_cmd._check_config(render.default_config("iso"), _Logger())

    def test_a_missing_comma_is_named(self, capsys):
        """`range: [-0.5 0.5]` is valid YAML for ONE string, not two numbers."""
        import yaml
        parsed = yaml.safe_load("range: [-0.5 0.5]")["range"]
        assert parsed == ["-0.5 0.5"]                     # the trap itself
        cfg = render.default_config("iso")
        cfg["color"]["range"] = parsed
        with pytest.raises(SystemExit) as exc:
            render_cmd._check_config(cfg, _Logger())
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "two numbers" in err and "missing comma" in err

    @pytest.mark.parametrize("bad", [[1.0], [1.0, 2.0, 3.0], "auto", [2.0, 1.0]])
    def test_other_bad_ranges_rejected(self, bad):
        cfg = render.default_config("iso")
        cfg["color"]["range"] = bad
        with pytest.raises(SystemExit):
            render_cmd._check_config(cfg, _Logger())


class TestCameraFrameValidation:
    """A frame with no position sets no camera -- silently, unless we look."""

    def test_a_render_config_is_rejected_by_name(self, tmp_path):
        """The mistake worth catching: --camera given a --config file."""
        from src.plt.camera import load_camera
        cfg = tmp_path / "template.yaml"
        cfg.write_text("output:\n  prefix: iso\nviews:\n  - {name: iso}\n")
        with pytest.raises(ValueError) as exc:
            load_camera(str(cfg))
        assert "render config" in str(exc.value)
        assert "--config" in str(exc.value)

    def test_a_frame_without_position_is_rejected(self, tmp_path):
        from src.plt.camera import load_camera
        f = tmp_path / "cam.yml"
        f.write_text("up: [0, 0, 1]\n")
        with pytest.raises(ValueError) as exc:
            load_camera(str(f))
        assert "not a camera frame" in str(exc.value)

    def test_a_bad_camera_stops_before_any_rendering(self, capsys, tmp_path):
        """Catch it at the flag, not at the first screenshot of a 100-step sweep."""
        cfg = tmp_path / "template.yaml"
        cfg.write_text("views:\n  - {name: iso}\n")
        with pytest.raises(SystemExit) as exc:
            render_cmd._apply_camera(args(camera=str(cfg)),
                                     render.default_config("iso"), _Logger())
        assert exc.value.code == 1
        assert "render config" in capsys.readouterr().err


class TestColours:
    """0-1 fractions, always floats: pyvista reads an int triple as 0-255."""

    @pytest.mark.parametrize("given, expected", [
        ("white", [1.0, 1.0, 1.0]),
        ("black", [0.0, 0.0, 0.0]),
        ("gray", [0.5, 0.5, 0.5]),
        ("WHITE", [1.0, 1.0, 1.0]),
        ("no such colour", [1.0, 1.0, 1.0]),      # falls back to white
    ])
    def test_names(self, given, expected):
        assert render.to_rgb(given) == expected

    def test_white_is_not_black(self):
        """The bug: [1, 1, 1] as ints is RGB(1,1,1) downstream, i.e. black."""
        assert render.to_rgb("white") == [1.0, 1.0, 1.0]
        assert all(isinstance(v, float) for v in render.to_rgb("white"))

    @pytest.mark.parametrize("given, expected", [
        ([1.0, 1.0, 1.0], [1.0, 1.0, 1.0]),       # 0-1 as written
        ([1, 1, 1], [1.0, 1.0, 1.0]),             # ints meaning 0-1
        ([255, 255, 255], [1.0, 1.0, 1.0]),       # 0-255 bytes
        ([0, 0, 0], [0.0, 0.0, 0.0]),
        ([51, 102, 153], [0.2, 0.4, 0.6]),
        ([0.2, 0.4, 0.6], [0.2, 0.4, 0.6]),
    ])
    def test_both_conventions(self, given, expected):
        assert render.to_rgb(given) == pytest.approx(expected)

    def test_the_defaults_are_floats(self):
        """A default background of [1, 1, 1] rendered black for every run."""
        assert render.to_rgb(render.DEFAULTS["image"]["background"]) == [1.0, 1.0, 1.0]
        assert render.to_rgb(render.DEFAULTS["color"]["text_color"]) == [0.0, 0.0, 0.0]


class TestNoVtp:
    """A .vtp of the cut surface is written beside each image unless told not to."""

    def test_flag_turns_it_off(self):
        cfg = render.default_config("iso")
        assert cfg["output"]["save_vtp"] is True
        render_cmd._apply_overrides(args(no_vtp=True), cfg, "iso")
        assert cfg["output"]["save_vtp"] is False

    def test_absent_leaves_the_config_alone(self):
        """The flag only turns it off; it must not switch a config's False back on."""
        cfg = render.default_config("iso")
        cfg["output"]["save_vtp"] = False
        render_cmd._apply_overrides(args(no_vtp=False), cfg, "iso")
        assert cfg["output"]["save_vtp"] is False

    def test_flag_overrides_a_config_that_left_it_on(self):
        cfg = render.default_config("iso")
        cfg["output"]["save_vtp"] = True
        render_cmd._apply_overrides(args(no_vtp=True), cfg, "iso")
        assert cfg["output"]["save_vtp"] is False


class TestVtuCache:
    """A converted .vtu is cached beside its .plt, and the cache must be trusted."""

    def test_a_complete_vtu_is_accepted(self, tmp_path):
        v = tmp_path / "riser.100.vtu"
        v.write_bytes(b'<?xml version="1.0"?>\n<VTKFile>...</VTKFile>\n')
        assert render_cmd._vtu_complete(v)

    def test_a_truncated_vtu_is_rejected(self, tmp_path):
        """What an interrupted conversion leaves: valid XML that just stops."""
        v = tmp_path / "riser.100.vtu"
        v.write_bytes(b'<?xml version="1.0"?>\n<VTKFile type="UnstructuredGrid">\n<Piece')
        assert not render_cmd._vtu_complete(v)

    def test_a_missing_file_is_rejected(self, tmp_path):
        assert not render_cmd._vtu_complete(tmp_path / "nope.vtu")

    def test_an_empty_file_is_rejected(self, tmp_path):
        v = tmp_path / "riser.100.vtu"
        v.write_bytes(b"")
        assert not render_cmd._vtu_complete(v)

    def test_the_temp_name_keeps_the_vtu_extension(self):
        """meshio picks its writer from the extension, so .partial alone breaks it."""
        sidecar = pathlib.Path("/case/binary/riser.100.vtu")
        tmp = sidecar.with_name(sidecar.stem + ".partial.vtu")
        assert tmp.suffix == ".vtu"
        assert tmp.name == "riser.100.partial.vtu"
        assert tmp != sidecar


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


class _Camera:
    """The attributes save_camera reads off a vtk/pyvista camera."""

    position = (3.0, -2.0, 1.5)
    focal_point = (0.0, 0.0, 0.5)
    up = (0.0, 0.0, 1.0)
    parallel_projection = True
    parallel_scale = 2.5
    view_angle = 30.0


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
