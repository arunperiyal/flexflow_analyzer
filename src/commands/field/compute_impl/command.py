"""
Field compute command: quantities derived from a surface zone's own elements.

`force` gives the pressure force on every surface element -- its area, its outward
normal and -p n dA -- for each selected timestep. Total force, sectional Cd/Cl and
force distributions are all sums over subsets of those rows, so no reference
length, flow direction or spanwise binning is baked in here.

Areas and normals come from the mesh, not from an assumed shape, so a grooved or
otherwise non-circular section is handled the same as a plain cylinder. Normals
are oriented against the volume zone: a body is a hole in the mesh, so the face's
own cell sits on the fluid side and fixes which way is "out of the body".
"""

import os
import sys
from pathlib import Path

import numpy as np

from ....utils.logger import Logger
from ....utils.progress import progress_enabled, spinner, step_bar
from ....plt.fxplt import PltFile, VOLUME_ZTYPES
from ....plt import surface
from ..locate import problem_name, find_plt, zone_index, resolve_steps

QUANTITIES = ("force",)
SURFACE_ZTYPES = (2, 3)          # FETRIANGLE, FEQUADRILATERAL
COLUMNS = ["element", "x", "y", "z", "area", "nx", "ny", "nz"]
SUMMARY_COLUMNS = ["timestep", "elements", "area", "Fx", "Fy", "Fz"]


def _comment_block(case_dir, args, pressure_var, n_elements, span):
    """The '#' header every table this command writes carries."""
    return [
        "FlexFlow field compute force -- pressure force per surface element",
        f"case: {case_dir.name}   zone: {args.zone}   pressure: {pressure_var}",
        "force: -p n dA, pressure only (no viscous skin friction)",
        "normal: unit, pointing out of the body (oriented by the adjacent volume cell)",
        f"elements: {n_elements:,}   {span}",
    ]


def _surface_zone(plt, name, logger):
    """Resolve --zone to a surface zone index, or exit explaining why it cannot be."""
    zi = zone_index(plt, name)
    if zi is None:
        logger.error(f"Zone '{name}' not found. Available: "
                     f"{', '.join(z['name'] for z in plt.zones)}")
        sys.exit(1)
    ztype = plt.zones[zi]["ztype"]
    if ztype in VOLUME_ZTYPES:
        surf = [z["name"] for z in plt.zones if z["ztype"] in SURFACE_ZTYPES]
        logger.error(f"Zone '{name}' is a volume zone; forces are integrated over a "
                     "surface. " + (f"Try {', '.join(surf)}." if surf
                                    else "This file has no surface zone."))
        sys.exit(1)
    if ztype not in SURFACE_ZTYPES:
        logger.error(f"Zone '{name}' is not made of triangles or quads (zone type {ztype}).")
        sys.exit(1)
    return zi


def _orient(normal, centroid, area, pts, volume_conn, owners, logger, warned):
    """Point normals out of the body, using the adjacent volume cell where possible."""
    found = owners >= 0
    if found.all():
        return surface.orient_outward(normal, centroid, pts[volume_conn[owners]].mean(axis=1))
    if not warned:
        logger.warning(f"{int((~found).sum()):,} of {len(owners):,} surface elements have no "
                       "adjacent volume cell; orienting the zone by its enclosed volume "
                       "instead, which a self-folding surface can defeat.")
    return surface.orient_by_divergence(normal, centroid, area)


INT_COLUMNS = ("timestep", "element", "elements")


def _write_csv(path, header, rows, comments):
    """Write the element table, keeping the identifying columns as plain integers."""
    as_int = [name in INT_COLUMNS for name in header]
    lines = [f"# {c}" for c in comments] + [",".join(header)]
    for row in rows:
        lines.append(",".join(str(int(v)) if is_int else f"{v:.8e}"
                              for v, is_int in zip(row, as_int)))
    Path(path).write_text("\n".join(lines) + "\n")


