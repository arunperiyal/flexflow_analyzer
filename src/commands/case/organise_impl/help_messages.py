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

    {Colors.CYAN}out{Colors.RESET}
        Delete the .out files of the run directory, a step's .out once the
        next file in the chain can stand in for them: its ASCII PLT, whole
        (each zone holds the lines its header counts) and written after
        every .out part; else its binary PLT, whole and written after
        them; else, when binary/ no longer holds it, its verified copy on
        the remote (--remote). A restart does not read .out. A step with no
        PLT, or one cut short or older than its .out (made before a
        restart), keeps its .out and is listed; the other steps go. The
        .rst are not touched.

        {Colors.CYAN}--remote NAME{Colors.RESET}
            The remote to ask about a binary PLT that binary/ no longer
            holds. Without it such a step keeps its .out.

    {Colors.CYAN}rst{Colors.RESET}
        Thin the .rst (restart sets) of the run directory: keeps the steps
        divisible by --keep-freq (default: 10 * freq, freq from outFreq in
        simflow.config or auto-detected), and always: the step of
        restartTsId in simflow.config (where a restart resumes), the
        newest --keep-newest complete sets (all nsg parts; default 2), and
        a newest set that is still incomplete. The .out are not touched.

        {Colors.CYAN}--keep-freq N{Colors.RESET}
            Keep the .rst of the steps divisible by N

        {Colors.CYAN}--keep-newest N{Colors.RESET}
            Also keep the N newest complete .rst sets (default 2): if the
            newest was cut short when a job was killed while writing it, the
            one before it restarts the run. 1 keeps only the newest

    (`case organise output` is gone: it did both; use `out` and `rst`.)

    {Colors.CYAN}plt{Colors.RESET}
        Pass at least one of --delete-ascii / --delete-binary.

        The chain: an ASCII PLT may go when its binary PLT is verified; a
        binary PLT may go when its copy on the remote is. A file with
        nothing to stand in for it is kept and listed; the others go.

        {Colors.CYAN}--delete-ascii{Colors.RESET}
            Delete ASCII PLT files from the run directory whose binary PLT
            stands in for them:
              • binary/ holds it whole (as long as its header says) and
                written after the ASCII file; or
              • binary/ no longer holds it, and the remote holds its
                verified copy (--remote), written after the ASCII file
              • Keeps the others, with the reason (prints with ⚠ or —)
              • Shows a per-file table before asking confirmation

        {Colors.CYAN}--delete-binary{Colors.RESET}
            Delete PLT files from binary/ within --t1/--t2 that have a copy
            on the remote with the same size and md5, both read at that
            moment (as `case check plt --verify` does).
              • Needs --remote NAME (or `use remote:NAME`)
              • A file whose copy is missing or differs, or that is cut
                short here, is kept and listed
              • When the remote cannot be asked, nothing is deleted
              • It reads every file in full on both sides: slow on purpose

        {Colors.CYAN}--remote NAME{Colors.RESET}
            The remote holding the copies; its folder comes from the case
            folder's .cases.yml
        {Colors.CYAN}--freq N{Colors.RESET}
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
    Available on history --update, out, rst, plt and vtu.
    NOT applied to the other history flags, which always use everything.

{Colors.BOLD}OTHER OPTIONS:{Colors.RESET}
    --dry-run                 Show what would be deleted without deleting anything
    --log                     Create log file of all deletions
    --no-confirm              Skip confirmation prompts (history --clean/--compile/--prune included)
    -v, --verbose             Show detailed information
    -h, --help                Show this help message
    --examples                Show usage examples

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set case context:     use case CS4SG1U1
    Then run:             case organise history --update

    Set timestep context: use t1:0 t2:1000
    Then run:              case organise out

