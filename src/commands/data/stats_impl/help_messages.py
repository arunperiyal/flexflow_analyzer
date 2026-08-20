"""Help text for `data stats`."""

from ....utils.colors import Colors


def print_statistics_help():
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Data Stats Command{Colors.RESET}

One row per variable instead of one row per timestep.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow data stats [{Colors.YELLOW}case{Colors.RESET}] --var {Colors.YELLOW}NAME{Colors.RESET} --func {Colors.YELLOW}FUNC{Colors.RESET} [options]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--var NAME{Colors.RESET}             Variable or component. Repeat it, or comma-separate.
                           {Colors.DIM}Every variable has a short name: dy, vx, ttx.
                           `data show` lists them.{Colors.RESET}
    {Colors.YELLOW}--func FUNC{Colors.RESET}            What to work out. Repeat it, or comma-separate.
    {Colors.YELLOW}--t1 TSID{Colors.RESET}              First tsId (alone: from there to the end)
    {Colors.YELLOW}--t2 TSID{Colors.RESET}              Last tsId
    {Colors.YELLOW}--node N{Colors.RESET}               Node to read       (default: 0)
    {Colors.YELLOW}--group ID{Colors.RESET}             Output group: othId in an othd file, osgId in an
                           oisd (default: the first). Only matters when a run
                           wrote more than one probe set into a file.
    {Colors.YELLOW}--output FILE{Colors.RESET}          Also write the summary to a .csv
    {Colors.YELLOW}--freq N{Colors.RESET}               PLT output frequency for maxloc
                           {Colors.DIM}(default: outFreq from simflow.config){Colors.RESET}
    {Colors.YELLOW}--othd{Colors.RESET} / {Colors.YELLOW}--oisd{Colors.RESET}        Which files to take variables from
    {Colors.YELLOW}-v, --verbose{Colors.RESET}          Verbose output
    {Colors.YELLOW}-h, --help{Colors.RESET}             Show this help message

{Colors.BOLD}FUNCTIONS:{Colors.RESET}
    {Colors.YELLOW}min{Colors.RESET}      smallest value in the window
    {Colors.YELLOW}max{Colors.RESET}      largest value
    {Colors.YELLOW}mean{Colors.RESET}     arithmetic mean
    {Colors.YELLOW}rms{Colors.RESET}      root mean square -- the amplitude of a vibration
    {Colors.YELLOW}std{Colors.RESET}      standard deviation
    {Colors.YELLOW}range{Colors.RESET}    max - min, the peak-to-peak swing
    {Colors.YELLOW}maxloc{Colors.RESET}   {Colors.BOLD}where{Colors.RESET} the maximum happens, not how big it is
    {Colors.YELLOW}minloc{Colors.RESET}   the same for the minimum
    {Colors.YELLOW}zeroloc{Colors.RESET}  where the signal crosses zero, both ways

{Colors.BOLD}MAXLOC / MINLOC:{Colors.RESET}
    Answer "which PLT should I render to see the wake at peak amplitude" --
    maxloc for the top of the cycle, minloc for the bottom.

    Each reports the tsId of the {Colors.BOLD}signed{Colors.RESET} extreme -- the same number
    {Colors.YELLOW}--func max{Colors.RESET} or {Colors.YELLOW}--func min{Colors.RESET} gives -- and then, separately, {Colors.BOLD}which PLT
    file comes closest to it{Colors.RESET}, with the value that file actually holds and
    the next best few behind it. Ask for both to bracket a cycle.

    The chosen file is the one whose own value is most extreme, {Colors.BOLD}not{Colors.RESET} the one
    nearest the extreme. The peak almost always falls between two outputs, so
    nearness is only a proxy for amplitude -- and a poor one: over this repo's
    sample case the nearest file is not the strongest in about three windows
    out of four, and in the worst of them it shows a quarter of the swing the
    best file does. Ties go to the earlier file.

    The runners-up are listed because a frame is also chosen on what else is in
    it, and the second-best file is often as good a picture.

    Candidates are the steps the data actually covers, so a run that stopped
    between two outputs never names a file that was not written. The step size
    comes from outFreq in simflow.config, or {Colors.YELLOW}--freq{Colors.RESET}.

{Colors.BOLD}ZEROLOC:{Colors.RESET}
    Where the cylinder passes through its undeflected position -- the frame
    halfway between the extremes, moving fastest.

    A settled run crosses zero once per half cycle, so "the crossing" has to be
    chosen: it is the one an existing PLT file comes closest to, the same way
    maxloc chooses. Both directions are reported -- {Colors.BOLD}descending{Colors.RESET} is the
    max{Colors.BOLD}->{Colors.RESET}min pass, {Colors.BOLD}ascending{Colors.RESET} the way back.

    Zero means zero, not the window's mean: a cylinder with a steady offset
    still crosses the axis, and that is a different instant from crossing its
    own average. A signal that never reaches zero says so rather than
    inventing a crossing.

    Direction comes from the local slope, so a file at the top of the swing on
    its way down counts as descending -- it simply ranks last. No sample lands
    exactly on zero, so a crossing is reported at whichever of the two
    straddling steps is nearer it. When the output frequency is coarse against
    the period, every file can land on a peak; the closest one is then still
    the answer, and how far from zero it sits is said out loud.

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    flexflow data stats CS4SG1U1 --var aleDisp_y --node 24 --func max,rms
    flexflow data stats CS4SG1U1 --var aleDisp_y --node 24 --func maxloc,minloc
    flexflow data stats CS4SG1U1 --var aleDisp_y --node 24 --func zeroloc
    flexflow data stats CS4SG1U1 --var totTrac --func rms,std --t1 3000 --t2 5000
    flexflow data stats CS4SG1U1 --var aleDisp --node 24 --func range --output swing.csv
""")


def print_statistics_examples():
    print(f"""
{Colors.BOLD}{Colors.CYAN}Data Stats Examples{Colors.RESET}

  {Colors.BOLD}Amplitude of cross-flow vibration, once the run has settled:{Colors.RESET}
    flexflow data stats CS4SG1U1 --var aleDisp_y --node 24 --func rms --t1 3000

  {Colors.BOLD}Which PLT to render at each end of the cycle:{Colors.RESET}
    flexflow data stats CS4SG1U1 --var aleDisp_y --node 24 --func maxloc,minloc

  {Colors.BOLD}Peak-to-peak, every component:{Colors.RESET}
    flexflow data stats CS4SG1U1 --var aleDisp --node 24 --func range

  {Colors.BOLD}Integrated loads:{Colors.RESET}
    flexflow data stats CS4SG1U1 --var totTrac --func max,rms,maxloc
""")
