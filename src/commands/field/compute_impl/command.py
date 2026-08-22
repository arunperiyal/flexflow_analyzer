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
from . import coefficients, separation as sep, wall_shear as shear

QUANTITIES = ("force", "force_coeff", "wall_shear", "separation", "lambda2")
# force and force_coeff integrate over a surface zone's elements; lambda2 is a
# nodal field over the volume, so it takes a different path and does not want
# --zone.
SURFACE_QUANTITIES = ("force", "force_coeff", "wall_shear")
# `separation` reads what wall_shear wrote rather than a PLT, so it needs neither
# a timestep range nor the mesh -- only the tables and the case's own declarations.
TABLE_QUANTITIES = ("separation",)
SURFACE_ZTYPES = (2, 3)          # FETRIANGLE, FEQUADRILATERAL
COLUMNS = ["element", "x", "y", "z", "area", "nx", "ny", "nz"]
SUMMARY_COLUMNS = ["timestep", "elements", "area", "Fx", "Fy", "Fz"]
SHEAR_SUMMARY_COLUMNS = ["timestep", "elements", "area", "Cf_mean", "Cf_max",
                         "reversed_fraction"]
SECTIONAL_COLUMNS = ["section", "station", "Fx", "Fy", "Fz", "Fd", "Fl",
                     "Cd", "Cl", "area", "elements"]
# Same leading columns as an element force table, so one reader serves both.
SHEAR_COLUMNS = ["element", "x", "y", "z", "area", "nx", "ny", "nz",
                 "wx", "wy", "wz", "taux", "tauy", "tauz",
                 "tau_theta", "tau_axial", "Cf", "theta", "station",
                 "Pressure", "Cp"]
COEFF_SUMMARY_COLUMNS = ["timestep", "elements", "area", "Fx", "Fy", "Fz",
                         "Fd", "Fl", "Cd", "Cl"]

# What each quantity's output directory is called, after the body it is about:
# `cyl.forces`, `cyl.force_coeff`. Naming outputs after the body rather than the
# run is what lets one case hold several bodies without their tables colliding.
OUTPUT_SUFFIX = {"force": "forces", "force_coeff": "force_coeff",
                 "wall_shear": "wall_shear", "separation": "separation"}
# ...which puts a dot in a directory name, so `cyl.force_coeff` would otherwise
# read as a file with a '.force_coeff' extension. These are the suffixes that mean
# "directory"; a suffix in neither set is a typo and is reported as one, rather
# than quietly becoming a directory nobody asked for.
DIR_SUFFIXES = tuple(f".{v}" for v in OUTPUT_SUFFIX.values())


def _comment_block(case_dir, args, pressure_var, n_elements, span):
    """The '#' header every element table carries."""
    quantity = getattr(args, "quantity", "force")
    return [
        f"FlexFlow field compute {quantity} -- pressure force per surface element",
        f"case: {case_dir.name}   zone: {args.zone}   pressure: {pressure_var}",
        "force: -p n dA, pressure only (no viscous skin friction)",
        "normal: unit, pointing out of the body (oriented by the adjacent volume cell)",
        f"elements: {n_elements:,}   {span}",
    ]


def _coeff_comments(case_dir, args, pressure_var, n_elements, span, reference,
                    sections=None, per_section=False, companion_files=False):
    """The full '#' block for a coefficient run: every number a Cd was divided by.

    It goes on summary.csv, which is the one file the whole run produces, rather
    than being repeated at the top of every per-timestep table. The reference
    state is a property of the run, not of a timestep, and saying it forty times
    over does not make it forty times as true.
    """
    lines = [
        "FlexFlow field compute force_coeff -- pressure force coefficients",
        f"case: {case_dir.name}   body: {reference.body}   zone: {args.zone}   "
        f"pressure: {pressure_var}",
        "force: -p n dA, pressure only (no viscous skin friction)",
        "normal: unit, pointing out of the body (oriented by the adjacent volume cell)",
        f"elements: {n_elements:,}   {span}",
    ] + reference.describe()
    if sections is not None:
        lines.append(f"sections: {sections.count} x {sections.width:g} along "
                     f"{reference.labels.get('span')}, cut once from the first "
                     "timestep and kept, so a section holds the same facets "
                     "throughout")
    # What *this* table was divided by, which is not the same question as what
    # the run computed: a single --output NAME.csv holds the per-section rows, and
    # heading it with the whole-body D*L would be wrong by a factor of L/dx.
    lines.append("this table: " + reference.normalisation(
        sections.width if (per_section and sections is not None) else None))
    if companion_files and sections is not None:
        # Only when such files exist: naming them in a run that wrote none invites
        # a reader to go looking for tables that were never written.
        lines.append("sectional_<step>.csv beside it: "
                     + reference.normalisation(sections.width))
    lines.append("coefficients are from pressure alone: no skin friction is included")
    return lines


