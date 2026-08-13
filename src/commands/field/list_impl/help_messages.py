"""Help text for `field list`."""

from ....utils.colors import Colors


def print_list_help():
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Field List Command{Colors.RESET}

Print the names you have to know before you can use them. Neither of these is
discoverable from your data: a colormap lives in matplotlib, and a derived
variable lives in FlexFlow.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow field list <what>

{Colors.BOLD}WHAT:{Colors.RESET}
    {Colors.YELLOW}--color{Colors.RESET}          Colormaps for {Colors.YELLOW}color.preset{Colors.RESET}, grouped by the kind of
                     field they suit, plus the ParaView preset names that are
                     accepted and translated. {Colors.YELLOW}-v{Colors.RESET} also lists every
                     colormap installed.
    {Colors.YELLOW}--variables{Colors.RESET}      Variables FlexFlow can compute when the solver did
                     not write them (lambda2), and what each needs.

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--verbose, -v{Colors.RESET}    More detail where there is more to show
    {Colors.YELLOW}--help, -h{Colors.RESET}       Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    flexflow field list --color
    flexflow field list --color -v
    flexflow field list --variables

{Colors.BOLD}NOTES:{Colors.RESET}
    {Colors.DIM}- For what a specific case holds -- its zones and the variables already
      in its PLT -- use `field info <case> --zones --variables`. This command
      lists what is available in general, not what is in your file.{Colors.RESET}
""")
