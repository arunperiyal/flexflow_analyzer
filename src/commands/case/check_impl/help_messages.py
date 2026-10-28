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

    {Colors.CYAN}history{Colors.RESET}
        List every .othd/.oisd history file in othd_files/ and oisd_files/
        with its start tsId, end tsId, step count and size, in one table per
        group: archive/, cleaned/, the compiled file (and any parts still in
        the old flat layout).
          {Colors.YELLOW}--archive{Colors.RESET}   only archive/
          {Colors.YELLOW}--cleaned{Colors.RESET}   only cleaned/
          {Colors.YELLOW}--compiled{Colors.RESET}  only the compiled file
        The flags combine; with none, every group is shown.

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
          • A table of binary/ and the run directory: files, steps, size
          • A step counts as present in either place; up to the last step
            found, the ones with no file are {Colors.RED}missing{Colors.RESET} and 0-byte ones
            {Colors.YELLOW}empty{Colors.RESET}, shown as runs: {Colors.DIM}300 · 650–750 (3) · 1200{Colors.RESET}
          • Steps after the last one found are {Colors.DIM}not yet{Colors.RESET} written (the run
            stopped or is still going), apart from the gaps
          • Also lists extra files (off the freq grid) and steps in both places
          • After a restart (restartFlag, restartTsId R), flags as {Colors.RED}stale{Colors.RESET} each
            PLT past R older than the resumed run's .out/.rst for that step or
            an earlier one: it was made from the earlier run's output, which the
            restart computed again, so it does not join up with the frames around
            it. Steps before the first .out/.rst left past R cannot be dated.

    {Colors.CYAN}def{Colors.RESET}
        Check that every file referenced via File( "..." ) in the .def file
        exists in the case directory:
          • Lists each referenced file as present (✓) or missing (✗)
          • Reports how many referenced files are present / missing

    {Colors.CYAN}out{Colors.RESET}
        List timesteps for which .out and .rst files are present in the
        active run directory (resolved from simflow.config 'dir' field):
          • Shows a table of tsId → .out present / .rst present
          • {Colors.YELLOW}--t1{Colors.RESET}/{Colors.YELLOW}--t2{Colors.RESET} restrict the listing to a timestep window (either
            alone is a one-sided bound); usable via context too:
            {Colors.DIM}use t1:0 t2:1000{Colors.RESET}
          • {Colors.YELLOW}--freq N{Colors.RESET} expects a step every N timesteps (N, 2N, ... up to --t2
            or the last step found) and lists each one with neither file
            as missing

    {Colors.CYAN}data{Colors.RESET}
        The completeness of the case's data files (was `case status`).

    {Colors.CYAN}all{Colors.RESET}
        Run every check in order: config, def, run, history, plt, out.
        Takes --freq (passed through to the plt check); not --t1/--t2 — use
        the `plt`/`out` subcommands directly for a windowed check.

{Colors.BOLD}OPTIONS:{Colors.RESET}
    -v, --verbose     Show detailed output
    -h, --help        Show this help message

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set case context:   use case CS4SG1U1
    Then run:           case check run

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Check run directory OTHD/OISD files
    case check run CS4SG1U1

    # Show the OTHD/OISD history files, one table per group
    case check history CS4SG1U1

    # Only cleaned/ and the compiled file
    case check history CS4SG1U1 --cleaned --compiled

    # Validate simflow.config
    case check config CS4SG1U1

    # Check PLT files against expected set
    case check plt CS4SG1U1
    case check plt CS4SG1U1 --freq 50
    case check plt CS4SG1U1 --t1 0 --t2 1000

    # Check .def File() references exist
    case check def CS4SG1U1

    # List timesteps with .out/.rst files in the run directory
    case check out CS4SG1U1
    case check out CS4SG1U1 --t1 0 --t2 1000
    case check out CS4SG1U1 --freq 1000          # flag missing restart steps

    # Data file completeness (was `case status`)
    case check data CS4SG1U1

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
