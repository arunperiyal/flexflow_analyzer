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

    {Colors.CYAN}history{Colors.RESET}
        Keep the OTHD/OISD history in three stages (the same for oisd_files/):

            othd_files/archive/{{problem}}N.othd   as each job wrote it
            othd_files/cleaned/{{problem}}N.othd   run N without the steps a
                                                 later run redid
            othd_files/{{problem}}.othd            cleaned/ joined: one file

        N numbers the jobs in the order they ran. Pass at least one flag;
        they combine and always run in the order
        --update → --clean → --compile → --verify → --prune.
        Parts still in the old layout (othd_files/{{problem}}N.othd) are moved
        into archive/ first.

        {Colors.CYAN}--update{Colors.RESET}
            Move .othd/.oisd from the run directory into archive/ as the next
            run (riser.othd → archive/riser6.othd), and .rcv into
            rcv_files/riser6.rcv. With --t1/--t2, only files whose timestep
            range overlaps that window. Moves, never deletes.
            mainFlex.sh does the same at the start of every job.

        {Colors.CYAN}--clean{Colors.RESET}
            Write cleaned/{{problem}}N for every run: its steps that no later
            run redid ("the later run wins" — a restart from step 4000
            replaces everything the run before wrote after 4000). A last
            step cut off by a killed job is left out; a run with nothing
            left has no cleaned file. Records where each run took over in
            {Colors.CYAN}.restarts{Colors.RESET}. Once archive/ is pruned a cleaned file is the
            run's only copy: cutting one shorter asks first.

        {Colors.CYAN}--compile{Colors.RESET}
            Join cleaned/ into othd_files/{{problem}}.othd and
            oisd_files/{{problem}}.oisd. Only from a cleaned/ that is up to date
            with archive/. Every command reads this file while it is newer
            than archive/ and cleaned/, and the runs otherwise.

        {Colors.CYAN}--verify{Colors.RESET}
            Read every file to the end and report its steps, tsId range and
            any problem: a cut-off last step, steps with a different layout,
            non-numeric values, no newline at the end. Also:
              • a cleaned file must follow on from the runs before it and be
                what --clean would write now
              • the compiled file must be cleaned/ joined
            A cut-off last step in archive/ is only noted (--clean leaves it
            out). tsIds in no run at all (a run restarted from later than the
            one before reached) are reported as lost. Anything else wrong
            stops --prune.

        {Colors.CYAN}--prune{Colors.RESET}
            Delete archive/ once cleaned/ reads through and is up to date
            with it: every step that counts is then in cleaned/. Asks first.
            Later jobs add to archive/ again, and --clean folds them in.
            rcv_files/ is not touched.

    {Colors.CYAN}output{Colors.RESET}
        Remove intermediate .out/.rst files from the run directory:
          • .rst (restart points): keeps the steps divisible by
            --keep-freq (default: 10 * freq, freq from outFreq in
            simflow.config or auto-detected)
          • .out: deletes every step whose <problem>.<step>.plt exists
            (binary/ or run dir), keep-freq steps too -- a restart does
            not read .out. Steps with no .plt yet keep their .out.

        {Colors.CYAN}--keep-freq N{Colors.RESET}
            Keep the .rst of the steps divisible by N

        {Colors.CYAN}--all-out{Colors.RESET}
            Delete every .out in range, even at steps with no .plt.
            Those steps can then never be converted.

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

        {Colors.CYAN}--freq N{Colors.RESET}       (with --delete-binary)
            Only the steps divisible by N
        {Colors.CYAN}--keep-freq N{Colors.RESET}  (with --delete-binary)
            Keep the steps divisible by N

    {Colors.CYAN}vtu{Colors.RESET}
        The .vtu files `field render` keeps beside each PLT in binary/
        ({{problem}}.{{step}}.vtu, .z{{N}}.vtu per zone, and .partial/.deriving
        leftovers of an interrupted run). A cache: deleting them loses
        nothing, the next render converts the PLT again. Other .vtu files
        in binary/ are not touched.
          • Without --clean: lists them with their sizes
          • A .vtu whose .plt is gone is marked: it cannot be rebuilt

        {Colors.CYAN}--clean{Colors.RESET}
            Delete them (within --t1/--t2), after confirmation

{Colors.BOLD}TARGETING BY TIMESTEP:{Colors.RESET}
    --t1 STEP                 Only target timesteps >= STEP
    --t2 STEP                 Only target timesteps <= STEP
    (either alone is a one-sided bound; both together is an inclusive range)
    Available on history --update, output, plt and vtu.
    NOT applied to the other history flags, which always use everything.

{Colors.BOLD}OTHER OPTIONS:{Colors.RESET}
    --dry-run                 Show what would be deleted without deleting anything
    --log                     Create log file of all deletions
    --no-confirm              Skip confirmation prompts
    -v, --verbose             Show detailed information
    -h, --help                Show this help message
    --examples                Show usage examples

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set case context:     use case CS4SG1U1
    Then run:             case organise history --update

    Set timestep context: use t1:0 t2:1000
    Then run:              case organise output

