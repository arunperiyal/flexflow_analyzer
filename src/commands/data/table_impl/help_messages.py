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
                           Every variable has a short name too: aleDisp is
                           {Colors.RESET}{Colors.YELLOW}d{Colors.RESET}{Colors.DIM} (dx/dy/dz), aleVel is {Colors.RESET}{Colors.YELLOW}v{Colors.RESET}{Colors.DIM}, vel is {Colors.RESET}{Colors.YELLOW}u{Colors.RESET}{Colors.DIM}, totTrac is {Colors.RESET}{Colors.YELLOW}tt{Colors.RESET}{Colors.DIM}.
                           `data show` lists every name this case has.{Colors.RESET}
    {Colors.YELLOW}--t1 TSID{Colors.RESET}              First tsId (alone: from there to the end)
    {Colors.YELLOW}--t2 TSID{Colors.RESET}              Last tsId
    {Colors.YELLOW}--last N{Colors.RESET}               Only the last N steps (of the --t1/--t2 window).
                           From context: use last:N
    {Colors.YELLOW}--node N{Colors.RESET}               Node to read       (default: 0)
    {Colors.YELLOW}--othid ID{Colors.RESET}             othId -- which probe set to read from the othd
                           files (default: the first). From context: use othid:N
    {Colors.YELLOW}--osgid ID{Colors.RESET}             osgId -- which surface group to read from the oisd
                           files (default: the first). From context: use osgid:N
                           The two numberings are unrelated; the variables decide
                           which files are read, and so which of the two applies.
                           Only matters when a file holds more than one group.
    {Colors.YELLOW}--group ID{Colors.RESET}             The id in whichever files are read (older spelling;
                           never filled from context)
    {Colors.YELLOW}--output [FILE]{Colors.RESET}        Write {Colors.BOLD}every{Colors.RESET} row to a .csv instead of printing.
                           Without FILE: <case>/data_tables/<var>.csv
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

    {Colors.YELLOW}--last N{Colors.RESET} keeps the N highest tsIds of what the window selects --
    of the whole history without --t1/--t2. Unlike {Colors.YELLOW}--tail{Colors.RESET}, which only
    decides what is printed, it decides what is read, so it applies to
    --output too.

{Colors.BOLD}OUTPUT:{Colors.RESET}
    {Colors.YELLOW}--output{Colors.RESET} with no file writes {Colors.CYAN}<case>/data_tables/<var>.csv{Colors.RESET}, named
    after the variables as given (dy.csv; dx_dy.csv for two), and replaces
    the file there. With {Colors.YELLOW}*{Colors.RESET} every case writes into its own data_tables/.
    For scripts: {Colors.DIM}use case:CS4SG1U1 var:dy last:1000{Colors.RESET}, then {Colors.DIM}data table --output{Colors.RESET}.

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    flexflow data table CS4SG1U1 --var aleDisp_y --node 24
    flexflow data table CS4SG1U1 --var aleDisp --node 24 --tail 20
    flexflow data table CS4SG1U1 --var vel_y,pres --node 24 --t1 4000 --t2 5000
    flexflow data table CS4SG1U1 --var totTrac_y --output trac.csv
    flexflow data table CS4SG1U1 --var dy --last 1000 --output
    flexflow data table * --var dy --last 1000 --output
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

  {Colors.BOLD}The last 1000 steps, to CS4SG1U1/data_tables/dy.csv:{Colors.RESET}
    flexflow data table CS4SG1U1 --var dy --last 1000 --output
""")
