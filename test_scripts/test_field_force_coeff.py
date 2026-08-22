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


def test_the_reference_describes_itself_in_values(case):
    """What a Cd was divided by, spelled out -- not the files it was read from."""
    text = " ".join(co.resolve(case, "cyl", _args(), LOG).describe())
    for expected in ("rho: 1000", "U_inf: 2", "q = 0.5*rho*U^2: 2000",
                     "diameter: 1", "length: 12", "span axis: +x"):
        assert expected in text
    assert "domain.yml" not in text and ".def" not in text


def test_where_each_number_came_from_is_still_available(case):
    """Not in the tables, but there for whoever asks with -v."""
    sources = co.resolve(case, "cyl", _args(), LOG).sources
    assert "riser.def densityModel" in sources["rho"]
    assert "domain.yml" in sources["U_inf"]


def test_normalisation_names_the_area_the_table_used(case):
    ref = co.resolve(case, "cyl", _args(), LOG)
    assert "D * L = 1 * 12" in ref.normalisation()
    assert "D * dx = 1 * 0.25" in ref.normalisation(0.25)
    assert "q = 2000" in ref.normalisation()


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
# Against the real case
#
# BR0SG0U1P0 is 1.5 GB, most of it five 162 MB PLT files, so copying it per test
# is not on. A run only ever *reads* a PLT, so those are symlinked and the rest --
# all of it text, and 24 KB of it -- is copied, which the run may then write over.
# ---------------------------------------------------------------------------

EXAMPLE = Path("examples/BR0SG0U1P0")
HAS_EXAMPLE = (EXAMPLE / "binary" / "riser.100.plt").exists()
needs_example = pytest.mark.skipif(not HAS_EXAMPLE,
                                   reason="needs the BR0SG0U1P0 example case")


def _lean_case(destination, steps=(100,)):
    """The example case with only what a compute run reads, PLTs symlinked."""
    import shutil

    destination.mkdir(parents=True, exist_ok=True)
    for name in ("riser.def", "simflow.config", "riser.cyl_nodes.nbc"):
        if (EXAMPLE / name).exists():
            shutil.copy2(EXAMPLE / name, destination / name)
    binary = destination / "binary"
    binary.mkdir(exist_ok=True)
    for step in steps:
        plt = (EXAMPLE / "binary" / f"riser.{step}.plt").resolve()
        (binary / plt.name).symlink_to(plt)
        # The reference implementation's own output, for the comparison below.
        produced = EXAMPLE / "binary" / f"sectional_Cd_Cl_{step}.csv"
        if produced.exists():
            shutil.copy2(produced, binary / produced.name)
    return destination


def _declared(case, radius=0.5, velocity=(0, 0, 1)):
    """`case domain --init`, plus the two things the case itself does not state."""
    from src.commands.case.domain_impl.command import init_case

    init_case(case)
    domain = DomainConfig.find(case)
    domain.set_body("cyl", "geometry.radius", radius)
    domain.set_field("velocity", list(velocity))
    domain.save()
    return domain


def _compute_args(case, **overrides):
    defaults = dict(quantity="force", case=str(case), zone="cyl", sectional=None,
                    direction=None, flow=None, azimuthal=None, body=None,
                    timestep=100, t1=None, t2=None,
                    freq=None, output_file=None, pressure=None, nen=None,
                    no_progress=True, verbose=False, help=False)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _run(case, **overrides):
    from src.commands.field.compute_impl.command import execute_compute
    execute_compute(_compute_args(case, **overrides))


def _read_csv(path):
    """(header, rows) from a table, ignoring its '#' provenance block."""
    lines = [ln for ln in path.read_text().splitlines() if not ln.startswith("#")]
    header = lines[0].split(",")
    return header, np.array([[float(v) for v in ln.split(",")] for ln in lines[1:]])


def _header(path):
    return [ln[2:] for ln in path.read_text().splitlines() if ln.startswith("# ")]


@needs_example
def test_matches_the_cases_own_reference_implementation(tmp_path):
    """The shipped sectional_Cd_Cl_<step>.csv were produced by binary/main.py.

    That script hard-codes the same reference state this derives (rho 1000, U 1,
    D 1, L 12, 48 sections along X, drag along Z) and has been used on this case,
    so agreeing with it to rounding is the real check that the sectioning, the
    axes, the sign of lift and the reference areas are all right.
    """
    case = _lean_case(tmp_path / "BR0SG0U1P0", steps=(100, 300, 500))
    _declared(case)
    _run(case, quantity="force_coeff", sectional=48, timestep=None, t1=100, t2=500)

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


