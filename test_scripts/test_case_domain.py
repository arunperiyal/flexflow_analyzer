"""Tests for `case domain` and the domain.yml it keeps.

The point of the file is joining up three vocabularies that name one body -- the
.def's `beamSolid`, the `riser.cyl.srf` on disk, the PLT zone `cyl` -- so most of
these check that the join survives being derived, written, read back and edited.
"""

import argparse
import os

import pytest

from src.core.def_config import DefConfig
from src.core.domain import (DomainConfig, DomainError, derive_from_def,
                             tag_from_file)
from src.core.parsers.def_parser import as_file, as_list, parse_blocks
from src.commands.case.domain_impl.command import (DomainCommandError, check_case,
                                                   execute_domain, init_case,
                                                   resolve_target_and_case)

DEF_TEMPLATE = """
nodeCoordinates {
    coordinates             = File( "riser.crd" )
}

elementGroup( "interior" ) {
    elements                = File( "riser.fluid.cnn" )
    shape                   = eightNodeBrick
}

physicalField {
    flow	= navierStokes
    mesh	= ale
}

define{
	variable = DIA
	value	 = 2.0
}

define{
	variable = SPAN
	value	 = 6*DIA
}

define{
	variable = RHO
	value = 1000.0
}

define{
	variable = MU
	value = RHO/500
}

# a commented-out body must not be picked up
#beamSolid( "ghost" ) {
#	pnt1 = {0, 0, 0}
#}

beamSolid( "beam_1" ) {
	nElems	= 48
	rhoA 	= 12.5
	EA	= 0.06
	EIx	= 3.0
	EIy	= 3.0
	EIz	= 3.0
	GJ	= 1e4
	J	= 0.1
	pnt1 	= {0, 0, 0}
	pnt2	= {SPAN, 0, 0}
	bcType	= fixFix
	activeDof = {0, 1, 1, 0, 1, 1}
	surfaceOutputs = { "cylinder_body" }
}

densityModel( "fluid" ) {
    density         = RHO
}

viscosityModel ( "fluid" ) {
    viscosity       = MU
}

materialModel  ( "fluid" ) {
	densityModel	= "fluid"
	viscosityModel	= "fluid"
}

elementProperty( "interior" ) {
	materialModel	= "fluid"
}

outputSurface( "cylinder_body"  ){
    surfaces        = File( "riser.cyl.srf" )
    elementGroup    = "interior"
}

outputTimeHistory( "riser_probe" ){
    type	    = nodal
    nodes	    = File( "riser.cyl_nodes.nbc" )
    outputFrequency = 1
}

# a coordinates block belongs to no body: its points need not sit on one
outputTimeHistory( "far_field" ){
    type	    = coordinates
    coordinates	    = File( "probe_dat.txt" )
}

# 'cylinder2' merely starts like 'cyl'; it is a different body
outputTimeHistory( "other_body" ){
    type	    = nodal
    nodes	    = File( "riser.cylinder2.nbc" )
}
"""


@pytest.fixture
def case(tmp_path):
    """A case directory with a .def and a couple of the geometry files it names."""
    (tmp_path / "riser.def").write_text(DEF_TEMPLATE)
    (tmp_path / "simflow.config").write_text('problem = "riser"\n')
    (tmp_path / "riser.cyl.srf").write_text("1 2 3 4\n")
    (tmp_path / "riser.cyl_BL.nbc").write_text("1\n2\n")
    (tmp_path / "riser.cyl_nodes.nbc").write_text("1\n2\n3\n")
    return tmp_path


def _args(**overrides):
    """An argparse Namespace with every flag `case domain` reads, defaulted off."""
    defaults = dict(target=None, case=None, init=False, check=False, path=False,
                    list=False, show=None, add=False, remove=None, name=None,
                    set=None, type=None, geotag=None, plttag=None, radius=None,
                    length=None, origin=None, axis=None, force=False,
                    verbose=False, help=False)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# The .def block parser
# ---------------------------------------------------------------------------