def _shear_comments(case_dir, args, n_elements, span, reference, mu, nu_t_max,
                    has_pressure):
    """The '#' block a wall-shear table carries.

    The theta zero, the sense it increases in, and how each section's centre was
    found are *conventions*, not data. A reader that has to guess them will guess
    one of them wrong, so they are stated here rather than left to a docstring
    nobody downstream reads.
    """
    q = reference.dynamic_pressure
    lines = [
        "FlexFlow field compute wall_shear -- viscous wall shear per surface element",
        f"case: {case_dir.name}   body: {reference.body}   zone: {args.zone}",
        "tau_w = mu_eff * (omega x n), exact at a no-slip wall: the velocity "
        "vanishes on the surface, so only the wall-normal gradient survives",
        f"mu: {mu:g}   rho: {reference.rho:g}   U_inf: {reference.u_inf:g}   "
        f"q = 0.5*rho*U^2: {q:g}",
        # The reference lengths belong here even though a shear does not divide by
        # them: a reader picking up one of these tables should not have to open a
        # force table to find out what body it is looking at.
        reference.describe()[1],
        f"elements: {n_elements:,}   {span}",
    ]
    if nu_t_max is None:
        lines.append("mu_eff = mu: the PLT carries no eddy viscosity")
    elif nu_t_max == 0:
        lines.append(f"mu_eff = mu + rho*eddy; eddy at the wall: max {nu_t_max:g} "
                     "(so mu_eff = mu here, with no turbulence-model ambiguity)")
    else:
        lines.append(f"mu_eff = mu + rho*eddy; eddy at the wall: max {nu_t_max:g} "
                     f"(so mu_eff reaches {mu + reference.rho * nu_t_max:g}, and the "
                     "shear is model-dependent)")
    lines += [
        f"theta: 0 at the forward stagnation point ({axis_label_of(-reference.flow)}), "
        f"increasing towards {reference.labels.get('lift')}, in (-180, 180] degrees",
        f"span axis: {reference.labels.get('span')}   "
        f"drag (flow): {reference.labels.get('flow')}   "
        f"lift: {reference.labels.get('lift')}",
        "section centre: the declared axis (domain.yml origin + station * axis) "
        "plus the area-weighted mean element displacement around that ring, "
        "interpolated to each element's own station",
        "Cf = |tau_w| / q; tau_theta and tau_axial are signed components along the "
        "azimuthal and span directions",
    ]
    if has_pressure:
        lines.append("Cp = Pressure / q, with the free-stream reference taken as 0")
    else:
        lines.append("the PLT carries no Pressure, so Pressure and Cp are written 0")
    return lines


def axis_label_of(vector):
    from .coefficients import axis_label
    return axis_label(vector)


def _sectional_comments(case_dir, reference, sections, timestep, n_elements):
    """The short '#' block a per-timestep sectional table carries.

    Four lines: which run and which step, and the one thing needed to read the
    numbers below without opening anything else -- what they were divided by. The
    rest of the reference state is in summary.csv beside it.
    """
    return [
        "FlexFlow field compute force_coeff -- sectional coefficients",
        f"case: {case_dir.name}   body: {reference.body}   timestep: {timestep}   "
        f"sections: {sections.count}   elements: {n_elements:,}",
        reference.normalisation(sections.width)
        + f"   drag {reference.labels.get('flow')}, lift {reference.labels.get('lift')}",
        "the rest of the reference state is in summary.csv",
    ]


def _zone_via_domain(case_dir, plt, name):
    """The PLT zone `name` means, when `name` is a body rather than a zone.

    A body has three names -- its own, its geotag, its plttag -- and only the
    plttag is what a PLT calls it. Anyone who has read domain.yml is as likely to
    type one of the other two, so a name that is not a zone is looked up there
    before being called missing. Returns (zone name, how it was found) or
    (None, None).
    """
    try:
        from ....core.domain import DomainConfig
        domain = DomainConfig.find(case_dir)
        if not domain.exists:
            return None, None
        entry = domain.entry(name)
        tag = domain.plt_zone(name)
    except Exception:
        return None, None
    if not tag or zone_index(plt, tag) is None:
        return None, None
    return tag, (f"'{name}' is {(entry or {}).get('name', name)} in domain.yml, "
                 f"whose plttag is '{tag}'")


