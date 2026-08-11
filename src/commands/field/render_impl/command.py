"""
Field render command -- pictures from PLT field data via pyvista (Tecplot-free).

Two modes, differing only in the surface they cut out of the volume:
    iso     an isosurface of a scalar (Q-criterion for vortex tubes, say)
    slice   a cut plane, or a series of them along a normal

Everything else -- the PLT->VTU conversion and its cache, the domain crop, the
threshold, the colour map, the cameras, the screenshots -- is shared, which is
why they are one subcommand with a mode rather than two subcommands.
"""

import copy
import os
import sys
from pathlib import Path

from ....utils.logger import Logger
from ....plt import render
from ....plt.convert import to_vtu
from ..locate import problem_name, find_plt, zone_index, resolve_steps
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
    """Resolve --output to (directory, ext).

    A run always writes into a directory of its own: even one timestep produces
    a file per camera view, and a range multiplies that by the number of steps.
    Loose files named after the .vtu would land in the case's binary/ among the
    PLTs, which is the last place to keep pictures.

    --output names that directory; its extension, if any, picks the format for
    what goes inside. Without --output the directory is render_<mode>.
    """
    raw = getattr(args, "output", None)
    if not raw:
        return f"render_{mode}", None
    ext = os.path.splitext(raw)[1].lower()
    if ext == "":
        return raw, None
    if ext == ".png" or ext in GEOMETRY_EXT:
        return os.path.splitext(raw)[0], ext
    logger.error(f"Unsupported --output extension '{ext}'. Use a bare NAME for a "
                 f"directory of images, or NAME with .png / "
                 f"{' / '.join(GEOMETRY_EXT)} to pick what goes in it.")
    sys.exit(1)


def _output_dir(args, name):
    """Where the run's directory sits: under the case, or beside the .vtu."""
    raw = Path(name)
    if raw.is_absolute():
        target = raw
    elif getattr(args, "case", None):
        target = Path(args.case) / raw
    else:
        # --vtu with no case: keep the directory next to the file it came from.
        target = Path(args.vtu).parent / raw
    target.mkdir(parents=True, exist_ok=True)
    return target


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


def _check_range(pair, logger):
    """argparse has given us two floats; only the ordering is left to check."""
    if pair is None:
        return None
    lo, hi = pair
    if lo >= hi:
        logger.error(f"--color-range needs MIN below MAX, got {lo} and {hi}")
        sys.exit(1)
    return [lo, hi]


def _resolve_steps(args, mode, logger):
    """Which timesteps to render. Returns (steps, binary_dir, problem).

    steps is [None] when the input is a .vtu rather than a case -- there is one
    thing to render and no step number attached to it.
    """
    if args.vtu:
        return [None], None, None
    if not args.case:
        # Nothing to render and nothing said about what to render: this is
        # someone finding their way, so show the mode's help rather than a
        # one-line complaint. (The same call `field extract` makes.)
        from .help_messages import print_iso_help, print_slice_help
        logger.error("nothing to render: give a <case> [--timestep N or "
                     "--t1 A --t2 B], or --vtu PATH, or set input.vtu in a "
                     "--config file")
        print()
        {"iso": print_iso_help, "slice": print_slice_help}[mode]()
        sys.exit(1)

    case_dir = Path(args.case)
    binary_dir = case_dir / "binary"
    if not binary_dir.exists():
        logger.error(f"Binary directory not found: {binary_dir}"); sys.exit(1)
    problem = problem_name(case_dir)

    steps, how = resolve_steps(args, binary_dir, problem)
    if steps is None:
        return [None], binary_dir, problem       # nothing asked: latest step
    if not steps:
        logger.error(f"No PLT files in the range given "
                     f"({args.t1} .. {args.t2}) under {binary_dir}")
        sys.exit(1)
    if how == "range" and len(steps) > 1 and not getattr(args, "color_range", None):
        # Auto-scaling is per surface, so every frame of a sweep would be
        # coloured on its own scale and none of them could be compared.
        logger.warning(f"{len(steps)} timesteps on an automatic colour scale: "
                       f"each is scaled to its own data, so the frames are not "
                       f"comparable. Give --color-range MIN MAX to fix it.")
    return steps, binary_dir, problem


def _vtu_for_step(args, cfg, step, binary_dir, problem, logger):
    """The .vtu for one timestep: explicit --vtu / config, or a converted PLT."""
    vtu = args.vtu or cfg["input"].get("vtu")
    if vtu:
        return vtu
    plt_path = find_plt(binary_dir, problem, step)
    if not plt_path:
        where = f"timestep {step}" if step is not None else "any timestep"
        logger.error(f"No PLT file for {where} in {binary_dir}"); sys.exit(1)

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
    if getattr(args, "color_range", None):
        cfg["color"]["range"] = args.color_range

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


