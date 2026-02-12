"""
Help messages for case check command
"""

from ....utils.colors import Colors


def print_check_help():
    """Print help message for case check command."""
    print(f"""
{Colors.BOLD}FLEXFLOW CASE CHECK{Colors.RESET}

Inspect OTHD/OISD time step ranges and validate simflow.config consistency.
Must specify at least one action flag.

{Colors.BOLD}USAGE:{Colors.RESET}
    case check [{Colors.YELLOW}case_directory{Colors.RESET}] --<flag> [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}case_directory{Colors.RESET}    Path to case directory (optional if context is set)

{Colors.BOLD}ACTION FLAGS:{Colors.RESET}

    {Colors.CYAN}--run{Colors.RESET}
        Check .othd and .oisd files in the active run directory
        (resolved from simflow.config 'dir' field).
          • Shows file name, start tsId, end tsId, step count and size
          • Checks restartTsId in simflow.config against first tsId in .othd:
              - If restartTsId is set and matches → ✓
              - If mismatch → ✗ (restart config may be wrong)
              - If restartTsId not set but file starts >0 → ⚠

    {Colors.CYAN}--archive{Colors.RESET}
        List all archived .othd/.oisd files in othd_files/ and oisd_files/
        with their start tsId, end tsId, step count and size.

    {Colors.CYAN}--config{Colors.RESET}
        Validate simflow.config for consistency:
          • 'problem' — checks that matching .geo and .def files exist
          • 'dir'     — checks that the run directory exists
          • 'outFreq' — reports the output frequency
          • 'np'      — reports processor count
          • 'restartTsId' — reports restart step if set

    {Colors.CYAN}--all{Colors.RESET}
        Run all three checks in order: --config, --run, --archive.

{Colors.BOLD}OPTIONS:{Colors.RESET}
    -v, --verbose     Show detailed output
    -h, --help        Show this help message

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set case context:   use case CS4SG1U1
    Then run:           case check --run

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Check run directory OTHD/OISD files
    case check CS4SG1U1 --run

    # Check all archived files
    case check CS4SG1U1 --archive

    # Validate simflow.config
    case check CS4SG1U1 --config

    # Run everything
    case check CS4SG1U1 --all

    # Using context
    use case CS4SG1U1
    case check --run
    case check --all

{Colors.BOLD}SEE ALSO:{Colors.RESET}
    case organise  - Archive and deduplicate output files
    case status    - Check data file completeness
    run check      - Validate case directory structure
""")
