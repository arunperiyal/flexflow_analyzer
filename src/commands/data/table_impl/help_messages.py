"""Help text for `data table`."""

from ....utils.colors import Colors


def print_table_help():
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Data Table Command{Colors.RESET}

The time history of chosen variables, as a table. {Colors.BOLD}Time runs down the rows{Colors.RESET}
and variables across the columns.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow data table [{Colors.YELLOW}case{Colors.RESET}] --var {Colors.YELLOW}NAME{Colors.RESET} [options]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--var NAME{Colors.RESET}             Variable or component. Repeat it, or comma-separate.
                           {Colors.DIM}`vel` gives all three components; `vel_y` gives one.
                           aleDisp and aleVel answer to {Colors.RESET}{Colors.YELLOW}d{Colors.RESET}{Colors.DIM} and {Colors.RESET}{Colors.YELLOW}v{Colors.RESET}{Colors.DIM}, so
                           dx/dy/dz and vx/vy/vz work too.
                           `data show` lists every name this case has.{Colors.RESET}
    {Colors.YELLOW}--t1 TSID{Colors.RESET}              First tsId (alone: only that step)
    {Colors.YELLOW}--t2 TSID{Colors.RESET}              Last tsId
    {Colors.YELLOW}--node N{Colors.RESET}               Node to read       (default: 0)
    {Colors.YELLOW}--group ID{Colors.RESET}             Output group: othId in an othd file, osgId in an
                           oisd (default: the first). Only matters when a run
                           wrote more than one probe set into a file.
    {Colors.YELLOW}--output FILE{Colors.RESET}          Write {Colors.BOLD}every{Colors.RESET} row to a .csv instead of printing
    {Colors.YELLOW}--head N{Colors.RESET}               Print the first N rows
    {Colors.YELLOW}--tail N{Colors.RESET}               Print the last N rows
    {Colors.YELLOW}--othd{Colors.RESET} / {Colors.YELLOW}--oisd{Colors.RESET}        Which files to take variables from
    {Colors.YELLOW}-v, --verbose{Colors.RESET}          Verbose output
    {Colors.YELLOW}-h, --help{Colors.RESET}             Show this help message

{Colors.BOLD}HOW MUCH IS PRINTED:{Colors.RESET}
    Without {Colors.YELLOW}--output{Colors.RESET}, the {Colors.BOLD}first 10 rows{Colors.RESET} -- enough to see the shape of a
    column without burying the header. {Colors.YELLOW}--head N{Colors.RESET} or {Colors.YELLOW}--tail N{Colors.RESET} change that;
    {Colors.YELLOW}--tail{Colors.RESET} is the one you want on a run that is still settling.

    With {Colors.YELLOW}--output{Colors.RESET} every selected row is written and nothing is printed,
    so --head/--tail do not apply.

{Colors.BOLD}TIMESTEPS:{Colors.RESET}
    {Colors.YELLOW}--t1{Colors.RESET}/{Colors.YELLOW}--t2{Colors.RESET} are {Colors.BOLD}tsIds{Colors.RESET}, the number in a PLT filename -- the same
    reading `field extract` and `field render` give them, and the units the
    t1/t2 context is set in. Physical time is a column, not a filter.

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    flexflow data table CS4SG1U1 --var aleDisp_y --node 24
    flexflow data table CS4SG1U1 --var aleDisp --node 24 --tail 20
    flexflow data table CS4SG1U1 --var vel_y,pres --node 24 --t1 4000 --t2 5000
    flexflow data table CS4SG1U1 --var totTrac_y --output trac.csv
""")


def print_table_examples():
    print(f"""
{Colors.BOLD}{Colors.CYAN}Data Table Examples{Colors.RESET}

  {Colors.BOLD}The last 20 steps of cross-flow displacement at node 24:{Colors.RESET}
    flexflow data table CS4SG1U1 --var aleDisp_y --node 24 --tail 20

  {Colors.BOLD}All three components at once:{Colors.RESET}
    flexflow data table CS4SG1U1 --var aleDisp --node 24

  {Colors.BOLD}A window, by tsId:{Colors.RESET}
    flexflow data table CS4SG1U1 --var aleDisp_y --node 24 --t1 4000 --t2 5000

  {Colors.BOLD}Everything, to a file for plotting:{Colors.RESET}
    flexflow data table CS4SG1U1 --var aleDisp_y --node 24 --output disp.csv
""")
