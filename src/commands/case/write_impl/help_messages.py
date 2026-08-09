"""Help messages for case write command."""

from ....utils.colors import Colors


def print_write_help():
    """Print case write command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Case Write Command{Colors.RESET}

Build small derived files from a case's own inputs.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case write <case_dir> --othd-map [NAME]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--othd-map [NAME]{Colors.RESET}  Write a node map for every nodal outputTimeHistory
                       block in the .def. Give NAME to do just one, matched
                       against the block name or the node-set name.
    {Colors.YELLOW}--verbose, -v{Colors.RESET}      Show which files were read
    {Colors.YELLOW}--help, -h{Colors.RESET}         Show this help message

{Colors.BOLD}WHY:{Colors.RESET}

    A nodal outputTimeHistory writes its records {Colors.BOLD}positionally{Colors.RESET}: row k of
    every aleDisp block is the k-th node of the node file the block was given.
    The othd carries no node id and no coordinate, so reading one back needs
    both the node file and the mesh coordinates -- and the coordinates file is
    usually the largest input in the case (137 MB for a 1.8M-node riser) even
    when the output covers a few dozen nodes.

    This writes those nodes out once, so the coordinates file can be deleted
    and the othd stays readable.

{Colors.BOLD}OUTPUT:{Colors.RESET}

    One {Colors.YELLOW}othd.<set>.map{Colors.RESET} per nodal block, in the case directory:

        row,node,x,y,z
        0,2,-2.1648901405887341e-17,3.5355339059327368e-01,-3.5355339059327379e-01

    {Colors.YELLOW}row{Colors.RESET}      index of the record within each aleDisp block of the othd
    {Colors.YELLOW}node{Colors.RESET}     mesh node id
    {Colors.YELLOW}x, y, z{Colors.RESET}  {Colors.BOLD}undeformed{Colors.RESET} coordinates -- add the othd displacement
             to get where the node moved to

    Rows keep the node file's order, because that order is what indexes the
    othd. They are not sorted by node id.

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}Every nodal block in the case:{Colors.RESET}
    flexflow case write BR0SG0U1P0 --othd-map

  {Colors.BOLD}Just one, by node-set or block name:{Colors.RESET}
    flexflow case write BR0SG0U1P0 --othd-map cyl_nodes
    flexflow case write BR0SG0U1P0 --othd-map riser_probe

{Colors.BOLD}NOTES:{Colors.RESET}

  - The coordinates file is read from the .def's nodeCoordinates block, not
    assumed to be <problem>.crd.
  - Blocks with type other than nodal (e.g. type = coordinates) are reported
    and skipped: their records are not indexed by a node file.
  - Every map in a case is built from a single pass over the coordinates file.

""")
