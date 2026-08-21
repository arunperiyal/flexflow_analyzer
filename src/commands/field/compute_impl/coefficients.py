"""
Force coefficients: the reference state a Cd means, and the sections it is cut into.

A force is a fact about the mesh -- `field compute force` needs nothing but the
PLT to produce one. A *coefficient* is not: Cd = F / (½ρU²A) needs a density, a
free-stream speed, a reference area and a direction to call drag, none of which
are in the PLT. Every one of them is somewhere in the case, though, so none of
them has to be typed:

    density                the .def -- through its own chain of model names
    free stream            domain.yml -- the field's declared velocity
    diameter, length, axis domain.yml -- the body's geometry
    drag / lift directions the free-stream vector, and the body's own axis

The free stream is *declared*, not read from the .def. The nearest thing the .def
has is `initField( velocity )`, and that is the initial condition: a case started
from rest, or ramped up at the inlet, has one that says nothing about the flow the
body ends up in. It would be right often enough to be trusted and wrong quietly
enough to matter.

That is the whole reason this needs `case domain`. What cannot be found is
reported by name, with the command that sets it, rather than defaulted: a Cd
normalised by a guessed diameter is wrong by exactly the factor nobody notices.
"""

from dataclasses import dataclass, field as _field
from pathlib import Path

import numpy as np

AXIS_VECTORS = {
    'x': (1.0, 0.0, 0.0), '+x': (1.0, 0.0, 0.0), '-x': (-1.0, 0.0, 0.0),
    'y': (0.0, 1.0, 0.0), '+y': (0.0, 1.0, 0.0), '-y': (0.0, -1.0, 0.0),
    'z': (0.0, 0.0, 1.0), '+z': (0.0, 0.0, 1.0), '-z': (0.0, 0.0, -1.0),
}


class ReferenceError(Exception):
    """Something a coefficient needs is missing, and guessing it would be wrong."""


@dataclass
class Reference:
    """Everything a coefficient is measured against, and where each part came from."""

    body: str
    span: np.ndarray            # unit vector sections are cut along
    flow: np.ndarray            # unit free-stream direction -> drag
    lift: np.ndarray            # flow x span -> lift
    rho: float
    u_inf: float
    diameter: float
    length: float
    labels: dict = _field(default_factory=dict)
    sources: dict = _field(default_factory=dict)

    @property
    def dynamic_pressure(self) -> float:
        return 0.5 * self.rho * self.u_inf ** 2

    def describe(self) -> list:
        """The reference state as '#' header lines, each saying where it came from."""
        return [
            f"rho: {self.rho:g}   U_inf: {self.u_inf:g}   "
            f"q = 0.5*rho*U^2: {self.dynamic_pressure:g}",
            f"diameter: {self.diameter:g}   length: {self.length:g}   "
            f"reference area: D*L = {self.diameter * self.length:g}",
            f"span axis: {self.labels.get('span')}   "
            f"drag (flow): {self.labels.get('flow')}   "
            f"lift: {self.labels.get('lift')}",
            "sources: " + "; ".join(f"{k} = {v}" for k, v in self.sources.items()),
        ]


def axis_vector(value, what):
    """A direction written as '+x', 'z' or [a, b, c], as a unit vector.

    Both forms are accepted because both are how a direction gets written: an
    axis name by a person at the prompt, a vector by domain.yml when the body is
    not axis-aligned.
    """
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip().lower()
        if text in AXIS_VECTORS:
            return np.array(AXIS_VECTORS[text], dtype=float)
        if text.startswith('['):
            import yaml
            try:
                value = yaml.safe_load(text)
            except yaml.YAMLError:
                value = None
        else:
            raise ReferenceError(
                f"{what} '{value}' is not a direction. Give an axis "
                f"(x, -x, y, -y, z, -z) or a vector like '[1, 0, 0]'.")
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or not all(isinstance(c, (int, float)) and not isinstance(c, bool)
                       for c in value)):
        raise ReferenceError(f"{what} must be an axis (x, -x, y, ...) or three "
                             f"numbers, not {value!r}")
    vector = np.asarray(value, dtype=float)
    norm = np.linalg.norm(vector)
    if norm == 0:
        raise ReferenceError(f"{what} is a zero vector, which points nowhere")
    return vector / norm


def axis_label(vector):
    """A unit vector as '+x' when it is an axis, else '[a, b, c]' -- for the header."""
    for name in ('+x', '-x', '+y', '-y', '+z', '-z'):
        if np.allclose(vector, AXIS_VECTORS[name], atol=1e-9):
            return name
    return "[" + ", ".join(f"{c:.4g}" for c in vector) + "]"


