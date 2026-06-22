"""
convert.py  --  PLT -> VTU conversion and a size / element-type audit.

No Tecplot dependency; uses fxplt (numpy) to read and meshio to write.
"""
import os

import numpy as np

from .fxplt import PltFile, NPE

VTK_CELL_BY_NPE = {2: "line", 3: "triangle", 8: "hexahedron"}
_BOX_AXES = (("xmin", 0, "ge"), ("xmax", 0, "le"), ("ymin", 1, "ge"),
             ("ymax", 1, "le"), ("zmin", 2, "ge"), ("zmax", 2, "le"))


def has_domain(domain):
    return bool(domain) and any(domain.get(k) is not None for k, _, _ in _BOX_AXES)


def node_in_box(pts, domain):
    """Boolean mask of nodes inside the (partial) axis-aligned box; None bounds open."""
    m = np.ones(len(pts), dtype=bool)
    for key, axis, op in _BOX_AXES:
        v = domain.get(key)
        if v is None:
            continue
        m &= (pts[:, axis] >= v) if op == "ge" else (pts[:, axis] <= v)
    return m


def crop_mesh(pts, conn, pdata, domain):
    """Keep cells whose nodes are all inside the box; remap to a compact mesh."""
    inside = node_in_box(pts, domain)
    conn = conn[inside[conn].all(axis=1)]
    used = np.unique(conn)
    remap = np.full(len(pts), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    return pts[used], remap[conn], {k: v[used] for k, v in pdata.items()}


def write_point_cloud(path, points, point_data):
    """Write a point cloud: .vtu/.vtk via meshio (vertex cells), .vtp via pyvista."""
    ext = os.path.splitext(str(path))[1].lower()
    if ext == ".vtp":
        try:
            import pyvista as pv
        except ImportError:
            raise ValueError(".vtp output needs pyvista; use .vtu or .vtk instead")
        cloud = pv.PolyData(np.asarray(points, dtype=float))
        for k, v in point_data.items():
            cloud.point_data[k] = v
        cloud.save(str(path))
    else:
        import meshio
        cells = [("vertex", np.arange(len(points), dtype=np.int64).reshape(-1, 1))]
        meshio.Mesh(points=points, cells=cells, point_data=point_data).write(str(path))


def cell_name(npe, ztype):
    """VTK cell name from nodes-per-element, disambiguating npe == 4."""
    if npe == 4:
        return "quad" if ztype == 3 else "tetra"
    return VTK_CELL_BY_NPE.get(npe, "?")


def audit(p, zi, nen=None):
    """Byte-accounting + element type for one zone (no data load).

    `p` is a PltFile. Returns a dict; `truncated` True means the file is shorter
    than the zone requires for `npe` nodes/element (often a wrong nen, not a
    real truncation).
    """
    fsize = os.path.getsize(p.path)
    z = p.zones[zi]
    npts, nelem, ztype = z["npts"], z["nelem"], z["ztype"]
    declared = NPE.get(ztype, 8)
    npe = nen if nen is not None else declared
    nvar = len(p.vars)
    var_bytes = nvar * npts * 4
    conn_bytes = nelem * npe * 4
    need = var_bytes + conn_bytes
    return dict(file=p.path, file_size=fsize, nvar=nvar, npts=npts, nelem=nelem,
                ztype=ztype, npe=npe, declared_npe=declared, nen_override=nen,
                cell=cell_name(npe, ztype), var_bytes=var_bytes,
                conn_bytes=conn_bytes, zone_need=need,
                short_by=max(0, need - fsize), truncated=fsize < need,
                zone=zi, zone_name=z["name"])


def to_vtu(plt_path, out_path=None, zone=None, nen=None, domain=None):
    """Convert one volume zone of a .plt to a binary .vtu, optionally cropped to a box.

    Returns (out_path, info) where info is the dict from PltFile.load_zone plus
    'cell', 'out', 'cells_out' and (if cropped) 'cropped'.
    """
    import meshio

    p = PltFile(plt_path)
    zi = zone if zone is not None else p.first_volume_zone()
    pts, conn, pdata, info = p.load_zone(zi, nen=nen)
    if conn is None:
        raise ValueError("zone %d shares connectivity from another zone; cannot export" % zi)
    if has_domain(domain):
        pts, conn, pdata = crop_mesh(pts, conn, pdata, domain)
        info["cropped"] = True
    info["cells_out"] = len(conn)
    cname = cell_name(info["npe"], info["ztype"])
    out = out_path or (os.path.splitext(plt_path)[0] + ".vtu")
    meshio.Mesh(points=pts, cells=[(cname, conn)], point_data=pdata).write(out, binary=True)
    info["cell"] = cname
    info["out"] = out
    return out, info
