"""Help messages for run command."""

from src.utils.colors import Colors


def print_run_help():
    """Print run command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Run Command{Colors.RESET}

Submit and manage SLURM jobs for FlexFlow simulations.

{Colors.BOLD}USAGE:{Colors.RESET}
    run <subcommand> [case_directory] [options]

{Colors.BOLD}SUBCOMMANDS:{Colors.RESET}
    {Colors.YELLOW}check{Colors.RESET}    Validate case directory structure
    {Colors.YELLOW}pre{Colors.RESET}      Submit preprocessing job (mesh generation)
    {Colors.YELLOW}main{Colors.RESET}     Submit main simulation job
    {Colors.YELLOW}post{Colors.RESET}     Submit postprocessing job (PLT generation)
    {Colors.YELLOW}sq{Colors.RESET}       Show SLURM job queue status
    {Colors.YELLOW}sb{Colors.RESET}       Submit any SLURM batch script
    {Colors.YELLOW}sc{Colors.RESET}       Cancel a SLURM job by ID or name

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Validate case structure
    run check Case001

    # Submit preprocessing job
    run pre Case001

    # Submit main simulation
    run main Case001

    # Submit main with restart
    run main Case001 --restart 5000

    # Submit postprocessing with cleanup
    run post Case001 --cleanup

    # Check job queue
    run sq

    # Watch job queue
    run sq --watch

    # Show detail for a specific job
    run sq 1258586

    # Submit a script directly
    run sb postFlex.sh

    # Cancel job by ID
    run sc 1258586

    # Cancel all jobs named 'postCase005'
    run sc postCase005

{Colors.BOLD}OPTIONS:{Colors.RESET}
    -h, --help     Show help for specific subcommand
    -v, --verbose  Verbose output

{Colors.BOLD}HELP:{Colors.RESET}
    For help on a specific subcommand:
        run <subcommand> --help

    For example:
        run check --help
        run main --help
        run post --help
""")