def _surface_zone(plt, name, logger, case_dir=None, announced=None):
    """Resolve --zone to a surface zone index, or exit explaining why it cannot be."""
    zi = zone_index(plt, name)
    if zi is None and case_dir is not None:
        resolved, how = _zone_via_domain(case_dir, plt, name)
        if resolved:
            # Said once, not once per timestep: it is orientation, not a warning.
            if announced is not None and not announced:
                logger.info(how)
                announced.append(True)
            zi, name = zone_index(plt, resolved), resolved
    if zi is None:
        known = ', '.join(z['name'] for z in plt.zones)
        logger.error(f"Zone '{name}' not found. Available: {known}. A body name or "
                     "geotag from domain.yml works too, when its plttag names one "
                     "of these.")
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


INT_COLUMNS = ("timestep", "element", "elements", "section", "theta_bin")


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


def _output_name(args, quantity, body):
    """Where this run writes: what --output asked for, or the default for the body.

    `--output NAME` is NAME. Anything else -- a bare `--output`, or none at all --
    is `<body>.forces` / `<body>.force_coeff` in the case directory. A run always
    writes: the tables are the point of it, and naming them after the body is what
    lets one case hold several without their outputs colliding.
    """
    raw = getattr(args, "output_file", None)
    if isinstance(raw, str) and raw:
        return raw
    return f"{body}.{OUTPUT_SUFFIX.get(quantity, quantity)}"


def _body_name(case_dir, zone, reference):
    """The name an output directory is built on: 'cyl' -> cyl.forces.

    force_coeff has resolved the body in full by now; force has not, and needs
    nothing from it but the name, so domain.yml is read for that alone. A case
    without one falls back to the zone, which is what the directory would have
    been called anyway.
    """
    if reference is not None:
        return reference.body
    try:
        from ....core.domain import DomainConfig
        entry = DomainConfig.find(case_dir).entry(zone)
    except Exception:
        entry = None
    return (entry or {}).get("name") or zone or "zone"


def _resolve_output(name, case, logger, kinds=(".csv", ".vtu", ".vtk", ".pvd")):
    """Resolve an output name to (path, kind).

    A bare NAME is a directory holding one table per timestep plus a summary --
    splitting a long run into per-step files without a script to do it. A NAME
    with an extension is a single file: .csv for the combined table, .vtu/.vtk or
    .pvd for the surface mesh.
    """
    if not name:
        return None, None
    base = Path(case) if case else Path.cwd()
    raw = Path(name)
    target = raw if raw.is_absolute() else base / raw
    ext = target.suffix.lower()
    if ext == "" or ext in DIR_SUFFIXES:
        target.mkdir(parents=True, exist_ok=True)
        return target, "dir"
    if ext in kinds:
        target.parent.mkdir(parents=True, exist_ok=True)
        return target, ext
    logger.error(f"Unsupported output extension '{ext}'. Use a bare NAME (or one "
                 f"ending {' / '.join(DIR_SUFFIXES)}) for a directory of "
                 f"per-timestep files, or {' / '.join(kinds)} for a single file.")
    sys.exit(1)


def _print_totals(totals, multi, columns=SUMMARY_COLUMNS):
    """Show the integrated force per timestep -- the summary the rows add up to."""
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
    if multi:
        table.add_column("timestep", justify="right")
    for name in columns[1:]:
        table.add_column(name, justify="right")
    shown = totals[:20]
    for row in shown:
        cells = ([str(int(row[0]))] if multi else []) + [f"{int(row[1]):,}"] + \
                [f"{v:.6g}" for v in row[2:]]
        table.add_row(*cells)
    console.print(table)
    if len(totals) > len(shown):
        console.print(f"[dim]... {len(totals) - len(shown)} more timestep(s)[/dim]")


