"""
Help messages for case organise command
"""

from ....utils.colors import Colors


def print_organise_help():
    """Print help message for organise command."""
    print(f"""
{Colors.BOLD}FLEXFLOW CASE ORGANISE{Colors.RESET}

Organize and clean up case directories. Must specify at least one action flag.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case organise [{Colors.YELLOW}case_directory{Colors.RESET}] --<flag> [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}case_directory{Colors.RESET}        Path to case directory (optional if context is set)

{Colors.BOLD}ACTION FLAGS:{Colors.RESET}

    {Colors.CYAN}--archive{Colors.RESET}
        Move .othd, .oisd (and .rcv if present) from the run directory
        into othd_files/, oisd_files/, rcv_files/.
        Uses numbered suffixes to avoid overwriting existing files.
        No confirmation required — safe archive operation.

    {Colors.CYAN}--organise{Colors.RESET}
        Deduplicate and clean redundant OTHD/OISD files in othd_files/
        and oisd_files/:
          • Removes duplicate files (same time step range)
          • Removes subset files (covered by larger files)
          • Keeps files with overlapping ranges
          • Renames remaining files sequentially by time step

    {Colors.CYAN}--clean-output{Colors.RESET}
        Remove intermediate .out/.rst/.plt files from the run directory:
          • Keeps .out/.rst files at multiples of freq * keep_every
          • Deletes ASCII .plt files if binary version exists in binary/
          • Uses outFreq from simflow.config or auto-detects

{Colors.BOLD}OPTIONS:{Colors.RESET}
    --keep-every N            Keep every Nth output (default: 10, means freq*10)
    --log                     Create log file of all deletions
    --no-confirm              Skip confirmation prompts
    -v, --verbose             Show detailed information
    -h, --help                Show this help message
    --examples                Show usage examples

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set case context:     use case CS4SG1U1
    Then run:             case organise --archive

{Colors.BOLD}SAFETY:{Colors.RESET}
    • --archive does not delete anything; it only moves files
    • --organise and --clean-output show summary and ask for confirmation
    • Use --no-confirm to skip confirmation
    • Fails if any OTHD/OISD file cannot be read (prevents data loss)

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Archive run output (move .othd/.oisd/.rcv to archive dirs)
    flexflow case organise CS4SG1U1 --archive

    # Deduplicate/clean OTHD and OISD files
    flexflow case organise CS4SG1U1 --organise

    # Remove intermediate output files
    flexflow case organise CS4SG1U1 --clean-output

    # Full workflow: archive first, then organise, then clean output
    flexflow case organise CS4SG1U1 --archive --organise --clean-output

    # Use context
    use case CS4SG1U1
    case organise --archive

{Colors.BOLD}SEE ALSO:{Colors.RESET}
    case show    - Display case information
    case status  - Check data file completeness
""")


def print_organise_examples():
    """Print examples for organise command."""
    print(f"""
{Colors.BOLD}CASE ORGANISE - EXAMPLES{Colors.RESET}

{Colors.BOLD}Archiving Run Output:{Colors.RESET}

    # Move .othd/.oisd/.rcv from run dir to archive directories
    flexflow case organise CS4SG1U1 --archive

    # Files are numbered automatically:
    #   riser.othd  → othd_files/riser1.othd
    #   riser.oisd  → oisd_files/riser1.oisd
    #   riser.rcv   → rcv_files/riser1.rcv (if present)

{Colors.BOLD}Deduplicating OTHD/OISD Files:{Colors.RESET}

    # Remove duplicate/subset OTHD and OISD files
    flexflow case organise CS4SG1U1 --organise

    # Skip confirmation
    flexflow case organise CS4SG1U1 --organise --no-confirm

{Colors.BOLD}Cleaning Output Directory:{Colors.RESET}

    # Remove intermediate .out/.rst/.plt files (keeps every freq*10)
    flexflow case organise CS4SG1U1 --clean-output

    # Custom retention interval (keep every freq*5)
    flexflow case organise CS4SG1U1 --clean-output --keep-every 5

    # Create log file of deletions
    flexflow case organise CS4SG1U1 --clean-output --log

{Colors.BOLD}Combined Operations:{Colors.RESET}

    # Run all three in sequence
    flexflow case organise CS4SG1U1 --archive --organise --clean-output

    # Archive and organise only
    flexflow case organise CS4SG1U1 --archive --organise

{Colors.BOLD}Using Context:{Colors.RESET}

    # Set case context
    use case CS4SG1U1

    # Run operations
    case organise --archive
    case organise --organise
    case organise --clean-output

{Colors.BOLD}What --organise Does:{Colors.RESET}

    Before:
    • riser1.othd [0-1000]    → Keep (unique range)
    • riser2.othd [0-1000]    → Delete (duplicate)
    • riser3.othd [0-500]     → Delete (subset of riser1)
    • riser4.othd [1000-2000] → Keep (unique range)
    • riser5.othd [500-1500]  → Keep (partial overlap, kept)

    After cleanup, files are renamed sequentially:
    riser1.othd [0-1000], riser2.othd [1000-2000], riser3.othd [500-1500]

{Colors.BOLD}What --clean-output Does (freq=50, keep_every=10):{Colors.RESET}

    • riser.50_1.out       → Delete (not multiple of 500)
    • riser.100_1.out      → Delete
    • riser.500_1.out      → Keep  (500 % 500 == 0)
    • riser.1000_1.out     → Keep  (1000 % 500 == 0)
    • riser.500.plt        → Delete (binary/riser.500.plt exists)

{Colors.BOLD}Notes:{Colors.RESET}
    • --archive runs immediately, no confirmation needed
    • --organise and --clean-output ask for confirmation unless --no-confirm
    • Binary PLT files in binary/ are never deleted
""")
