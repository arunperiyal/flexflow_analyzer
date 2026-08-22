"""Tests for `field compute wall_shear` and `field compute separation`.

The shear itself is an identity, so it can be checked against a flow whose answer
is known by inspection. Everything after it is convention -- where theta is zero,
which way it runs, where a section's centre is, which zero crossing is separation
-- and a convention is only right if it is the one the reader assumes. These pin
each of them.
"""

import argparse

import numpy as np
import pytest

from src.commands.field.compute_impl import coefficients as co
from src.commands.field.compute_impl import separation as sep
from src.commands.field.compute_impl import wall_shear as ws
from src.utils.logger import Logger

LOG = Logger(verbose=False)


def _reference(span=(1, 0, 0), flow=(0, 0, 1), origin=(0, 0, 0), length=12.0,
               diameter=1.0, rho=1000.0, u_inf=1.0):
    span = np.array(span, dtype=float)
    flow = np.array(flow, dtype=float)
    lift = np.cross(flow, span)
    lift = lift / np.linalg.norm(lift)
    return co.Reference(
        body="cyl", span=span, flow=flow, lift=lift, rho=rho, u_inf=u_inf,
        diameter=diameter, length=length, origin=np.array(origin, dtype=float),
        labels={"span": co.axis_label(span), "flow": co.axis_label(flow),
                "lift": co.axis_label(lift)})


# ---------------------------------------------------------------------------
# The identity
# ---------------------------------------------------------------------------

def test_wall_shear_is_the_answer_by_inspection():
    """u = (gamma*y, 0, 0) over a wall at n = +y gives tau = mu*gamma along x."""
    gamma, mu = 3.0, 2.0
    # omega = curl u = (0, 0, -gamma)
    omega = np.array([[0.0, 0.0, -gamma]])
    normal = np.array([[0.0, 1.0, 0.0]])
    tau = ws.wall_shear_stress(omega, normal, np.array([mu]))
    np.testing.assert_allclose(tau, [[mu * gamma, 0.0, 0.0]])


def test_a_flipped_normal_flips_the_shear():
    """Which is why the normal must be oriented against the volume first."""
    omega = np.array([[0.0, 0.0, -3.0]])
    out = ws.wall_shear_stress(omega, np.array([[0.0, 1.0, 0.0]]), np.array([1.0]))
    flipped = ws.wall_shear_stress(omega, np.array([[0.0, -1.0, 0.0]]), np.array([1.0]))
    np.testing.assert_allclose(out, -flipped)


def test_eddy_viscosity_enters_as_rho_nu_t():
    """`eddy` is kinematic, so mu_eff = mu + rho*nu_t."""
    conn = np.array([[0, 1, 2, 3]])
    pdata = {"eddy": np.array([0.5, 0.5, 0.5, 0.5])}
    mu_eff, nu_max = ws.effective_viscosity(pdata, conn, mu=1.0, rho=1000.0)
    assert mu_eff[0] == pytest.approx(1.0 + 1000.0 * 0.5)
    assert nu_max == 0.5
    # ...and a PLT without it says so rather than guessing
    mu_eff, nu_max = ws.effective_viscosity({}, conn, mu=1.0, rho=1000.0)
    assert mu_eff[0] == 1.0 and nu_max is None


def test_missing_vorticity_is_an_error_not_a_reconstruction(capsys):
    reference = _reference()
    with pytest.raises(ws.WallShearError) as exc:
        ws.compute({"Pressure": np.zeros(4)}, np.array([[0, 1, 2, 3]]),
                   np.zeros((1, 3)), np.ones(1), np.array([[0.0, 1.0, 0.0]]),
                   reference, 1.0, LOG, [])
    assert "xVor" in str(exc.value)


# ---------------------------------------------------------------------------
# The angle convention
# ---------------------------------------------------------------------------

