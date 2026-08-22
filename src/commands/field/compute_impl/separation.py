"""
Where the flow leaves the surface, per spanwise section.

A reduction over what `wall_shear` wrote, not a second pass over the PLT: the
expensive part is reading a 162 MB file per timestep, and binning its output by
angle costs nothing. So the binning can be redone at a different resolution
without touching the PLTs again, which is the whole point of splitting the two.

The separation angle is where the azimuthal skin friction changes sign -- but
*not* simply where it first reaches zero, because it is zero at the forward
stagnation point too, and on a body that is deflecting and shedding the
stagnation point is not at theta = 0 either. Walking outward from the front, the
first zero is the stagnation point and the second is separation. So the peak is
found first and the crossing taken after it.
"""

import csv
import re
from pathlib import Path

import numpy as np

AZIMUTHAL_COLUMNS = ["section", "station", "theta_bin", "theta", "Cf_theta",
                     "Cf_axial", "Cp", "area", "elements"]
SEPARATION_COLUMNS = ["timestep", "section", "station", "theta_sep_pos",
                      "theta_sep_neg", "reversed_fraction", "Cf_max", "crossings"]

# A section of a plain cylinder reverses its azimuthal shear four times around the
# perimeter: the forward stagnation point, the two separations, and the rear. Every
# groove adds its own local reversal without the boundary layer having left the
# body, so a grooved section shows six to thirteen -- and "the first crossing after
# the peak" then picks a groove-scale flip rather than a separation. The count is
# written into every row so a reader can tell which is which; it is not thresholded
# here, because the bare and grooved ranges overlap and no single number separates
# them.
CLEAN_CROSSINGS = 4

STEP = re.compile(r"elements_(\d+)\.csv$")


class SeparationError(Exception):
    """There is nothing to reduce, or what there is cannot be read."""


def find_tables(directory):
    """[(timestep, path)] of the element tables in a wall_shear directory."""
    directory = Path(directory)
    if not directory.is_dir():
        raise SeparationError(
            f"No {directory.name}/ in the case. Write it first with "
            "`field compute wall_shear <case> --zone <zone> --t1 .. --t2 ..`.")
    found = []
    for path in sorted(directory.glob("elements_*.csv")):
        match = STEP.search(path.name)
        if match:
            found.append((int(match.group(1)), path))
    if not found:
        raise SeparationError(f"{directory}/ holds no elements_<step>.csv tables")
    return sorted(found)


# What a table's own header says it was made with. Read back rather than
# re-derived: these are the numbers that went into the rows below, and the .def
# may have moved since.
HEADER_VALUES = {
    "q": re.compile(r"q = 0\.5\*rho\*U\^2:\s*([-\d.eE+]+)"),
    "mu": re.compile(r"(?:^|\s)mu:\s*([-\d.eE+]+)"),
}


def read_table(path):
    """(columns, rows) from one element table, and what its header recorded."""
    meta = {}
    rows = []
    header = None
    with open(path, newline="") as handle:
        for line in handle:
            if line.startswith("#"):
                for name, pattern in HEADER_VALUES.items():
                    match = pattern.search(line)
                    if match and name not in meta:
                        meta[name] = float(match.group(1))
                continue
            fields = line.rstrip("\n").split(",")
            if header is None:
                header = fields
                continue
            rows.append(fields)
    if header is None or not rows:
        raise SeparationError(f"{path.name} holds no rows")
    table = np.array(rows, dtype=float)
    return {name: table[:, i] for i, name in enumerate(header)}, meta


def bin_azimuth(theta, n_bins):
    """(bin index, bin centre in degrees), with theta = 0 at a bin *centre*.

    Centred rather than edged so the forward stagnation point sits in the middle
    of a bin instead of being split across two, which would put a spurious sign
    change at the one angle where the shear is genuinely near zero.
    """
    width = 360.0 / n_bins
    index = np.mod(np.rint(theta / width).astype(int), n_bins)
    centre = index * width
    return index, np.where(centre > 180.0, centre - 360.0, centre)