{Colors.BOLD}SAFETY:{Colors.RESET}
    • history --update, --clean, --compile and --verify never delete a
      job's data. --clean asks before it writes or removes cleaned files
      (with a stronger warning when one is the only copy of its run) and
      --compile before it replaces the compiled file; --prune asks once and
      only deletes archive/ when cleaned/ holds it; out, rst and plt show a
      summary and ask for confirmation
    • --delete-binary only deletes a file whose copy on the remote has the
      same md5; --delete-ascii and out only what a later file stands in for
    • A t1/t2 context left over from something else never silently narrows
      history --clean — it always cleans the whole history
    • Use --no-confirm to skip confirmation
    • Fails if any OTHD/OISD file cannot be read (prevents data loss)

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Move the latest .othd/.oisd/.rcv from the run dir into archive/
    flexflow case organise history CS4SG1U1 --update

    # Clean and join the runs, check everything, then drop archive/
    flexflow case organise history CS4SG1U1 --clean --compile --verify --prune

    # Delete the .out files a PLT stands in for, and thin the .rst
    flexflow case organise out CS4SG1U1
    flexflow case organise rst CS4SG1U1

    # Delete PLT files from run dir where binary/ has a newer copy
    flexflow case organise plt CS4SG1U1 --delete-ascii

    # Delete PLT files from binary/ for a timestep range
    flexflow case organise plt CS4SG1U1 --delete-binary --t1 0 --t2 1000

    # List, then delete, the .vtu caches field render left in binary/
    flexflow case organise vtu CS4SG1U1
    flexflow case organise vtu CS4SG1U1 --clean

    # Only target a timestep range
    flexflow case organise out CS4SG1U1 --t1 0 --t2 1000

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

{Colors.BOLD}Cleaning the .out and .rst files:{Colors.RESET}

    # Delete the .out a whole, newer PLT stands in for (the others stay)
    flexflow case organise out CS4SG1U1

    # Thin the .rst (keeps those every freq*10, the restart point and the newest 2)
    flexflow case organise rst CS4SG1U1

    # Keep only the .rst of the steps divisible by 5000
    flexflow case organise rst CS4SG1U1 --keep-freq 5000

    # Only clean up to timestep 5000
    flexflow case organise out CS4SG1U1 --t2 5000

    # Create log file of deletions
    flexflow case organise rst CS4SG1U1 --log

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
    case organise out

    # Set a timestep window and reuse it across subcommands
    use t1:0 t2:1000
    case organise out
    case organise plt --delete-ascii

{Colors.BOLD}What history --clean and --compile Do:{Colors.RESET}

    • archive/riser1.othd [1-1073], archive/riser2.othd [1001-2084]
      (riser2 restarted from 1000)
    → cleaned/riser1.othd [1-1000], cleaned/riser2.othd [1001-2084]
    → riser.othd [1-2084]

{Colors.BOLD}What rst Does (freq=50, no --keep-freq):{Colors.RESET}

    • riser.50_1.rst       → Delete (not multiple of 500)
    • riser.500_1.rst      → Keep   (500 % 500 == 0, a restart point)

{Colors.BOLD}What out Does:{Colors.RESET}

    • riser.500_1.out      → Delete (riser.500.plt is whole and newer)
    • riser.550_1.out      → Keep   (no riser.550.plt yet -- convert it first)

{Colors.BOLD}What plt --delete-ascii Does:{Colors.RESET}

    • riser.500.plt (run dir)    → Delete (binary/riser.500.plt is whole and newer)
    • riser.550.plt (run dir)    → Keep   (binary/riser.550.plt is cut short)

{Colors.BOLD}What plt --delete-binary Does (--t1 1000 --t2 2000):{Colors.RESET}

    • binary/riser.1500.plt      → Delete (in range, same md5 on the remote)
    • binary/riser.1550.plt      → Keep   (in range, not on the remote)
    • binary/riser.3000.plt      → Keep   (outside range)

{Colors.BOLD}... with --keep-freq 500:{Colors.RESET}

    • binary/riser.1500.plt      → Keep   (1500 % 500 == 0)
    • binary/riser.1550.plt      → Delete

{Colors.BOLD}Notes:{Colors.RESET}
    • history --update and --verify run immediately
    • history --clean, --compile and --prune, and out, rst, plt and vtu --clean, ask for
      confirmation unless --no-confirm (auto apply passes it: it asks once itself)
    • --delete-ascii never touches binary/; --delete-binary never touches the run dir
    • --delete-binary with no --t1/--t2/--freq/--keep-freq takes every PLT file in binary/
      that has a verified copy on the remote
""")
