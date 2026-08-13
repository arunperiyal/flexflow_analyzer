"""
derive.py  --  Variables computed from the ones a PLT already carries.

A vortex-identification criterion is a function of the velocity gradient, so it
can be worked out from U/V/W rather than written by the solver. lambda2 is the
one FlexFlow's cases lack: the solver writes QCriterion but not lambda2, and the
two disagree about which structures count as vortices, so having only one of
them decides the picture for you.

Everything here needs pyvista (for the gradient on an unstructured mesh) and is
imported lazily, so the rest of the `plt` package works without it.

    ensure(mesh, "lambda2")   ->  mesh gains a "lambda2" point array
"""

import numpy as np


def _velocity(mesh):
    """The velocity vector, assembled from whatever the file calls it."""
    for names in (("U", "V", "W"), ("u", "v", "w"),
                  ("VelocityX", "VelocityY", "VelocityZ")):
        if all(n in mesh.point_data for n in names):
            return np.column_stack([mesh.point_data[n] for n in names]), names
    raise ValueError(
        "no velocity in this mesh: expected U,V,W (or u,v,w / VelocityX..Z), "
        "found " + ", ".join(sorted(mesh.point_data.keys())))


def _velocity_gradient(mesh, log=print):
    """d(u_i)/d(x_j) at every node, as an (n, 3, 3) array."""
    vel, names = _velocity(mesh)
    log("computing the velocity gradient from %s over %d nodes"
        % ("/".join(names), mesh.n_points))
    work = mesh.copy(deep=False)
    work.point_data["__velocity__"] = vel
    out = work.compute_derivative(scalars="__velocity__", gradient=True)
    return np.asarray(out["gradient"]).reshape(-1, 3, 3)


def lambda2(mesh, log=print):
    """The lambda2 vortex criterion (Jeong & Hussain 1995).

    Split the velocity gradient into strain S and rotation Omega, and take the
    middle eigenvalue of S^2 + Omega^2. It is negative inside a vortex core, so
    contour it at a small negative value -- the opposite sign convention from
    QCriterion, which is positive there.

    S^2 + Omega^2 is symmetric, so eigvalsh applies: real eigenvalues, sorted
    ascending, and much faster than the general solver.
    """
    g = _velocity_gradient(mesh, log)
    gt = np.transpose(g, (0, 2, 1))
    strain = 0.5 * (g + gt)
    rotation = 0.5 * (g - gt)
    a = strain @ strain + rotation @ rotation
    values = np.linalg.eigvalsh(a)          # ascending: [l3, l2, l1]
    l2 = values[:, 1].astype(np.float32)
    log("lambda2: %.4g .. %.4g (%.1f%% of nodes negative -- vortex cores)"
        % (l2.min(), l2.max(), 100.0 * float((l2 < 0).mean())))
    return l2


# name -> (function, what it needs, one-line description)
DERIVED = {
    "lambda2": (lambda2, "U,V,W",
                "Jeong & Hussain vortex criterion; negative in a vortex core"),
}


def is_derived(name):
    return name in DERIVED


def names():
    return sorted(DERIVED)


def describe():
    """(name, inputs, description) for each derived variable, for listings."""
    return [(n, DERIVED[n][1], DERIVED[n][2]) for n in names()]


def ensure(mesh, name, log=print):
    """Add `name` to the mesh if it is missing and we know how to compute it.

    Returns True when something was computed, False when it was already there.
    Raises for a name that is neither present nor derivable, since the caller
    asked for a variable that will not exist however long it waits.
    """
    if name in mesh.point_data:
        return False
    if name not in DERIVED:
        raise ValueError(
            "'%s' is not in this mesh and is not a variable FlexFlow can "
            "compute. Present: %s. Computable: %s."
            % (name, ", ".join(sorted(mesh.point_data.keys())),
               ", ".join(names()) or "none"))
    mesh.point_data[name] = DERIVED[name][0](mesh, log)
    return True
