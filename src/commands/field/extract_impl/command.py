"""
Field extract command implementation (Tecplot-free, uses src/plt/fxplt).

Extracts nodal variables (optionally within an x/y/z box) for one timestep, or
for a range of timesteps consolidated into a single output (with a `timestep`
column/array). Output format is chosen by the output-file extension:
CSV, or a point cloud .vtu/.vtk/.vtp.
"""

import sys
from pathlib import Path

import numpy as np

from ....utils.logger import Logger
from ....plt.fxplt import PltFile
from ..locate import problem_name, find_plt, zone_index, list_steps


def _resolve_steps(args, binary_dir, problem):
    """Decide which timesteps to extract. Returns (steps, mode) or (None, None)."""
    if getattr(args, "timestep", None) is not None:
        return [args.timestep], "single"
    t1, t2 = getattr(args, "t1", None), getattr(args, "t2", None)
    if t1 is not None and t2 is not None:
        lo, hi = sorted((t1, t2))
        freq = getattr(args, "freq", None)
        sel = [s for s in list_steps(binary_dir, problem) if lo <= s <= hi]
        if freq and freq > 0:
            sel = [s for s in sel if s % freq == 0]
        return sel, "range"
    if t1 is not None:
        return [int(t1)], "single"
    if t2 is not None:
        return [int(t2)], "single"
    return None, None


def execute_extract(args):
    from .help_messages import print_extract_help

    if getattr(args, "help", False):
        print_extract_help(); return

    logger = Logger(verbose=getattr(args, "verbose", False))
    if not args.case:
        print_extract_help(); sys.exit(1)
    for req in ("variables", "zone"):
        if not getattr(args, req, None):
            logger.error(f"--{req} flag is required"); print(); print_extract_help(); sys.exit(1)
    if not getattr(args, "output_file", None):
        logger.error("--output is required (e.g. --output results.csv or results.vtu)")
        print(); print_extract_help(); sys.exit(1)

    case_dir = Path(args.case)
    binary_dir = case_dir / "binary"
    if not binary_dir.exists():
        logger.error(f"Binary directory not found: {binary_dir}"); sys.exit(1)
    problem = problem_name(case_dir)

    steps, mode = _resolve_steps(args, binary_dir, problem)
    if steps is None:
        logger.error("No timestep given. Pass --timestep N, or --t1/--t2, "
                     "or set the t1/t2 context (use t1:.. t2:..).")
        sys.exit(1)
    if not steps:
        logger.error(f"No PLT files in step range [{args.t1}, {args.t2}] in {binary_dir}")
        sys.exit(1)

    # subdomain bounds (applied to node coordinates each step)
    bounds = [("xmin", 0, "ge"), ("xmax", 0, "le"), ("ymin", 1, "ge"),
              ("ymax", 1, "le"), ("zmin", 2, "ge"), ("zmax", 2, "le")]
    applied = {n: getattr(args, n) for n, _, _ in bounds if getattr(args, n, None) is not None}

    requested = [v.strip() for v in args.variables.split(",")]
    cols = None          # resolved against the first file's variable names
    coord_names = None
    acc_pts, acc_ts = [], []
    acc_cols = None

    for ts in steps:
        plt_path = find_plt(binary_dir, problem, ts)
        if not plt_path:
            logger.warning(f"no PLT for timestep {ts}; skipping"); continue
        plt = PltFile(plt_path)
        zi = zone_index(plt, args.zone)
        if zi is None:
            logger.error(f"Zone '{args.zone}' not found in {plt_path.name}. Available: "
                         f"{', '.join(z['name'] for z in plt.zones)}")
            sys.exit(1)
        pts, conn, pdata, info = plt.load_zone(zi)
        if not pdata:
            logger.error(f"Zone '{args.zone}' carries no own data (variables are shared). "
                         f"Use the volume zone (e.g. {plt.zones[plt.first_volume_zone()]['name']}).")
            sys.exit(1)
        if info.get("truncated"):
            logger.warning(f"step {ts}: PLT connectivity incomplete; nodal data still complete.")

        columns = {plt.vars[0]: pts[:, 0], plt.vars[1]: pts[:, 1], plt.vars[2]: pts[:, 2]}
        columns.update(pdata)

        if cols is None:          # resolve requested names once (case-insensitive)
            coord_names = set(plt.vars[:3])
            lower = {k.lower(): k for k in columns}
            cols = []
            for v in requested:
                key = v if v in columns else lower.get(v.lower())
                if key is None:
                    logger.error(f"Variable '{v}' not in file. Available: {', '.join(columns)}")
                    sys.exit(1)
                cols.append(key)
            acc_cols = {c: [] for c in cols}

        mask = np.ones(len(pts), dtype=bool)
        for name, axis, op in bounds:
            v = getattr(args, name, None)
            if v is None:
                continue
            mask &= (pts[:, axis] >= v) if op == "ge" else (pts[:, axis] <= v)

        acc_pts.append(pts[mask])
        acc_ts.append(np.full(int(mask.sum()), ts, dtype=np.int64))
        for c in cols:
            acc_cols[c].append(columns[c][mask])

    if not acc_pts:
        logger.error("Nothing extracted (no matching PLT files)."); sys.exit(1)

    multi = len({int(t[0]) for t in acc_ts if len(t)}) > 1 or mode == "range"
    P = np.concatenate(acc_pts)
    ts_all = np.concatenate(acc_ts)
    col_arrays = {c: np.concatenate(acc_cols[c]) for c in cols}
    span = (f"steps {steps[0]}..{steps[-1]}" if mode == "range" else f"timestep {steps[0]}")
    logger.info(f"Extracting {', '.join(cols)} from zone '{args.zone}' ({span})")
    if applied:
        logger.info(f"Subdomain filter {applied}: {len(P):,} nodes kept")

    out_path = Path(args.output_file)
    ext = out_path.suffix.lower()
    if ext in (".vtu", ".vtk", ".vtp"):
        from ....plt.convert import write_point_cloud
        cloud_data = {c: col_arrays[c] for c in cols if c not in coord_names}
        if multi:
            cloud_data = {"timestep": ts_all, **cloud_data}
        try:
            write_point_cloud(out_path, P, cloud_data)
        except Exception as e:
            logger.error(str(e)); sys.exit(1)
        logger.success(f"Wrote {len(P):,} points x {len(cloud_data)} array(s) -> {out_path}")
    else:
        header = (["timestep"] if multi else []) + cols
        data_cols = ([ts_all] if multi else []) + [col_arrays[c] for c in cols]
        fmt = (["%d"] if multi else []) + ["%.8e"] * len(cols)
        np.savetxt(out_path, np.column_stack(data_cols), delimiter=",",
                   header=",".join(header), comments="", fmt=fmt)
        logger.success(f"Wrote {len(P):,} rows x {len(header)} cols -> {out_path}")