def _compute_lambda2(args, steps, binary_dir, problem, logger):
    """Write a mesh carrying lambda2, one file per timestep.

    A nodal field over the volume, unlike `force`, which integrates over a
    surface zone's elements -- so this converts the volume zone and adds an
    array to it rather than producing a table of rows.
    """
    from ....plt import derive
    from ....plt.convert import to_vtu
    import pyvista as pv

    raw = getattr(args, "output_file", None)
    if raw is True:
        raw = "lambda2"      # a bare --output: name it after the quantity
    if not raw:
        logger.error("--output is required for lambda2: it writes a mesh "
                     "(NAME.vtu), or a directory NAME/ for a range of steps")
        sys.exit(1)
    base = Path(args.case)
    target = Path(raw) if Path(raw).is_absolute() else base / raw
    many = len(steps) > 1
    if many and target.suffix:
        target = target.with_suffix("")
    if many:
        target.mkdir(parents=True, exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)

    written = []
    for i, step in enumerate(steps, 1):
        plt_path = find_plt(binary_dir, problem, step)
        if not plt_path:
            logger.warning(f"no PLT for timestep {step}; skipping"); continue
        if many:
            print(f"  [{i}/{len(steps)}] timestep {step}", flush=True)
        sidecar = Path(str(plt_path)[:-4] + ".vtu")
        if not sidecar.exists():
            logger.info(f"converting {plt_path.name} -> {sidecar.name}")
            to_vtu(str(plt_path), str(sidecar), nen=getattr(args, "nen", None))
        mesh = pv.read(str(sidecar))
        derive.ensure(mesh, "lambda2", logger.info)
        out = (target / f"lambda2_{step}.vtu") if many else target
        if not many and not out.suffix:
            out = out.with_suffix(".vtu")
        mesh.save(str(out))
        written.append(out)
        logger.info(f"wrote {out}")

    if not written:
        logger.error("nothing written"); sys.exit(1)
    where = written[0] if len(written) == 1 else target
    print(f"lambda2 over {len(written)} timestep{'' if len(written) == 1 else 's'} -> {where}")


def _finish_coefficients(out_path, ext, totals, rows, entries, comments, multi,
                         sections, reference, logger):
    """Report and write what force_coeff produced.

    The whole-body series always goes to summary.csv -- it is the thing a
    coefficient run is usually for -- and the per-section tables go beside it,
    one per timestep, when --sectional asked for them.
    """
    _print_totals(totals, multi, COEFF_SUMMARY_COLUMNS)
    cd = np.asarray([row[-2] for row in totals], dtype=float)
    cl = np.asarray([row[-1] for row in totals], dtype=float)
    if len(cd) > 1:
        print(f"Cd {cd.mean():.4f} +/- {cd.std():.4f}   "
              f"Cl {cl.mean():+.4f} +/- {cl.std():.4f}   "
              f"over {len(cd)} timestep(s), pressure only")
    else:
        print(f"Cd {cd[0]:.4f}   Cl {cl[0]:+.4f}   (pressure only)")

    if out_path is None:
        return
    if ext == "dir":
        _write_csv(out_path / "summary.csv", COEFF_SUMMARY_COLUMNS,
                   np.asarray(totals), comments)
        print(f"Wrote {len(entries)} sectional table(s) x {sections.count} "
              f"section(s) + summary.csv -> {out_path}/")
        return
    if rows:
        header = (["timestep"] if multi else []) + SECTIONAL_COLUMNS
        _write_csv(out_path, header, np.vstack(rows), comments)
        print(f"Wrote {sum(len(r) for r in rows):,} section row(s) -> {out_path}")
    else:
        _write_csv(out_path, COEFF_SUMMARY_COLUMNS, np.asarray(totals), comments)
        print(f"Wrote {len(totals)} timestep row(s) of whole-body Cd/Cl -> {out_path}")