{Colors.BOLD}SAFETY:{Colors.RESET}
    • history --update, --clean, --compile and --verify never delete a
      job's data (--clean asks before cutting a run's only copy); --prune
      asks once and only deletes archive/ when cleaned/ holds it; output
      and plt show a summary and ask for confirmation
    • --delete-binary is unconditional: it does not check the run dir first
    • A t1/t2 context left over from something else never silently narrows
      history --clean — it always cleans the whole history
    • Use --no-confirm to skip confirmation
    • Fails if any OTHD/OISD file cannot be read (prevents data loss)

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Move the latest .othd/.oisd/.rcv from the run dir into archive/
    flexflow case organise history CS4SG1U1 --update

    # Clean and join the runs, check everything, then drop archive/
    flexflow case organise history CS4SG1U1 --clean --compile --verify --prune

    # Remove intermediate output files
    flexflow case organise output CS4SG1U1

    # Delete PLT files from run dir where binary/ has a newer copy
    flexflow case organise plt CS4SG1U1 --delete-ascii

    # Delete PLT files from binary/ for a timestep range
    flexflow case organise plt CS4SG1U1 --delete-binary --t1 0 --t2 1000

    # List, then delete, the .vtu caches field render left in binary/
    flexflow case organise vtu CS4SG1U1
    flexflow case organise vtu CS4SG1U1 --clean

    # Only target a timestep range
    flexflow case organise output CS4SG1U1 --t1 0 --t2 1000

    # Use context
    use case CS4SG1U1
    case organise history --update

{Colors.BOLD}SEE ALSO:{Colors.RESET}
    case show    - Display case information
    case status  - Check data file completeness
""")


def print_organise_examples():
    """Print examples for organise command."""
    print(f"""
{Colors.BOLD}CASE ORGANISE - EXAMPLES{Colors.RESET}

{Colors.BOLD}The OTHD/OISD History:{Colors.RESET}

    # Move .othd/.oisd/.rcv from the run dir: the next run number
    #   riser.othd  → othd_files/archive/riser6.othd
    #   riser.oisd  → oisd_files/archive/riser6.oisd
    #   riser.rcv   → rcv_files/riser6.rcv (if present)
    flexflow case organise history CS4SG1U1 --update

    # Each run without what later runs redid, into cleaned/
    flexflow case organise history CS4SG1U1 --clean

    # One file per type: othd_files/riser.othd, oisd_files/riser.oisd
    flexflow case organise history CS4SG1U1 --clean --compile

    # Check archive/, cleaned/ and the compiled files
    flexflow case organise history CS4SG1U1 --verify

    # The whole round, deleting archive/ at the end (asks first)
    flexflow case organise history CS4SG1U1 --update --clean --compile --verify --prune

    # See what would happen, changing nothing
    flexflow case organise history CS4SG1U1 --clean --compile --dry-run

{Colors.BOLD}Cleaning Output Directory:{Colors.RESET}

    # Remove converted .out and intermediate .rst (keeps .rst every freq*10)
    flexflow case organise output CS4SG1U1

    # Delete all .out, converted or not (asks first)
    flexflow case organise output CS4SG1U1 --all-out

    # Keep only the .rst of the steps divisible by 5000
    flexflow case organise output CS4SG1U1 --keep-freq 5000

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

    # Thin binary/ out: in 4000-5000, keep only the steps divisible by 5
    flexflow case organise plt CS4SG1U1 --delete-binary --t1 4000 --t2 5000 --freq 1 --keep-freq 5

    # Both directions in one call
    flexflow case organise plt CS4SG1U1 --delete-ascii --delete-binary --t1 1000 --t2 2000

    # The .vtu caches of field render: list them, delete those up to step 3000
    flexflow case organise vtu CS4SG1U1
    flexflow case organise vtu CS4SG1U1 --clean --t2 3000

{Colors.BOLD}Using Context:{Colors.RESET}

    # Set case context
    use case CS4SG1U1

    # Run operations
    case organise history --update
    case organise history --clean --compile
    case organise output

    # Set a timestep window and reuse it across subcommands
    use t1:0 t2:1000
    case organise output
    case organise plt --delete-ascii

{Colors.BOLD}What history --clean and --compile Do:{Colors.RESET}

    • archive/riser1.othd [1-1073], archive/riser2.othd [1001-2084]
      (riser2 restarted from 1000)
    → cleaned/riser1.othd [1-1000], cleaned/riser2.othd [1001-2084]
    → riser.othd [1-2084]

{Colors.BOLD}What output Does (freq=50, no --keep-freq):{Colors.RESET}

    • riser.50_1.rst       → Delete (not multiple of 500)
    • riser.500_1.rst      → Keep   (500 % 500 == 0, a restart point)
    • riser.500_1.out      → Delete (binary/riser.500.plt exists)
    • riser.550_1.out      → Keep   (no riser.550.plt yet -- convert it first)

{Colors.BOLD}What plt --delete-ascii Does:{Colors.RESET}

    • riser.500.plt (run dir)    → Delete (binary/riser.500.plt exists and is newer)

{Colors.BOLD}What plt --delete-binary Does (--t1 1000 --t2 2000):{Colors.RESET}

    • binary/riser.1500.plt      → Delete (in range, regardless of run dir)
    • binary/riser.3000.plt      → Keep   (outside range)

{Colors.BOLD}... with --keep-freq 500:{Colors.RESET}

    • binary/riser.1500.plt      → Keep   (1500 % 500 == 0)
    • binary/riser.1550.plt      → Delete

{Colors.BOLD}Notes:{Colors.RESET}
    • history --update, --clean, --compile and --verify run immediately
    • history --prune, output, plt and vtu --clean ask for confirmation unless --no-confirm
    • --delete-ascii never touches binary/; --delete-binary never touches the run dir
    • --delete-binary with no --t1/--t2/--freq/--keep-freq deletes every PLT file in binary/
""")
