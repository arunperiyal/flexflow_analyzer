"""
Viscous wall shear, read straight out of the vorticity the solver already wrote.

At a no-slip wall the velocity vanishes on the surface, so every tangential
derivative of it does too and the only surviving gradient is the one normal to
the wall. That collapses the stress to an identity rather than an approximation:

    tau_w = mu_eff * (omega x n)        n the unit normal out of the body

which is exact, not a reconstruction. Take n = +y and u = (gamma*y, 0, 0): the
only non-zero vorticity component is omega_z = -gamma, omega x n = (gamma, 0, 0),
and tau_w = mu*gamma along x -- the answer by inspection.

It matters because the alternative is reconstructing a velocity gradient on an
unstructured mesh at the one place the mesh is worst conditioned. `xVor`, `yVor`
and `zVor` are already in the PLT, so nothing has to be reconstructed and nothing
outside numpy has to be loaded to do it.

The turbulence model is the one thing that could spoil it: mu_eff = mu + rho*nu_t,
and nu_t is not zero everywhere. At a resolved no-slip wall it is, and that is
checked and reported per run rather than assumed.
"""

import numpy as np

# A nodal field averaged onto elements is exact enough here -- the shear varies
# smoothly over a facet -- and it is what keeps the table one row per element,
# matching the force tables so that one reader serves both.
VORTICITY_VARS = ("xVor", "yVor", "zVor")
DISPLACEMENT_VARS = ("dispX", "dispY", "dispZ")

# Above this many distinct stations the mesh is not layered in any useful sense,
# and the axis displacement is averaged over equal bins instead.
MAX_RINGS = 2000
FALLBACK_RINGS = 200


class WallShearError(Exception):
    """The PLT does not carry what a wall shear needs."""


def element_mean(pdata, names, conn):
    """A nodal vector field averaged onto each element, as an (n, 3) array."""
    missing = [name for name in names if name not in pdata]
    if missing:
        return None
    return np.column_stack([pdata[name][conn].mean(axis=1) for name in names])


def effective_viscosity(pdata, conn, mu, rho):
    """(mu_eff per element, max nu_t seen at the wall).

    `eddy` is a *kinematic* eddy viscosity -- the .def initialises it to 5*MU/RHO
    -- so it enters as rho*nu_t. At a wall a resolved model drives it to zero and
    mu_eff is just mu; the maximum is returned so a run can say that rather than
    assume it.
    """
    if "eddy" not in pdata:
        return np.full(len(conn), mu, dtype=float), None
    nu_t = pdata["eddy"][conn].mean(axis=1)
    return mu + rho * nu_t, float(np.abs(nu_t).max())


def wall_shear_stress(omega, normal, mu_eff):
    """tau_w = mu_eff * (omega x n), per element.

    `normal` must already point out of the body, which is how the force path
    orients it -- against the adjacent volume cell. A flipped normal flips the
    shear, and a flipped shear puts the separation point on the wrong side.
    """
    return mu_eff[:, None] * np.cross(omega, normal)


def axis_displacement(station, disp, area, logger):
    """How far the body's axis has moved, at each element's station.

    Averaged around the ring rather than taken per facet. A facet sits on the
    surface, not on the axis, so its own displacement carries whatever the
    surface is doing locally; the ring mean of *displacement* does not, because
    the displacement field is smooth along and around the span whatever shape the
    surface is. That is what makes this work on a grooved body, where the facets
    are not symmetric about the axis and the ring mean of *coordinates* drifts off
    it by an amount that varies with angle -- which reads as a separation shift
    that is not there.

    Interpolated back to each element's own station afterwards, so the result does
    not step from ring to ring.
    """
    key = np.round(station, 6)
    groups, inverse = np.unique(key, return_inverse=True)
    if len(groups) > MAX_RINGS:
        # Not a layered mesh: bin equally instead. The interpolation afterwards
        # means the exact bin count barely shows.
        edges = np.linspace(station.min(), station.max(), FALLBACK_RINGS + 1)
        inverse = np.clip(np.searchsorted(edges, station, side="right") - 1,
                          0, FALLBACK_RINGS - 1)
        groups = 0.5 * (edges[:-1] + edges[1:])
        logger.info(f"axis displacement averaged over {FALLBACK_RINGS} equal bins "
                    f"({len(np.unique(key)):,} distinct stations is not a layered mesh)")
    else:
        logger.info(f"axis displacement averaged over {len(groups):,} element ring(s)")

    weight = np.bincount(inverse, weights=area, minlength=len(groups))
    weight[weight == 0] = 1.0
    mean = np.column_stack([
        np.bincount(inverse, weights=area * disp[:, i], minlength=len(groups)) / weight
        for i in range(3)])
    return np.column_stack([np.interp(station, groups, mean[:, i]) for i in range(3)])


