"""
Help messages for case organise command
"""

from ....utils.colors import Colors


def print_organise_help():
    """Print help message for organise command."""
    print(f"""
{Colors.BOLD}FLEXFLOW CASE ORGANISE{Colors.RESET}

Organize and clean up case directories. Pick one subcommand.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case organise <{Colors.YELLOW}subcommand{Colors.RESET}> [{Colors.YELLOW}case_directory{Colors.RESET}] [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}case_directory{Colors.RESET}        Path to case directory (optional if context is set)

{Colors.BOLD}SUBCOMMANDS:{Colors.RESET}

    {Colors.CYAN}archive{Colors.RESET}
        Move .othd, .oisd (and .rcv if present) from the run directory
        into othd_files/, oisd_files/, rcv_files/. With --t1/--t2, only
        files whose timestep range overlaps that window are moved.
        Uses numbered suffixes to avoid overwriting existing files.
        No confirmation required — safe archive operation.

        {Colors.CYAN}--clean{Colors.RESET}
            After archiving, deduplicate and clean redundant OTHD/OISD
            files in othd_files/ and oisd_files/:
              • Removes duplicate files (same time step range)
              • Removes subset files (covered by larger files)
              • Keeps files with overlapping ranges
              • Renames remaining files sequentially by time step
              • Always analyzes the complete archived set — --t1/--t2 do
                NOT scope --clean; excluding a file could hide the very
                superset that makes another file redundant, and silently
                leave it uncleaned

    {Colors.CYAN}output{Colors.RESET}
        Remove intermediate .out/.rst files from the run directory:
          • Keeps files at multiples of freq * keep_every
          • Uses outFreq from simflow.config or auto-detects

        {Colors.CYAN}--keep-every N{Colors.RESET}
            Keep every Nth output (default: 10, means freq*10)

    {Colors.CYAN}plt{Colors.RESET}
        Pass at least one of --delete-ascii / --delete-binary.

        {Colors.CYAN}--delete-ascii{Colors.RESET}
            Delete PLT files from the run directory where binary/ has a
            corresponding file (exact filename match) with a newer mtime:
              • Safe: only deletes if the binary copy is confirmed newer
              • Skips files with no binary copy (prints with —)
              • Skips files where the binary copy is same age or older (prints with ⚠)
              • Shows a per-file table before asking confirmation

        {Colors.CYAN}--delete-binary{Colors.RESET}
            Delete PLT files from binary/ within --t1/--t2.
              • Unconditional — no check against the run directory
              • Omitting both --t1 and --t2 deletes every PLT file in binary/
              • Can leave no surviving copy of that timestep's PLT data

{Colors.BOLD}TARGETING BY TIMESTEP:{Colors.RESET}
    --t1 STEP                 Only target timesteps >= STEP
    --t2 STEP                 Only target timesteps <= STEP
    (either alone is a one-sided bound; both together is an inclusive range)
    Available on the archive move step, output and plt.
    NOT applied to archive --clean, which always dedupes everything.

{Colors.BOLD}OTHER OPTIONS:{Colors.RESET}
    --dry-run                 Show what would be deleted without deleting anything
    --log                     Create log file of all deletions
    --no-confirm              Skip confirmation prompts
    -v, --verbose             Show detailed information
    -h, --help                Show this help message
    --examples                Show usage examples

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set case context:     use case CS4SG1U1
    Then run:             case organise archive

    Set timestep context: use t1:0 t2:1000
    Then run:              case organise output

{Colors.BOLD}SAFETY:{Colors.RESET}
    • archive (without --clean) does not delete anything; it only moves files
    • archive --clean, output and plt show a summary and ask for confirmation
    • --delete-binary is unconditional: it does not check the run dir first
    • A t1/t2 context left over from something else never silently narrows
      archive --clean — it always cleans the complete archived set
    • Use --no-confirm to skip confirmation
    • Fails if any OTHD/OISD file cannot be read (prevents data loss)

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Archive run output (move .othd/.oisd/.rcv to archive dirs)
    flexflow case organise archive CS4SG1U1

    # Archive, then deduplicate/clean OTHD and OISD files
    flexflow case organise archive CS4SG1U1 --clean

    # Remove intermediate output files
    flexflow case organise output CS4SG1U1

    # Delete PLT files from run dir where binary/ has a newer copy
    flexflow case organise plt CS4SG1U1 --delete-ascii

    # Delete PLT files from binary/ for a timestep range
    flexflow case organise plt CS4SG1U1 --delete-binary --t1 0 --t2 1000

    # Only target a timestep range
    flexflow case organise output CS4SG1U1 --t1 0 --t2 1000

    # Use context
    use case CS4SG1U1
    case organise archive

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
    flexflow case organise archive CS4SG1U1

    # Files are numbered automatically:
    #   riser.othd  → othd_files/riser1.othd
    #   riser.oisd  → oisd_files/riser1.oisd
    #   riser.rcv   → rcv_files/riser1.rcv (if present)

    # Only archive files whose timestep range overlaps [0, 1000]
    flexflow case organise archive CS4SG1U1 --t1 0 --t2 1000

{Colors.BOLD}Deduplicating OTHD/OISD Files:{Colors.RESET}

    # Archive, then remove duplicate/subset OTHD and OISD files
    # --clean always inspects the full archived set, even with a t1/t2
    # context left over from something else
    flexflow case organise archive CS4SG1U1 --clean

    # Skip confirmation
    flexflow case organise archive CS4SG1U1 --clean --no-confirm

{Colors.BOLD}Cleaning Output Directory:{Colors.RESET}

    # Remove intermediate .out/.rst files (keeps every freq*10)
    flexflow case organise output CS4SG1U1

    # Custom retention interval (keep every freq*5)
    flexflow case organise output CS4SG1U1 --keep-every 5

    # Only clean up to timestep 5000
    flexflow case organise output CS4SG1U1 --t2 5000

    # Create log file of deletions
    flexflow case organise output CS4SG1U1 --log

{Colors.BOLD}Cleaning PLT Files:{Colors.RESET}

    # Delete run-dir PLT files that have a newer copy in binary/
    flexflow case organise plt CS4SG1U1 --delete-ascii

    # Only within a timestep window
    flexflow case organise plt CS4SG1U1 --delete-ascii --t1 1000 --t2 2000

    # Unconditionally delete PLT files from binary/ for a timestep window
    flexflow case organise plt CS4SG1U1 --delete-binary --t1 1000 --t2 2000

    # Both directions in one call
    flexflow case organise plt CS4SG1U1 --delete-ascii --delete-binary --t1 1000 --t2 2000

{Colors.BOLD}Using Context:{Colors.RESET}

    # Set case context
    use case CS4SG1U1

    # Run operations
    case organise archive
    case organise archive --clean
    case organise output

    # Set a timestep window and reuse it across subcommands
    use t1:0 t2:1000
    case organise output
    case organise plt --delete-ascii

{Colors.BOLD}What archive --clean Does:{Colors.RESET}

    Before:
    • riser1.othd [0-1000]    → Keep (unique range)
    • riser2.othd [0-1000]    → Delete (duplicate)
    • riser3.othd [0-500]     → Delete (subset of riser1)
    • riser4.othd [1000-2000] → Keep (unique range)
    • riser5.othd [500-1500]  → Keep (partial overlap, kept)

    After cleanup, files are renamed sequentially:
    riser1.othd [0-1000], riser2.othd [1000-2000], riser3.othd [500-1500]

{Colors.BOLD}What output Does (freq=50, keep_every=10):{Colors.RESET}

    • riser.50_1.out       → Delete (not multiple of 500)
    • riser.100_1.out      → Delete
    • riser.500_1.out      → Keep  (500 % 500 == 0)
    • riser.1000_1.out     → Keep  (1000 % 500 == 0)

{Colors.BOLD}What plt --delete-ascii Does:{Colors.RESET}

    • riser.500.plt (run dir)    → Delete (binary/riser.500.plt exists and is newer)

{Colors.BOLD}What plt --delete-binary Does (--t1 1000 --t2 2000):{Colors.RESET}

    • binary/riser.1500.plt      → Delete (in range, regardless of run dir)
    • binary/riser.3000.plt      → Keep   (outside range)

{Colors.BOLD}Notes:{Colors.RESET}
    • archive (without --clean) runs immediately, no confirmation needed
    • archive --clean, output and plt ask for confirmation unless --no-confirm
    • --delete-ascii never touches binary/; --delete-binary never touches the run dir
    • --delete-binary with no --t1/--t2 deletes every PLT file in binary/
""")