def _domain_for(case_dir, zone):
    """The case's domain.yml and the body `zone` names, or why neither can be had."""
    from ....core.domain import FILENAME, DomainConfig, DomainError

    case_dir = Path(case_dir)
    try:
        domain = DomainConfig.find(case_dir)
    except DomainError as exc:
        raise ReferenceError(str(exc))
    if not domain.exists:
        raise ReferenceError(
            f"No {FILENAME} in {case_dir.name}, so there is no free stream, diameter, "
            f"length or axis to normalise by. Write one with "
            f"`case domain {case_dir.name} --init`, then declare the two things the "
            "case does not state: `case domain field --velocity X,Y,Z` and "
            f"`case domain body --name {zone} --radius R`.")
    body = domain.body(zone)
    if body is None:
        raise ReferenceError(
            f"No body in {FILENAME} matches '{zone}'. Declared: "
            f"{', '.join(domain.body_names()) or 'none'}. A body resolves by name, "
            "geotag or plttag; `case domain body --list` shows all three.")
    return domain, body


def _free_stream(domain, case_dir):
    """The field's declared velocity, as three numbers, or why it cannot be used."""
    how = f"Declare it with `case domain field {Path(case_dir).name} --velocity X,Y,Z`."
    velocity = domain.velocity
    if velocity is None:
        raise ReferenceError(
            "domain.yml declares no velocity for the field, and a coefficient needs "
            f"one: its direction is what drag is measured along, its magnitude the U "
            f"in 0.5*rho*U^2. {how}")
    if (not isinstance(velocity, list) or len(velocity) != 3
            or not all(isinstance(c, (int, float)) and not isinstance(c, bool)
                       for c in velocity)):
        raise ReferenceError(f"domain.yml has velocity {velocity!r} for the field, "
                             f"which is not three numbers. {how}")
    if not any(velocity):
        raise ReferenceError(
            "domain.yml gives the field a velocity of zero, so there is no flow "
            f"direction and U_inf is 0, which every coefficient would divide by. {how}")
    return velocity


def _required(body, key, case_dir, zone, how):
    """A geometry value that must be there, or an error naming the command that sets it."""
    value = (body.get('geometry') or {}).get(key)
    if value is None:
        raise ReferenceError(
            f"Body '{body.get('name')}' has no {key} in domain.yml, and a coefficient "
            f"cannot be normalised without it. Set it with "
            f"`case domain body {Path(case_dir).name} --name {body.get('name')} {how}`.")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferenceError(f"Body '{body.get('name')}' has {key} = {value!r} in "
                             "domain.yml, which is not a number")
    if value <= 0:
        raise ReferenceError(f"Body '{body.get('name')}' has {key} = {value:g} in "
                             "domain.yml; it must be positive")
    return float(value)


def resolve(case_dir, zone, args, logger):
    """Assemble the Reference for one body, from domain.yml and the .def.

    `--direction` and `--flow` override the two directions; everything else is
    read from the case. Raises ReferenceError naming what is missing and the
    command that supplies it.
    """
    from ....core.def_config import DefConfig
    from ....core.simflow_config import SimflowConfig

    case_dir = Path(case_dir)
    domain, body = _domain_for(case_dir, zone)
    name = body.get('name') or zone
    sources = {}

    radius = _required(body, 'radius', case_dir, zone, '--radius R')
    length = _required(body, 'length', case_dir, zone, '--length L')
    sources['diameter'] = f"2 x domain.yml radius ({radius:g})"
    sources['length'] = "domain.yml"

    # -- span: what sections are cut along -------------------------------------
    if getattr(args, 'direction', None):
        span = axis_vector(args.direction, '--direction')
        sources['span axis'] = "--direction"
    else:
        declared = (body.get('geometry') or {}).get('axis')
        if declared is None:
            raise ReferenceError(
                f"Body '{name}' has no axis in domain.yml and --direction was not "
                "given, so there is no direction to cut sections along. Set it with "
                f"`case domain body {case_dir.name} --name {name} --axis +x`, or pass "
                "--direction.")
        span = axis_vector(declared, "domain.yml axis")
        sources['span axis'] = "domain.yml"

    # -- the .def: density and free stream -------------------------------------
    try:
        problem = SimflowConfig.find(case_dir).problem
    except Exception:
        problem = None
    cfg = DefConfig.find(case_dir, problem)
    if not cfg.exists:
        raise ReferenceError(f"No .def file in {case_dir}, so there is no density or "
                             "free-stream speed to normalise by")

    rho = cfg.density()
    if rho is None:
        raise ReferenceError(
            f"{cfg.path.name} gives no fluid density: the chain elementGroup -> "
            "elementProperty -> materialModel -> densityModel does not lead to a "
            "number. Check it with `def var`.")
    if rho <= 0:
        raise ReferenceError(f"{cfg.path.name} gives a density of {rho:g}")
    sources['rho'] = f"{cfg.path.name} densityModel"

    stream = _free_stream(domain, case_dir)
    speed = float(np.linalg.norm(stream))

    if getattr(args, 'flow', None):
        flow = axis_vector(args.flow, '--flow')
        sources['flow'] = "--flow"
    else:
        flow = np.asarray(stream, dtype=float) / speed
        sources['flow'] = "domain.yml velocity"
    sources['U_inf'] = f"|domain.yml velocity| = {speed:g}"

    # -- lift: perpendicular to both -------------------------------------------
    # flow x span rather than span x flow, so that a body along +x in flow along
    # +z gets lift along +y -- the sign the case's own post-processing uses.
    lift = np.cross(flow, span)
    norm = np.linalg.norm(lift)
    if norm < 1e-9:
        raise ReferenceError(
            f"The span ({axis_label(span)}) and the flow ({axis_label(flow)}) are "
            "the same direction, so there is no plane for lift to act in. Pass "
            "--direction or --flow to separate them.")
    lift = lift / norm

    reference = Reference(
        body=name, span=span, flow=flow, lift=lift,
        rho=float(rho), u_inf=speed, diameter=2.0 * radius, length=length,
        labels={'span': axis_label(span), 'flow': axis_label(flow),
                'lift': axis_label(lift)},
        sources=sources,
    )
    logger.info(f"reference: rho={reference.rho:g} U={reference.u_inf:g} "
                f"D={reference.diameter:g} L={reference.length:g} "
                f"span={reference.labels['span']} flow={reference.labels['flow']}")
    return reference


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

