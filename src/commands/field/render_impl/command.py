"""
Field render command -- pictures from PLT field data via pyvista (Tecplot-free).

Two modes, differing only in the surface they cut out of the volume:
    iso     an isosurface of a scalar (Q-criterion for vortex tubes, say)
    slice   a cut plane, or a series of them along a normal

Everything else -- the PLT->VTU conversion and its cache, the domain crop, the
threshold, the colour map, the cameras, the screenshots -- is shared, which is
why they are one subcommand with a mode rather than two subcommands.
"""

import os
import sys
from pathlib import Path

from ....utils.logger import Logger
from ....plt import render
from ....plt.convert import to_vtu
from ..locate import problem_name, find_plt, zone_index
from .templates import TEMPLATES


MODES = ("iso", "slice")

# Flags that mean something in one mode only. Passing one to the other mode is
# an error rather than a silent no-op: `field render slice --values 20` is
# someone who thinks they are contouring, and quietly rendering a plane would
# answer a question they did not ask.
MODE_ONLY = {
    "iso":   ("contour", "values"),
    "slice": ("origin", "normal", "slices"),
}

GEOMETRY_EXT = (".vtp", ".vtu", ".vtk", ".csv")


def _resolve_output(args, mode, logger):
    """Resolve --output to (kind, value).

    A bare NAME is a prefix, as it has always been for images. An extension
    picks a format instead: .png for the image itself, or a geometry file, in
    which case nothing is rendered at all.
    """
    raw = getattr(args, "output", None)
    if not raw:
        return "prefix", None
    ext = os.path.splitext(raw)[1].lower()
    if ext == "":
        return "prefix", raw
    if ext == ".png":
        return "image", raw
    if ext in GEOMETRY_EXT:
        return "geometry", raw
    logger.error(f"Unsupported --output extension '{ext}'. Use a bare NAME for an "
                 f"image prefix, NAME.png for one image, or "
                 f"{', '.join(GEOMETRY_EXT)} for the cut surface itself.")
    sys.exit(1)


def _check_mode_flags(args, mode, logger):
    """Reject a flag that belongs to the other mode."""
    for other, flags in MODE_ONLY.items():
        if other == mode:
            continue
        for flag in flags:
            if getattr(args, flag, None) not in (None, False):
                logger.error(f"--{flag.replace('_', '-')} is only for "
                             f"`field render {other}`, not `field render {mode}`")
                sys.exit(1)


def _parse_vector(text, what, logger):
    """'x' / '-z' / '1,1,0' -> what render.py accepts as a normal or origin."""
    if text is None:
        return None
    if "," not in text:
        return text                       # an axis name; render validates it
    try:
        parts = [float(v) for v in text.split(",")]
    except ValueError:
        logger.error(f"--{what} must be an axis (x/y/z) or numbers separated by "
                     f"commas, got '{text}'")
        sys.exit(1)
    if len(parts) != 3:
        logger.error(f"--{what} needs 3 comma-separated numbers, got {len(parts)}")
        sys.exit(1)
    return parts


def _resolve_vtu(args, cfg, logger):
    """Return a .vtu path: explicit --vtu / config, or convert the case's PLT."""
    vtu = args.vtu or cfg["input"].get("vtu")
    if vtu:
        return vtu
    if not args.case:
        logger.error("need a .vtu (set input.vtu / --vtu) or a <case> [+ --timestep]")
        sys.exit(1)
    case_dir = Path(args.case)
    binary_dir = case_dir / "binary"
    if not binary_dir.exists():
        logger.error(f"Binary directory not found: {binary_dir}"); sys.exit(1)
    plt_path = find_plt(binary_dir, problem_name(case_dir), getattr(args, "timestep", None))
    if not plt_path:
        logger.error(f"No PLT file found in {binary_dir}"); sys.exit(1)

    zone = _resolve_zone(plt_path, getattr(args, "zone", None), logger)
    # The sidecar name carries the zone, because a zone-specific conversion is
    # not interchangeable with the default one and must not poison its cache.
    suffix = ".vtu" if zone is None else f".z{zone}.vtu"
    sidecar = Path(str(plt_path)[:-4] + suffix)
    if sidecar.exists() and sidecar.stat().st_mtime >= plt_path.stat().st_mtime:
        logger.info(f"using cached {sidecar.name}")
        return str(sidecar)
    logger.info(f"converting {plt_path.name} -> {sidecar.name}")
    out, info = to_vtu(str(plt_path), str(sidecar), zone=zone,
                       nen=getattr(args, "nen", None))
    if info.get("truncated"):
        logger.warning(f"connectivity incomplete: {info['nhex_valid']:,}/{info['nelem']:,} cells")
    return out


