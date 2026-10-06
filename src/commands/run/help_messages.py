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
    {Colors.YELLOW}check{Colors.RESET}    Validate case directory and check SLURM job status
    {Colors.YELLOW}pre{Colors.RESET}      Submit preprocessing job (mesh generation)
    {Colors.YELLOW}main{Colors.RESET}     Submit main simulation job
    {Colors.YELLOW}post{Colors.RESET}     Submit postprocessing job (PLT generation)
    {Colors.YELLOW}sq{Colors.RESET}       Show SLURM job queue status
    {Colors.YELLOW}sb{Colors.RESET}       Submit any SLURM batch script
    {Colors.YELLOW}sc{Colors.RESET}       Cancel a SLURM job by ID or name

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Validate case structure and check SLURM status
    run check Case001

    # Verbose check with error details
    run check Case001 --verbose

    # Show SBATCH headers of the job scripts
    run check headers Case001

    # Count mesh elements and check for triangles
    run check mesh Case001

    # Submit preprocessing job
    run pre Case001

    # Submit main simulation
    run main Case001

    # Submit main with restart
    run main restart 5000 Case001

    # Submit main fresh, ignoring restart settings
    run main reset Case001

    # Submit postprocessing with cleanup
    run post full Case001 --cleanup

    # Convert existing .plt files to binary only
    run post convert Case001

    # Check job queue
    run sq

    # Watch job queue
    run sq watch

    # Find jobs for one case
    run sq find CS4SG3U3P0

    # Sort queue by a column
    run sq --sort submitted

    # Show detail for a specific job
    run sq 1258586

    # Show job stdout tail
    run sq 1258586 --out -n 50

    # Submit a script directly
    run sb postFlex.sh

    # Cancel job by ID
    run sc 1258586

    # Cancel all jobs named 'postCase005'
    run sc postCase005

{Colors.BOLD}OPTIONS:{Colors.RESET}
    -h, --help     Show help for specific subcommand
    -v, --verbose  Verbose output (shows more error details in check)

{Colors.BOLD}HELP:{Colors.RESET}
    For help on a specific subcommand:
        run <subcommand> --help

    For example:
        run check --help
        run main --help
        run post --help
""")