# ---------------------------------------------------------------------------
# Where a run writes when nobody says
# ---------------------------------------------------------------------------

@needs_example
@pytest.mark.parametrize("quantity,suffix", [("force", "forces"),
                                             ("force_coeff", "force_coeff")])
def test_output_defaults_to_a_directory_named_for_the_body(tmp_path, quantity, suffix):
    """A run always writes, and names the directory after the body it is about.

    One place per body, so a case holding several does not have their tables
    collide, and nobody has to invent a name for the ordinary case.
    """
    case = _lean_case(tmp_path / "BR0SG0U1P0")
    _declared(case)
    _run(case, quantity=quantity)
    written = case / f"cyl.{suffix}"
    assert written.is_dir() and (written / "summary.csv").exists()


@needs_example
def test_the_directory_takes_the_bodys_name_not_the_zones(tmp_path):
    """--zone names a PLT zone; the directory is named for the body it belongs to."""
    case = _lean_case(tmp_path / "BR0SG0U1P0")
    domain = _declared(case)
    domain.set_body("cyl", "name", "riser_body")      # plttag stays 'cyl'
    domain.save()
    _run(case)
    assert (case / "riser_body.forces").is_dir()
    assert not (case / "cyl.forces").exists()


@needs_example
def test_a_case_without_a_domain_falls_back_to_the_zone(tmp_path):
    """force needs no domain.yml, so the zone names the directory when there is none."""
    case = _lean_case(tmp_path / "BR0SG0U1P0")
    _run(case)
    assert (case / "cyl.forces").is_dir()


@needs_example
def test_output_still_wins_over_the_default(tmp_path):
    case = _lean_case(tmp_path / "BR0SG0U1P0")
    _run(case, output_file="loads")
    assert (case / "loads").is_dir() and not (case / "cyl.forces").exists()
    _run(case, output_file="one.csv")
    assert (case / "one.csv").is_file()


# ---------------------------------------------------------------------------
# What the '#' headers say
# ---------------------------------------------------------------------------

@needs_example
def test_headers_carry_values_not_the_files_they_came_from(tmp_path):
    """A table records what a Cd was divided by, not where the number was read.

    The two are different claims: a domain.yml can be edited afterwards, and a
    header pointing at one says nothing about the numbers below it.
    """
    case = _lean_case(tmp_path / "BR0SG0U1P0", steps=(100, 200, 300))
    _declared(case)
    _run(case, quantity="force_coeff", sectional=48, timestep=None, t1=100, t2=300)

    summary = _header(case / "cyl.force_coeff" / "summary.csv")
    assert not any("domain.yml" in line or ".def" in line for line in summary)
    joined = " ".join(summary)
    for value in ("rho: 1000", "U_inf: 1", "q = 0.5*rho*U^2: 500", "diameter: 1",
                  "length: 12", "span axis: +x", "drag (flow): +z"):
        assert value in joined, value


@needs_example
def test_the_common_block_is_in_summary_not_repeated_per_timestep(tmp_path):
    """The reference state belongs to the run, so it is stated once."""
    case = _lean_case(tmp_path / "BR0SG0U1P0", steps=(100, 200, 300))
    _declared(case)
    _run(case, quantity="force_coeff", sectional=4, timestep=None, t1=100, t2=300)

    written = case / "cyl.force_coeff"
    summary = _header(written / "summary.csv")
    sectional = _header(written / "sectional_100.csv")

    assert len(sectional) < len(summary)
    assert not any(line.startswith("rho:") for line in sectional)
    assert any("summary.csv" in line for line in sectional)
    # ...but enough to read the numbers below without opening anything else.
    assert any("q = 500" in line for line in sectional)
    assert any("timestep: 100" in line for line in sectional)


@needs_example
def test_each_table_says_what_it_was_divided_by(tmp_path):
    """A single --output NAME.csv holds sections, so it is D*dx, not D*L."""
    case = _lean_case(tmp_path / "BR0SG0U1P0")
    _declared(case)

    _run(case, quantity="force_coeff", sectional=6, output_file="sections.csv")
    this = [ln for ln in _header(case / "sections.csv") if ln.startswith("this table:")]
    assert this and "D * dx" in this[0]

    # Without --sectional the same file holds one row per timestep: D * L.
    _run(case, quantity="force_coeff", output_file="whole.csv")
    lines = _header(case / "whole.csv")
    this = [ln for ln in lines if ln.startswith("this table:")]
    assert this and "D * L" in this[0]
    assert not any("sectional_<step>" in ln for ln in lines)


