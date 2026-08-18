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
      - how many nodes  {Colors.DIM}(1 means integrated output -- one value per step
        for the whole surface, rather than one per node){Colors.RESET}
      - how many timesteps, and the time and tsId span they cover
      - which tsIds also have a PLT beside them, from outFreq
      - every variable in the files, and the name to give {Colors.YELLOW}--var{Colors.RESET}
        {Colors.DIM}(a 3-component variable is listed with its _x/_y/_z names too){Colors.RESET}

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

  {Colors.BOLD}Just the surface-integrated output:{Colors.RESET}
    flexflow data show CS4SG1U1 --oisd

  {Colors.BOLD}Just the nodal history:{Colors.RESET}
    flexflow data show CS4SG1U1 --othd
""")