def _crossing(theta, value):
    """The angle where `value` first changes sign after its peak, or NaN.

    `theta` runs outward from the front and `value` is the azimuthal skin
    friction along it. Interpolated between samples: quantising a separation
    angle to the bin width would put a 5-degree step in a quantity whose whole
    interest is where it moves by a degree or two along the span.
    """
    if len(theta) < 2:
        return float("nan")
    peak = int(np.argmax(value))
    after = value[peak:]
    negative = np.flatnonzero(after < 0)
    if not len(negative):
        return float("nan")                     # this side stays attached
    i = peak + int(negative[0])
    if i == 0:
        return float("nan")
    before, here = value[i - 1], value[i]
    if before == here:
        return float(theta[i])
    fraction = before / (before - here)          # linear crossing of zero
    return float(theta[i - 1] + fraction * (theta[i] - theta[i - 1]))


def sign_changes(cf_theta):
    """How many times the azimuthal shear reverses around the whole section.

    The ring is periodic, so the wrap from the last bin to the first counts. Bins
    that are exactly zero carry the previous sign rather than counting twice --
    a bin can land on the crossing itself, and that is one reversal, not two.
    """
    signs = np.sign(cf_theta)
    signs = signs[signs != 0]
    if len(signs) < 2:
        return 0
    return int(np.count_nonzero(signs != np.roll(signs, 1)))


def separation_angles(theta, cf_theta):
    """(theta_sep_pos, theta_sep_neg) for one section, in degrees.

    The two shear layers are handled as two walks outward from the front, so each
    finds its own peak and its own crossing. A side that never reverses is NaN
    rather than an invented angle -- an attached section is a real answer.
    """
    order = np.argsort(theta)
    theta, cf_theta = theta[order], cf_theta[order]

    forward = theta >= 0
    positive = _crossing(theta[forward], cf_theta[forward])

    # The other branch walks the other way, so both are "outward from the front".
    backward = theta <= 0
    negative = _crossing(-theta[backward][::-1], -cf_theta[backward][::-1])
    return positive, (float("nan") if np.isnan(negative) else -negative)


def reduce_step(table, sections, n_bins, q):
    """One timestep's element table as (azimuthal rows, separation rows).

    Areas weight everything. A grooved section has no single radius and its
    facets are not the same size, so counting bins or averaging per element would
    let the finely-meshed parts of the surface speak for the rest of it.
    """
    section = sections["index"]
    theta_bin, theta_centre = bin_azimuth(table["theta"], n_bins)
    area = table["area"]

    flat = section * n_bins + theta_bin
    size = sections["count"] * n_bins
    weight = np.bincount(flat, weights=area, minlength=size)
    live = weight > 0

    def weighted(values):
        return np.divide(np.bincount(flat, weights=area * values, minlength=size),
                         weight, out=np.zeros(size), where=live)

    cf_theta = weighted(table["tau_theta"]) / q
    cf_axial = weighted(table["tau_axial"]) / q
    cp = weighted(table["Cp"]) if "Cp" in table else np.zeros(size)
    station = weighted(table["station"])
    counts = np.bincount(flat, minlength=size)
    centres = np.zeros(size)
    centres[flat] = theta_centre

    azimuthal = []
    for cell in np.flatnonzero(live):
        s, b = divmod(cell, n_bins)
        azimuthal.append([s, station[cell], b, centres[cell], cf_theta[cell],
                          cf_axial[cell], cp[cell], weight[cell], counts[cell]])

    # ...and the answer, one row per section.
    per_section = []
    for s in range(sections["count"]):
        cells = np.flatnonzero(live[s * n_bins:(s + 1) * n_bins]) + s * n_bins
        if not len(cells):
            continue
        angles = centres[cells]
        shear = cf_theta[cells]
        pos, neg = separation_angles(angles, shear)
        reversed_area = weight[cells][shear < 0].sum() / weight[cells].sum()
        per_section.append([s, station[cells] @ weight[cells] / weight[cells].sum(),
                            pos, neg, reversed_area, float(np.abs(shear).max()),
                            sign_changes(shear[np.argsort(angles)])])
    return azimuthal, per_section


def write_csv(path, header, rows, comments):
    """A table with its '#' block, matching what the rest of field compute writes."""
    lines = [f"# {line}" for line in comments] + [",".join(header)]
    for row in rows:
        lines.append(",".join(
            str(int(v)) if name in ("section", "theta_bin", "elements", "timestep",
                                    "crossings")
            else f"{v:.8e}" for name, v in zip(header, row)))
    Path(path).write_text("\n".join(lines) + "\n")


def write_csv_dict(path, header, rows, comments):
    """As write_csv, for rows already ordered to `header`."""
    write_csv(path, header, rows, comments)
