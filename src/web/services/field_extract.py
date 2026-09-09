"""services/field_extract.py -- probe-point sampling and single-timestep mesh
export from PLT field data, for the Field -> Extract dialog.

A trimmed v1 of `field extract` (src/commands/field/extract_impl/command.py):
probe points only (no domain-box crop), full x/y/z points only (no partial-
axis probes), nearest-node or --interpolate. Reuses the CLI's own pure
helpers (extract_impl/probe.py, extract_impl/interp.py, plt/convert.py)
directly -- this module is the web-shaped orchestration around them, with
JSON-friendly errors (ValueError) instead of sys.exit.
"""

from pathlib import Path

import numpy as np

from ...commands.field.extract_impl import interp
from ...commands.field.extract_impl import probe as probe_util
from ...commands.field.locate import find_plt, list_steps, zone_index
from ...plt.convert import cell_name
from ...plt.fxplt import PltFile

_AXES_XYZ = np.array([0, 1, 2])


def resolve_steps(binary_dir, problem, timestep=None, t1=None, t2=None):
    """Which timesteps to act on -- a single step, a t1/t2 range (existing
    PLT steps within it), or None when nothing was given."""
    if timestep is not None:
        return [int(timestep)]
    if t1 is not None and t2 is not None:
        lo, hi = sorted((int(t1), int(t2)))
        return [s for s in list_steps(binary_dir, problem) if lo <= s <= hi]
    if t1 is not None:
        return [int(t1)]
    if t2 is not None:
        return [int(t2)]
    return None


def _resolve_columns(available, requested, zone_name):
    lower = {k.lower(): k for k in available}
    cols = []
    for v in requested:
        key = v if v in available else lower.get(v.lower())
        if key is None:
            raise ValueError(f"variable '{v}' is not available in zone '{zone_name}'. "
                             f"Available: {', '.join(sorted(available))}")
        cols.append(key)
    return cols


def run_probe_extract(binary_dir, problem, zone_name, variables, points, steps,
                      interpolate=False, nen=None):
    """(columns, rows, notes) for probe samples at `points` (an [P,3] array of
    full x/y/z coordinates) over `steps`. Raises ValueError on anything that
    stops the whole extraction (bad zone, no matching PLT files, an
    interpolate request with no pyvista installed); a probe that merely
    lands in a hole of the mesh becomes a note, not a failure.
    """
    points = np.asarray(points, dtype=float)
    if interpolate and not interp.available():
        raise ValueError('interpolate needs pyvista (pip install pyvista); '
                         'uncheck it to sample the nearest node instead')

    multi = len(steps) > 1
    cols = None
    rows = []
    fell_back, nudged, far_msgs = {}, {}, {}

    for ts in steps:
        plt_path = find_plt(binary_dir, problem, ts)
        if not plt_path:
            continue
        plt = PltFile(str(plt_path))
        zi = zone_index(plt, zone_name)
        if zi is None:
            names = ', '.join(z['name'] for z in plt.zones)
            raise ValueError(f"zone '{zone_name}' not found in {Path(plt_path).name}. "
                             f"Available: {names}")
        pts, conn, pdata, info = plt.load_zone(zi, nen=nen)
        columns = {plt.vars[0]: pts[:, 0], plt.vars[1]: pts[:, 1], plt.vars[2]: pts[:, 2]}
        columns.update(pdata)
        if cols is None:
            cols = _resolve_columns(columns, variables, zone_name)

        nearest = [probe_util.nearest_node(pts, pt, _AXES_XYZ) for pt in points]
        bounds = probe_util.point_bounds(pts)

        values, source = None, None
        if interpolate:
            if conn is None:
                raise ValueError(f"zone '{zone_name}' has no connectivity; "
                                 "--interpolate needs a volume zone")
            data = {c: columns[c] for c in cols}
            lo, hi = bounds
            spacing = probe_util.mean_spacing(lo, hi, len(pts)) or 0.0
            pad = max(4 * spacing, 4 * max(d for _, d in nearest), 1e-12)
            cell = cell_name(info['npe'], info['ztype'])
            values, source, moved = interp.sample(
                pts, conn, cell, data, points, pad, [i for i, _ in nearest])
            for pi, (src, dx) in enumerate(zip(source, moved), start=1):
                if src == interp.NUDGED:
                    nudged[pi] = max(nudged.get(pi, 0.0), float(dx))

        for pi, pt in enumerate(points, start=1):
            idx, dist = nearest[pi - 1]
            found = interpolate and source[pi - 1] != interp.MISSING
            row = {'probe': pi}
            if multi:
                row['timestep'] = ts
            if interpolate:
                row['source'] = source[pi - 1] or 'node'
                if not found:
                    fell_back[pi] = fell_back.get(pi, 0) + 1
            else:
                row['node'] = int(idx)
                row['x_node'] = float(pts[idx][0])
                row['y_node'] = float(pts[idx][1])
                row['z_node'] = float(pts[idx][2])
                row['distance'] = float(dist)
                far = probe_util.far_probe_warning(dist, *bounds, len(pts))
                if far:
                    far_msgs.setdefault(pi, far)   # first occurrence is enough to report
            for c in cols:
                row[c] = float(values[c][pi - 1]) if found else float(columns[c][idx])
            rows.append(row)

    if not rows:
        raise ValueError('nothing extracted (no matching PLT files)')

    notes = []
    for pi, moved in sorted(nudged.items()):
        notes.append(f"probe {pi}: moved up to {moved:g} inward to land inside an element "
                     "(that row is marked source=nudged)")
    for pi, count in sorted(fell_back.items()):
        notes.append(f"probe {pi}: inside the zone's bounds but in no element, at {count} "
                     "step(s) -- the nearest node was used instead")
    for pi, msg in sorted(far_msgs.items()):
        notes.append(f"probe {pi}: {msg}")

    columns_out = (['timestep'] if multi else []) + ['probe']
    columns_out += ['source'] if interpolate else ['node', 'x_node', 'y_node', 'z_node', 'distance']
    columns_out += cols
    return columns_out, rows, notes


def write_mesh_vtu(plt_path, zone_name, out_path, nen=None):
    """Write one zone's mesh (cells + every variable it carries) to a binary
    .vtu -- the "download this timestep" button, not a variable-filtered
    export like the CLI's own --variables list."""
    import meshio

    plt = PltFile(str(plt_path))
    zi = zone_index(plt, zone_name)
    if zi is None:
        names = ', '.join(z['name'] for z in plt.zones)
        raise ValueError(f"zone '{zone_name}' not found in {Path(plt_path).name}. Available: {names}")
    pts, conn, pdata, info = plt.load_zone(zi, nen=nen)
    if conn is None:
        raise ValueError(f"zone '{zone_name}' has no connectivity of its own "
                         "(it shares from another zone); cannot export a mesh")
    cname = cell_name(info['npe'], info['ztype'])
    meshio.Mesh(points=pts, cells=[(cname, conn)], point_data=pdata).write(str(out_path), binary=True)
