"""Tests for `field compute force_coeff`.

A coefficient is a force divided by four numbers the PLT does not hold, so most
of these are about where those numbers come from and what happens when one of
them is missing -- being wrong there is silent, and wrong by exactly the factor
nobody checks.
"""

import argparse
from pathlib import Path

import numpy as np
import pytest

from src.commands.field.compute_impl import coefficients as co
from src.core.def_config import DefConfig
from src.core.domain import DomainConfig
from src.utils.logger import Logger

DEF_TEMPLATE = """
nodeCoordinates {
    coordinates             = File( "riser.crd" )
}

elementGroup( "interior" ) {
    elements                = File( "riser.fluid.cnn" )
    shape                   = eightNodeBrick
}

define{
	variable = RHO
	value = 1000.0
}
define{
	variable = U
	value = 0.0
}
define{
	variable = V
	value = 0.0
}
define{
	variable = W
	value = 2.0
}
define{
	variable = SPEED
	value = (U^2 + V^2 + W^2)^0.5
}

# initField writes its label unquoted, unlike most of the .def
initField( velocity ) {
    defaultValues   = {U, V, W}
}

initField( pressure ) {
    defaultValue    = 0.0
}

densityModel( "fluid" ) {
    density         = RHO
}

viscosityModel ( "fluid" ) {
    viscosity       = 1.0
}

materialModel  ( "fluid" ) {
	densityModel	= "fluid"
	viscosityModel	= "fluid"
}

elementProperty( "interior" ) {
	materialModel	= "fluid"
}

beamSolid( "beam_1" ) {
	pnt1 	= {0, 0, 0}
	pnt2	= {12, 0, 0}
	surfaceOutputs = { "cylinder_body" }
}

outputSurface( "cylinder_body"  ){
    surfaces        = File( "riser.cyl.srf" )
}

outputTimeHistory( "riser_probe" ){
    type	    = nodal
    nodes	    = File( "riser.cyl_nodes.nbc" )
}
"""


@pytest.fixture
def case(tmp_path):
    """A case with a .def and a domain.yml whose body is fully specified."""
    (tmp_path / "riser.def").write_text(DEF_TEMPLATE)
    (tmp_path / "simflow.config").write_text('problem = "riser"\n')
    (tmp_path / "riser.cyl.srf").write_text("1 2 3 4\n")
    from src.commands.case.domain_impl.command import init_case
    init_case(tmp_path)
    domain = DomainConfig.find(tmp_path)
    domain.set_body("cyl", "geometry.radius", 0.5)
    domain.set_body("cyl", "plttag", "cyl")
    domain.set_field("velocity", [0, 0, 2])
    domain.save()
    return tmp_path


def _args(**overrides):
    defaults = dict(direction=None, flow=None, sectional=None)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


LOG = Logger(verbose=False)


# ---------------------------------------------------------------------------
# Reading the reference state out of the case
# ---------------------------------------------------------------------------

def test_density_follows_the_defs_own_chain(case):
    """elementGroup -> elementProperty -> materialModel -> densityModel."""
    assert DefConfig.find(case, "riser").density() == 1000.0


def test_the_def_is_not_asked_for_a_free_stream(case):
    """initField( velocity ) is an initial condition, not the flow a body sees.

    It is right often enough to be trusted and wrong quietly enough to matter, so
    the free stream is declared in domain.yml and nothing reads the .def for it.
    """
    assert not hasattr(DefConfig.find(case, "riser"), "free_stream")


def test_reference_is_assembled_from_domain_and_def(case):
    ref = co.resolve(case, "cyl", _args(), LOG)
    assert ref.body == "cyl"
    assert ref.rho == 1000.0
    assert ref.u_inf == 2.0                      # |domain.yml velocity|
    assert ref.diameter == 1.0                   # 2 x radius
    assert ref.length == 12.0                    # |pnt2 - pnt1|
    assert ref.dynamic_pressure == 0.5 * 1000.0 * 4.0
    np.testing.assert_allclose(ref.span, [1, 0, 0])
    np.testing.assert_allclose(ref.flow, [0, 0, 1])
    # flow x span: a body along +x in flow along +z lifts along +y
    np.testing.assert_allclose(ref.lift, [0, 1, 0], atol=1e-12)
    assert ref.labels == {"span": "+x", "flow": "+z", "lift": "+y"}


def test_the_reference_says_where_every_number_came_from(case):
    text = " ".join(co.resolve(case, "cyl", _args(), LOG).describe())
    for expected in ("rho: 1000", "U_inf: 2", "diameter: 1", "length: 12",
                     "riser.def densityModel", "domain.yml velocity"):
        assert expected in text


def test_flags_override_the_derived_directions(case):
    ref = co.resolve(case, "cyl", _args(direction="z", flow="-x"), LOG)
    np.testing.assert_allclose(ref.span, [0, 0, 1])
    np.testing.assert_allclose(ref.flow, [-1, 0, 0])
    assert ref.sources["span axis"] == "--direction"


