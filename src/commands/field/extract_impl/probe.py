"""Point probes for `field extract --probe X,Y,Z`.

A probe samples the requested variables at the mesh node nearest to a fixed
coordinate, for every selected timestep -- the usual way to pull a time signal
(velocity in the wake, pressure at a gauge point) out of a run.

Coordinates are matched per timestep, so a moving/deforming mesh is followed
correctly: the node closest to the probe is looked up again at each step.
"""

import sys

import numpy as np

AXIS = ("x", "y", "z")
TABLE_ROWS = 20          # rows shown on screen before falling back to the file
TABLE_HIDDEN = ("x_probe", "y_probe", "z_probe", "x_node", "y_node", "z_node")


def parse_probes(specs, logger):
    """Parse --probe values into (points[P,3], axes[P]).

    Each spec is `X,Y,Z` (or `X,Y` for a 2D mesh -- Z is then left unspecified and
    ignored when matching). Several probes may share one flag, separated by ';'.
    `axes[i]` holds the indices of the coordinates the user actually gave.
    Exits on malformed input.
    """
    points, axes = [], []
    if isinstance(specs, str):          # a single --probe reaching us unwrapped
        specs = [specs]
    for spec in specs:
        for item in str(spec).split(";"):
            parts = [p.strip() for p in item.split(",") if p.strip()]
            if not parts:
                continue
            try:
                vals = [float(p) for p in parts]
            except ValueError:
                logger.error(f"Bad --probe '{item.strip()}': expected numbers like X,Y,Z")
                sys.exit(1)
            if len(vals) not in (2, 3):
                logger.error(f"Bad --probe '{item.strip()}': expected X,Y[,Z] "
                             f"({len(vals)} value(s) given)")
                sys.exit(1)
            axes.append(np.arange(len(vals)))
            points.append(vals + [np.nan] * (3 - len(vals)))
    if not points:
        logger.error("--probe given without any coordinates (expected X,Y,Z)")
        sys.exit(1)
    return np.asarray(points, dtype=float), axes


def label(point, axes):
    """Human-readable probe coordinate, e.g. '(1.5, 0, -)'."""
    return "(" + ", ".join(f"{point[a]:g}" if a in axes else "-" for a in range(3)) + ")"


def header_bounds(plt, zi):
    """Coordinate bounds of a zone straight from the PLT header, or None.

    Cheap (no data load), so probes can be rejected before reading a large file.
    Returns None when the coordinates are shared/passive in this zone.
    """
    try:
        mm = plt.minmax(zi)
    except Exception:
        return None
    lo, hi = [], []
    for var in plt.vars[:3]:
        rng = mm.get(var)
        if not rng:
            return None
        lo.append(rng[0])
        hi.append(rng[1])
    return np.asarray(lo, dtype=float), np.asarray(hi, dtype=float)


def point_bounds(pts):
    """Coordinate bounds computed from loaded nodes."""
    return pts.min(axis=0).astype(float), pts.max(axis=0).astype(float)


def format_bounds(lo, hi):
    return "  ".join(f"{AXIS[a]} [{lo[a]:g}, {hi[a]:g}]" for a in range(3))


def check_inside(points, axes, lo, hi, zone, logger, tol=0.0):
    """Exit unless every probe lies within the zone's bounding box (per given axis).

    `tol` widens the box on each side, for probes meant to sit exactly on a
    boundary that floating-point round-off pushes just outside.
    """
    bad = []
    for i, (point, ax) in enumerate(zip(points, axes), start=1):
        violations = [(a, point[a]) for a in ax
                      if point[a] < lo[a] - tol or point[a] > hi[a] + tol]
        if violations:
            bad.append((i, point, ax, violations))
    if not bad:
        return
    for i, point, ax, violations in bad:
        logger.error(f"Probe P{i} {label(point, ax)} is outside zone '{zone}':")
        for a, v in violations:
            logger.error(f"    {AXIS[a]} = {v:g} not in [{lo[a]:g}, {hi[a]:g}]")
    logger.error(f"Domain bounds: {format_bounds(lo, hi)}")
    sys.exit(1)


def nearest_node(pts, point, axes, chunk=200_000):
    """Return (node index, distance) of the mesh node closest to `point`.

    Only the coordinates the user specified take part in the distance, so a 2D
    probe (X,Y) matches in-plane. Scans in chunks to bound peak memory on meshes
    with millions of nodes.
    """
    target = point[axes]
    best_i, best_d2 = -1, np.inf
    for start in range(0, len(pts), chunk):
        block = pts[start:start + chunk][:, axes].astype(np.float64)
        d2 = ((block - target) ** 2).sum(axis=1)
        i = int(d2.argmin())
        if d2[i] < best_d2:
            best_d2, best_i = float(d2[i]), start + i
    return best_i, float(np.sqrt(best_d2))


def far_probe_warning(dist, lo, hi, npts, factor=2.0):
    """Message when the matched node is suspiciously far from the probe, else None.

    Inside the bounding box but far from any node means the probe sits in a hole
    of the meshed region (inside a body, outside an irregular boundary). "Far" is
    measured against the mean node spacing estimated from the bounding box and
    node count, so the check adapts to coarse and fine meshes alike.
    """
    diag = float(np.linalg.norm(np.asarray(hi, dtype=float) - np.asarray(lo, dtype=float)))
    if diag <= 0 or npts < 2:
        return None
    spacing = diag / npts ** (1.0 / 3.0)
    if dist > factor * spacing:
        return (f"nearest node is {dist:g} away, {dist / spacing:.0f}x the mean node "
                f"spacing (~{spacing:g}) -- the probe may sit in a hole of the mesh "
                "(inside a body, or beyond an irregular boundary)")
    return None


def build_header(cols, multi):
    """CSV/table columns for probe output."""
    return ((["timestep"] if multi else [])
            + ["probe", "x_probe", "y_probe", "z_probe",
               "node", "x_node", "y_node", "z_node", "distance"]
            + list(cols))


def _fmt(value, precision="%.8e"):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return precision % float(value)
    return str(value)


def write_csv(path, header, rows):
    """Write probe rows to CSV (blank cells for coordinates the user left out)."""
    lines = [",".join(header)]
    lines += [",".join(_fmt(v) for v in row) for row in rows]
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def print_table(header, rows, truncate=True):
    """Print probe rows as a table, capped at TABLE_ROWS when `truncate`.

    The six coordinate columns are folded away here -- the requested point rides
    along in the probe label -- so the table stays readable in a terminal. The
    CSV keeps every column.
    """
    from rich.console import Console
    from rich.table import Table
    from rich import box

    shown = rows[:TABLE_ROWS] if truncate else rows
    keep = [i for i, name in enumerate(header) if name not in TABLE_HIDDEN]
    name_at = header.index("probe")
    coord_at = [header.index(f"{a}_probe") for a in AXIS]

    console = Console()
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
    for i in keep:
        table.add_column(header[i], justify="left" if i == name_at else "right")
    for row in shown:
        point = [row[i] for i in coord_at]
        cells = [f"{row[i]} ({', '.join(_fmt(v, '%g') or '-' for v in point)})"
                 if i == name_at else _fmt(row[i], "%.6g") for i in keep]
        table.add_row(*cells)
    console.print(table)
    if len(rows) > len(shown):
        console.print(f"[dim]... {len(rows) - len(shown)} more row(s); "
                      "use --output probes.csv for the full table[/dim]")