def test_theta_is_zero_facing_the_flow_and_grows_towards_lift():
    """Span +x, flow +z: theta = 0 at -z, +90 at +y, 180 at +z."""
    reference = _reference()
    centre = np.zeros((4, 3))
    centroid = np.array([[0.0, 0.0, -0.5],     # facing the oncoming flow
                         [0.0, 0.5, 0.0],      # the lift side
                         [0.0, 0.0, 0.5],      # the wake
                         [0.0, -0.5, 0.0]])
    theta, radial, azimuthal = ws.azimuthal_frame(centroid, centre, reference)
    np.testing.assert_allclose(theta, [0.0, 90.0, 180.0, -90.0], atol=1e-9)
    # +theta points the way theta increases: at the front, that is +y
    np.testing.assert_allclose(azimuthal[0], reference.lift, atol=1e-9)


def test_the_span_component_is_removed_before_the_angle():
    """A facet offset along the span is at the same angle as one that is not."""
    reference = _reference()
    theta_a, _, _ = ws.azimuthal_frame(np.array([[0.0, 0.5, 0.0]]),
                                       np.zeros((1, 3)), reference)
    theta_b, _, _ = ws.azimuthal_frame(np.array([[7.0, 0.5, 0.0]]),
                                       np.array([[7.0, 0.0, 0.0]]), reference)
    np.testing.assert_allclose(theta_a, theta_b)


# ---------------------------------------------------------------------------
# The section centre -- the thing a groove breaks
# ---------------------------------------------------------------------------

def _grooved_ring(station, centre_y, n=64, radius=0.5, groove=0.15):
    """A ring whose facets are not symmetric about its axis.

    One quadrant is cut in, as a groove would cut it. The mean of the ring's own
    coordinates is then no longer the axis, which is the whole difficulty.
    """
    angle = np.linspace(0, 2 * np.pi, n, endpoint=False)
    r = np.where((angle > 0.4) & (angle < 1.4), radius - groove, radius)
    y = centre_y + r * np.cos(angle)
    z = r * np.sin(angle)
    return np.column_stack([np.full(n, station), y, z])


def test_the_centre_comes_from_the_declared_axis_and_the_displacement():
    """On a grooved ring the coordinate mean is off-axis; the declared one is not."""
    reference = _reference()
    deflection = -0.85
    centroid = _grooved_ring(6.0, deflection)
    station = centroid @ reference.span
    area = np.ones(len(centroid))
    disp = np.tile([0.0, deflection, 0.0], (len(centroid), 1))

    centre = ws.ring_centres(centroid, station, area, disp, reference, LOG, [])
    np.testing.assert_allclose(centre[0], [6.0, deflection, 0.0], atol=1e-12)

    # What measuring it from the ring itself would have given, on this shape:
    drift = np.linalg.norm(centroid.mean(axis=0)[1:] - [deflection, 0.0])
    assert drift > 0.01, "the fixture is not actually asymmetric"


def test_a_grooved_ring_reads_the_same_angles_as_a_round_one():
    """Which is the point: the groove must not move the separation angle."""
    reference = _reference()
    round_ring = _grooved_ring(6.0, -0.85, groove=0.0)
    grooved = _grooved_ring(6.0, -0.85, groove=0.15)
    area = np.ones(len(grooved))
    disp = np.tile([0.0, -0.85, 0.0], (len(grooved), 1))

    angles = []
    for ring in (round_ring, grooved):
        station = ring @ reference.span
        centre = ws.ring_centres(ring, station, area, disp, reference, LOG, [])
        theta, _, _ = ws.azimuthal_frame(ring, centre, reference)
        angles.append(theta)
    # The groove changes the radius, never the angle a facet sits at.
    np.testing.assert_allclose(angles[0], angles[1], atol=1e-9)


def test_without_an_origin_it_falls_back_and_says_so(capsys):
    reference = _reference()
    reference.origin = None
    ring = _grooved_ring(6.0, -0.85)
    station = ring @ reference.span
    warned = []
    ws.ring_centres(ring, station, np.ones(len(ring)), None, reference, LOG, warned)
    assert warned, "the fallback must announce itself"
    assert "grooved" in capsys.readouterr().err


