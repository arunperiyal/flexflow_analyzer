"""
Help messages for case status command
"""

from ....utils.colors import Colors


def print_status_help():
    """Print help message for case status command."""
    print(f"""
{Colors.BOLD}FLEXFLOW CASE STATUS{Colors.RESET}

The case's own notes, kept in {Colors.CYAN}.casestatus.md{Colors.RESET} in the case directory, shown
under what its files say now: the setup, the step the run reached, the restart,
the last PLT and the case's jobs in the queue (those are read each time, never
saved, so they cannot go stale).

{Colors.BOLD}USAGE:{Colors.RESET}
    case status [{Colors.YELLOW}case{Colors.RESET}] [--no-create]
    case status update [{Colors.YELLOW}case{Colors.RESET}] [-m {Colors.YELLOW}TEXT{Colors.RESET}] [--state {Colors.YELLOW}STATE{Colors.RESET}]
    case status '*'

{Colors.BOLD}SHOW:{Colors.RESET}
    The first time, it writes the file from a template (--no-create: don't).
    The markdown is rendered as it is written.

{Colors.BOLD}UPDATE:{Colors.RESET}
    With nothing else, opens the file in $VISUAL / $EDITOR (else vi, vim, nano).
    {Colors.YELLOW}-m TEXT{Colors.RESET}        Add a timestamped line to the ## Log section
    {Colors.YELLOW}--state STATE{Colors.RESET}  new | meshing | running | stopped | done | failed | archived
                   (the change is logged too)
    A case directory named 'update' is ./update.

{Colors.BOLD}THE FILE:{Colors.RESET}
    ---
    state: running
    tags: [CS4, sweep-A]
    ---
    # CS4SG3U6P0
    What the case is for, what it is compared with ...
    ## Notes
    ## Log
    - 2026-10-20 14:02  main job 81234 started: resumed from 4000
    The log is oldest first. The job scripts (mainFlex.sh, postFlex.sh) add
    their own lines: started, resumed from, ended with exit code, cancelled.
    Keep ## Log a top-level section; lines go at its end.

{Colors.BOLD}'*':{Colors.RESET}
    One line per case in .cases: its state and last log line.

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    case status CS4SG3U6P0
    case status update CS4SG3U6P0
    case status update CS4SG3U6P0 -m "lock-in from U=5.5; compare with U1"
    case status update CS4SG3U6P0 --state done
    case status '*'

    The old `case status` (data file completeness) is now `case check data`.
""")
