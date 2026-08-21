"""Help messages for the case domain command."""

from ....utils.colors import Colors


def print_domain_help():
    """Print case domain command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Case Domain Command{Colors.RESET}

What a case's domain is made of -- the fluid field and the bodies in it -- kept in
{Colors.YELLOW}domain.yml{Colors.RESET} beside the .def.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case domain [CASE]                     {Colors.DIM}# summary of the domain{Colors.RESET}
    flexflow case domain [CASE] --init              {Colors.DIM}# derive it from the .def{Colors.RESET}
    flexflow case domain [CASE] --check             {Colors.DIM}# does the case still agree?{Colors.RESET}
    flexflow case domain body [CASE] [options]
    flexflow case domain field [CASE] [options]

    CASE may be left out: the interactive case context is used, or the current
    directory. {Colors.YELLOW}*{Colors.RESET} means every case in the .cases registry, for reading
    and for --init.

{Colors.BOLD}WHY:{Colors.RESET}

    A case names the same cylinder four times, in four vocabularies, and joins
    none of them up:

        {Colors.YELLOW}riser.def{Colors.RESET}    beamSolid( "beam_1" ), elementGroup( "interior" )
        {Colors.YELLOW}on disk{Colors.RESET}      riser.cyl.srf, riser.cyl_BL.nbc, riser.fluid.cnn
        {Colors.YELLOW}in the PLT{Colors.RESET}   zone "cyl", zone "FIELD"
        {Colors.YELLOW}in the othd{Colors.RESET}  outputTimeHistory( "riser_probe" ), along riser.cyl_nodes.nbc

    So `field compute --zone cyl`, `case out --map cyl_nodes` and the beamSolid
    the displacements belong to are four names for one body, and only the person
    at the keyboard knows it. domain.yml writes that join down once:

        {Colors.BOLD}name{Colors.RESET}     what you call it
        {Colors.BOLD}type{Colors.RESET}     what it is: a body is beam | rigid | fixed, the field is fluid
        {Colors.BOLD}geotag{Colors.RESET}   the token in its geometry file names -- 'cyl' is riser.cyl.srf
        {Colors.BOLD}plttag{Colors.RESET}   its zone name inside a .plt
        {Colors.BOLD}outputs{Colors.RESET}  the outputTimeHistory block written along it, and the node
                 file that orders its records

    Given those, a body named once resolves to its mesh files, its PLT zone and
    its displacement history without anything re-deriving the convention.

    It says {Colors.BOLD}where a thing is{Colors.RESET}, not what it is made of. Shape is here because
    nothing else records it. A beam's stiffnesses and the fluid's density and
    viscosity are not: the .def has them and the solver reads them from there,
    and a second copy in a file nobody feeds back would only drift.

{Colors.BOLD}OPTIONS:{Colors.RESET}

  {Colors.BOLD}On the domain as a whole:{Colors.RESET}
    {Colors.YELLOW}--init{Colors.RESET}             Write domain.yml from the case's own .def and PLT
                       zones. Refuses to overwrite; --force does it again.
    {Colors.YELLOW}--check{Colors.RESET}            Check every name, tag and type against the case's
                       real files: geotags against the geometry files present,
                       plttags against the zones in the newest PLT, and every
                       output's node file against what is on disk. Exits
                       non-zero if anything is wrong.
    {Colors.YELLOW}--path{Colors.RESET}             Print the path domain.yml would have, and stop.

  {Colors.BOLD}On a body or the field:{Colors.RESET}
    {Colors.YELLOW}--list{Colors.RESET}             Table of what is declared.
    {Colors.YELLOW}--show [NAME]{Colors.RESET}      One entry in full, with the geometry files its
                       geotag matches. A body needs the NAME; the field does not.
    {Colors.YELLOW}--add{Colors.RESET}              Declare a new one. Needs --name and --type.
    {Colors.YELLOW}--remove NAME{Colors.RESET}      Remove a body.
    {Colors.YELLOW}--name NAME{Colors.RESET}        Which body to edit -- or the name to give a new one.
    {Colors.YELLOW}--set KEY=VALUE{Colors.RESET}    Set anything, repeatable. Dotted keys reach inside:
                       {Colors.DIM}--set geometry.radius=0.5 --set plttag=cyl_surface{Colors.RESET}
                       The value is read as YAML, so 0.5 is a number, [0, 0, 0] is
                       a vector and null is an explicit "not known".

  {Colors.BOLD}Shorthand for the common keys:{Colors.RESET}
    {Colors.YELLOW}--type T{Colors.RESET}           beam | rigid | fixed for a body, fluid for the field
    {Colors.YELLOW}--geotag T{Colors.RESET}         Token in the geometry file names
    {Colors.YELLOW}--plttag T{Colors.RESET}         Zone name in the PLT
    {Colors.YELLOW}--radius R{Colors.RESET}         Body radius        {Colors.DIM}(= --set geometry.radius=R){Colors.RESET}
    {Colors.YELLOW}--length L{Colors.RESET}         Body length        {Colors.DIM}(= --set geometry.length=L){Colors.RESET}
    {Colors.YELLOW}--origin X,Y,Z{Colors.RESET}     Body origin        {Colors.DIM}(= --set geometry.origin=[X,Y,Z]){Colors.RESET}
    {Colors.YELLOW}--axis A{Colors.RESET}           +x -x +y -y +z -z, or a vector like '[1, 0, 0]'

    {Colors.YELLOW}--force{Colors.RESET}            With --init: derive again over an existing file.
    {Colors.YELLOW}--verbose, -v{Colors.RESET}      Show what was read
    {Colors.YELLOW}--help, -h{Colors.RESET}         Show this help message

{Colors.BOLD}WHAT --init CAN AND CANNOT WORK OUT:{Colors.RESET}

    The field is the .def's first elementGroup, tagged from the element file it
    names: `riser.fluid.cnn` makes its geotag `fluid`.

    Every beamSolid becomes a body. Its origin, length and axis come from
    pnt1/pnt2, with define{{}} variables {Colors.BOLD}evaluated{Colors.RESET} on the way --
    `pnt2 = {{SPAN, 0, 0}}` with `SPAN = 12*DIA` gives a length of 12. Its geotag
    comes from surfaceOutputs -> outputSurface -> the .srf file that block names.
    Its {Colors.YELLOW}outputs{Colors.RESET} are the nodal outputTimeHistory blocks whose node file
    carries the body's tag -- `riser.cyl_nodes.nbc` belongs to `cyl`, and
    `riser.cylinder2.nbc` does not.

    plttags come from the zone names in the newest PLT under binary/: the volume
    zone is the field, a surface zone is a body.

    A beam's {Colors.BOLD}radius{Colors.RESET} is in the mesh, not the .def, so it is written as
    {Colors.YELLOW}null{Colors.RESET} rather than guessed. A guessed radius would silently rescale
    every coefficient normalised by it, and nothing downstream could tell.
    Everything --init could not work out is printed as a note when it runs.

{Colors.BOLD}EDITING:{Colors.RESET}

    domain.yml is a plain YAML file -- edit it by hand if you prefer. The
    {Colors.YELLOW}--add{Colors.RESET}/{Colors.YELLOW}--set{Colors.RESET} paths {Colors.BOLD}rewrite{Colors.RESET} it, so a comment added inside the file
    does not survive an edit; the header it carries is regenerated each time.

    On --add, geotag and plttag default to the body's name -- the cylinder called
    cyl is usually riser.cyl.srf and zone cyl -- and it says so, because a case
    that names them otherwise would get two wrong tags in silence.

    After any edit, anything the case now contradicts is reported straight away.

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}Start from what the case already says:{Colors.RESET}
    flexflow case domain BR0SG0U1P0 --init
    flexflow case domain BR0SG0U1P0                {Colors.DIM}# read it back{Colors.RESET}

  {Colors.BOLD}Fill in what the .def could not say:{Colors.RESET}
    flexflow case domain body --name cyl --radius 0.5
    flexflow case domain field --set name=water
    {Colors.DIM}(--init names the field after its elementGroup, e.g. 'interior'){Colors.RESET}

  {Colors.BOLD}Declare a body by hand:{Colors.RESET}
    flexflow case domain body --add --name cyl --type beam
    flexflow case domain body --add --name strake --type rigid --geotag stk \\
        --radius 0.6 --length 12 --origin 0,0,0 --axis +x

  {Colors.BOLD}Look at one thing:{Colors.RESET}
    flexflow case domain body --list
    flexflow case domain body --show cyl
    flexflow case domain field --show

  {Colors.BOLD}Check it against the case:{Colors.RESET}
    flexflow case domain BR0SG0U1P0 --check

  {Colors.BOLD}Across every registered case:{Colors.RESET}
    flexflow case domain * --list
    flexflow case domain * --init
    {Colors.DIM}(or set the context once: use case:*){Colors.RESET}

{Colors.BOLD}NOTES:{Colors.RESET}

  - The first word after `domain` is read as a target only when it is exactly
    {Colors.YELLOW}body{Colors.RESET} or {Colors.YELLOW}field{Colors.RESET}; anything else is taken as the case directory.
  - A body resolves by name, geotag {Colors.BOLD}or{Colors.RESET} plttag, so whichever of the three
    names you have to hand will find it.
  - {Colors.YELLOW}outputs{Colors.RESET} is a list: two blocks may read different node sets on the same
    body, at different frequencies, and both belong to it.
  - Only the PLT header is read to list zones, so --init and --check stay fast on
    a case whose PLT files are hundreds of megabytes.
  - The {Colors.YELLOW}*{Colors.RESET} case is read-only apart from --init: editing every case's domain
    at once would write the same body into all of them.

""")
