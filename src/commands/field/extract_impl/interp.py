"""Cell interpolation for `field extract --probe --interpolate`.

Values are taken from *inside* the element containing the probe -- VTK's probe
filter through pyvista, the same thing ParaView's "Probe Location" does -- rather
than from the nearest node. Only a small box of mesh around the probes is handed
to VTK, so a long time series stays quick on a multi-million-cell mesh; the box
grows and finally gives up on the whole zone if a probe is not found inside it.
"""

import numpy as np

from ....plt.convert import crop_mesh

# VTK cell type ids for the element kinds src/plt/convert.py names.
VTK_CELL = {"line": 3, "triangle": 5, "quad": 9, "tetra": 10, "hexahedron": 12}
PAD_STEPS = (1.0, 4.0, None)      # box padding factors; None = the whole zone


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


def _sample(pts, conn, cell, data, targets, pad):
    """Interpolate `data` at `targets` on the mesh (optionally cropped to a box).

    Returns (values{name: array}, valid mask), or None when the box holds no cells.
    """
    import pyvista as pv

    if pad is not None:
        pts, conn, data = crop_mesh(pts, conn, data, _box(targets, pad))
        if len(conn) == 0:
            return None

    npe = conn.shape[1]
    cells = np.column_stack([np.full(len(conn), npe, dtype=np.int64), conn]).ravel()
    types = np.full(len(conn), VTK_CELL[cell], dtype=np.uint8)
    grid = pv.UnstructuredGrid(cells, types, np.asarray(pts, dtype=float))
    for name, values in data.items():
        grid.point_data[name] = np.asarray(values, dtype=float)

    out = pv.PolyData(np.asarray(targets, dtype=float)).sample(grid)
    valid = np.asarray(out.point_data["vtkValidPointMask"], dtype=bool)
    return {name: np.asarray(out.point_data[name], dtype=float) for name in data}, valid


def sample(pts, conn, cell, data, targets, pad):
    """Interpolate at `targets`, widening the search box until every probe lands.

    `pad` is the starting half-width of the box around the probes -- a few node
    spacings. Returns (values, valid); `valid` is False for probes that lie in no
    cell at all (a hole in the mesh, or outside its boundary), which the caller
    handles.
    """
    if cell not in VTK_CELL:
        raise ValueError(f"cannot interpolate on '{cell}' cells")
    result = None
    for factor in PAD_STEPS:
        attempt = _sample(pts, conn, cell, data, targets,
                          None if factor is None else pad * factor)
        if attempt is None:
            continue
        result = attempt
        if result[1].all():
            break
    if result is None:                      # no cells anywhere near the probes
        empty = {name: np.zeros(len(targets)) for name in data}
        return empty, np.zeros(len(targets), dtype=bool)
    return result
