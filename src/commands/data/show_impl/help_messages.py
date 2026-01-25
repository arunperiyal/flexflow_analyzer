"""Help messages for preview command."""

from src.utils.colors import Colors

def print_preview_help():
    """Print preview command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Data Show Command{Colors.RESET}

Preview displacement data from OTHD files in tabular format.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow data show {Colors.YELLOW}<case_directory>{Colors.RESET} [options]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--node <node_id>{Colors.RESET}       Node ID to preview (default: 0)
    {Colors.YELLOW}--start-time <time>{Colors.RESET}    Start time for preview
    {Colors.YELLOW}--end-time <time>{Colors.RESET}      End time for preview
    {Colors.YELLOW}--verbose, -v{Colors.RESET}          Show detailed information
    {Colors.YELLOW}--examples{Colors.RESET}             Show usage examples
    {Colors.YELLOW}--help, -h{Colors.RESET}             Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    The preview command displays displacement data in a tabular format.
    
    Default behavior (no flags):
    - Shows first 10 timesteps
    - Displays data for node 0
    
    With time flags:
    - Filters data to specified time range
    - Shows all timesteps within the range
    
    With node flag:
    - Displays data for the specified node
    
    The table includes:
    - Step number
    - Time value
    - Displacement components (dx, dy, dz)
    - Displacement magnitude
""")


def print_preview_examples():
    """Print preview command examples."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}Preview Command Examples{Colors.RESET}

{Colors.BOLD}Preview first 10 timesteps for node 0 (default):{Colors.RESET}
    flexflow data show CS4SG1U1

{Colors.BOLD}Preview specific node:{Colors.RESET}
    flexflow data show CS4SG1U1 --node 24
    flexflow data show CS4SG1U1 --node 10

{Colors.BOLD}Preview specific time range:{Colors.RESET}
    flexflow data show CS4SG1U1 --start-time 50.0 --end-time 100.0
    flexflow data show CS4SG1U1 --node 24 --start-time 100.0 --end-time 150.0

{Colors.BOLD}Preview with verbose output:{Colors.RESET}
    flexflow data show CS4SG1U1 --node 10 --verbose
""")
