"""Help messages for statistics command."""

from module.utils.colors import Colors

def print_statistics_help():
    """Print statistics command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Statistics Command{Colors.RESET}

Display statistical information about displacement and force data.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow statistics {Colors.YELLOW}<case_directory>{Colors.RESET} [options]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--node <node_id>{Colors.RESET}       Show statistics for a specific node (default: all nodes)
    {Colors.YELLOW}--verbose, -v{Colors.RESET}          Show detailed information
    {Colors.YELLOW}--examples{Colors.RESET}             Show usage examples
    {Colors.YELLOW}--help, -h{Colors.RESET}             Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    The statistics command provides comprehensive statistical analysis of simulation data:
    
    For displacement data (OTHD):
    - Mean, standard deviation, min, max, and range for dx, dy, dz components
    - Magnitude statistics
    
    For force/traction data (OISD):
    - Mean, standard deviation, min, max, and range for tx, ty, tz components
    - Moment statistics (mx, my, mz)
    - Average pressure statistics
    
    When --node is specified, statistics are calculated only for that node.
    Otherwise, statistics are computed across all nodes and timesteps.
""")


def print_statistics_examples():
    """Print statistics command examples."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}Statistics Command Examples{Colors.RESET}

{Colors.BOLD}Show statistics for all nodes:{Colors.RESET}
    flexflow statistics CS4SG1U1

{Colors.BOLD}Show statistics for a specific node:{Colors.RESET}
    flexflow statistics CS4SG1U1 --node 0
    flexflow statistics CS4SG1U1 --node 10

{Colors.BOLD}Show statistics with verbose output:{Colors.RESET}
    flexflow statistics CS4SG1U1 --node 0 --verbose
""")