def _compute_separation(args, case_dir, logger):
    """Reduce a wall_shear directory to separation angles, per section per step."""
    import argparse

    zone = getattr(args, "body", None) or getattr(args, "zone", None)
    if not zone:
        logger.error("--body is required: which body's wall_shear tables to reduce "
                     "(--zone works too)")
        sys.exit(1)
    try:
        reference = coefficients.resolve(case_dir, zone, args, logger)
    except coefficients.ReferenceError as exc:
        logger.error(str(exc)); sys.exit(1)

    # Where wall_shear would have written, asked of the same function that put it
    # there, so the two cannot drift apart.
    source_name = _output_name(argparse.Namespace(output_file=None), "wall_shear",
                               reference.body)
    source = case_dir / source_name
    try:
        tables = sep.find_tables(source)
    except sep.SeparationError as exc:
        logger.error(str(exc)); sys.exit(1)

    n_bins = getattr(args, "azimuthal", None) or 36
    n_sections = getattr(args, "sectional", None) or 48
    if n_bins < 2 or n_sections < 1:
        logger.error("--azimuthal needs at least 2 bins and --sectional at least 1")
        sys.exit(1)

    out_path, ext = _resolve_output(
        _output_name(args, "separation", reference.body), args.case, logger,
        kinds=(".csv",))
    if ext != "dir":
        logger.error("separation writes a directory of tables, so --output takes a "
                     "bare name, not a file")
        sys.exit(1)

    logger.info(f"reducing {len(tables)} table(s) from {source_name}/")
    written, answers, q_seen = [], [], set()
    sections = None
    bar_on = progress_enabled(args, len(tables)) and len(tables) > 1
    with step_bar(len(tables), "Reducing", enabled=bar_on) as bar:
        for step, path in tables:
            bar.step(f"step {step}")
            try:
                table, meta = sep.read_table(path)
            except sep.SeparationError as exc:
                logger.error(str(exc)); sys.exit(1)
            q_header, mu = meta.get("q"), meta.get("mu")
            for needed in ("theta", "station", "tau_theta", "tau_axial", "area"):
                if needed not in table:
                    logger.error(f"{path.name} has no '{needed}' column, so it was "
                                 "not written by `field compute wall_shear`")
                    sys.exit(1)
            if q_header is not None:
                q_seen.add(round(q_header, 9))
            if sections is None:
                sections = _table_sections(table, reference, n_sections, logger)
            rows, per_section = sep.reduce_step(table, sections, n_bins,
                                                reference.dynamic_pressure)
            sep.write_csv(out_path / f"azimuthal_{step}.csv", sep.AZIMUTHAL_COLUMNS,
                          rows,
                          _separation_comments(case_dir, reference, sections,
                                               n_bins, step, mu))
            written.append(step)
            answers += [[step] + row for row in per_section]
            bar.advance()

    # The tables record the q they were written with. If it no longer matches what
    # the case declares, one of the two has moved since, and the Cf in these files
    # is not the Cf those were made from.
    q = reference.dynamic_pressure
    if q_seen and round(q, 9) not in q_seen:
        logger.warning(
            f"the wall_shear tables were written with q = "
            f"{', '.join(f'{v:g}' for v in sorted(q_seen))}, but domain.yml and the "
            f".def now give q = {q:g}. Something has changed since; re-run "
            "wall_shear so the two agree.")

    _warn_if_grooved(answers, logger)
    sep.write_csv(out_path / "separation.csv", sep.SEPARATION_COLUMNS, answers,
                  _separation_comments(case_dir, reference, sections, n_bins, None,
                                       mu))
    _print_separation(answers)
    print(f"Wrote {len(written)} azimuthal table(s) x {n_sections} section(s) x "
          f"{n_bins} bin(s) + separation.csv -> {out_path}/")


def _warn_if_grooved(answers, logger):
    """Say so when the sections reverse too often for theta_sep to mean anything.

    A plain section reverses its azimuthal shear four times around the perimeter:
    stagnation, the two separations, the rear. Every groove adds a local reversal
    without the boundary layer having left the body, so "the first crossing after
    the peak" then finds a groove rather than a separation -- and returns a
    perfectly plausible angle for it, which is worse than returning nothing.

    Not thresholded into a NaN, because the ranges overlap: a bare section reaches
    eight on the measured cases while a grooved one starts at six. What separates
    them is how many sections do it -- all of them, on a grooved body, against a
    fifth of them on a bare one -- so that is what is reported.
    """
    if not answers:
        return
    crossings = np.array([row[-1] for row in answers], dtype=int)
    over = crossings > sep.CLEAN_CROSSINGS
    if over.mean() < 0.5:
        return
    logger.warning(
        f"{int(over.sum())} of {len(crossings)} section-steps reverse more than "
        f"{sep.CLEAN_CROSSINGS} times around the perimeter (median "
        f"{int(np.median(crossings))}). A plain, settled section reverses "
        f"{sep.CLEAN_CROSSINGS} times -- stagnation, the two separations, the rear. "
        "The extras come from grooves, each adding a local flip without the layer "
        "leaving the surface, or from a field that has not settled; either way "
        "theta_sep has found one of those rather than a separation, and it will look "
        "like a plausible angle. Read reversed_fraction instead -- it integrates the "
        "sign of the shear rather than hunting one crossing, so it does not care how "
        "many there are. The `crossings` column carries the count per row.")