def test_block_body_survives_a_nested_vector(case):
    """A beamSolid holds `pnt1 = {0, 0, 0}`, so its body is not `[^}]*`."""
    beams = parse_blocks(case / "riser.def", "beamSolid")
    assert len(beams) == 1
    values = beams[0]["values"]
    # Everything after pnt1 is what a first-`}` match would have lost.
    assert values["bcType"] == "fixFix"
    assert as_list(values["activeDof"]) == ["0", "1", "1", "0", "1", "1"]
    assert as_list(values["surfaceOutputs"]) == ["cylinder_body"]
    assert as_file(values["pnt1"]) is None


def test_commented_blocks_are_not_read(case):
    assert [b["name"] for b in parse_blocks(case / "riser.def", "beamSolid")] == ["beam_1"]


def test_nested_blocks_are_not_top_level(case):
    kinds = [b["kind"] for b in parse_blocks(case / "riser.def")]
    assert kinds.count("elementGroup") == 1
    assert "File" not in kinds


def test_tag_from_file():
    assert tag_from_file("riser.cyl.srf", "riser") == "cyl"
    assert tag_from_file("riser.fluid.cnn", "riser") == "fluid"
    assert tag_from_file("riser.cyl_BL.nbc", "riser") == "cyl_BL"
    # No problem name given: the first dotted component is taken as the prefix.
    assert tag_from_file("riser.cyl.srf") == "cyl"
    # Nothing between the prefix and the extension is not a tag.
    assert tag_from_file("riser.crd", "riser") is None


# ---------------------------------------------------------------------------
# define{} expression evaluation
# ---------------------------------------------------------------------------

def test_define_expressions_are_evaluated(case):
    cfg = DefConfig(case / "riser.def")
    assert cfg.evaluate("DIA") == 2.0
    assert cfg.evaluate("SPAN") == 12.0        # 6*DIA, followed through
    assert cfg.evaluate("MU") == 2.0           # RHO/500
    assert cfg.evaluate("2^3") == 8.0          # '^' is a power, not xor
    assert cfg.resolved_variables["SPAN"] == 12.0


def test_non_arithmetic_expressions_give_none(case):
    cfg = DefConfig(case / "riser.def")
    assert cfg.evaluate("fixFix") is None      # a name, but not a variable
    assert cfg.evaluate("1/0") is None         # arithmetic that cannot be done
    assert cfg.evaluate('__import__("os")') is None   # not arithmetic at all
    assert cfg.evaluate("") is None


def test_a_circular_define_does_not_hang(tmp_path):
    (tmp_path / "loop.def").write_text(
        "define{\n variable = A\n value = B\n}\n"
        "define{\n variable = B\n value = A\n}\n")
    assert DefConfig(tmp_path / "loop.def").evaluate("A") is None


# ---------------------------------------------------------------------------
# Deriving domain.yml from the .def
# ---------------------------------------------------------------------------

def test_derive_joins_the_vocabularies(case):
    domain, _ = derive_from_def(case)
    body = domain.bodies[0]
    # beamSolid -> surfaceOutputs -> outputSurface -> riser.cyl.srf -> 'cyl'
    assert body["geotag"] == "cyl"
    assert body["type"] == "beam"
    # elementGroup( "interior" ) -> riser.fluid.cnn -> 'fluid'
    assert domain.field["name"] == "interior"
    assert domain.field["geotag"] == "fluid"
    assert domain.field["type"] == "fluid"


def test_a_body_links_to_the_block_written_along_it(case):
    domain, _ = derive_from_def(case)
    assert domain.bodies[0]["outputs"] == [
        {"block": "riser_probe", "nodes": "riser.cyl_nodes.nbc"}]


def test_a_similarly_named_set_is_a_different_body(case):
    """'cylinder2' starts like 'cyl' but is not part of it."""
    blocks = [o["block"] for o in derive_from_def(case)[0].bodies[0]["outputs"]]
    assert "other_body" not in blocks
    # A coordinates block indexes its own points, not a body's nodes.
    assert "far_field" not in blocks