def test_axis_displacement_is_interpolated_not_stepped():
    """A centre that steps from ring to ring would step the separation angle too."""
    reference = _reference()
    station = np.repeat(np.linspace(0.5, 11.5, 12), 8)
    # A smooth mode shape, sampled at the rings
    disp = np.column_stack([np.zeros_like(station),
                            -np.sin(np.pi * station / 12.0), np.zeros_like(station)])
    out = ws.axis_displacement(station, disp, np.ones_like(station), LOG)
    np.testing.assert_allclose(out[:, 1], disp[:, 1], atol=1e-12)


# ---------------------------------------------------------------------------
# Finding the crossing
# ---------------------------------------------------------------------------

def _profile(theta_deg, stagnation=0.0, separation=100.0):
    """Cf_theta over a ring: zero at the stagnation point AND at separation.

    A half sine from one to the other, carrying on negative into the
    recirculation behind. Bounded on purpose: a shape that grows past separation
    puts its largest value in the wake, and then the peak the search anchors on
    is the tail rather than the attached boundary layer.
    """
    return np.sin(np.pi * (theta_deg - stagnation) / (separation - stagnation))


def test_the_first_zero_is_the_stagnation_point_not_separation():
    """Cf_theta vanishes at the front too, so 'first zero' is the wrong answer."""
    theta = np.arange(-180.0, 180.0, 5.0)
    pos, neg = sep.separation_angles(theta, _profile(theta, separation=100.0))
    assert pos == pytest.approx(100.0, abs=1.0)
    assert neg == pytest.approx(-100.0, abs=1.0)


def test_a_stagnation_point_off_theta_zero_does_not_fool_it():
    """On a deflecting, shedding body the front is not at theta = 0.

    The profile is built about a stagnation point at -12, so its zeros sit at
    -12 (the front), +95 and -119. Anchoring the search at theta = 0 instead of
    at each branch's own peak would return -12 for both sides.
    """
    theta = np.arange(-180.0, 180.0, 5.0)
    stagnation, forward = -12.0, 95.0
    pos, neg = sep.separation_angles(theta, _profile(theta, stagnation, forward))
    assert pos == pytest.approx(forward, abs=2.0)
    assert neg == pytest.approx(2 * stagnation - forward, abs=2.0)


def test_the_crossing_is_interpolated_between_bins():
    """Otherwise theta_sep quantises to the bin width and the span trend vanishes."""
    theta = np.arange(-180.0, 180.0, 10.0)
    for true in (101.0, 104.0, 107.0):
        found = sep.separation_angles(theta, _profile(theta, separation=true))[0]
        # Snapping to the nearest 10 deg bin would be out by up to 5.
        assert found == pytest.approx(true, abs=1.0), f"{true} -> {found}"


def test_an_attached_side_is_nan_rather_than_an_invented_angle():
    theta = np.arange(-180.0, 180.0, 5.0)
    # Attached means the shear runs away from the front on *both* sides, so it is
    # positive for positive theta and negative for negative theta -- never
    # reversed. |sin| would be reversed flow over the whole back half.
    attached = np.sin(np.radians(theta))
    pos, neg = sep.separation_angles(theta, attached)
    assert np.isnan(pos) and np.isnan(neg)


def test_theta_zero_sits_at_a_bin_centre():
    """Edged bins would split the front across two and put a false sign change there."""
    index, centre = sep.bin_azimuth(np.array([0.0, 4.9, -4.9, 90.0, 180.0]), 36)
    assert centre[0] == 0.0 and index[0] == 0
    np.testing.assert_allclose(centre[:3], 0.0)     # all within half a 10 deg bin
    assert centre[3] == pytest.approx(90.0)
    assert centre[4] == pytest.approx(180.0)


# ---------------------------------------------------------------------------
# The reduction
# ---------------------------------------------------------------------------