def _table_sections(table, reference, n_sections, logger):
    """Section every row of an element table, anchored to the body as elsewhere."""
    station = table["station"]
    width = reference.length / n_sections
    root = reference.root
    if root is None:
        root = float(station.min())
        logger.warning("the body declares no origin in domain.yml, so sections are "
                       "anchored to the first element rather than to the body, and "
                       "will not line up with another mesh of the same body.")
    index = np.clip(((station - root) / width).astype(int), 0, n_sections - 1)
    counts = np.bincount(index, minlength=n_sections)
    if counts.min() == 0:
        logger.warning(f"{int((counts == 0).sum())} of {n_sections} sections hold no "
                       "elements")
    logger.info(f"sections: {n_sections} x {width:g} along "
                f"{reference.labels.get('span')}, "
                f"{counts.min()}/{counts.mean():.1f}/{counts.max()} rows (min/mean/max)")
    return {"index": index, "count": n_sections, "width": width}


def _separation_comments(case_dir, reference, sections, n_bins, step, mu=None):
    """The '#' block a separation table carries, conventions and all.

    `mu` is carried through from the wall_shear header rather than re-read from
    the .def: tau_w = mu * (omega x n) is how these numbers were made, and the
    value that made them is the one worth recording, whatever the case says now.
    """
    lines = [
        "FlexFlow field compute separation -- where the flow leaves the surface",
        f"case: {case_dir.name}   body: {reference.body}",
        f"reduced from {reference.body}.wall_shear/elements_<step>.csv",
        # In full, in every one of these: this directory has no summary.csv to
        # hold a block in common -- separation.csv is an answer, not a header --
        # so each table states the whole reference state or none of it does.
        *reference.describe(),
    ]
    if mu is not None:
        lines.append(f"mu: {mu:g}   (tau_w = mu * (omega x n), from the wall_shear "
                     "tables these were reduced from)")
    lines += [
        f"sections: {sections['count']} x {sections['width']:g} along "
        f"{reference.labels.get('span')}, anchored at the body's declared origin",
        f"azimuthal bins: {n_bins} x {360.0 / n_bins:g} deg, theta = 0 at a bin centre",
        "theta: 0 at the forward stagnation point, increasing towards "
        f"{reference.labels.get('lift')}, in (-180, 180] degrees",
        "Cf_theta, Cf_axial, Cp: area-weighted within each bin",
    ]
    if step is not None:
        lines.append(f"timestep: {step}")
    else:
        lines += [
            "theta_sep: the first sign change in Cf_theta *after* its peak, "
            "interpolated between bins. The first zero going outward is the "
            "stagnation point, which on a shedding body does not sit at theta = 0",
            "theta_sep_pos/neg are nan where that side stays attached, which is an "
            "answer rather than a failure",
            "reversed_fraction: the area-weighted share of the section's perimeter "
            "with Cf_theta < 0 -- one number per section that survives a crossing "
            "too ambiguous to place",
            "Cf_max: the largest |Cf_theta| in the section",
            f"crossings: how often Cf_theta reverses around the whole section. A "
            f"plain one reverses {sep.CLEAN_CROSSINGS} times -- stagnation, the two "
            "separations, the rear",
            "theta_sep IS ONLY A SEPARATION ANGLE ON A PLAIN, SETTLED SECTION. A "
            "groove adds a local reversal without the layer leaving the surface, and "
            "so does a field that has not settled; the crossing after the peak is "
            "then one of those, and it looks like a plausible angle. Check "
            f"`crossings` against {sep.CLEAN_CROSSINGS} and prefer reversed_fraction "
            "wherever it is higher",
        ]
    return lines