# ---------------------------------------------------------------------------
# Sections belong to the body, not to the mesh
# ---------------------------------------------------------------------------

def _helical_stations(n_sections=48, per_layer=252):
    """The spanwise layer pattern of the helical-groove mesh, CH4SG3U1P1.

    96 layers over a body of 12, two to each 0.25 slice, sitting at 1/12 and 2/12
    of the way through it -- so the spacing alternates 0.0833 / 0.1667 rather than
    being uniform. Reconstructed rather than shipped: the case is 17M elements and
    lives outside this repo.
    """
    layers = np.sort(np.concatenate([(1 + 3 * np.arange(n_sections)) / 12.0,
                                     (2 + 3 * np.arange(n_sections)) / 12.0]))
    return np.repeat(layers, per_layer)


def _uniform_stations(n_sections=48, per_layer=248):
    """The layer pattern of the bare and straight-groove meshes: 0.125 + 0.25k.

    One layer to a slice, landing exactly on a boundary under min(x) anchoring
    just as the helical one does -- but 0.125 and 0.25 are powers of two, so
    (x - x_min)/w is exactly integral and floor() is deterministic. Same
    degeneracy, different arithmetic, and it survives by luck rather than design.
    """
    return np.repeat(0.125 + 0.25 * np.arange(n_sections), per_layer)


def test_anchoring_at_the_origin_removes_the_degeneracy(case):
    """Not "gets the right answer despite it" -- removes it.

    Under min(x) anchoring every layer of all three meshes sits exactly on a slice
    boundary, and only the binary representability of the coordinates decides
    whether floor() lands consistently. Anchored at the declared origin, no layer
    is on a boundary at all, so there is no tie for rounding to break.
    """
    reference = co.resolve(case, "cyl", _args(), LOG)
    reference.length = 12.0
    width = 12.0 / 48

    for stations in (_uniform_stations(), _helical_stations(per_layer=1)):
        layers = np.unique(stations)
        on_edge = lambda root: int(np.sum(
            np.abs((layers - root) / width - np.round((layers - root) / width)) < 1e-12))
        assert on_edge(layers.min()) > 0, "the fixture should be degenerate as found"
        assert on_edge(0.0) == 0, "anchored at the body, nothing sits on an edge"


def test_the_exactly_representable_meshes_were_never_affected(case):
    """Which is why this went unnoticed: the bare and straight cases are clean."""
    reference = co.resolve(case, "cyl", _args(), LOG)
    reference.length = 12.0
    station = _uniform_stations()
    centroid = np.column_stack([station, np.zeros_like(station),
                                np.zeros_like(station)])
    drifted = np.bincount(
        np.clip(((station - station.min()) / (12.0 / 48)).astype(int), 0, 47),
        minlength=48)
    assert drifted.min() == drifted.max() == 248        # degenerate, but consistent
    sections = co.build_sections(centroid, reference, 48, LOG)
    assert sections.counts.min() == sections.counts.max() == 248


def test_sections_are_anchored_to_the_body_not_its_first_element(case):
    """Anchoring at min(centroid) puts section edges exactly on element layers.

    On this mesh every other layer then lands on a boundary, and which side it
    falls is decided by floating-point rounding -- so the misfilled sections are
    not at the ends, and not even reproducible. Anchored at the declared origin,
    a layer is in the slice its station is in, by construction.
    """
    reference = co.resolve(case, "cyl", _args(), LOG)
    reference.length = 12.0
    station = _helical_stations()
    centroid = np.column_stack([station, np.zeros_like(station),
                                np.zeros_like(station)])
    sections = co.build_sections(centroid, reference, 48, LOG)
    assert sections.counts.min() == sections.counts.max() == 252 * 2

    # What anchoring to the mesh would have done with the same stations:
    width = 12.0 / 48
    drifted = np.bincount(
        np.clip(((station - station.min()) / width).astype(int), 0, 47),
        minlength=48)
    misfilled = [i for i, v in enumerate(drifted) if v != 504]
    assert misfilled, "the fixture no longer reproduces the bug it is guarding"
    assert any(0 < i < 47 for i in misfilled), "and they are interior, not clipped ends"


