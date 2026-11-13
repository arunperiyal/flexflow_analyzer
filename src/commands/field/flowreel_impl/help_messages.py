"""Help for `field flowreel`."""

from ....utils.colors import Colors


def print_flowreel_help():
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow FlowReel Export{Colors.RESET}

Write the bodies block that FlowReel needs but PLT files cannot carry.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow field flowreel CASE [--output FILE] [--body NAME ...] [--stdout]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--output FILE{Colors.RESET}  Write or update flowreel.yml (default: CASE/flowreel.yml)
    {Colors.YELLOW}--body NAME{Colors.RESET}    Export only these bodies; repeat for more than one
    {Colors.YELLOW}--stdout{Colors.RESET}        Print the bodies block and write nothing
    {Colors.YELLOW}-h, --help{Colors.RESET}     Show this help
""")