def _write_mesh(path, pts, conn, cell_data):
    """Write the surface with the per-element values attached as cell data.

    The connectivity indexes the volume zone's node array, so the surface's own
    nodes are pulled out first -- otherwise the file carries every volume point.
    """
    import meshio
    used = np.unique(conn)
    remap = np.full(len(pts), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    name = "quad" if conn.shape[1] == 4 else "triangle"
    meshio.Mesh(points=np.asarray(pts[used], dtype=float), cells=[(name, remap[conn])],
                cell_data={k: [v] for k, v in cell_data.items()}).write(str(path), binary=True)


def _write_pvd(path, entries):
    lines = ['<?xml version="1.0"?>',
             '<VTKFile type="Collection" version="0.1" byte_order="LittleEndian">',
             '  <Collection>']
    lines += [f'    <DataSet timestep="{ts}" group="" part="0" file="{fn}"/>'
              for ts, fn in entries]
    lines += ['  </Collection>', '</VTKFile>']
    Path(path).write_text("\n".join(lines) + "\n")


def _resolve_output(args, logger):
    """Resolve --output to (path, kind).

    A bare NAME is a directory holding one element table per timestep plus a
    summary -- splitting a long run into per-step files without a script to do it.
    A NAME with an extension is a single file: .csv for the combined table,
    .vtu/.vtk or .pvd for the surface mesh.
    """
    if not getattr(args, "output_file", None):
        return None, None
    base = Path(args.case) if args.case else Path.cwd()
    raw = Path(args.output_file)
    target = raw if raw.is_absolute() else base / raw
    ext = target.suffix.lower()
    if ext == "":
        target.mkdir(parents=True, exist_ok=True)
        return target, "dir"
    if ext in (".csv", ".vtu", ".vtk", ".pvd"):
        target.parent.mkdir(parents=True, exist_ok=True)
        return target, ext
    logger.error(f"Unsupported output extension '{ext}'. Use a bare NAME for a "
                 "directory of per-timestep files, or .csv, .vtu/.vtk or .pvd.")
    sys.exit(1)


def _print_totals(totals, multi):
    """Show the integrated force per timestep -- the summary the rows add up to."""
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
    if multi:
        table.add_column("timestep", justify="right")
    for name in ("elements", "area", "Fx", "Fy", "Fz"):
        table.add_column(name, justify="right")
    shown = totals[:20]
    for row in shown:
        cells = ([str(row[0])] if multi else []) + [f"{row[1]:,}"] + \
                [f"{v:.6g}" for v in row[2:]]
        table.add_row(*cells)
    console.print(table)
    if len(totals) > len(shown):
        console.print(f"[dim]... {len(totals) - len(shown)} more timestep(s)[/dim]")


def execute_compute(args):
    from .help_messages import print_compute_help

    if getattr(args, "help", False):
        print_compute_help(); return

    logger = Logger(verbose=getattr(args, "verbose", False))
    quantity = getattr(args, "quantity", None)
    if not quantity or not args.case:
        print_compute_help()
        sys.exit(0 if not quantity and not args.case else 1)
    if quantity not in QUANTITIES:
        logger.error(f"Unknown quantity '{quantity}'. Available: {', '.join(QUANTITIES)}")
        sys.exit(1)
    if not getattr(args, "zone", None):
        logger.error("--zone is required (the surface zone to integrate over)")
        print(); print_compute_help(); sys.exit(1)

    case_dir = Path(args.case)
    binary_dir = case_dir / "binary"
    if not binary_dir.exists():
        logger.error(f"Binary directory not found: {binary_dir}"); sys.exit(1)
    problem = problem_name(case_dir)

    steps, mode = resolve_steps(args, binary_dir, problem)
    if steps is None:
        logger.error("No timestep given. Pass --timestep N, or --t1/--t2, "
                     "or set the t1/t2 context (use t1:.. t2:..).")
        sys.exit(1)
    if not steps:
        logger.error(f"No PLT files in step range [{args.t1}, {args.t2}] in {binary_dir}")
        sys.exit(1)

    out_path, ext = _resolve_output(args, logger)
    pressure_var = getattr(args, "pressure", None) or "Pressure"
    multi = mode == "range"
    rows, totals, entries = [], [], []
    owners = cached_surf = cached_vol = None
    warned = False
    bar_on, spin_on = (lambda on: (on and len(steps) > 1, on and len(steps) == 1))(
        progress_enabled(args, len(steps)))

    with step_bar(len(steps), "Computing", enabled=bar_on) as bar:
        for ts in steps:
            bar.step(f"step {ts}")
            plt_path = find_plt(binary_dir, problem, ts)
            if not plt_path:
                logger.warning(f"no PLT for timestep {ts}; skipping"); bar.advance(); continue
            plt = PltFile(plt_path)
            si = _surface_zone(plt, args.zone, logger)
            vi = plt.first_volume_zone()
            surf_conn = plt.load_connectivity(si)
            if surf_conn is None or not len(surf_conn):
                logger.error(f"Zone '{args.zone}' has no elements of its own to integrate.")
                sys.exit(1)
            with spinner(f"Reading {Path(plt_path).name}", enabled=spin_on):
                pts, vol_conn, pdata, info = plt.load_zone(vi, nen=getattr(args, "nen", None))
            if pressure_var not in pdata:
                logger.error(f"Variable '{pressure_var}' not in zone "
                             f"'{plt.zones[vi]['name']}'. Available: {', '.join(pdata)}")
                sys.exit(1)

            centroid, area, normal = surface.element_geometry(pts, surf_conn)
            # Topology is fixed across timesteps, so the face->cell map is built once;
            # rebuild it if the file ever disagrees rather than trusting that silently.
            if (owners is None or not np.array_equal(surf_conn, cached_surf)
                    or not np.array_equal(vol_conn, cached_vol)):
                if owners is not None:
                    logger.warning(f"step {ts}: mesh topology changed; "
                                   "recomputing surface-to-volume adjacency")
                owners = surface.adjacent_cells(surf_conn, vol_conn)
                cached_surf, cached_vol = surf_conn, vol_conn
                logger.info(f"{int((owners >= 0).sum()):,}/{len(owners):,} surface elements "
                            "matched to a volume cell")
            normal = _orient(normal, centroid, area, pts, vol_conn, owners, logger, warned)
            warned = warned or (owners < 0).any()

            face_p, force = surface.pressure_force(pdata[pressure_var], surf_conn, area, normal)
            totals.append([ts, len(surf_conn), area.sum(),
                           force[:, 0].sum(), force[:, 1].sum(), force[:, 2].sum()])

            if ext == "dir":
                # One file per timestep, written as we go: a long run never has to
                # be held in memory, and the step is named by the file.
                block = np.column_stack([np.arange(len(surf_conn)), centroid, area,
                                         normal, face_p, force])
                _write_csv(out_path / f"elements_{ts}.csv",
                           COLUMNS + [pressure_var, "Fx", "Fy", "Fz"], block,
                           _comment_block(case_dir, args, pressure_var, len(block),
                                          f"timestep: {ts}"))
            elif ext == ".csv" or out_path is None:
                block = np.column_stack([np.arange(len(surf_conn)), centroid, area,
                                         normal, face_p, force])
                if multi:
                    block = np.column_stack([np.full(len(block), ts), block])
                rows.append(block)
            elif ext in (".vtu", ".vtk", ".pvd"):
                data = {"area": area, "Pressure": face_p, "nx": normal[:, 0],
                        "ny": normal[:, 1], "nz": normal[:, 2], "Fx": force[:, 0],
                        "Fy": force[:, 1], "Fz": force[:, 2]}
                if ext == ".pvd":
                    stem = out_path.with_suffix("")
                    piece = f"{stem}_{ts}.vtu"
                    _write_mesh(piece, pts, surf_conn, data)
                    entries.append((ts, os.path.basename(piece)))
                else:
                    _write_mesh(out_path, pts, surf_conn, data)
            bar.advance()

    if not totals:
        logger.error("Nothing computed (no matching PLT files)."); sys.exit(1)

    span = (f"timesteps: {steps[0] if len(steps) == 1 else f'{steps[0]}..{steps[-1]}'} "
            f"({len(totals)} written)")
    comments = _comment_block(case_dir, args, pressure_var, int(totals[0][1]), span)
    for line in comments:
        logger.info(line)
    _print_totals(totals, multi)

    if out_path is None:
        return
    if ext == "dir":
        _write_csv(out_path / "summary.csv", SUMMARY_COLUMNS, np.asarray(totals), comments)
        print(f"Wrote {len(totals)} element table(s) + summary.csv -> {out_path}/")
    elif ext == ".csv":
        header = (["timestep"] if multi else []) + COLUMNS + [pressure_var,
                                                              "Fx", "Fy", "Fz"]
        _write_csv(out_path, header, np.vstack(rows), comments)
        print(f"Wrote {sum(len(r) for r in rows):,} element row(s) x {len(header)} cols "
              f"-> {out_path}")
    elif ext == ".pvd":
        _write_pvd(out_path, entries)
        print(f"Wrote surface series: {len(entries)} mesh file(s) + {out_path}")
    else:
        print(f"Wrote surface mesh with per-element force -> {out_path}")
