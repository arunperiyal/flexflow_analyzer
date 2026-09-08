"""Help messages for case out command."""

from ....utils.colors import Colors


def print_out_help():
    """Print case out command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Case Out Command{Colors.RESET}

Build small derived files from a case's own inputs.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case out <case_dir> --map [NAME]
    flexflow case out * --map            {Colors.DIM}# every case in .cases{Colors.RESET}
    flexflow case out * --list           {Colors.DIM}# survey them all in one table{Colors.RESET}

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--list{Colors.RESET}             Table of the case's outputTimeHistory blocks:
                       name, input file, predicted othId, type, map file, probe.
                       Says which blocks are mapped and what each othId holds.
                       A case with an outputSurface block gets a second table
                       for it -- name, .srf, predicted osgId, elementGroup,
                       shape, map file -- printed only when the case has one,
                       since most don't yet. With the {Colors.YELLOW}*{Colors.RESET} case both surveys
                       run across the whole .cases registry, each as one table
                       with a Case column -- which is how you see which cases
                       still need mapping.
    {Colors.YELLOW}--map [NAME]{Colors.RESET}  Write a map for every outputTimeHistory block in the
                       .def that names a file its records are indexed by, and
                       for every outputSurface block. Give NAME to do just
                       one, matched against the block name or the
                       node/point/surface-set name.
    {Colors.YELLOW}--probe-type TYPE{Colors.RESET}  Declare how the probe set should be read:
                       {Colors.YELLOW}point{Colors.RESET} independent locations, nothing shared between them
                       {Colors.YELLOW}line{Colors.RESET}  ordered samples along a curve -- parameterise by arc length
                       {Colors.YELLOW}helix{Colors.RESET} a curve wrapping a body -- axial position and angle,
                             not arc length alone
                       {Colors.YELLOW}surface{Colors.RESET} a patch -- parameterise by two coordinates
                       {Colors.YELLOW}cloud{Colors.RESET} scattered, no structure to exploit
    {Colors.YELLOW}--closed{Colors.RESET}           With --probe-type line or helix: the curve joins up
                       (a ring), needing different handling from an open curve
    {Colors.YELLOW}--verbose, -v{Colors.RESET}      Show which files were read
    {Colors.YELLOW}--help, -h{Colors.RESET}         Show this help message

{Colors.BOLD}WHY:{Colors.RESET}

    An outputTimeHistory writes its records {Colors.BOLD}positionally{Colors.RESET}: row k of every
    output block is the k-th entry of the file the block was given. The othd
    carries no id and no coordinate of its own, so reading one back needs that
    file -- and for a nodal block, the mesh coordinates too, which are usually
    the largest input in the case (137 MB for a 1.8M-node riser) even when the
    output covers a few dozen nodes.

    This writes the few dozen out once, so the mesh can be deleted and the othd
    stays readable.

{Colors.BOLD}OUTPUT:{Colors.RESET}

    One {Colors.YELLOW}othd.<block>.map{Colors.RESET} per mappable block, in the case directory, named
    after the outputTimeHistory block rather than its input file -- two blocks may
    read the same node file, and naming by file would put both on one path. What a
    row says depends on what the block is indexed by:

    {Colors.BOLD}type = nodal{Colors.RESET} -- indexed by a node file, resolved against the mesh:

        row,node,x,y,z
        0,2,-2.1648901405887341e-17,3.5355339059327368e-01,-3.5355339059327379e-01

        {Colors.YELLOW}x, y, z{Colors.RESET} are {Colors.BOLD}undeformed{Colors.RESET} -- add the othd displacement to get
        where the node moved to.

    {Colors.BOLD}type = coordinates{Colors.RESET} -- indexed by its own point file, so no mesh is
    read and there is no node column: a requested point need not sit on a node.

        row,x,y,z
        0,0.0000000000000000e+00,0.0000000000000000e+00,3.0000000000000000e+00

    A point file is read as {Colors.YELLOW}index x y z{Colors.RESET} when it has four columns and the
    first reads as a row index, or {Colors.YELLOW}x y z{Colors.RESET} when it has three. The layout is
    checked rather than assumed -- taking the first three fields of a four-column
    file turns the point (0, 0, 3) into (1, 0, 0), which nothing downstream can
    detect. Anything else is an error rather than a guess.

    Rows keep the source file's order, because that order is what indexes the
    othd. They are not sorted.

    A block whose type names no file to index its records by is reported and
    skipped -- there is nothing to map it against. So is one whose input file is
    missing or empty: the solver writes no record for it either. Naming such a
    block with --map NAME is an error rather than a silent skip.

{Colors.BOLD}othId:{Colors.RESET}

    Each map carries {Colors.YELLOW}# othId: <n>{Colors.RESET} -- which output within the othd it
    describes. Declaration order in the .def does not give it: an output whose
    input file is missing or empty is not written at all, and every id after it
    shifts down. On BR0SG0U1P0, probe_dat.txt is absent, so "riser_probe" is
    othId 0 rather than 1.

    The id is {Colors.BOLD}predicted{Colors.RESET} from the .def and the files present, not read
    from an othd, and the header says so alongside it -- a reader that trusts a
    wrong id is worse off than one that has none.

    If an input file is {Colors.BOLD}newer{Colors.RESET} than the case's othd files, those were written
    without it and their ids are lower than the ones predicted here. That is
    reported and noted in the map. Read the ids from the othd and prefer them.

{Colors.BOLD}OUTPUT SURFACES (oisd):{Colors.RESET}

    An outputSurface is a different shape of output: its oisd holds {Colors.BOLD}one
    aggregate record per timestep for the whole surface{Colors.RESET} (totTrac, totMoment,
    totArea, avePres, ...), not one row per node -- so there is no positional
    row to resolve against the mesh the way a nodal othd needs.

    {Colors.YELLOW}oisd.<name>.map{Colors.RESET} is written anyway, but for a different reason: not to
    make the oisd readable, but to record {Colors.BOLD}which surface it is{Colors.RESET} -- the .srf
    and .nbc it is built from, and the osgId predicted for it, none of which
    the oisd file states either. Two tables, not one:

        row,node,x,y,z                         {Colors.DIM}# every node in the .nbc{Colors.RESET}
        0,2,-2.1648901405887341e-17,3.5355339059327368e-01,-3.5355339059327379e-01
        row,parent,id,node1,node2,node3,node4  {Colors.DIM}# every element in the .srf{Colors.RESET}
        0,1482577,34858,2,220,40798,812

    {Colors.YELLOW}parent{Colors.RESET} is the volume element this face belongs to (elementGroup), {Colors.YELLOW}id{Colors.RESET}
    the surface element's own id. Both come straight from the .srf gmshCnvt
    wrote; nodeN count matches the block's declared shape. {Colors.YELLOW}x, y, z{Colors.RESET} are the
    node's {Colors.BOLD}undeformed{Colors.RESET} mesh coordinates -- resolved against the mesh in the
    same pass a nodal othd map already needs it for, so the mesh can still be
    read once and then deleted. Unlike a nodal othd's coordinates, there is no
    per-node displacement to add: oisd is a whole-surface aggregate, so these
    are handy mainly for rendering the surface's shape, e.g. alongside a PLT.
    An element's own row does not repeat them -- join its node ids back to the
    node table above.

    {Colors.YELLOW}# osgId: <n>{Colors.RESET} is predicted the same way {Colors.YELLOW}othId{Colors.RESET} is: declaration order among
    outputSurface blocks, shifted down by one for each earlier block whose
    .srf is missing or empty. An oisd record carries osgId, not a name, and
    nothing else says which block it belongs to.

{Colors.BOLD}PROBE GEOMETRY:{Colors.RESET}

    --probe-type is {Colors.BOLD}declared, never derived{Colors.RESET}, and the map says so. It cannot
    be worked out from the coordinates: a dense square grid snakes into a path
    with perfectly uniform steps, indistinguishable from a curve, and rank alone
    does not separate a ring from a grid. Nor is it in the .def or the .nbc,
    which carry node ids and nothing about shape. Three collinear points are
    either a coarse line or three independent probes, and only you know which.

    It applies to whichever maps the run writes, so use {Colors.YELLOW}--map NAME{Colors.RESET} to
    give different sets different types:

        case out BR0SG0U1P0 --map cyl_nodes --probe-type line
        case out BR0SG0U1P0 --map probe_dat --probe-type point

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}Every nodal block in the case:{Colors.RESET}
    flexflow case out BR0SG0U1P0 --map

  {Colors.BOLD}Just one, by node-set or block name:{Colors.RESET}
    flexflow case out BR0SG0U1P0 --map cyl_nodes
    flexflow case out BR0SG0U1P0 --map riser_probe

  {Colors.BOLD}Every registered case at once:{Colors.RESET}
    flexflow case out * --map
    {Colors.DIM}(or set the context once: use case:*){Colors.RESET}

{Colors.BOLD}NOTES:{Colors.RESET}

  - The coordinates file is read from the .def's nodeCoordinates block, not
    assumed to be <problem>.crd.
  - Blocks with type other than nodal (e.g. type = coordinates) are reported
    and skipped: their records are not indexed by a node file.
  - Every map in a case is built from a single pass over the coordinates file.
  - With the {Colors.YELLOW}*{Colors.RESET} wildcard, cases are read from the .cases registry in the
    current directory. A case with nothing to map is skipped and one that fails
    is reported, and neither ends the batch.

""")
