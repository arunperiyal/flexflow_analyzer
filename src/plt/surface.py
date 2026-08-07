"""Surface-element geometry: areas, normals, and which side of them the fluid is on.

Everything here works off the mesh itself, so it holds for any boundary zone --
a circular cylinder, a grooved section, a hull -- with no assumption that the
cross-section is round or that facets are evenly sized.
"""

import numpy as np

TRI, QUAD = 3, 4


def element_geometry(pts, conn):
    """(centroid, area, unit normal) for every surface element.

    Quads use the diagonal cross product -- exact for a planar quad, and the usual
    mean normal for a warped one -- triangles the edge cross product. The sign
    follows the node ordering and carries no physical meaning yet; pass the result
    through orient_outward() before using it.
    """
    q = np.asarray(pts, dtype=float)[conn]
    npe = conn.shape[1]
    if npe == QUAD:
        vec = 0.5 * np.cross(q[:, 2] - q[:, 0], q[:, 3] - q[:, 1])
    elif npe == TRI:
        vec = 0.5 * np.cross(q[:, 1] - q[:, 0], q[:, 2] - q[:, 0])
    else:
        raise ValueError(f"surface elements must be triangles or quads, got {npe} nodes")
    area = np.linalg.norm(vec, axis=1)
    unit = np.zeros_like(vec)
    good = area > 0
    unit[good] = vec[good] / area[good, None]
    return q.mean(axis=1), area, unit


def adjacent_cells(surface_conn, volume_conn):
    """Volume cell owning each surface element (-1 where none was found).

    A boundary face is exactly the node set it shares with one volume cell, so the
    match is by node set -- no geometric tolerance, nothing to tune.
    """
    npe = surface_conn.shape[1]
    on = np.isin(volume_conn, np.unique(surface_conn))
    owner = {}
    for cell in np.flatnonzero(on.sum(axis=1) == npe):
        owner.setdefault(tuple(sorted(volume_conn[cell][on[cell]].tolist())), cell)
    return np.array([owner.get(tuple(sorted(e.tolist())), -1) for e in surface_conn],
                    dtype=np.int64)


def orient_outward(normal, centroid, anchor):
    """Flip normals to point from the surface toward `anchor` -- the volume side.

    A body is a hole in the mesh: the fluid cells sit outside it, so the normal
    facing the adjacent cell is the body's outward normal, the one the pressure
    force -p n dA is written against.
    """
    inward = ((np.asarray(anchor, dtype=float) - centroid) * normal).sum(axis=1) < 0
    return np.where(inward[:, None], -normal, normal)


def orient_by_divergence(normal, centroid, area):
    """Orient a whole zone at once when no volume mesh is available.

    Sum(c.n)dA is +3V for outward normals on a closed surface, and keeps its sign
    on a tube or a cap as long as the surface wraps the body. Coarser than
    orient_outward(): one sign for the zone, so a surface folded back on itself
    can defeat it.
    """
    if float((centroid * normal * area[:, None]).sum()) < 0:
        return -normal
    return normal


def pressure_force(pressure_at_nodes, conn, area, normal):
    """Pressure force on each element: -p n dA, with p averaged over its nodes.

    Nodal averaging is exact for a field varying linearly across the facet. This is
    the pressure (form) contribution only -- viscous skin friction needs velocity
    gradients from the volume mesh and is not included.
    """
    face_p = np.asarray(pressure_at_nodes, dtype=float)[conn].mean(axis=1)
    return face_p, -(face_p * area)[:, None] * normal
