"""Help text for `data check`."""

from ....utils.colors import Colors


def print_check_help():
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Data Check Command{Colors.RESET}

Verdicts on the time history.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow data check steady [{Colors.YELLOW}case{Colors.RESET}] --var {Colors.YELLOW}NAME{Colors.RESET} [options]

{Colors.BOLD}SUBCOMMANDS:{Colors.RESET}
    {Colors.YELLOW}steady{Colors.RESET}                 Whether a variable has settled, and from which tsId

`data check steady --help` for its options.
""")


def print_steady_help():
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Data Check Steady Command{Colors.RESET}

Whether the history of a variable has settled into a steady state -- a
steady oscillation, or a steady value -- and from which tsId it has.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow data check steady [{Colors.YELLOW}case{Colors.RESET}] --var {Colors.YELLOW}NAME{Colors.RESET} [options]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--var NAME{Colors.RESET}             Variable or component. Repeat it, or comma-separate;
                           each component is judged on its own
    {Colors.YELLOW}--t1 TSID{Colors.RESET}              First tsId (alone: from there to the end)
    {Colors.YELLOW}--t2 TSID{Colors.RESET}              Last tsId
    {Colors.YELLOW}--last N{Colors.RESET}               Only the last N steps (of the --t1/--t2 window).
                           From context: use last:N
    {Colors.YELLOW}--node N{Colors.RESET}               Node to read       (default: 0)
    {Colors.YELLOW}--othid ID{Colors.RESET} / {Colors.YELLOW}--osgid ID{Colors.RESET}  Probe set / surface group, as for `data table`
    {Colors.YELLOW}--blocks K{Colors.RESET}             Blocks of whole cycles compared   (default: 4)
    {Colors.YELLOW}--min-cycles M{Colors.RESET}         Whole cycles needed in the window (default: 10)
    {Colors.YELLOW}--tol F{Colors.RESET}                Largest amplitude and period spread (default: 0.05)
    {Colors.YELLOW}--mean-tol F{Colors.RESET}           Largest mean shift, in std        (default: 0.1)
    {Colors.YELLOW}--othd{Colors.RESET} / {Colors.YELLOW}--oisd{Colors.RESET}        Which files to take variables from
    {Colors.YELLOW}-v, --verbose{Colors.RESET}          Also print each variable's blocks
    {Colors.YELLOW}-h, --help{Colors.RESET}             Show this help message

{Colors.BOLD}HOW IT DECIDES:{Colors.RESET}
    The window is cut at its upward zero crossings about its mean into whole
    cycles (a crossing counts only after the signal was 0.1 std below the
    mean, so noise adds none), and the cycles into K blocks of equal count;
    leftover cycles are dropped from the start. Per block: the mean, the
    amplitude (rms about that mean) and the period. Steady when

        cycles in the window                    >= --min-cycles
        (max mean - min mean) / std             <= --mean-tol
        (max amplitude - min amplitude) / mean  <= --tol
        (max period - min period) / mean        <= --tol

    Whole cycles keep a block's mean free of the half-cycle bias that
    equal-length blocks would carry. The mean shift is measured against the
    std, not the mean: a cross-flow displacement has a mean near zero.

    A failing test says which way it went -- {Colors.BOLD}amplitude growing{Colors.RESET} is a run
    still developing; mean drifting, period lengthening and so on.

    A signal with under 2 cycles whose std is below --tol of its mean (a mean
    drag) is {Colors.BOLD}flat{Colors.RESET}: K equal blocks, steady when the shift of their means
    is under --tol of the mean. One that fluctuates but has too few cycles is
    {Colors.BOLD}too short{Colors.RESET} to say.

{Colors.BOLD}COLUMNS:{Colors.RESET}
    {Colors.YELLOW}mean Δ{Colors.RESET} is the spread of the block means in std, {Colors.YELLOW}amp Δ{Colors.RESET} and {Colors.YELLOW}period Δ{Colors.RESET}
    the spread of the block amplitudes and periods over their mean; ✗ marks
    one past its limit, and why a variable fails is printed under the table.

{Colors.BOLD}FROM:{Colors.RESET}
    The tsId from which the rest of the window is steady -- the --t1 to use,
    or the transient to discard. The candidates are the cycle starts, earliest
    first; each rest is judged afresh, its own mean included, and the answer
    is where its first block starts (the leftover cycles before it were not
    judged). It is looked for inside the window: with --last, it is about the
    window start when all of it is steady. "-" when no rest passes.

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    flexflow data check steady CS4SG1U1 --var dy --node 24
    flexflow data check steady CS4SG1U1 --var dx,dy --node 24 --last 4000
    flexflow data check steady CS4SG1U1 --var tt --oisd --tol 0.1 -v
    flexflow data check steady * --var dy --last 4000
""")


def print_steady_examples():
    print(f"""
{Colors.BOLD}{Colors.CYAN}Data Check Steady Examples{Colors.RESET}

  {Colors.BOLD}Has the cross-flow displacement settled, and from when?{Colors.RESET}
    flexflow data check steady CS4SG1U1 --var dy --node 24

  {Colors.BOLD}Only the last 4000 steps, with the blocks shown:{Colors.RESET}
    flexflow data check steady CS4SG1U1 --var dy --node 24 --last 4000 -v

  {Colors.BOLD}From the shell context:{Colors.RESET}
    use case:CS4SG1U1 var:dy node:24 last:4000
    data check steady
""")
