"""
Help messages for case check command
"""

from ....utils.colors import Colors


def print_check_help():
    """Print help message for case check command."""
    print(f"""
{Colors.BOLD}FLEXFLOW CASE CHECK{Colors.RESET}

Inspect OTHD/OISD time step ranges and validate simflow.config consistency.
Pick one subcommand.

{Colors.BOLD}USAGE:{Colors.RESET}
    case check <{Colors.YELLOW}subcommand{Colors.RESET}> [{Colors.YELLOW}case_directory{Colors.RESET}] [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}case_directory{Colors.RESET}    Path to case directory (optional if context is set)

{Colors.BOLD}SUBCOMMANDS:{Colors.RESET}

    {Colors.CYAN}run{Colors.RESET}
        Check .othd and .oisd files in the active run directory
        (resolved from simflow.config 'dir' field).
          • Shows file name, start tsId, end tsId, step count and size
          • Checks restartTsId in simflow.config against first tsId in .othd:
              - FlexFlow resumes from restartTsId+1, so file start is expected to be restartTsId+1
              - If restartTsId+1 matches file start → ✓
              - If mismatch → ✗ (restart config may be wrong)
              - If restartTsId not set but file starts >0 → ⚠

    {Colors.CYAN}archive{Colors.RESET}
        List all archived .othd/.oisd files in othd_files/ and oisd_files/
        with their start tsId, end tsId, step count and size.

    {Colors.CYAN}config{Colors.RESET}
        Validate simflow.config for consistency:
          • 'problem' — checks that matching .geo and .def files exist
          • 'dir'     — checks that the run directory exists
          • 'outFreq' — reports the output frequency
          • 'np'      — reports processor count
          • 'restartTsId' — reports restart step if set

    {Colors.CYAN}plt{Colors.RESET}
        Check PLT files in binary/ and the active run directory:
          • Builds the expected set from outFreq and maxTimeSteps in the .def file
            (e.g. outFreq=50, maxTimeSteps=5000 → expects 50, 100, ..., 5000)
          • {Colors.YELLOW}--freq N{Colors.RESET} checks against N instead. simflow.config records what
            the run was asked to write; after a restart at another frequency,
            or an edit since, that is a different claim from what is on disk --
            and checking the wrong one calls every file that was never meant to
            exist missing. The freq context supplies it: {Colors.DIM}use freq:50{Colors.RESET}
          • {Colors.YELLOW}--t1{Colors.RESET}/{Colors.YELLOW}--t2{Colors.RESET} restrict both the expected and found sets to a
            timestep window (either alone is a one-sided bound); usable via
            context too: {Colors.DIM}use t1:0 t2:1000{Colors.RESET}
          • Reports how many expected files are present / missing
          • Lists each missing tsId explicitly
          • Reports extra files not in the expected set

    {Colors.CYAN}def{Colors.RESET}
        Check that every file referenced via File( "..." ) in the .def file
        exists in the case directory:
          • Lists each referenced file as present (✓) or missing (✗)
          • Reports how many referenced files are present / missing

    {Colors.CYAN}all{Colors.RESET}
        Run every check in order: config, def, run, archive, plt.
        Takes --freq (passed through to the plt check); not --t1/--t2 — use
        the `plt` subcommand directly for a windowed check.

{Colors.BOLD}OPTIONS:{Colors.RESET}
    -v, --verbose     Show detailed output
    -h, --help        Show this help message

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set case context:   use case CS4SG1U1
    Then run:           case check run

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Check run directory OTHD/OISD files
    case check run CS4SG1U1

    # Check all archived files
    case check archive CS4SG1U1

    # Validate simflow.config
    case check config CS4SG1U1

    # Check PLT files against expected set
    case check plt CS4SG1U1
    case check plt CS4SG1U1 --freq 50
    case check plt CS4SG1U1 --t1 0 --t2 1000

    # Check .def File() references exist
    case check def CS4SG1U1

    # Run everything
    case check all CS4SG1U1

    # Using context
    use case CS4SG1U1
    case check run
    case check all

{Colors.BOLD}SEE ALSO:{Colors.RESET}
    case organise  - Archive and clean output files
    case status    - Check data file completeness
    run check      - Validate case directory structure
""")