def test_nothing_the_def_already_holds_is_copied(case):
    """The file says where a thing is, not what it is made of.

    The .def in this fixture carries a beam's stiffnesses and the fluid's density
    and viscosity; none of them belong here, where a second copy could drift.
    """
    domain, _ = derive_from_def(case)
    assert set(domain.field) == {"name", "type", "geotag", "plttag"}
    assert set(domain.bodies[0]) == {"name", "type", "geotag", "plttag",
                                     "geometry", "outputs"}


def test_derive_evaluates_and_measures(case):
    body = derive_from_def(case)[0].bodies[0]
    # pnt2 = {SPAN, 0, 0} with SPAN = 6*DIA = 12
    assert body["geometry"]["length"] == 12.0
    assert body["geometry"]["axis"] == "+x"
    assert body["geometry"]["origin"] == [0, 0, 0]


def test_derive_leaves_the_radius_unknown(case):
    """The radius is in the mesh, not the .def, so it must not be invented."""
    domain, _ = derive_from_def(case)
    assert domain.bodies[0]["geometry"]["radius"] is None


def test_derive_says_what_it_could_not_work_out(case):
    _, notes = derive_from_def(case)
    assert any("PLT" in note for note in notes)   # no binary/ here, so no plttag


def test_derive_without_a_def_is_an_error(tmp_path):
    with pytest.raises(DomainError):
        derive_from_def(tmp_path)


# ---------------------------------------------------------------------------
# The file itself
# ---------------------------------------------------------------------------

def test_round_trip_through_yaml(case):
    domain, _ = derive_from_def(case)
    path = domain.save()
    text = path.read_text()
    assert text.startswith("# domain.yml")
    assert "origin: [0, 0, 0]" in text        # short scalar lists stay on one line

    reloaded = DomainConfig(path)
    assert reloaded.bodies[0]["geometry"]["length"] == 12.0
    assert reloaded.field["name"] == domain.field["name"]


def test_a_body_resolves_by_any_of_its_three_names(case):
    domain, _ = derive_from_def(case)
    domain.set_body("cyl", "name", "riser_body")
    domain.set_body("riser_body", "plttag", "CYL_ZONE")
    for token in ("riser_body", "cyl", "CYL_ZONE", "cyl_zone"):
        assert domain.body(token) is not None, token
    assert domain.body("nothing") is None


def test_outputs_resolve_by_any_of_the_bodys_names(case):
    domain, _ = derive_from_def(case)
    assert domain.outputs("cyl")[0]["nodes"] == "riser.cyl_nodes.nbc"
    assert domain.outputs("CYL")[0]["block"] == "riser_probe"   # plttag, cased
    assert domain.outputs("nothing") == []


def test_check_flags_a_missing_node_file(case):
    domain, _ = derive_from_def(case)
    domain.set_body("cyl", "outputs", [{"block": "riser_probe",
                                        "nodes": "riser.gone.nbc"}])
    domain.save()
    assert any(severity == "warning" and "riser.gone.nbc" in message
               for severity, message in check_case(case))


def test_check_flags_an_output_naming_no_block(case):
    domain, _ = derive_from_def(case)
    domain.set_body("cyl", "outputs", [{"nodes": "riser.cyl_nodes.nbc"}])
    domain.save()
    assert any(severity == "error" and "outputs" in message
               for severity, message in check_case(case))


def test_geometry_files_include_the_bodys_other_sets(case):
    domain, _ = derive_from_def(case)
    names = {p.name for p in domain.geometry_files("cyl", "riser", case)}
    # The boundary-layer and probe node sets belong to the same body as the surface.
    assert names == {"riser.cyl.srf", "riser.cyl_BL.nbc", "riser.cyl_nodes.nbc"}