def test_a_body_resolves_by_any_of_its_names(case):
    domain = DomainConfig.find(case)
    domain.set_body("cyl", "name", "riser_body")
    domain.save()
    for token in ("riser_body", "cyl"):     # name, then plttag
        assert co.resolve(case, token, _args(), LOG).body == "riser_body"


# ---------------------------------------------------------------------------
# What is missing is named, never defaulted
# ---------------------------------------------------------------------------

def test_a_missing_radius_names_the_command_that_sets_it(case):
    domain = DomainConfig.find(case)
    domain.set_body("cyl", "geometry.radius", None)
    domain.save()
    with pytest.raises(co.ReferenceError) as exc:
        co.resolve(case, "cyl", _args(), LOG)
    assert "radius" in str(exc.value) and "case domain body" in str(exc.value)


def test_a_missing_domain_file_says_how_to_write_one(tmp_path):
    (tmp_path / "riser.def").write_text(DEF_TEMPLATE)
    with pytest.raises(co.ReferenceError) as exc:
        co.resolve(tmp_path, "cyl", _args(), LOG)
    assert "--init" in str(exc.value)


def test_an_unknown_body_lists_the_declared_ones(case):
    with pytest.raises(co.ReferenceError) as exc:
        co.resolve(case, "nothing", _args(), LOG)
    assert "cyl" in str(exc.value)


def test_an_undeclared_velocity_names_the_command_that_sets_it(case):
    domain = DomainConfig.find(case)
    domain.set_field("velocity", None)
    domain.save()
    with pytest.raises(co.ReferenceError) as exc:
        co.resolve(case, "cyl", _args(), LOG)
    assert "velocity" in str(exc.value) and "case domain field" in str(exc.value)


def test_a_still_fluid_gives_no_reference_speed(case):
    """U_inf = 0 would divide every coefficient by zero."""
    domain = DomainConfig.find(case)
    domain.set_field("velocity", [0, 0, 0])
    domain.save()
    with pytest.raises(co.ReferenceError) as exc:
        co.resolve(case, "cyl", _args(flow="z"), LOG)
    assert "zero" in str(exc.value)


def test_a_velocity_that_is_not_three_numbers_is_refused(case):
    domain = DomainConfig.find(case)
    domain.set_field("velocity", "downstream")
    domain.save()
    with pytest.raises(co.ReferenceError):
        co.resolve(case, "cyl", _args(), LOG)


def test_flow_overrides_the_direction_but_not_the_speed(case):
    """--flow re-aims drag; U_inf stays the magnitude that was declared."""
    ref = co.resolve(case, "cyl", _args(flow="y"), LOG)
    np.testing.assert_allclose(ref.flow, [0, 1, 0])
    assert ref.u_inf == 2.0


def test_span_and_flow_may_not_be_the_same_direction(case):
    with pytest.raises(co.ReferenceError) as exc:
        co.resolve(case, "cyl", _args(direction="x", flow="x"), LOG)
    assert "lift" in str(exc.value)


def test_a_direction_that_is_not_one_is_refused(case):
    with pytest.raises(co.ReferenceError):
        co.resolve(case, "cyl", _args(direction="sideways"), LOG)
    with pytest.raises(co.ReferenceError):
        co.resolve(case, "cyl", _args(direction="[0, 0, 0]"), LOG)


def test_axis_vector_reads_both_forms():
    np.testing.assert_allclose(co.axis_vector("-y", "x"), [0, -1, 0])
    np.testing.assert_allclose(co.axis_vector("[0, 3, 4]", "x"), [0, 0.6, 0.8])
    np.testing.assert_allclose(co.axis_vector([1, 0, 0], "x"), [1, 0, 0])
    assert co.axis_label(np.array([0.0, 0.0, -1.0])) == "-z"
    assert co.axis_label(np.array([0.0, 0.6, 0.8])).startswith("[")


# ---------------------------------------------------------------------------
# The arithmetic
# ---------------------------------------------------------------------------

def _uniform_body(reference, n_layers=4, per_layer=8):
    """A cylinder of `n_layers` element rings, each carrying a unit drag force.

    The rings sit at the centres of `n_layers` equal slices of the 12-long body,
    so sectioning by that same count puts exactly one ring in each.
    """
    width = reference.length / n_layers
    x = np.repeat((np.arange(n_layers) + 0.5) * width, per_layer)
    centroid = np.column_stack([x, np.zeros_like(x), np.zeros_like(x)])
    force = np.zeros((len(x), 3))
    force[:, 2] = 1.0                    # 1 N of drag on every facet, along +z
    area = np.full(len(x), 0.25)
    return centroid, force, area


def test_sections_hold_the_elements_they_should(case):
    ref = co.resolve(case, "cyl", _args(), LOG)
    centroid, _, _ = _uniform_body(ref)
    sections = co.build_sections(centroid, ref, 4, LOG)
    assert sections.count == 4
    assert sections.width == 3.0                     # 12 / 4
    assert list(sections.counts) == [8, 8, 8, 8]
    # Stations report where the elements are, not the nominal slice centre.
    np.testing.assert_allclose(sections.centres, [1.5, 4.5, 7.5, 10.5])