@dataclass
class Sections:
    """Which spanwise slice each surface element falls in."""

    index: np.ndarray           # slice of each element
    centres: np.ndarray         # where each slice's elements actually are
    counts: np.ndarray
    width: float
    count: int


def build_sections(centroid, reference, n_sections, logger):
    """Cut `n_sections` equal slices along the span and place every element in one.

    Built once, from the first timestep, and reused: element ids are stable
    across timesteps, so a section keeps the same facets even as the body
    deflects. Rebuilding it per step would let a slice quietly change membership
    as the mesh moves, and the time series would no longer be of one thing.
    """
    station = centroid @ reference.span
    width = reference.length / n_sections
    index = np.clip(((station - station.min()) / width).astype(int), 0, n_sections - 1)
    counts = np.bincount(index, minlength=n_sections)
    if counts.min() == 0:
        logger.warning(f"{int((counts == 0).sum())} of {n_sections} sections hold no "
                       "elements; --sectional is finer than the mesh along the span")
    # Each section is reported where its elements actually are, not at the nominal
    # slice centre: the two differ by half a width when there is one element layer
    # per section, and by more on an uneven mesh.
    centres = (np.bincount(index, weights=station, minlength=n_sections)
               / np.maximum(counts, 1))
    logger.info(f"sections: {n_sections} x {width:g} along "
                f"{reference.labels['span']}, "
                f"{counts.min()}/{counts.mean():.1f}/{counts.max()} elements "
                "(min/mean/max)")
    return Sections(index=index, centres=centres, counts=counts, width=width,
                    count=n_sections)


def sectional_rows(force, area, sections, reference):
    """Per-section drag and lift, and the coefficients they normalise to.

    Rows are `section, station, Fx, Fy, Fz, Fd, Fl, Cd, Cl, area, elements`. All
    three force components are kept alongside the resolved drag and lift, so
    nothing is lost to the choice of axes.
    """
    n = sections.count
    idx = sections.index
    totals = np.column_stack([
        np.bincount(idx, weights=force[:, i], minlength=n) for i in range(3)])
    drag = totals @ reference.flow
    lift = totals @ reference.lift
    # Reference area of a slice is its frontal area, D * dx -- not its wetted area,
    # which is pi * D * dx and would divide every coefficient by another pi.
    q_ref = reference.dynamic_pressure * reference.diameter * sections.width
    return np.column_stack([
        np.arange(n), sections.centres, totals, drag, lift,
        drag / q_ref, lift / q_ref,
        np.bincount(idx, weights=area, minlength=n), sections.counts,
    ])


def total_coefficients(force, reference):
    """Whole-body (Fd, Fl, Cd, Cl) -- the same sums over every element at once."""
    total = force.sum(axis=0)
    drag = float(total @ reference.flow)
    lift = float(total @ reference.lift)
    q_ref = reference.dynamic_pressure * reference.diameter * reference.length
    return drag, lift, drag / q_ref, lift / q_ref