def _resolve_zone(plt_path, zone_name, logger):
    """A --zone name -> its index in the PLT, or None for the first volume zone."""
    if not zone_name:
        return None
    from ....plt.fxplt import PltFile

    plt = PltFile(str(plt_path))
    idx = zone_index(plt, zone_name)
    if idx is None:
        names = ", ".join(z["name"] for z in plt.zones)
        logger.error(f"Zone '{zone_name}' not found in {Path(plt_path).name}. "
                     f"Available: {names}")
        sys.exit(1)
    return idx


def _apply_overrides(args, cfg, mode):
    """Map the CLI flags onto the config for the mode in play."""
    if getattr(args, "color", None):
        cfg["color"]["variable"] = args.color

    if mode == "iso":
        if getattr(args, "contour", None):
            cfg["contour"]["variable"] = args.contour
        if getattr(args, "values", None):
            cfg["contour"]["isosurfaces"] = args.values
    else:
        if getattr(args, "normal", None):
            cfg["slice"]["normal"] = args.normal
        if getattr(args, "origin", None):
            cfg["slice"]["origin"] = args.origin
        if getattr(args, "slices", None):
            cfg["slice"]["count"] = args.slices


def _aim_camera_at_the_plane(args, cfg, user_cfg):
    """Point the default slice view down the requested normal.

    Only when the user gave no views: of their own -- an explicit views: block
    always wins, since they have said what they want to look at.
    """
    if "views" in (user_cfg or {}):
        return
    direction = render.view_direction_for(cfg["slice"]["normal"])
    if direction:
        for view in cfg["views"]:
            view["direction"] = direction


def execute_render(args):
    from .help_messages import (print_render_help, print_iso_help,
                                print_slice_help)

    mode_help = {"iso": print_iso_help, "slice": print_slice_help}
    mode = getattr(args, "mode", None)

    if getattr(args, "help", False):
        mode_help.get(mode, print_render_help)()
        return

    logger = Logger(verbose=getattr(args, "verbose", False))

    if not mode:
        print_render_help()
        sys.exit(0)
    if mode not in MODES:
        # Both positionals are optional, so a forgotten mode word binds the case
        # to `mode`. Say that in the error itself -- logger.info is silent
        # without --verbose, which is exactly when the hint is needed.
        hint = ""
        if Path(mode).is_dir():
            hint = (f"\n        '{mode}' looks like a case -- did you mean "
                    f"`field render iso {mode}`?")
        logger.error(f"Unknown render mode '{mode}'. "
                     f"Available: {', '.join(MODES)}{hint}")
        sys.exit(1)

    _check_mode_flags(args, mode, logger)

    if getattr(args, "write_template", None):
        with open(args.write_template, "w") as f:
            f.write(TEMPLATES[mode])
        logger.success(f"wrote {mode} config template -> {args.write_template}")
        return

    args.normal = _parse_vector(getattr(args, "normal", None), "normal", logger)
    args.origin = _parse_vector(getattr(args, "origin", None), "origin", logger)

    user_cfg = {}
    cfg = render.default_config(mode)
    if getattr(args, "config", None):
        import yaml
        user_cfg = yaml.safe_load(open(args.config)) or {}
        cfg = render.deep_merge(cfg, user_cfg)
    other = "slice" if mode == "iso" else "contour"
    if other in user_cfg:
        logger.warning(f"config has a '{other}:' section, which `field render "
                       f"{mode}` does not read -- it is ignored")

    _apply_overrides(args, cfg, mode)
    if mode == "slice":
        _aim_camera_at_the_plane(args, cfg, user_cfg)

    kind, value = _resolve_output(args, mode, logger)
    if kind == "prefix" and value:
        cfg["output"]["prefix"] = value
    elif kind == "image":
        cfg["output"]["image_path"] = value
        cfg["output"]["prefix"] = os.path.splitext(value)[0]
        cfg["output"]["save_vtp"] = False
    elif kind == "geometry":
        cfg["output"]["geometry"] = value
        cfg["output"]["images"] = False

    cfg["input"]["vtu"] = _resolve_vtu(args, cfg, logger)
    if kind == "prefix" and not value and cfg["output"]["prefix"] == mode:
        cfg["output"]["prefix"] = os.path.splitext(cfg["input"]["vtu"])[0] + f"_{mode}"

    renderer = render.render_iso if mode == "iso" else render.render_slice
    try:
        outs = renderer(cfg, log=logger.info)
    except ImportError:
        logger.error(f"pyvista is required for `field render {mode}`. "
                     f"Install with: pip install pyvista")
        sys.exit(1)
    except Exception as e:
        logger.error(f"rendering failed: {e}"); sys.exit(1)

    if not outs:
        logger.warning(f"nothing written (empty {mode}?)")
    elif cfg["output"].get("images", True):
        logger.success(f"wrote {len(outs)} image(s): "
                       f"{', '.join(os.path.basename(o) for o in outs)}")
    else:
        logger.success(f"wrote {os.path.basename(outs[0])}")
