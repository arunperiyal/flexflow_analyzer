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
    {Colors.YELLOW}maxloc{Colors.RESET}   {Colors.BOLD}where{Colors.RESET} the largest swing happens, not how big it is

{Colors.BOLD}MAXLOC:{Colors.RESET}
    Answers "which PLT should I render to see the wake at peak amplitude".
    It reports the tsId of the largest {Colors.BOLD}absolute{Colors.RESET} value -- the biggest
    excursion of a vibration is as likely to be a trough as a crest -- along
    with its time, and the nearest tsId {Colors.BOLD}at or below{Colors.RESET} it that has a PLT.

    Rounding down rather than up, because a PLT past the end of the run is no
    use. The step size comes from outFreq in simflow.config, or {Colors.YELLOW}--freq{Colors.RESET}.

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    flexflow data stats CS4SG1U1 --var aleDisp_y --node 24 --func max,rms
    flexflow data stats CS4SG1U1 --var aleDisp_y --node 24 --func maxloc
    flexflow data stats CS4SG1U1 --var totTrac --func rms,std --t1 3000 --t2 5000
    flexflow data stats CS4SG1U1 --var aleDisp --node 24 --func range --output swing.csv
""")


def print_statistics_examples():
    print(f"""
{Colors.BOLD}{Colors.CYAN}Data Stats Examples{Colors.RESET}

  {Colors.BOLD}Amplitude of cross-flow vibration, once the run has settled:{Colors.RESET}
    flexflow data stats CS4SG1U1 --var aleDisp_y --node 24 --func rms --t1 3000

  {Colors.BOLD}Which PLT to render for the biggest swing:{Colors.RESET}
    flexflow data stats CS4SG1U1 --var aleDisp_y --node 24 --func maxloc

  {Colors.BOLD}Peak-to-peak, every component:{Colors.RESET}
    flexflow data stats CS4SG1U1 --var aleDisp --node 24 --func range

  {Colors.BOLD}Integrated loads:{Colors.RESET}
    flexflow data stats CS4SG1U1 --var totTrac --func max,rms,maxloc
""")
