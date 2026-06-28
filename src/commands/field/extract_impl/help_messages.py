"""Help messages for field extract command."""

from ....utils.colors import Colors


def print_extract_help():
    """Print field extract command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Field Extract Command{Colors.RESET}

Extract nodal data from binary PLT files to CSV (Tecplot-free; pure numpy).

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow field extract <case_dir> [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}case_dir{Colors.RESET}              Path to case directory containing binary/ folder

{Colors.BOLD}REQUIRED OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--variables VAR1,VAR2{Colors.RESET}  Comma-separated list of variables to extract
                             (e.g., Y, X,Y,Z, U,V,W)
    {Colors.YELLOW}--zone ZONE{Colors.RESET}            Zone name to extract from (e.g., FIELD, BODY)

{Colors.BOLD}TIMESTEP SELECTION (one of):{Colors.RESET}
    {Colors.YELLOW}--timestep STEP{Colors.RESET}        A single timestep (e.g., 1000)
    {Colors.YELLOW}--t1 STEP{Colors.RESET}              A single step (alone), or the start of a range
    {Colors.YELLOW}--t2 STEP{Colors.RESET}              End of a range; --t1..--t2 extracts every PLT in
                             that range into ONE file with a 'timestep' column/array
    {Colors.YELLOW}--freq N{Colors.RESET}               With --t1/--t2: keep only steps that are multiples of N
    {Colors.DIM}Setting the t1/t2/freq context (use t1:.. t2:.. freq:..) supplies these automatically.{Colors.RESET}

    {Colors.YELLOW}--output NAME{Colors.RESET}          (required) Output; format from the extension:
                             .csv      tabular point values (range -> 'timestep' column)
                             .vtu/.vtk a trimmed MESH with only the selected vars
                                       (cells kept -> contourable in ParaView; one step)
                             .pvd      time series: one <stem>_<step>.vtu per step
                                       + the .pvd collection (for a --t1/--t2 range)
                             {Colors.DIM}A bare NAME (no extension) makes a directory NAME/ holding the
                             outputs (NAME/NAME.pvd + per-step .vtu for a range, else
                             NAME/NAME.vtu). Relative paths go under the case directory.
                             Alias: --output-file{Colors.RESET}

{Colors.BOLD}OPTIONAL:{Colors.RESET}
    {Colors.YELLOW}--verbose, -v{Colors.RESET}          Show detailed extraction progress
    {Colors.YELLOW}--help, -h{Colors.RESET}             Show this help message

{Colors.BOLD}SUBDOMAIN EXTRACTION:{Colors.RESET}
    Extract data only from a specific spatial region using coordinate bounds.
    Supports 2D (X,Y) and 3D (X,Y,Z) filtering.

    {Colors.YELLOW}--xmin VALUE{Colors.RESET}           Minimum X coordinate
    {Colors.YELLOW}--xmax VALUE{Colors.RESET}           Maximum X coordinate
    {Colors.YELLOW}--ymin VALUE{Colors.RESET}           Minimum Y coordinate
    {Colors.YELLOW}--ymax VALUE{Colors.RESET}           Maximum Y coordinate
    {Colors.YELLOW}--zmin VALUE{Colors.RESET}           Minimum Z coordinate (for 3D)
    {Colors.YELLOW}--zmax VALUE{Colors.RESET}           Maximum Z coordinate (for 3D)

    Note: Coordinate variables (X,Y,Z) are only included in output if
          explicitly specified in --variables flag.

{Colors.BOLD}EXAMPLES:{Colors.RESET}  ({Colors.DIM}--output is required{Colors.RESET})

  {Colors.BOLD}Single variable to CSV:{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD --output y.csv

  {Colors.BOLD}Single timestep to a contourable mesh (.vtu):{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables U,QCriterion --zone FIELD --output snap.vtu

  {Colors.BOLD}Range to a CSV table (one file, 'timestep' column):{Colors.RESET}
    flexflow field extract CS4SG1U1 --t1 1000 --t2 5000 --variables U,V --zone FIELD --output range.csv

  {Colors.BOLD}Range to a ParaView time series of meshes (.pvd):{Colors.RESET}
    flexflow field extract CS4SG1U1 --t1 1000 --t2 5000 --freq 1000 --variables U,QCriterion \\
      --zone FIELD --output wake.pvd     # -> wake_1000.vtu, wake_2000.vtu, ... + wake.pvd

  {Colors.BOLD}3D subdomain box:{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables U,V --zone FIELD --output box.csv \\
      --xmin -1.0 --xmax 1.0 --ymin -2.0 --ymax 2.0 --zmin -3.0 --zmax 3.0

{Colors.BOLD}WORKFLOW:{Colors.RESET}

  1. Discover variables and zones:
     {Colors.YELLOW}flexflow field info CS4SG1U1 --variables --zones{Colors.RESET}

  2. Optionally set context once, then extract without repeating flags:
     {Colors.YELLOW}use zone:FIELD var:U,V t1:1000 t2:5000{Colors.RESET}
     {Colors.YELLOW}flexflow field extract CS4SG1U1 --output range.csv{Colors.RESET}

{Colors.BOLD}NOTES:{Colors.RESET}

  - No Tecplot license or pytecplot needed; reads the .plt binary directly
  - Works on Python 3.13+
  - Extracts nodal (point) data; subdomain filtering is by node coordinates
  - Output CSV header is the comma-separated variable names
  - Coordinate variables (X,Y,Z) are available but only written if requested
    in --variables

""")