def test_bodies_written_as_a_mapping_are_accepted(tmp_path):
    """A hand-written file may label bodies rather than list them."""
    (tmp_path / "domain.yml").write_text(
        "bodies:\n  cyl:\n    type: beam\n    geotag: cyl\n")
    domain = DomainConfig(tmp_path / "domain.yml")
    assert domain.body_names() == ["cyl"]
    assert domain.body("cyl")["type"] == "beam"


def test_a_list_of_single_key_mappings_is_accepted(tmp_path):
    (tmp_path / "domain.yml").write_text(
        "bodies:\n  - cyl:\n      type: beam\n      geotag: cyl\n")
    assert DomainConfig(tmp_path / "domain.yml").body_names() == ["cyl"]


def test_a_file_that_is_not_a_mapping_is_refused(tmp_path):
    (tmp_path / "domain.yml").write_text("- just\n- a\n- list\n")
    with pytest.raises(DomainError):
        DomainConfig(tmp_path / "domain.yml")


def test_dotted_keys_reach_inside(case):
    domain, _ = derive_from_def(case)
    domain.set_body("cyl", "geometry.radius", 0.5)
    domain.set_body("cyl", "properties.new.deeper", 3)
    assert domain.body("cyl")["geometry"]["radius"] == 0.5
    assert domain.body("cyl")["properties"]["new"]["deeper"] == 3


def test_a_duplicate_body_name_is_refused(case):
    domain, _ = derive_from_def(case)
    with pytest.raises(DomainError):
        domain.add_body("cyl", type="beam")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_check_flags_a_geotag_with_no_files(case):
    domain, _ = derive_from_def(case)
    domain.save()
    problems = check_case(case)
    # riser.fluid.cnn was never created, so the field's geotag matches nothing.
    assert any(severity == "warning" and "fluid" in message
               for severity, message in problems)
    assert not any(severity == "error" for severity, _ in problems)


def test_check_flags_a_duplicate_tag(case):
    domain, _ = derive_from_def(case)
    domain.set_body("cyl", "geotag", "fluid")     # already the field's
    domain.save()
    assert any(severity == "error" and "geotag" in message
               for severity, message in check_case(case))


def test_check_flags_an_unknown_type(case):
    domain, _ = derive_from_def(case)
    domain.set_body("cyl", "type", "wobbly")
    domain.save()
    assert any(severity == "error" and "wobbly" in message
               for severity, message in check_case(case))


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------

def test_target_and_case_share_two_slots():
    """`domain body <case>` and `domain <case>` both have to parse."""
    assert resolve_target_and_case(_args(target="body", case="C1")) == ("body", "C1")
    assert resolve_target_and_case(_args(target="field")) [0] == "field"
    # A lone word that is not a target is the case.
    assert resolve_target_and_case(_args(target="C1")) == (None, "C1")


def test_a_case_named_before_a_target_is_an_error():
    with pytest.raises(DomainCommandError):
        resolve_target_and_case(_args(target="C1", case="body"))


def test_resolve_falls_back_to_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert resolve_target_and_case(_args())[1] == os.getcwd()


def test_init_then_edit_then_read_back(case, capsys):
    execute_domain(_args(case=str(case), init=True))
    assert (case / "domain.yml").exists()

    execute_domain(_args(target="body", case=str(case), name="cyl", radius="0.5"))
    execute_domain(_args(target="field", case=str(case), set=["name=water"]))

    domain = DomainConfig(case / "domain.yml")
    assert domain.body("cyl")["geometry"]["radius"] == 0.5
    assert domain.field["name"] == "water"

    capsys.readouterr()
    execute_domain(_args(target="body", case=str(case), list=True))
    assert "cyl" in capsys.readouterr().out


def test_init_refuses_to_overwrite(case):
    init_case(case)
    with pytest.raises(DomainCommandError):
        init_case(case)
    # --force derives it again, discarding whatever was added by hand.
    domain = DomainConfig(case / "domain.yml")
    domain.set_body("cyl", "geometry.radius", 0.5)
    domain.save()
    init_case(case, force=True)
    assert DomainConfig(case / "domain.yml").body("cyl")["geometry"]["radius"] is None


