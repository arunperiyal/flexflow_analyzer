"""Help messages for case write command."""

from ....utils.colors import Colors


def print_write_help():
    """Print case write command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Case Write Command{Colors.RESET}

Build small derived files from a case's own inputs.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case write <case_dir> --othd-map [NAME]
    flexflow case write * --othd-map            {Colors.DIM}# every case in .cases{Colors.RESET}

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--othd-map [NAME]{Colors.RESET}  Write a map for every outputTimeHistory block in the
                       .def that names a file its records are indexed by.
                       Give NAME to do just one, matched against the block
                       name or the node/point-set name.
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

    One {Colors.YELLOW}othd.<set>.map{Colors.RESET} per mappable block, in the case directory. What a
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

    Rows keep the source file's order, because that order is what indexes the
    othd. They are not sorted.

    A block whose type names no file to index its records by is reported and
    skipped -- there is nothing to map it against.

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}Every nodal block in the case:{Colors.RESET}
    flexflow case write BR0SG0U1P0 --othd-map

  {Colors.BOLD}Just one, by node-set or block name:{Colors.RESET}
    flexflow case write BR0SG0U1P0 --othd-map cyl_nodes
    flexflow case write BR0SG0U1P0 --othd-map riser_probe

  {Colors.BOLD}Every registered case at once:{Colors.RESET}
    flexflow case write * --othd-map
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