def test_bins_are_area_weighted_not_element_counted():
    """A grooved section has no single radius, so its facets are not equal."""
    n_bins = 4
    sections = {"index": np.zeros(3, dtype=int), "count": 1, "width": 12.0}
    table = {
        "theta": np.array([0.0, 0.0, 90.0]),
        "station": np.array([6.0, 6.0, 6.0]),
        "tau_theta": np.array([1.0, 3.0, 0.0]),
        "tau_axial": np.zeros(3),
        "area": np.array([1.0, 9.0, 1.0]),          # the second facet is 9x the first
        "Cp": np.zeros(3),
    }
    rows, _ = sep.reduce_step(table, sections, n_bins, q=1.0)
    front = [r for r in rows if r[2] == 0][0]
    # area-weighted: (1*1 + 9*3) / 10 = 2.8, not the unweighted mean of 2
    assert front[4] == pytest.approx(2.8)
    assert front[7] == pytest.approx(10.0)          # area, not count
    assert front[8] == 2


def test_reversed_fraction_is_a_share_of_perimeter_area():
    sections = {"index": np.zeros(4, dtype=int), "count": 1, "width": 12.0}
    table = {
        "theta": np.array([0.0, 90.0, 180.0, -90.0]),
        "station": np.full(4, 6.0),
        "tau_theta": np.array([1.0, 1.0, -1.0, -1.0]),
        "tau_axial": np.zeros(4),
        "area": np.array([1.0, 1.0, 3.0, 1.0]),     # the reversed side is bigger
        "Cp": np.zeros(4),
    }
    _, per_section = sep.reduce_step(table, sections, 4, q=1.0)
    # 4 of 6 units of area are reversed, not 2 of 4 bins
    assert per_section[0][4] == pytest.approx(4.0 / 6.0)


# ---------------------------------------------------------------------------
# When theta_sep is not a separation angle
# ---------------------------------------------------------------------------

def test_a_plain_section_reverses_four_times():
    """Stagnation, the two separations, the rear -- and nothing else."""
    theta = np.arange(-180.0, 180.0, 5.0)
    assert sep.sign_changes(_profile(theta, separation=100.0)) == sep.CLEAN_CROSSINGS


def _with_grooves(theta, centres, separation=100.0, half_width=6.0):
    """A clean profile with a local shear reversal at each groove."""
    profile = _profile(theta, separation=separation)
    for centre in centres:
        profile[np.abs(theta - centre) < half_width] *= -1.0
    return profile


def test_a_groove_between_the_peak_and_separation_is_taken_for_separation():
    """Which is the whole failure: the angle returned is plausible and wrong."""
    theta = np.arange(-180.0, 180.0, 5.0)
    grooved = _with_grooves(theta, (70.0, -70.0))
    assert sep.sign_changes(grooved) > sep.CLEAN_CROSSINGS

    found, _ = sep.separation_angles(theta, grooved)
    assert not np.isnan(found), "it does not decline -- it answers, wrongly"
    assert abs(found - 100.0) > 20.0
    assert found < 100.0, "it stops at the groove, short of the real separation"


def test_a_groove_inboard_of_the_peak_does_not_mislead_it():
    """Only reversals between the peak and the separation are taken for it.

    Worth pinning because it says what the crossing count does and does not
    imply: a high count is a reason to distrust theta_sep, not proof it is wrong.
    """
    theta = np.arange(-180.0, 180.0, 5.0)
    inboard = _with_grooves(theta, (35.0, -35.0))
    assert sep.sign_changes(inboard) > sep.CLEAN_CROSSINGS
    found, _ = sep.separation_angles(theta, inboard)
    assert found == pytest.approx(100.0, abs=1.0)


def test_the_ring_wraps_when_counting():
    """The last bin is adjacent to the first; a reversal across the seam counts."""
    assert sep.sign_changes(np.array([1.0, 1.0, -1.0, -1.0])) == 2
    assert sep.sign_changes(np.array([1.0, 1.0, 1.0, -1.0])) == 2


def test_a_bin_landing_on_zero_is_one_reversal_not_two():
    assert sep.sign_changes(np.array([-1.0, 0.0, 1.0, 1.0])) == 2


def test_an_attached_ring_never_reverses():
    assert sep.sign_changes(np.array([1.0, 2.0, 3.0])) == 0