def test_outputs_survive_the_round_trip(case):
    init_case(case)
    text = (case / "domain.yml").read_text()
    assert "outputs:" in text and "block: riser_probe" in text
    assert DomainConfig(case / "domain.yml").outputs("cyl")[0]["nodes"] == \
        "riser.cyl_nodes.nbc"


def test_add_defaults_the_tags_to_the_name(case):
    init_case(case)
    execute_domain(_args(target="body", case=str(case), add=True, name="strake",
                         type="rigid"))
    body = DomainConfig(case / "domain.yml").body("strake")
    assert body["geotag"] == "strake" and body["plttag"] == "strake"


def test_add_without_a_type_is_refused(case, capsys):
    init_case(case)
    with pytest.raises(SystemExit):
        execute_domain(_args(target="body", case=str(case), add=True, name="strake"))
    assert "type" in capsys.readouterr().err.lower()


def test_an_unknown_type_names_the_valid_ones(case, capsys):
    init_case(case)
    with pytest.raises(SystemExit):
        execute_domain(_args(target="body", case=str(case), add=True, name="x",
                             type="wobbly"))
    assert "beam" in capsys.readouterr().err


def test_set_values_are_read_as_yaml(case):
    init_case(case)
    execute_domain(_args(target="body", case=str(case), name="cyl",
                         set=["geometry.radius=0.5", "geometry.origin=[1, 2, 3]",
                              "properties.note=free text"]))
    body = DomainConfig(case / "domain.yml").body("cyl")
    assert body["geometry"]["radius"] == 0.5
    assert body["geometry"]["origin"] == [1, 2, 3]
    assert body["properties"]["note"] == "free text"


def test_geometry_flags_are_refused_on_the_field(case, capsys):
    init_case(case)
    with pytest.raises(SystemExit):
        execute_domain(_args(target="field", case=str(case), radius="0.5"))
    assert "radius" in capsys.readouterr().err


def test_remove_takes_a_body_out(case):
    init_case(case)
    execute_domain(_args(target="body", case=str(case), remove="cyl"))
    assert DomainConfig(case / "domain.yml").body_names() == []


def test_editing_needs_a_case_that_has_the_file(tmp_path, capsys):
    with pytest.raises(SystemExit):
        execute_domain(_args(target="body", case=str(tmp_path), list=True))
    assert "--init" in capsys.readouterr().err


def test_the_wildcard_case_refuses_to_edit(case, capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        execute_domain(_args(target="body", case="*", add=True, name="x", type="beam"))
    assert "reading" in capsys.readouterr().err


def test_refusing_to_overwrite_flags_a_file_from_an_older_shape(case):
    """A domain.yml written before properties and source were dropped.

    --init will not overwrite, so such a file simply stays as it was -- and
    someone comparing it against a fresh one has no way to tell why they differ
    unless the refusal says so.
    """
    (case / "domain.yml").write_text(
        "version: 1\n"
        "field: {name: interior, type: fluid, properties: {density: 1000.0}}\n"
        "bodies:\n"
        "  - {name: cyl, type: beam, source: {block: 'beamSolid(\"beam_1\")'}}\n")
    with pytest.raises(DomainCommandError) as exc:
        init_case(case)
    assert "properties" in str(exc.value) and "source" in str(exc.value)
    assert "--force" in str(exc.value)


def test_a_current_file_is_refused_without_the_aside(case):
    init_case(case)
    with pytest.raises(DomainCommandError) as exc:
        init_case(case)
    assert "no longer writes" not in str(exc.value)


def test_force_rewrites_an_older_file_in_the_current_shape(case):
    (case / "domain.yml").write_text(
        "version: 1\n"
        "field: {name: interior, type: fluid, properties: {density: 1000.0}}\n"
        "bodies:\n"
        "  - {name: cyl, type: beam, properties: {axial_stiffness: 0.06}}\n")
    init_case(case, force=True)
    text = (case / "domain.yml").read_text()
    assert "properties:" not in text and "source:" not in text
