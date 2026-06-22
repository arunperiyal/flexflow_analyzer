"""
Field iso command implementation -- isosurface PNGs via pyvista (Tecplot-free).
"""

import os
import sys
from pathlib import Path

from ....utils.logger import Logger
from ....plt import render
from ....plt.convert import to_vtu
from ..locate import problem_name, find_plt, zone_index


TEMPLATE = """\
# flexflow field iso -- configuration
input:
  vtu: null                      # set, or let `field iso <case> --timestep N` make one

output:
  prefix: iso                    # writes <prefix>.vtp and <prefix>_<view>.png
  save_vtp: true

image:
  resolution: [1600, 1000]
  background: white              # name (white/black/gray) or RGB [r,g,b] in 0-1
  transparent: false

contour:
  variable: QCriterion
  isosurfaces: [20]

color:
  variable: U                    # flow in z -> W ; flow in x -> U
  preset: coolwarm               # matplotlib cmap, or a ParaView preset name
  range: null                    # [min, max] or null = auto
  log_scale: false
  title: null
  show_scalar_bar: true
  text_color: black

domain:                          # crop to a box before contouring; null = no limit
  xmin: null
  xmax: null
  ymin: null
  ymax: null
  zmin: null
  zmax: null

threshold:                       # keep cells with scalar in [min,max]; null disables
  variable: null
  min: null
  max: null

surface:
  opacity: 1.0
  show_edges: false

axes:
  orientation_axes: true

# One PNG per view. Pick ONE camera style: camera_file / direction / position / azimuth.
views:
  - {name: iso, azimuth: 30, elevation: 20, zoom: 1.0}
  - {name: top, direction: "+z", up: [0, 1, 0]}
  # - {name: saved, camera_file: mystate.pvsm}   # reuse a ParaView Save State frame
"""


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
    sidecar = Path(str(plt_path)[:-4] + ".vtu")
    if sidecar.exists() and sidecar.stat().st_mtime >= plt_path.stat().st_mtime:
        logger.info(f"using cached {sidecar.name}")
        return str(sidecar)
    logger.info(f"converting {plt_path.name} -> {sidecar.name}")
    out, info = to_vtu(str(plt_path), str(sidecar), nen=getattr(args, "nen", None))
    if info.get("truncated"):
        logger.warning(f"connectivity incomplete: {info['nhex_valid']:,}/{info['nelem']:,} cells")
    return out


def execute_iso(args):
    from .help_messages import print_iso_help

    if getattr(args, "help", False):
        print_iso_help(); return

    logger = Logger(verbose=getattr(args, "verbose", False))

    if getattr(args, "write_template", None):
        with open(args.write_template, "w") as f:
            f.write(TEMPLATE)
        logger.success(f"wrote config template -> {args.write_template}")
        return

    cfg = render.default_config()
    if getattr(args, "config", None):
        import yaml
        cfg = render.deep_merge(cfg, yaml.safe_load(open(args.config)) or {})

    # CLI overrides
    if getattr(args, "out", None):
        cfg["output"]["prefix"] = args.out
    if getattr(args, "contour", None):
        cfg["contour"]["variable"] = args.contour
    if getattr(args, "iso", None):
        cfg["contour"]["isosurfaces"] = args.iso
    if getattr(args, "color", None):
        cfg["color"]["variable"] = args.color

    cfg["input"]["vtu"] = _resolve_vtu(args, cfg, logger)
    if not getattr(args, "out", None) and cfg["output"]["prefix"] == "iso":
        cfg["output"]["prefix"] = os.path.splitext(cfg["input"]["vtu"])[0] + "_iso"

    try:
        outs = render.render_iso(cfg, log=logger.info)
    except ImportError:
        logger.error("pyvista is required for `field iso`. Install with: pip install pyvista")
        sys.exit(1)
    except Exception as e:
        logger.error(f"rendering failed: {e}"); sys.exit(1)

    if outs:
        logger.success(f"wrote {len(outs)} image(s): {', '.join(os.path.basename(o) for o in outs)}")
    else:
        logger.warning("no images written (empty isosurface?)")