def _print_separation(answers):
    """A per-section digest of the last timestep, so a run says what it found."""
    from rich.console import Console
    from rich.table import Table
    from rich import box

    if not answers:
        return
    console = Console()
    last = max(row[0] for row in answers)
    rows = [row for row in answers if row[0] == last]
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow",
                  title=f"separation at timestep {int(last)}", title_justify="left",
                  title_style="bold cyan")
    for name in ("section", "station", "theta_sep +", "theta_sep -", "reversed",
                 "Cf_max"):
        table.add_column(name, justify="right")
    every = max(1, len(rows) // 12)
    shown = rows[::every][:12]
    for row in shown:
        table.add_row(str(int(row[1])), f"{row[2]:.3f}",
                      "--" if np.isnan(row[3]) else f"{row[3]:+.1f}",
                      "--" if np.isnan(row[4]) else f"{row[4]:+.1f}",
                      f"{row[5]:.3f}", f"{row[6]:.4f}")
    console.print()
    console.print(table)
    if len(rows) > len(shown):
        console.print(f"[dim]{len(rows)} sections; every {every} shown[/dim]")
    attached = sum(1 for row in rows if np.isnan(row[3]) and np.isnan(row[4]))
    if attached:
        console.print(f"[dim]{attached} of {len(rows)} section(s) stay attached on "
                      "both sides at this step[/dim]")


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
    if quantity in SURFACE_QUANTITIES and not getattr(args, "zone", None):
        logger.error("--zone is required (the surface zone to integrate over)")
        print(); print_compute_help(); sys.exit(1)
    for flag, owners in (("sectional", ("force_coeff", "separation")),
                         ("direction", ("force_coeff", "wall_shear", "separation")),
                         ("flow", ("force_coeff", "wall_shear", "separation")),
                         ("azimuthal", ("separation",)),
                         ("body", ("separation",))):
        if quantity not in owners and getattr(args, flag, None) is not None:
            logger.error(f"--{flag} belongs to "
                         + " or ".join(f"`field compute {o}`" for o in owners)
                         + f", not to '{quantity}'.")
            sys.exit(1)

    case_dir = Path(args.case)

    if quantity in TABLE_QUANTITIES:
        # Reads what wall_shear wrote, so it wants neither the PLTs nor a range.
        _compute_separation(args, case_dir, logger)
        return

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

    if quantity == "lambda2":
        _compute_lambda2(args, steps, binary_dir, problem, logger)
        return

    reference = sections = None
    n_sections = getattr(args, "sectional", None)
    mu = nu_t_max = None
    shear_has_pressure = False
    shear_warned = []
    if quantity == "wall_shear":
        # Everything it needs is declared, so failing here costs nothing where
        # failing after forty timesteps costs the lot.
        try:
            reference = coefficients.resolve(case_dir, args.zone, args, logger)
        except coefficients.ReferenceError as exc:
            logger.error(str(exc)); sys.exit(1)
        from ....core.simflow_config import SimflowConfig
        from ....core.def_config import DefConfig
        try:
            problem_for_def = SimflowConfig.find(case_dir).problem
        except Exception:
            problem_for_def = None
        mu = DefConfig.find(case_dir, problem_for_def).viscosity()
        if mu is None:
            logger.error(
                "the .def gives no viscosity: the chain elementGroup -> "
                "elementProperty -> materialModel -> viscosityModel does not lead "
                "to a number, and a wall shear is mu times a vorticity. Check it "
                "with `def var`.")
            sys.exit(1)
    if quantity == "force_coeff":
        # Resolved before a single PLT is opened: everything it needs is in
        # domain.yml and the .def, and failing here costs nothing, where failing
        # after reading forty timesteps costs the lot.
        try:
            reference = coefficients.resolve(case_dir, args.zone, args, logger)
        except coefficients.ReferenceError as exc:
            logger.error(str(exc)); sys.exit(1)
        if n_sections is not None and n_sections < 1:
            logger.error(f"--sectional wants a positive count of slices (got "
                         f"{n_sections})")
            sys.exit(1)

    out_path, ext = _resolve_output(
        _output_name(args, quantity, _body_name(case_dir, args.zone, reference)),
        args.case, logger,
        kinds=(".csv",) if quantity == "force_coeff" else
              (".csv", ".vtu", ".vtk", ".pvd"))
    if quantity == "force_coeff" and ext == "dir" and n_sections is None:
        # Without --sectional there is nothing per timestep, so the directory holds
        # summary.csv alone. It still goes in the directory: everything about this
        # body belongs in one place whether or not sections were asked for.
        out_path, ext = out_path / "summary.csv", ".csv"

    pressure_var = getattr(args, "pressure", None) or "Pressure"
    multi = mode == "range"
    rows, totals, entries = [], [], []
    owners = cached_surf = cached_vol = None
    warned = False
    zone_announced = []
    bar_on, spin_on = (lambda on: (on and len(steps) > 1, on and len(steps) == 1))(
        progress_enabled(args, len(steps)))

    with step_bar(len(steps), "Computing", enabled=bar_on) as bar:
        for ts in steps:
            bar.step(f"step {ts}")
            plt_path = find_plt(binary_dir, problem, ts)
            if not plt_path:
                logger.warning(f"no PLT for timestep {ts}; skipping"); bar.advance(); continue
            plt = PltFile(plt_path)
            si = _surface_zone(plt, args.zone, logger, case_dir, zone_announced)
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

            if quantity == "wall_shear":
                try:
                    out = shear.compute(pdata, surf_conn, centroid, area, normal,
                                        reference, mu, logger, shear_warned)
                except shear.WallShearError as exc:
                    logger.error(str(exc)); sys.exit(1)
                nu_t_max = out["nu_t_max"]
                shear_has_pressure = out["has_pressure"]
                q = reference.dynamic_pressure
                block = np.column_stack([
                    np.arange(len(surf_conn)), centroid, area, normal,
                    out["omega"], out["tau"], out["tau_theta"], out["tau_axial"],
                    out["magnitude"] / q, out["theta"], out["station"],
                    out["pressure"], out["pressure"] / q])
                totals.append([ts, len(surf_conn), area.sum(),
                               float((out["magnitude"] * area).sum() / area.sum() / q),
                               float((out["magnitude"] / q).max()),
                               float(area[out["tau_theta"] < 0].sum() / area.sum())])
                if ext == "dir":
                    piece = out_path / f"elements_{ts}.csv"
                    _write_csv(piece, SHEAR_COLUMNS, block,
                               _shear_comments(case_dir, args, len(surf_conn),
                                               f"timestep: {ts}", reference, mu,
                                               nu_t_max, out["has_pressure"]))
                    entries.append((ts, piece))
                else:
                    rows.append(np.column_stack([np.full(len(block), ts), block])
                                if multi else block)
                bar.advance()
                continue

            if quantity == "force_coeff":
                drag, lift, cd, cl = coefficients.total_coefficients(force, reference)
                totals.append([ts, len(surf_conn), area.sum(),
                               *force.sum(axis=0), drag, lift, cd, cl])
                if n_sections is not None:
                    # Built once and reused: element ids are stable across
                    # timesteps, so a section keeps the same facets as the body
                    # deflects. Rebuilt only if the mesh itself changed, which
                    # would otherwise make the series one of two different things.
                    if sections is None or len(sections.index) != len(surf_conn):
                        if sections is not None:
                            logger.warning(f"step {ts}: element count changed; "
                                           "re-cutting the sections")
                        sections = coefficients.build_sections(
                            centroid, reference, n_sections, logger)
                    block = coefficients.sectional_rows(force, area, sections,
                                                        reference)
                    if ext == "dir":
                        piece = out_path / f"sectional_{ts}.csv"
                        _write_csv(piece, SECTIONAL_COLUMNS, block,
                                   _sectional_comments(case_dir, reference, sections,
                                                       ts, len(surf_conn)))
                        entries.append((ts, piece))
                    else:
                        rows.append(np.column_stack([np.full(len(block), ts), block])
                                    if multi else block)
                bar.advance()
                continue

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
    if quantity == "wall_shear":
        comments = _shear_comments(case_dir, args, int(totals[0][1]), span,
                                   reference, mu, nu_t_max, shear_has_pressure)
        for line in comments:
            logger.info(line)
        _print_totals(totals, multi, SHEAR_SUMMARY_COLUMNS)
        if out_path is None:
            return
        if ext == "dir":
            _write_csv(out_path / "summary.csv", SHEAR_SUMMARY_COLUMNS,
                       np.asarray(totals), comments)
            print(f"Wrote {len(entries)} element table(s) + summary.csv "
                  f"-> {out_path}/")
        else:
            header = (["timestep"] if multi else []) + SHEAR_COLUMNS
            _write_csv(out_path, header, np.vstack(rows), comments)
            print(f"Wrote {sum(len(r) for r in rows):,} element row(s) -> {out_path}")
        return

    if quantity == "force_coeff":
        # `rows` is only filled on the single-file path, so it is what says whether
        # the table being headed holds sections or one line per timestep.
        comments = _coeff_comments(case_dir, args, pressure_var, int(totals[0][1]),
                                   span, reference, sections,
                                   per_section=bool(rows),
                                   companion_files=(ext == "dir"))
        for line in comments:
            logger.info(line)
        _finish_coefficients(out_path, ext, totals, rows, entries, comments, multi,
                             sections, reference, logger)
        return

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
