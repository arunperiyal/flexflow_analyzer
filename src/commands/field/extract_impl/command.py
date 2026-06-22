"""
Field extract command implementation (Tecplot-free, uses src/plt/fxplt).
"""

import sys
from pathlib import Path

import numpy as np

from ....utils.logger import Logger
from ....plt.fxplt import PltFile


def _find_plt(binary_dir, problem, timestep):
    """Locate the PLT file for a timestep, e.g. <problem>.<step>.plt."""
    if problem:
        cand = binary_dir / f"{problem}.{timestep}.plt"
        if cand.exists():
            return cand
    matches = sorted(binary_dir.glob(f"*.{timestep}.plt"))
    return matches[0] if matches else None


def _zone_index(plt, zone_name):
    """Resolve a zone name (case-insensitive) to its index."""
    names = [z["name"] for z in plt.zones]
    for i, n in enumerate(names):
        if n.lower() == zone_name.lower():
            return i
    return None


def execute_extract(args):
    """Extract variables (optionally within an x/y/z box) to CSV."""
    from .help_messages import print_extract_help

    if getattr(args, "help", False):
        print_extract_help()
        return

    logger = Logger(verbose=getattr(args, "verbose", False))

    if not args.case:
        print_extract_help(); sys.exit(1)
    for req in ("variables", "zone", "timestep"):
        if not getattr(args, req, None):
            logger.error(f"--{req} flag is required"); print(); print_extract_help(); sys.exit(1)

    case_dir = Path(args.case)
    binary_dir = case_dir / "binary"
    if not binary_dir.exists():
        logger.error(f"Binary directory not found: {binary_dir}"); sys.exit(1)

    # problem name (best effort) for file naming
    try:
        from ....core.simflow_config import SimflowConfig
        problem = SimflowConfig.find(case_dir).problem
    except Exception:
        problem = None

    plt_path = _find_plt(binary_dir, problem, args.timestep)
    if not plt_path:
        logger.error(f"No PLT file for timestep {args.timestep} in {binary_dir}"); sys.exit(1)

    plt = PltFile(plt_path)
    zi = _zone_index(plt, args.zone)
    if zi is None:
        logger.error(f"Zone '{args.zone}' not found. Available: "
                     f"{', '.join(z['name'] for z in plt.zones)}")
        sys.exit(1)

    pts, conn, pdata, info = plt.load_zone(zi)
    if not pdata:
        logger.error(f"Zone '{args.zone}' carries no own data (its variables are shared). "
                     f"Extract from the volume zone instead "
                     f"(e.g. {plt.zones[plt.first_volume_zone()]['name']}).")
        sys.exit(1)
    if info.get("truncated"):
        logger.warning(f"PLT connectivity looks incomplete ({info['nhex_valid']}/{info['nelem']} "
                       "cells); nodal data is still complete for extraction.")

    # full column set: X,Y,Z + nodal variables
    columns = {plt.vars[0]: pts[:, 0], plt.vars[1]: pts[:, 1], plt.vars[2]: pts[:, 2]}
    columns.update(pdata)
    lower = {k.lower(): k for k in columns}

    requested = [v.strip() for v in args.variables.split(",")]
    cols = []
    for v in requested:
        key = v if v in columns else lower.get(v.lower())
        if key is None:
            logger.error(f"Variable '{v}' not in file. Available: {', '.join(columns)}")
            sys.exit(1)
        cols.append(key)
    logger.info(f"Extracting {', '.join(cols)} from zone '{plt.zones[zi]['name']}' "
                f"(timestep {args.timestep})")

    # subdomain mask on node coordinates
    mask = np.ones(len(pts), dtype=bool)
    bounds = {"xmin": (0, "ge"), "xmax": (0, "le"), "ymin": (1, "ge"),
              "ymax": (1, "le"), "zmin": (2, "ge"), "zmax": (2, "le")}
    applied = {}
    for name, (axis, op) in bounds.items():
        val = getattr(args, name, None)
        if val is None:
            continue
        mask &= (pts[:, axis] >= val) if op == "ge" else (pts[:, axis] <= val)
        applied[name] = val
    if applied:
        logger.info(f"Subdomain filter {applied}: {int(mask.sum())} of {len(pts)} nodes")

    out_path = Path(args.output_file) if args.output_file else case_dir / f"extracted_{args.timestep}.csv"
    ext = out_path.suffix.lower()
    if ext in (".vtu", ".vtk", ".vtp"):
        # point cloud: XYZ is the geometry, requested non-coordinate vars are arrays
        from ....plt.convert import write_point_cloud
        coord = set(plt.vars[:3])
        P = pts[mask]
        cloud_data = {c: columns[c][mask] for c in cols if c not in coord}
        try:
            write_point_cloud(out_path, P, cloud_data)
        except Exception as e:
            logger.error(str(e)); sys.exit(1)
        logger.success(f"Wrote {len(P):,} points x {len(cloud_data)} array(s) -> {out_path}")
    else:
        data = np.column_stack([columns[c][mask] for c in cols])
        np.savetxt(out_path, data, delimiter=",", header=",".join(cols), comments="", fmt="%.8e")
        logger.success(f"Wrote {data.shape[0]:,} rows x {len(cols)} cols -> {out_path}")
