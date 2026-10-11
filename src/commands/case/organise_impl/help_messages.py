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
        Manage the OTHD/OISD archive. Pass at least one flag; they combine
        and always run in the order
        --update → --verify → --clean → --compile → --prune.

        {Colors.CYAN}--update{Colors.RESET}
            Move .othd, .oisd (and .rcv if present) from the run directory
            into othd_files/, oisd_files/, rcv_files/ under the next free
            number (riser.othd → riser6.othd). With --t1/--t2, only files
            whose timestep range overlaps that window are moved.
            No confirmation required — moves, never deletes.

        {Colors.CYAN}--verify{Colors.RESET}
            Read every archived part and compiled file to the end and
            report, per file, the steps, tsId range and any problem:
              • a last step cut off by a killed job
              • steps whose layout differs from the rest of the file
              • non-numeric values, or no newline at the end
            Restarts inside a file are listed but are fine. If anything is
            wrong, --clean / --compile / --prune do not run.

        {Colors.CYAN}--clean{Colors.RESET}
            Deduplicate othd_files/ and oisd_files/ under manual supervision
            (works on the archive only, never the run directory):
              • Shows every archived file with its tsId range and the
                proposed action (keep / delete + reason)
              • Duplicates (same tsId range) and subsets (covered by a
                larger file) are proposed for deletion; overlaps are kept
              • Asks about each proposed deletion: y = delete, n = keep,
                a = delete this and the rest, q = abort (change nothing)
              • Then shows the renumbering by starting tsId and asks once
              • --no-confirm accepts the whole plan unattended
              • Always analyzes the complete archived set — --t1/--t2 do
                NOT scope --clean

        {Colors.CYAN}--compile{Colors.RESET}
            Combine the archived parts into othd_files/compiled/{{problem}}.othd
            and oisd_files/compiled/{{problem}}.oisd (parts are kept):
              • Parts are taken in order of their first tsId
              • A restart (a tsId at or below one already taken) replaces
                everything from that tsId on with the restarted run's data
              • Gaps in the combined tsIds are reported
              • Parts with different headers (probe/surface sets) are not
                combined
              • Rewrites the compiled file each time; ignores --t1/--t2

        {Colors.CYAN}--prune{Colors.RESET}
            Replace the parts with the compiled file: the parts in
            othd_files/ and oisd_files/ are deleted and the compiled file
            becomes {{problem}}1.othd / {{problem}}1.oisd, an ordinary part that
            every command reads. The next --update numbers from 2.
              • Only when the compiled file holds all of the parts' data —
                compiling again would write exactly the same file;
                out-of-date or missing compiled files are refused
              • The compiled data stays on disk throughout: it is moved
                into place first, then the parts are deleted
              • A compiled file with no parts left is just moved into place
              • Asks before deleting. RCV files are not touched.

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
    Available on archive --update, output and plt.
    NOT applied to the other archive flags, which always use everything.

{Colors.BOLD}OTHER OPTIONS:{Colors.RESET}
    --dry-run                 Show what would be deleted without deleting anything
    --log                     Create log file of all deletions
    --no-confirm              Skip confirmation prompts
    -v, --verbose             Show detailed information
    -h, --help                Show this help message
    --examples                Show usage examples

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set case context:     use case CS4SG1U1
    Then run:             case organise archive --update

    Set timestep context: use t1:0 t2:1000
    Then run:              case organise output

{Colors.BOLD}SAFETY:{Colors.RESET}
    • archive --update, --verify and --compile never delete anything
    • archive --clean asks about each file, --prune asks once and only
      deletes parts already in a current compiled file; output and plt
      show a summary and ask for confirmation
    • --delete-binary is unconditional: it does not check the run dir first
    • A t1/t2 context left over from something else never silently narrows
      archive --clean — it always cleans the complete archived set
    • Use --no-confirm to skip confirmation
    • Fails if any OTHD/OISD file cannot be read (prevents data loss)

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Move the latest .othd/.oisd/.rcv from the run dir into the archive
    flexflow case organise archive CS4SG1U1 --update

    # Update, deduplicate (asking per file), then build one file per type
    flexflow case organise archive CS4SG1U1 --update --clean --compile

    # Check the archive, build one file per type, then drop the parts
    flexflow case organise archive CS4SG1U1 --verify --compile --prune

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
    case organise archive --update

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
    flexflow case organise archive CS4SG1U1 --update

    # Files get the next free number:
    #   riser.othd  → othd_files/riser6.othd
    #   riser.oisd  → oisd_files/riser6.oisd
    #   riser.rcv   → rcv_files/riser6.rcv (if present)

    # Only archive files whose timestep range overlaps [0, 1000]
    flexflow case organise archive CS4SG1U1 --update --t1 0 --t2 1000

{Colors.BOLD}Deduplicating OTHD/OISD Files:{Colors.RESET}

    # Remove duplicate/subset files, confirming each one (y/n/a/q)
    # --clean always inspects the full archived set, even with a t1/t2
    # context left over from something else
    flexflow case organise archive CS4SG1U1 --clean

    # Accept the whole plan unattended
    flexflow case organise archive CS4SG1U1 --clean --no-confirm

{Colors.BOLD}Compiling OTHD/OISD Files:{Colors.RESET}

    # One file per type in othd_files/compiled/ and oisd_files/compiled/
    flexflow case organise archive CS4SG1U1 --compile

    # Show what would be combined without writing
    flexflow case organise archive CS4SG1U1 --compile --dry-run

{Colors.BOLD}Verifying and Pruning:{Colors.RESET}

    # Check every archived file reads through to the end
    flexflow case organise archive CS4SG1U1 --verify

    # Keep only the compiled files (asks first)
    flexflow case organise archive CS4SG1U1 --verify --compile --prune

    # Later runs are added as riser2, riser3, ... and folded in again
    flexflow case organise archive CS4SG1U1 --update --compile --prune

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
    case organise archive --update
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

    Each "Delete" is asked about first (y/n/a/q). After cleanup, files are
    renamed sequentially by starting step (also confirmed):
    riser1.othd [0-1000], riser2.othd [500-1500], riser3.othd [1000-2000]

{Colors.BOLD}What archive --compile Does:{Colors.RESET}

    • riser1.othd [1-1073], riser2.othd [1001-2084] (restart from 1000)
    → compiled/riser.othd [1-2084]: steps 1-1000 from riser1,
      1001-2084 from riser2

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
    • archive --update, --verify and --compile run immediately, no confirmation needed
    • archive --clean, output and plt ask for confirmation unless --no-confirm
    • --delete-ascii never touches binary/; --delete-binary never touches the run dir
    • --delete-binary with no --t1/--t2 deletes every PLT file in binary/
""")