def test_sectional_coefficients_use_the_frontal_area(case):
    ref = co.resolve(case, "cyl", _args(), LOG)
    centroid, force, area = _uniform_body(ref)
    sections = co.build_sections(centroid, ref, 4, LOG)
    rows = co.sectional_rows(force, area, sections, ref)
    columns = {name: i for i, name in enumerate(
        ["section", "station", "Fx", "Fy", "Fz", "Fd", "Fl", "Cd", "Cl",
         "area", "elements"])}
    # 8 facets x 1 N of drag per slice, over q * D * dx = 2000 * 1 * 3
    np.testing.assert_allclose(rows[:, columns["Fd"]], 8.0)
    np.testing.assert_allclose(rows[:, columns["Cd"]], 8.0 / (2000.0 * 1.0 * 3.0))
    np.testing.assert_allclose(rows[:, columns["Cl"]], 0.0)
    # wetted area is reported but not what the coefficient divides by
    np.testing.assert_allclose(rows[:, columns["area"]], 2.0)


def test_total_matches_the_sections_it_is_made_of(case):
    ref = co.resolve(case, "cyl", _args(), LOG)
    centroid, force, area = _uniform_body(ref)
    drag, lift, cd, cl = co.total_coefficients(force, ref)
    assert drag == pytest.approx(32.0)               # 32 facets x 1 N
    assert lift == pytest.approx(0.0)
    assert cd == pytest.approx(32.0 / (2000.0 * 1.0 * 12.0))
    assert cl == pytest.approx(0.0)

    # The whole body is the sections added up, weighted by their widths.
    sections = co.build_sections(centroid, ref, 4, LOG)
    rows = co.sectional_rows(force, area, sections, ref)
    assert (rows[:, 7] * sections.width).sum() / ref.length == pytest.approx(cd)


def test_lift_is_signed_off_the_flow_and_span(case):
    """Force along +y is lift for a +x body in +z flow, not drag."""
    ref = co.resolve(case, "cyl", _args(), LOG)
    force = np.zeros((4, 3))
    force[:, 1] = 2.5
    drag, lift, _, _ = co.total_coefficients(force, ref)
    assert drag == pytest.approx(0.0)
    assert lift == pytest.approx(10.0)


def test_a_finer_sectioning_than_the_mesh_is_reported(case, capsys):
    ref = co.resolve(case, "cyl", _args(), LOG)
    centroid, _, _ = _uniform_body(ref, n_layers=2, per_layer=4)
    co.build_sections(centroid, ref, 40, LOG)
    assert "no elements" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Against the case's own reference implementation
# ---------------------------------------------------------------------------

def _read_csv(path):
    """(header, rows) from a table, ignoring its '#' provenance block."""
    lines = [ln for ln in path.read_text().splitlines() if not ln.startswith("#")]
    header = lines[0].split(",")
    return header, np.array([[float(v) for v in ln.split(",")] for ln in lines[1:]])


EXAMPLE = Path("examples/BR0SG0U1P0")


@pytest.mark.skipif(not (EXAMPLE / "binary" / "riser.100.plt").exists(),
                    reason="needs the BR0SG0U1P0 example case")
def test_matches_the_cases_own_reference_implementation(tmp_path):
    """The shipped sectional_Cd_Cl_<step>.csv were produced by binary/main.py.

    That script hard-codes the same reference state this derives (rho 1000,
    U 1, D 1, L 12, 48 sections along X, drag along Z) and has been used on this
    case, so agreeing with it to rounding is the real check that the sectioning,
    the axes, the sign of lift and the reference areas are all right.
    """
    import shutil

    from src.commands.case.domain_impl.command import init_case
    from src.commands.field.compute_impl.command import execute_compute

    case = tmp_path / "BR0SG0U1P0"
    shutil.copytree(EXAMPLE, case)
    init_case(case)
    domain = DomainConfig.find(case)
    domain.set_body("cyl", "geometry.radius", 0.5)     # D = 1, as binary/config.py
    domain.set_field("velocity", [0, 0, 1])            # U_INF = 1, DRAG_AXIS = Z
    domain.save()

    execute_compute(argparse.Namespace(
        quantity="force_coeff", case=str(case), zone="cyl", sectional=48,
        direction=None, flow=None, timestep=None, t1=100, t2=500, freq=None,
        output_file=None, pressure=None, nen=None, no_progress=True,
        verbose=False, help=False))

    produced = case / "cyl.force_coeff"
    assert produced.is_dir()
    for step in (100, 300, 500):
        _, want = _read_csv(case / "binary" / f"sectional_Cd_Cl_{step}.csv")
        header, got = _read_csv(produced / f"sectional_{step}.csv")
        column = {name: i for i, name in enumerate(header)}
        assert len(got) == len(want) == 48
        # The reference writes 8 decimals, so agreement is to that, not to eps.
        for theirs, ours in ((1, "station"), (4, "Cd"), (5, "Cl"), (6, "area")):
            np.testing.assert_allclose(got[:, column[ours]], want[:, theirs],
                                       rtol=1e-6, atol=1e-8)
    assert (produced / "summary.csv").exists()