def _check_config(cfg, logger):
    """Catch config values that would only fail deep inside the renderer.

    A malformed colour range is the one that bites: `range: [-0.5 0.5]` is
    valid YAML for a *one-element list holding the string* "-0.5 0.5", not two
    numbers, and it surfaces much later as an IndexError out of pyvista with
    nothing pointing back at the file.
    """
    rng = cfg["color"].get("range")
    if rng is None:
        return
    ok = (isinstance(rng, (list, tuple)) and len(rng) == 2
          and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in rng))
    if not ok:
        logger.error(f"color.range must be two numbers, e.g. [-0.5, 0.5] -- got "
                     f"{rng!r}.")
        if isinstance(rng, (list, tuple)) and len(rng) == 1:
            logger.error("        That is what a missing comma looks like: YAML "
                         "reads [-0.5 0.5] as one string, not two numbers.")
        sys.exit(1)
    if rng[0] >= rng[1]:
        logger.error(f"color.range needs MIN below MAX, got {rng[0]} and {rng[1]}")
        sys.exit(1)


def _apply_camera(args, cfg, logger):
    """--camera FILE: render from a saved view instead of the mode's defaults."""
    camera = getattr(args, "camera", None)
    if not camera:
        return
    if not Path(camera).exists():
        logger.error(f"camera file not found: {camera}")
        sys.exit(1)
    # Read it now, not at the first screenshot: a frame that turns out to be
    # unusable should stop the run before it converts a hundred PLT files.
    try:
        from ....plt.camera import load_camera
        load_camera(camera)
    except Exception as e:
        logger.error(f"--camera {camera}: {e}")
        sys.exit(1)
    # One view from the saved frame, replacing the mode's defaults: a chosen
    # camera is the answer to "which view", so the others would be noise --
    # multiplied by every timestep of a sweep.
    cfg["views"] = [{"name": "view", "camera_file": camera}]


def _pick_camera(args, cfg, mode, steps, binary_dir, problem, path, logger):
    """Show one timestep, save the view the user settles on, and stop.

    Choosing a camera is a setup step, not a render: it runs on a single step
    (the first selected) and writes a file, rather than producing pictures.
    """
    step = steps[0]
    cfg = copy.deepcopy(cfg)
    cfg["input"]["vtu"] = _vtu_for_step(args, cfg, step, binary_dir, problem, logger)
    if step is not None:
        logger.info(f"picking a camera on timestep {step}")

    try:
        cfg, surf = render.build_surface(cfg, mode, log=logger.info)
        frame = render.pick_camera(cfg, surf, path, log=logger.info)
    except ImportError:
        logger.error(f"pyvista is required for `field render {mode}`. "
                     f"Install with: pip install pyvista")
        sys.exit(1)
    except Exception as e:
        logger.error(f"could not pick a camera: {e}")
        sys.exit(1)

    where = f" from timestep {step}" if step is not None else ""
    print(f"saved the view{where} -> {path}")
    print(f"  reuse it: field render {mode} "
          f"{args.case or '<case>'} --camera {path}")
    print(f"  position {[round(v, 4) for v in frame['position']]}  "
          f"focal {[round(v, 4) for v in frame['focal']]}")


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
    args.color_range = _check_range(getattr(args, "color_range", None), logger)

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

    pick = getattr(args, "pick_camera", None)
    if getattr(args, "camera", None) and pick:
        logger.error("--camera reads a saved view and --pick-camera writes one; "
                     "give one or the other")
        sys.exit(1)
    _apply_camera(args, cfg, logger)
    _check_config(cfg, logger)

    name, ext = _resolve_output(args, mode, logger)
    steps, binary_dir, problem = _resolve_steps(args, mode, logger)

    if pick:
        _pick_camera(args, cfg, mode, steps, binary_dir, problem, pick, logger)
        return
    out_dir = _output_dir(args, name)
    stem = Path(name).name

    renderer = render.render_iso if mode == "iso" else render.render_slice
    written = []
    total = len(steps)
    for i, step in enumerate(steps, 1):
        if total > 1:
            # A sweep converts and renders one PLT per step and can run for many
            # minutes. Say where it is, or it looks hung and gets interrupted.
            print(f"  [{i}/{total}] timestep {step}", flush=True)
        step_cfg = copy.deepcopy(cfg)
        step_cfg["input"]["vtu"] = _vtu_for_step(args, cfg, step, binary_dir,
                                                 problem, logger)
        base = str(out_dir / (stem if step is None else f"{stem}_{step}"))
        if ext in GEOMETRY_EXT:
            step_cfg["output"]["geometry"] = base + ext
            step_cfg["output"]["images"] = False
        else:
            step_cfg["output"]["prefix"] = base
            if ext == ".png":
                step_cfg["output"]["image_path"] = base + ".png"
                step_cfg["output"]["save_vtp"] = False

        try:
            outs = renderer(step_cfg, log=logger.info)
        except ImportError:
            logger.error(f"pyvista is required for `field render {mode}`. "
                         f"Install with: pip install pyvista")
            sys.exit(1)
        except Exception as e:
            where = f" (timestep {step})" if step is not None else ""
            logger.error(f"rendering failed{where}: {e}")
            sys.exit(1)

        if not outs:
            logger.warning(f"nothing written for "
                           f"{'timestep ' + str(step) if step is not None else 'this input'}"
                           f" (empty {mode}?)")
        written += outs

    if not written:
        logger.warning(f"nothing written (empty {mode}?)")
        sys.exit(1)
    noun = "file" if ext in GEOMETRY_EXT else "image"
    print(f"{len(written)} {noun}{'' if len(written) == 1 else 's'} "
          f"over {len(steps)} timestep{'' if len(steps) == 1 else 's'} "
          f"-> {out_dir}{os.sep}")
