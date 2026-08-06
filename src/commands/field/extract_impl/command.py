"""
Field extract command implementation (Tecplot-free, uses src/plt/fxplt).

Extracts SELECTED variables (optionally within an x/y/z box) for one timestep
or a range of timesteps. Output format is chosen by the output extension:

  .csv              tabular point values (range -> one file with a `timestep` column)
  .vtu / .vtk       a trimmed *mesh* (cells kept) carrying only the selected
                    variables -- contourable in ParaView (single timestep)
  .pvd              a time series: one trimmed-mesh <stem>_<step>.vtu per step
                    plus the <stem>.pvd collection (range)

With --probe X,Y,Z the box is replaced by point sampling: the variables are read
at the mesh node nearest each probe, giving a time signal in CSV (or on screen).
"""

import os
import sys
from pathlib import Path

import numpy as np

from ....utils.logger import Logger
from ....utils.progress import progress_enabled, spinner, step_bar
from ....plt.fxplt import PltFile
from ....plt.convert import cell_name, crop_mesh, has_domain
from ..locate import problem_name, find_plt, zone_index, list_steps
from . import probe as probe_util


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


def _domain(args):
    return {k: getattr(args, k, None) for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")}


def _resolve_output(args, steps, mode, logger, probing=False):
    """Resolve --output to (file_path, ext).

    Relative paths are placed under the case directory (cwd if no case). A name
    WITH a known extension (.csv/.vtu/.vtk/.pvd) is a single file; a name with NO
    extension becomes a directory holding the outputs, named after the directory
    (e.g. `--output wake` -> <case>/wake/wake.pvd + wake/wake_<step>.vtu).
    Probe output is a table of point values, so only .csv is allowed there.
    """
    base = Path(args.case) if args.case else Path.cwd()
    raw = Path(args.output_file)
    target = raw if raw.is_absolute() else base / raw
    ext = target.suffix.lower()

    if ext == "":
        if probing:
            chosen = ".csv"
        else:
            chosen = ".pvd" if (mode == "range" and len(steps) > 1) else ".vtu"
        target.mkdir(parents=True, exist_ok=True)
        logger.info(f"output directory: {target}")
        return target / (target.name + chosen), chosen
    if probing and ext != ".csv":
        logger.error(f"--probe writes point values, so '{ext}' is not supported. "
                     "Use a .csv output (or drop --output to print a table).")
        sys.exit(1)
    if ext in (".csv", ".vtu", ".vtk", ".pvd"):
        target.parent.mkdir(parents=True, exist_ok=True)
        return target, ext
    logger.error(f"Unsupported output extension '{ext}'. "
                 "Use .csv / .vtu / .vtk / .pvd, or a bare name for a folder.")
    sys.exit(1)


def _resolve_cols(plt, columns, requested, logger, zone=None):
    """Map requested variable names (case-insensitive) to file keys, or exit.

    `columns` holds only what this zone actually carries, so a variable that
    exists in the file but is shared/passive here is reported as unavailable for
    the zone rather than missing from the file.
    """
    lower = {k.lower(): k for k in columns}
    cols = []
    for v in requested:
        key = v if v in columns else lower.get(v.lower())
        if key is None:
            where = f"zone '{zone}'" if zone else "file"
            logger.error(f"Variable '{v}' is not available in {where}. "
                         f"Available: {', '.join(columns)}")
            if v.lower() in {n.lower() for n in plt.vars}:
                logger.error(f"  ('{v}' exists in the file but carries no data in this "
                             "zone -- try the volume zone.)")
            sys.exit(1)
        cols.append(key)
    return cols


def _zone_or_exit(plt, zone, plt_path, logger):
    """Resolve a zone name to its index, or exit listing what the file holds."""
    zi = zone_index(plt, zone)
    if zi is None:
        logger.error(f"Zone '{zone}' not found in {Path(plt_path).name}. Available: "
                     f"{', '.join(z['name'] for z in plt.zones)}")
        sys.exit(1)
    return zi


def _load_step(plt_path, zone, logger, want_conn):
    """Load a zone; return (plt, zi, pts, conn, pdata). Exits on bad zone/shared data."""
    plt = PltFile(plt_path)
    zi = _zone_or_exit(plt, zone, plt_path, logger)
    pts, conn, pdata, info = plt.load_zone(zi)
    if not pdata:
        logger.error(f"Zone '{zone}' carries no own data (variables are shared). "
                     f"Use the volume zone (e.g. {plt.zones[plt.first_volume_zone()]['name']}).")
        sys.exit(1)
    if want_conn and conn is None:
        logger.error(f"Zone '{zone}' has no connectivity; mesh output needs a volume zone.")
        sys.exit(1)
    if info.get("truncated"):
        logger.warning(f"{Path(plt_path).name}: PLT connectivity incomplete; data still complete.")
    return plt, zi, pts, conn, pdata, info


def _node_mask(pts, domain):
    mask = np.ones(len(pts), dtype=bool)
    for name, axis, op in (("xmin", 0, "ge"), ("xmax", 0, "le"), ("ymin", 1, "ge"),
                           ("ymax", 1, "le"), ("zmin", 2, "ge"), ("zmax", 2, "le")):
        v = domain.get(name)
        if v is not None:
            mask &= (pts[:, axis] >= v) if op == "ge" else (pts[:, axis] <= v)
    return mask


def _write_mesh(plt_path, zone, requested, domain, out_vtu, logger):
    """Write one trimmed mesh (cells + selected non-coordinate vars) to out_vtu."""
    import meshio
    plt, zi, pts, conn, pdata, info = _load_step(plt_path, zone, logger, want_conn=True)
    columns = {plt.vars[0]: pts[:, 0], plt.vars[1]: pts[:, 1], plt.vars[2]: pts[:, 2]}
    columns.update(pdata)
    cols = _resolve_cols(plt, columns, requested, logger, zone)
    coord = set(plt.vars[:3])
    data = {c: columns[c] for c in cols if c not in coord}      # selected vars only
    if has_domain(domain):
        pts, conn, data = crop_mesh(pts, conn, data, domain)
    cname = cell_name(info["npe"], info["ztype"])
    meshio.Mesh(points=pts, cells=[(cname, conn)], point_data=data).write(out_vtu, binary=True)
    return len(pts), len(conn), list(data.keys())


def _write_pvd(path, entries):
    """Write a ParaView .pvd collection: entries = [(timestep, filename), ...]."""
    lines = ['<?xml version="1.0"?>',
             '<VTKFile type="Collection" version="0.1" byte_order="LittleEndian">',
             '  <Collection>']
    for ts, fn in entries:
        lines.append(f'    <DataSet timestep="{ts}" group="" part="0" file="{fn}"/>')
    lines += ['  </Collection>', '</VTKFile>']
    Path(path).write_text("\n".join(lines) + "\n")


def _feedback(args, steps):
    """(bar, spinner) switches -- rich allows only one live display at a time."""
    on = progress_enabled(args, len(steps))
    return on and len(steps) > 1, on and len(steps) == 1


def _extract_csv(steps, mode, binary_dir, problem, args, requested, out_path, logger):
    domain = _domain(args)
    applied = {k: v for k, v in domain.items() if v is not None}
    cols = coord_names = None
    acc_pts, acc_ts = [], []
    acc_cols = None
    bar_on, spin_on = _feedback(args, steps)
    with step_bar(len(steps), "Extracting", enabled=bar_on) as bar:
        for ts in steps:
            bar.step(f"step {ts}")
            plt_path = find_plt(binary_dir, problem, ts)
            if not plt_path:
                logger.warning(f"no PLT for timestep {ts}; skipping"); bar.advance(); continue
            with spinner(f"Reading {Path(plt_path).name}", enabled=spin_on):
                plt, zi, pts, conn, pdata, info = _load_step(plt_path, args.zone, logger,
                                                             want_conn=False)
            columns = {plt.vars[0]: pts[:, 0], plt.vars[1]: pts[:, 1], plt.vars[2]: pts[:, 2]}
            columns.update(pdata)
            if cols is None:
                coord_names = set(plt.vars[:3])
                cols = _resolve_cols(plt, columns, requested, logger, args.zone)
                acc_cols = {c: [] for c in cols}
            mask = _node_mask(pts, domain)
            acc_pts.append(pts[mask])
            acc_ts.append(np.full(int(mask.sum()), ts, dtype=np.int64))
            for c in cols:
                acc_cols[c].append(columns[c][mask])
            bar.advance()
    if not acc_pts:
        logger.error("Nothing extracted (no matching PLT files)."); sys.exit(1)

    multi = mode == "range"
    ts_all = np.concatenate(acc_ts)
    col_arrays = {c: np.concatenate(acc_cols[c]) for c in cols}
    if applied:
        logger.info(f"Subdomain filter {applied}: {len(ts_all):,} nodes kept")
    header = (["timestep"] if multi else []) + cols
    data_cols = ([ts_all] if multi else []) + [col_arrays[c] for c in cols]
    fmt = (["%d"] if multi else []) + ["%.8e"] * len(cols)
    np.savetxt(out_path, np.column_stack(data_cols), delimiter=",",
               header=",".join(header), comments="", fmt=fmt)
    logger.success(f"Wrote {len(ts_all):,} rows x {len(header)} cols -> {out_path}")


def _probe_precheck(binary_dir, problem, steps, zone, points, axes, tol, logger):
    """Reject probes outside the zone before reading any bulk data.

    Uses the PLT header's per-variable min/max (no data load). Returns the bounds
    when they were available, else None -- the caller then checks against the
    first loaded step instead.
    """
    plt_path = next((p for p in (find_plt(binary_dir, problem, ts) for ts in steps) if p), None)
    if not plt_path:
        logger.error("Nothing to probe (no matching PLT files)."); sys.exit(1)
    plt = PltFile(plt_path)
    bounds = probe_util.header_bounds(plt, _zone_or_exit(plt, zone, plt_path, logger))
    if bounds is None:
        return None
    probe_util.check_inside(points, axes, bounds[0], bounds[1], zone, logger, tol=tol)
    logger.info(f"Domain bounds: {probe_util.format_bounds(*bounds)}")
    return bounds


def _extract_probe(steps, mode, binary_dir, problem, args, requested, out_path, logger):
    """Sample the requested variables at fixed points, one row per probe per step."""
    points, axes = probe_util.parse_probes(args.probe, logger)
    if has_domain(_domain(args)):
        logger.warning("--xmin/--xmax/... are ignored with --probe (probes sample points)")

    tol = getattr(args, "probe_tol", None) or 0.0
    bounds = _probe_precheck(binary_dir, problem, steps, args.zone, points, axes, tol, logger)
    multi = mode == "range"
    cols, rows, warned = None, [], set()
    bar_on, spin_on = _feedback(args, steps)
    with step_bar(len(steps), "Probing", enabled=bar_on) as bar:
        for ts in steps:
            bar.step(f"step {ts}")
            plt_path = find_plt(binary_dir, problem, ts)
            if not plt_path:
                logger.warning(f"no PLT for timestep {ts}; skipping"); bar.advance(); continue
            with spinner(f"Reading {Path(plt_path).name}", enabled=spin_on):
                plt, zi, pts, conn, pdata, info = _load_step(plt_path, args.zone, logger,
                                                             want_conn=False)
            columns = {plt.vars[0]: pts[:, 0], plt.vars[1]: pts[:, 1], plt.vars[2]: pts[:, 2]}
            columns.update(pdata)
            if cols is None:
                cols = _resolve_cols(plt, columns, requested, logger, args.zone)
            if bounds is None:                      # header carried no coordinate range
                bounds = probe_util.point_bounds(pts)
                probe_util.check_inside(points, axes, bounds[0], bounds[1], args.zone,
                                        logger, tol=tol)
                logger.info(f"Domain bounds: {probe_util.format_bounds(*bounds)}")
            for pi, (point, ax) in enumerate(zip(points, axes), start=1):
                idx, dist = probe_util.nearest_node(pts, point, ax)
                far = probe_util.far_probe_warning(dist, bounds[0], bounds[1], len(pts))
                if far and pi not in warned:
                    logger.warning(f"Probe P{pi} {probe_util.label(point, ax)}: {far}")
                    warned.add(pi)
                node = pts[idx]
                rows.append(([ts] if multi else [])
                            + [f"P{pi}", point[0], point[1], point[2],
                               int(idx), float(node[0]), float(node[1]), float(node[2]), dist]
                            + [float(columns[c][idx]) for c in cols])
            bar.advance()
    if not rows:
        logger.error("Nothing probed (no matching PLT files)."); sys.exit(1)

    header = probe_util.build_header(cols, multi)
    if out_path is None or len(rows) <= probe_util.TABLE_ROWS:
        probe_util.print_table(header, rows, truncate=out_path is None)
    if out_path:
        probe_util.write_csv(out_path, header, rows)
        print(f"Wrote {len(rows):,} probe row(s) x {len(header)} cols -> {out_path}")


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
    probing = bool(getattr(args, "probe", None))
    wants_file = bool(getattr(args, "output_file", None))
    # Probes print a table when no file is asked for; every other mode needs a target.
    if not wants_file and not probing:
        logger.error("--output is required (e.g. --output results.csv / .vtu / .pvd)")
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

    requested = [v.strip() for v in args.variables.split(",")]
    out_path, ext = (_resolve_output(args, steps, mode, logger, probing) if wants_file
                     else (None, ".csv"))
    domain = _domain(args)

    if probing:
        _extract_probe(steps, mode, binary_dir, problem, args, requested, out_path, logger)
        return

    if ext == ".csv":
        _extract_csv(steps, mode, binary_dir, problem, args, requested, out_path, logger)
        return

    if ext in (".vtu", ".vtk"):
        if mode == "range" and len(steps) > 1:
            logger.error(f"A range ({len(steps)} steps) can't go to one {ext}. "
                         "Use .pvd (time series) or .csv.")
            sys.exit(1)
        plt_path = find_plt(binary_dir, problem, steps[0])
        if not plt_path:
            logger.error(f"No PLT for timestep {steps[0]}"); sys.exit(1)
        _, spin_on = _feedback(args, steps)
        with spinner(f"Extracting {Path(plt_path).name}", enabled=spin_on):
            n, c, arrs = _write_mesh(plt_path, args.zone, requested, domain, str(out_path), logger)
        logger.success(f"Wrote mesh {n:,} pts / {c:,} cells, vars {arrs} -> {out_path}")
        return

    if ext == ".pvd":
        stem = out_path.with_suffix("")
        entries = []
        bar_on, spin_on = _feedback(args, steps)
        with step_bar(len(steps), "Writing meshes", enabled=bar_on) as bar:
            for ts in steps:
                bar.step(f"step {ts}")
                plt_path = find_plt(binary_dir, problem, ts)
                if not plt_path:
                    logger.warning(f"no PLT for timestep {ts}; skipping"); bar.advance(); continue
                vtu = f"{stem}_{ts}.vtu"
                with spinner(f"Extracting {Path(plt_path).name}", enabled=spin_on):
                    n, c, arrs = _write_mesh(plt_path, args.zone, requested, domain, vtu, logger)
                logger.info(f"  step {ts}: {n:,} pts / {c:,} cells -> {os.path.basename(vtu)}")
                entries.append((ts, os.path.basename(vtu)))
                bar.advance()
        if not entries:
            logger.error("Nothing written (no matching PLT files)."); sys.exit(1)
        _write_pvd(out_path, entries)
        logger.success(f"Wrote time series: {len(entries)} mesh file(s) + {out_path}")
        return
