"""Help text for `data show`."""

from ....utils.colors import Colors


def print_preview_help():
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Data Show Command{Colors.RESET}

What a case's time-history data holds -- {Colors.BOLD}not{Colors.RESET} the numbers themselves.
Run it before `data table` or `data stats` to learn what can be named to --var.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow data show [{Colors.YELLOW}case{Colors.RESET}] [options]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--othd{Colors.RESET}                 The othd files alone
    {Colors.YELLOW}--oisd{Colors.RESET}                 The oisd files alone
    {Colors.YELLOW}-v, --verbose{Colors.RESET}          Verbose output
    {Colors.YELLOW}-h, --help{Colors.RESET}             Show this help message

{Colors.BOLD}REPORTS:{Colors.RESET}
    For each of othd and oisd:
      - how many files
      - how many nodes each output group writes  {Colors.DIM}(a count of 1 may be a
        surface integral or a single probe point -- the count alone does not
        say which, so nothing here guesses){Colors.RESET}
      - how many timesteps, and the time and tsId span they cover
      - which tsIds also have a PLT beside them, from outFreq
      - every variable in the files, and the name to give {Colors.YELLOW}--var{Colors.RESET}
        {Colors.DIM}(a 3-component variable is listed with its _x/_y/_z names, and
        every variable with a short name: aleDisp is d, so dx/dy/dz; vel is u;
        totTrac is tt. The Short column lists them all.){Colors.RESET}
      - the output groups: the othIds of an othd file, the osgIds of an oisd.
        Always reported, since one group numbered 0 is still an answer. When a
        run wrote several, each has its own nodes and its own variables

    The variables are read out of the files rather than listed in FlexFlow, so
    whatever a run was asked to write is what shows up here.

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    flexflow data show CS4SG1U1
    flexflow data show CS4SG1U1 --othd
    flexflow data show CS4SG1U1 --oisd

{Colors.BOLD}THEN:{Colors.RESET}
    {Colors.DIM}data table CS4SG1U1 --var aleDisp_y --node 24
    data stats CS4SG1U1 --var aleDisp_y --func max,rms{Colors.RESET}
""")


def print_preview_examples():
    print(f"""
{Colors.BOLD}{Colors.CYAN}Data Show Examples{Colors.RESET}

  {Colors.BOLD}Everything the case has:{Colors.RESET}
    flexflow data show CS4SG1U1

  {Colors.BOLD}Just the surface output:{Colors.RESET}
    flexflow data show CS4SG1U1 --oisd

  {Colors.BOLD}Just the nodal history:{Colors.RESET}
    flexflow data show CS4SG1U1 --othd
""")