def test_a_body_without_an_origin_falls_back_and_says_so(case, capsys):
    reference = co.resolve(case, "cyl", _args(), LOG)
    reference.origin = None
    station = _helical_stations(per_layer=1)
    centroid = np.column_stack([station, np.zeros_like(station),
                                np.zeros_like(station)])
    co.build_sections(centroid, reference, 48, LOG)
    assert "--origin" in capsys.readouterr().err


def test_elements_outside_the_declared_extent_are_reported(case, capsys):
    """domain.yml disagreeing with the mesh is worth a word, not a silent clip."""
    reference = co.resolve(case, "cyl", _args(), LOG)
    station = np.array([-1.0, 6.0, 13.0])
    centroid = np.column_stack([station, np.zeros(3), np.zeros(3)])
    co.build_sections(centroid, reference, 12, LOG)
    assert "outside the body's declared extent" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# The reference state a downstream reader depends on
# ---------------------------------------------------------------------------

# Parsed out of the '#' block by the MATLAB readers in the study tree, as
# `name: value`. They tolerate the block being split between a per-step table and
# a sibling summary.csv, but not a name that has been spelled differently -- and a
# missing one comes back NaN and scales a result by it rather than failing. So the
# spellings are a contract, and this is where it is written down.
REFERENCE_NAMES = ("rho", "U_inf", "diameter", "length",
                   "span axis", "drag (flow)", "lift", "body")
# A shear table and anything reduced from one also state the viscosity that made
# them (tau_w = mu * (omega x n)) and where theta is measured from. Neither is
# arithmetic anyone downstream redoes, but both are how the number was arrived at.
SHEAR_NAMES = REFERENCE_NAMES + ("mu", "theta")


def _reference_names_in(path, names=None):
    return {name for name in (names or REFERENCE_NAMES)
            for line in _header(path) if line.startswith(f"{name}:")
            or f"   {name}:" in line}


@needs_example
def test_every_table_states_the_whole_reference_state(tmp_path):
    """Each table names all seven, so no reader has to find a sibling to be sure.

    cyl.separation/ is the case that forces it: there is no summary.csv in it to
    hold a block in common, because separation.csv is an answer rather than a
    header.
    """
    case = _lean_case(tmp_path / "BR0SG0U1P0", steps=(100, 300))
    _declared(case)
    _run(case, quantity="wall_shear", timestep=None, t1=100, t2=300)
    _run(case, quantity="separation", body="cyl", sectional=8, azimuthal=36,
         timestep=None)

    _run(case, quantity="force_coeff", timestep=None, t1=100, t2=300)
    produced = [
        (case / "cyl.wall_shear" / "elements_100.csv", SHEAR_NAMES),
        (case / "cyl.wall_shear" / "summary.csv", SHEAR_NAMES),
        (case / "cyl.separation" / "azimuthal_100.csv", SHEAR_NAMES),
        (case / "cyl.separation" / "separation.csv", SHEAR_NAMES),
        (case / "cyl.force_coeff" / "summary.csv", REFERENCE_NAMES),
    ]
    for path, names in produced:
        assert path.exists(), path
        missing = set(names) - _reference_names_in(path, names)
        assert not missing, f"{path.name} does not state {sorted(missing)}"


@needs_example
def test_mu_is_the_one_the_shear_was_made_with(tmp_path):
    """Carried from the wall_shear header, not re-read from the .def.

    A separation table is a reduction of a shear that mu scaled. If the case has
    moved since, the value that made these numbers is the one worth recording --
    and it is the one already written into the tables being reduced.
    """
    case = _lean_case(tmp_path / "BR0SG0U1P0")
    _declared(case)
    _run(case, quantity="wall_shear")
    shear = case / "cyl.wall_shear" / "elements_100.csv"
    shear.write_text(shear.read_text().replace("mu: 1 ", "mu: 7 ", 1))
    _run(case, quantity="separation", body="cyl", sectional=4, timestep=None)
    stated = [ln for ln in _header(case / "cyl.separation" / "separation.csv")
              if ln.startswith("mu:")]
    assert stated and stated[0].startswith("mu: 7"), stated


@needs_example
def test_a_per_step_table_stays_shorter_than_the_summary(tmp_path):
    """Stating the reference state everywhere must not undo the header split."""
    case = _lean_case(tmp_path / "BR0SG0U1P0", steps=(100, 300))
    _declared(case)
    _run(case, quantity="force_coeff", sectional=8, timestep=None, t1=100, t2=300)
    written = case / "cyl.force_coeff"
    assert len(_header(written / "sectional_100.csv")) < \
        len(_header(written / "summary.csv"))
