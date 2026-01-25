"""Help messages for info command."""

from src.utils.colors import Colors

def print_info_help():
    """Print info command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Case Show Command{Colors.RESET}

Display information about a FlexFlow case directory.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case show {Colors.YELLOW}<case_directory>{Colors.RESET} [options]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--verbose, -v{Colors.RESET}          Show detailed information
    {Colors.YELLOW}--examples{Colors.RESET}             Show usage examples
    {Colors.YELLOW}--help, -h{Colors.RESET}             Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    The info command displays:
    - Problem name from simflow.config
    - Time increment from .def file
    - Available data files (OTHD, OISD)
    - Number of time steps
    - Time range
""")


def print_info_examples():
    """Print info command examples."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}Info Command Examples{Colors.RESET}

{Colors.BOLD}Basic Usage:{Colors.RESET}
    flexflow case show CS4SG1U1
    flexflow case show CS4SG1U1 --verbose
""")
