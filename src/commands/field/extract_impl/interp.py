"""Cell interpolation for `field extract --probe --interpolate`.

Values are taken from *inside* the element containing the probe -- VTK's probe
filter through pyvista, the same thing ParaView's "Probe Location" does -- rather
than from the nearest node. Only a small box of mesh around the probes is handed
to VTK, so a long time series stays quick on a multi-million-cell mesh; the box
grows and finally gives up on the whole zone if a probe is not found inside it.

A probe meant to sit on a wall usually lands a hair *outside* the faceted mesh
boundary, where VTK finds no element at all (its own tolerance settings do not
rescue this). Such probes are stepped a fraction of the way toward their nearest
node until they land inside one -- reported as `nudged`, never silently.
"""

import numpy as np

from ....plt.convert import crop_mesh

# VTK cell type ids for the element kinds src/plt/convert.py names.
VTK_CELL = {"line": 3, "triangle": 5, "quad": 9, "tetra": 10, "hexahedron": 12}
PAD_STEPS = (1.0, 4.0, None)                    # box padding factors; None = whole zone
NUDGE_FRACTIONS = (1e-6, 1e-3, 1e-2, 0.1)       # of the way to the nearest node

FOUND, NUDGED, MISSING = "cell", "nudged", ""


def available():
    """True if the VTK stack needed for interpolation is importable."""
    try:
        import pyvista  # noqa: F401
    except Exception:
        return False
    return True


def _box(targets, pad):
    """Axis-aligned box covering every probe, padded by `pad`."""
    lo = np.asarray(targets, dtype=float).min(axis=0) - pad
    hi = np.asarray(targets, dtype=float).max(axis=0) + pad
    return dict(xmin=lo[0], xmax=hi[0], ymin=lo[1], ymax=hi[1],
                zmin=lo[2], zmax=hi[2])


def _grid(pts, conn, cell, data):
    """Build the VTK unstructured grid for a (sub)mesh, carrying `data` on nodes."""
    import pyvista as pv

    npe = conn.shape[1]
    cells = np.column_stack([np.full(len(conn), npe, dtype=np.int64), conn]).ravel()
    types = np.full(len(conn), VTK_CELL[cell], dtype=np.uint8)
    grid = pv.UnstructuredGrid(cells, types, np.asarray(pts, dtype=float))
    for name, values in data.items():
        grid.point_data[name] = np.asarray(values, dtype=float)
    return grid


def _probe(pts, conn, cell, data, targets, pad):
    """Interpolate `data` at `targets` (optionally on a box-cropped submesh).

    Returns (values{name: array}, valid mask), or None when the box holds no cells.
    """
    import pyvista as pv

    if pad is not None:
        pts, conn, data = crop_mesh(pts, conn, data, _box(targets, pad))
        if len(conn) == 0:
            return None
    out = pv.PolyData(np.asarray(targets, dtype=float)).sample(_grid(pts, conn, cell, data))
    valid = np.asarray(out.point_data["vtkValidPointMask"], dtype=bool)
    return {name: np.asarray(out.point_data[name], dtype=float) for name in data}, valid


def _widen(pts, conn, cell, data, targets, pad):
    """Interpolate, growing the search box until every probe lands (or the zone runs out)."""
    result = None
    for factor in PAD_STEPS:
        attempt = _probe(pts, conn, cell, data, targets,
                         None if factor is None else pad * factor)
        if attempt is None:
            continue
        result = attempt
        if result[1].all():
            break
    if result is None:                          # no cells anywhere near the probes
        return ({name: np.zeros(len(targets)) for name in data},
                np.zeros(len(targets), dtype=bool))
    return result


def interior_anchor(pts, conn, node):
    """A point strictly inside the mesh next to `node`: centroid of its elements.

    Aiming a boundary probe at its nearest *node* is useless -- that node lies on
    the boundary too, so no step short of landing on it gets inside. The centroid
    of the elements touching it is genuinely interior, roughly half a cell away.
    """
    rows = np.flatnonzero((conn == node).any(axis=1))
    if not len(rows):
        return None
    return pts[conn[rows]].reshape(-1, 3).mean(axis=0)


def sample(pts, conn, cell, data, targets, pad, anchor_nodes=None):
    """Interpolate at `targets`, nudging boundary probes inside the mesh.

    `anchor_nodes` are the probes' nearest-node indices. A probe that lands in no
    element -- what VTK reports for a point even 1e-9 outside a faceted wall -- is
    stepped toward the interior by growing fractions until it lands in one; a
    probe in a genuine hole never lands and is left to the caller.
    Returns (values, source, moved) where source[i] is 'cell', 'nudged' or ''
    (in no element) and moved[i] is how far probe i was displaced.
    """
    if cell not in VTK_CELL:
        raise ValueError(f"cannot interpolate on '{cell}' cells")
    targets = np.asarray(targets, dtype=float)
    values, valid = _widen(pts, conn, cell, data, targets, pad)
    source = [FOUND if ok else MISSING for ok in valid]
    moved = np.zeros(len(targets))
    if anchor_nodes is None or valid.all():
        return values, source, moved

    anchors, pending = {}, []
    for i in np.flatnonzero(~valid):
        anchor = interior_anchor(pts, conn, anchor_nodes[i])
        if anchor is not None:
            anchors[i] = anchor
            pending.append(i)
    for fraction in NUDGE_FRACTIONS:
        if not pending:
            break
        shifted = np.array([targets[i] + fraction * (anchors[i] - targets[i])
                            for i in pending])
        retry, ok = _widen(pts, conn, cell, data, shifted, pad)
        for slot, hit in enumerate(ok):
            if not hit:
                continue
            i = pending[slot]
            for name in values:
                values[name][i] = retry[name][slot]
            source[i] = NUDGED
            moved[i] = float(np.linalg.norm(shifted[slot] - targets[i]))
        pending = [i for slot, i in enumerate(pending) if not ok[slot]]
    return values, source, moved


def check_cells(pts, conn, cell, data, targets, values, rtol=1e-6):
    """Complaints where an interpolated value fell outside its element's nodal range.

    Linear and trilinear shape functions are non-negative inside an element, so an
    interpolated value must be a convex combination of that element's nodal values.
    Anything outside that range means the element was not really located or the
    connectivity is wrong -- most often a hex mesh mislabelled as tetrahedra (see
    `field info --checks` and --nen). Runs on the whole zone, so call it once.
    """
    grid = _grid(pts, conn, cell, data)
    problems = []
    for i, target in enumerate(targets):
        cid = int(grid.find_containing_cell(np.asarray(target, dtype=float)))
        if cid < 0:
            continue
        nodes = conn[cid]
        for name, arr in data.items():
            lo, hi = float(np.min(arr[nodes])), float(np.max(arr[nodes]))
            slack = rtol * max(abs(lo), abs(hi), 1.0)
            got = float(values[name][i])
            if not (lo - slack <= got <= hi + slack):
                problems.append(f"probe {i + 1}: interpolated {name}={got:g} is outside its "
                                f"element's nodal range [{lo:g}, {hi:g}]")
    return problems
