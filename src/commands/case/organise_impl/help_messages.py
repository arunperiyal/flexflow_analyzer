"""
Help messages for case organise command
"""

from ....utils.colors import Colors


def print_organise_help():
    """Print help message for organise command."""
    print(f"""
{Colors.BOLD}FLEXFLOW CASE ORGANISE{Colors.RESET}

Organize and clean up case directories by removing redundant files.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case organise [{Colors.YELLOW}case_directory{Colors.RESET}] [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}case_directory{Colors.RESET}        Path to case directory (optional if context is set)

{Colors.BOLD}WHAT IT DOES:{Colors.RESET}

    1. {Colors.BOLD}OTHD/OISD Cleanup:{Colors.RESET}
       • Removes duplicate files (same time step range)
       • Removes subset files (covered by larger files)
       • Keeps files with overlapping ranges
       • Automatically renames remaining files in order

    2. {Colors.BOLD}Output Directory Cleanup:{Colors.RESET}
       • Removes .out/.rst files at intermediate steps
       • Keeps files at multiples of freq*10 (e.g., 500, 1000, 1500...)
       • Uses outFreq from simflow.config or auto-detects

{Colors.BOLD}OPTIONS:{Colors.RESET}
    --dry-run                 Preview changes without deleting
    --freq N                  Override outFreq from simflow.config
    --keep-every N            Keep every Nth output (default: 10)
    --clean-othd              Clean OTHD files only
    --clean-oisd              Clean OISD files only
    --clean-output            Clean output directory only
    --log                     Create log file of all deletions
    --no-confirm              Skip confirmation prompts
    -v, --verbose             Show detailed information
    -h, --help                Show this help message
    --examples                Show usage examples

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set case context:     use case CS4SG1U1
    Then run:             case organise

{Colors.BOLD}SAFETY:{Colors.RESET}
    • Shows summary before deletion
    • Asks for confirmation (unless --no-confirm)
    • Use --dry-run to preview changes safely
    • Fails if any file cannot be read (prevents data loss)

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Preview what would be cleaned
    flexflow case organise CS4SG1U1 --dry-run

    # Clean everything with confirmation
    flexflow case organise CS4SG1U1

    # Clean OTHD files only
    flexflow case organise CS4SG1U1 --clean-othd

    # Override frequency and create log
    flexflow case organise CS4SG1U1 --freq 50 --log

    # Use context
    flexflow use case CS4SG1U1
    flexflow case organise

{Colors.BOLD}SEE ALSO:{Colors.RESET}
    case show    - Display case information
    case run     - Submit simulation jobs
""")


def print_organise_examples():
    """Print examples for organise command."""
    print(f"""
{Colors.BOLD}CASE ORGANISE - EXAMPLES{Colors.RESET}

{Colors.BOLD}Basic Usage:{Colors.RESET}

    # Preview changes (safe, no deletion)
    flexflow case organise CS4SG1U1 --dry-run

    # Organize with confirmation
    flexflow case organise CS4SG1U1

    # Organize without confirmation
    flexflow case organise CS4SG1U1 --no-confirm

{Colors.BOLD}Selective Cleaning:{Colors.RESET}

    # Clean only OTHD files
    flexflow case organise CS4SG1U1 --clean-othd

    # Clean only OISD files
    flexflow case organise CS4SG1U1 --clean-oisd

    # Clean only output directory
    flexflow case organise CS4SG1U1 --clean-output

{Colors.BOLD}Frequency Control:{Colors.RESET}

    # Override frequency from simflow.config
    flexflow case organise CS4SG1U1 --freq 50

    # Keep every 10th output (freq * 10)
    flexflow case organise CS4SG1U1 --keep-every 10

    # Keep every 5th output (freq * 5)
    flexflow case organise CS4SG1U1 --keep-every 5

{Colors.BOLD}Logging and Verbosity:{Colors.RESET}

    # Create log file of all deletions
    flexflow case organise CS4SG1U1 --log

    # Show detailed information
    flexflow case organise CS4SG1U1 --verbose

    # Combine options
    flexflow case organise CS4SG1U1 --log --verbose --dry-run

{Colors.BOLD}Using Context:{Colors.RESET}

    # Set case context
    flexflow use case CS4SG1U1

    # Organize current case
    flexflow case organise

    # Preview current case
    flexflow case organise --dry-run

{Colors.BOLD}Common Workflows:{Colors.RESET}

    1. Check before cleaning:
       flexflow case organise CS4SG1U1 --dry-run
       flexflow case organise CS4SG1U1

    2. Clean with logging:
       flexflow case organise CS4SG1U1 --log --verbose

    3. Clean specific parts:
       flexflow case organise CS4SG1U1 --clean-othd --dry-run
       flexflow case organise CS4SG1U1 --clean-othd

{Colors.BOLD}What Gets Cleaned:{Colors.RESET}

    OTHD/OISD Files:
    • riser1.othd [0-1000]    → Keep (unique range)
    • riser2.othd [0-1000]    → Delete (duplicate)
    • riser3.othd [0-500]     → Delete (subset)
    • riser4.othd [1000-2000] → Keep (unique range)
    • riser5.othd [500-1500]  → Keep (overlap, not subset)

    After cleanup, files are renamed: riser1.othd, riser2.othd, riser3.othd

    Output Directory (freq=50):
    • riser.50.out      → Delete (not multiple of 500)
    • riser.100.out     → Delete
    • riser.500.out     → Keep (500 % 500 == 0)
    • riser.1000.out    → Keep (1000 % 500 == 0)

{Colors.BOLD}Notes:{Colors.RESET}
    • Binary PLT files are never deleted
    • Files are renamed based on time step order
    • Both OTHD and OISD files are renamed
    • If multiple RUN_* directories exist, you'll be asked which to clean
""")