def ring_centres(centroid, station, area, disp, reference, logger, warned):
    """The point on the deformed axis opposite each element.

    Built as the *declared* axis plus the displacement of it, rather than measured
    from the surface: the declared axis is exact whatever the surface looks like,
    and the displacement is smooth. Measuring the centre from the ring's own
    coordinates is only right for a body whose facets are symmetric about the
    axis, which a grooved one is not.
    """
    if disp is not None and reference.origin is not None:
        axis = reference.origin + station[:, None] * reference.span
        return axis + axis_displacement(station, disp, area, logger)

    if not warned:
        why = ("the PLT carries no dispX/dispY/dispZ" if disp is None
               else "the body declares no origin in domain.yml")
        logger.warning(
            f"{why}, so each section's centre is measured from its own facets "
            "instead. That is right for a body whose section is symmetric about "
            "its axis and wrong for a grooved one, where it drifts with angle and "
            "shifts the separation point."
            + ("" if disp is None else
               " Set it with `case domain body --origin X,Y,Z`."))
        warned.append(True)

    # Fall back to the ring mean of coordinates, perpendicular to the span.
    key = np.round(station, 6)
    groups, inverse = np.unique(key, return_inverse=True)
    weight = np.bincount(inverse, weights=area, minlength=len(groups))
    weight[weight == 0] = 1.0
    mean = np.column_stack([
        np.bincount(inverse, weights=area * centroid[:, i], minlength=len(groups))
        / weight for i in range(3)])
    centre = mean[inverse]
    # Keep the station exactly where the element is; only the off-axis part is
    # being estimated.
    along = (centre @ reference.span) - station
    return centre - along[:, None] * reference.span


def azimuthal_frame(centroid, centre, reference):
    """(theta in degrees, radial unit vector, azimuthal unit vector) per element.

    theta is 0 at the forward stagnation point -- the upstream side, facing the
    free stream -- and increases towards the lift direction, so the two shear
    layers come out as a positive and a negative branch and a separation angle
    reads the way it is drawn in a paper. That zero and that sense are
    conventions, not data, so they are written into every table's header.
    """
    radial = centroid - centre
    radial = radial - (radial @ reference.span)[:, None] * reference.span
    norm = np.linalg.norm(radial, axis=1)
    norm[norm == 0] = 1.0
    radial = radial / norm[:, None]

    upstream = -reference.flow          # theta = 0 points into the oncoming flow
    theta = np.degrees(np.arctan2(radial @ reference.lift, radial @ upstream))
    # span x radial: at theta = 0 this is the lift direction, which is +theta.
    azimuthal = np.cross(reference.span, radial)
    return theta, radial, azimuthal


def compute(pdata, conn, centroid, area, normal, reference, mu, logger, warned):
    """Everything a wall-shear table holds, for one timestep.

    Returns a dict of per-element arrays plus the run-level facts a header has to
    record: the effective viscosity actually used, and the largest eddy viscosity
    seen at the wall, which is what says whether it was mu or not.
    """
    omega = element_mean(pdata, VORTICITY_VARS, conn)
    if omega is None:
        raise WallShearError(
            "the PLT carries no xVor/yVor/zVor, so there is no wall shear to read. "
            "The solver writes them when vorticity is among its outputs; without "
            "them the shear would have to come from a velocity gradient "
            "reconstructed at the wall, which this does not do.")

    mu_eff, nu_t_max = effective_viscosity(pdata, conn, mu, reference.rho)
    tau = wall_shear_stress(omega, normal, mu_eff)

    station = centroid @ reference.span
    disp = element_mean(pdata, DISPLACEMENT_VARS, conn)
    centre = ring_centres(centroid, station, area, disp, reference, logger, warned)
    theta, radial, azimuthal = azimuthal_frame(centroid, centre, reference)

    pressure = pdata.get("Pressure")
    face_p = (pressure[conn].mean(axis=1) if pressure is not None
              else np.zeros(len(conn)))

    return {
        "omega": omega,
        "tau": tau,
        "tau_theta": np.einsum("ij,ij->i", tau, azimuthal),
        "tau_axial": tau @ reference.span,
        "magnitude": np.linalg.norm(tau, axis=1),
        "theta": theta,
        "station": station,
        "pressure": face_p,
        "mu_eff": mu_eff,
        "nu_t_max": nu_t_max,
        "has_pressure": pressure is not None,
    }
