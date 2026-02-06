"""Help messages for info command."""

from src.utils.colors import Colors

def print_info_help():
    """Print info command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Case Show Command{Colors.RESET}

Display information about a FlexFlow case directory.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case show [{Colors.YELLOW}case_directory{Colors.RESET}] [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}case_directory{Colors.RESET}        Path to case directory (optional if context is set)

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}-v, --verbose{Colors.RESET}          Show detailed information
    {Colors.YELLOW}--examples{Colors.RESET}             Show usage examples
    {Colors.YELLOW}-h, --help{Colors.RESET}             Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Displays comprehensive case information:
    - Case directory and problem name
    - Time increment from .def file
    - Available data files (OTHD, OISD)
    - Number of nodes and timesteps
    - Time range of simulation data

    If a case context is set with 'use case <path>', the case_directory
    argument can be omitted and the current case will be used.

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set case context:     use case CS4SG1U1
    Then run:             case show
""")


def print_info_examples():
    """Print info command examples."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}Case Show Command Examples{Colors.RESET}

{Colors.BOLD}Basic Usage:{Colors.RESET}
    # Show case information
    flexflow case show CS4SG1U1

    # Show with verbose output
    flexflow case show CS4SG1U1 --verbose

    # Show relative path case
    flexflow case show ./cases/CS4SG1U1

    # Show absolute path case
    flexflow case show /full/path/to/CS4SG1U1

{Colors.BOLD}Using Context:{Colors.RESET}
    # Set case context
    flexflow use case CS4SG1U1

    # Show current case (no argument needed)
    flexflow case show

    # Verbose with context
    flexflow case show --verbose

{Colors.BOLD}Workflow Example:{Colors.RESET}
    # Navigate and analyze
    cd ~/simulations
    find CS4*
    use case CS4SG1U1
    case show
    data show --node 24
    plot --node 10
""")
