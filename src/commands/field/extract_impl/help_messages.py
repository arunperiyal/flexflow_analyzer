"""Help messages for field extract command."""

from ....utils.colors import Colors


def print_extract_help():
    """Print field extract command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Field Extract Command{Colors.RESET}

Extract data from Tecplot PLT binary files to CSV format using pytecplot.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow field extract <case_dir> [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}case_dir{Colors.RESET}              Path to case directory containing binary/ folder

{Colors.BOLD}REQUIRED OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--variables VAR1,VAR2{Colors.RESET}  Comma-separated list of variables to extract
                             (e.g., Y, X,Y,Z, U,V,W)
    {Colors.YELLOW}--zone ZONE{Colors.RESET}            Zone name to extract from (e.g., FIELD, BODY)
    {Colors.YELLOW}--timestep STEP{Colors.RESET}        Timestep number to extract (e.g., 1000, 2000)

{Colors.BOLD}OPTIONAL:{Colors.RESET}
    {Colors.YELLOW}--output-file FILE{Colors.RESET}     Output CSV file path
                             (default: case/extracted_STEP.csv)
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

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}Extract single variable:{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD

  {Colors.BOLD}Extract multiple variables:{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables X,Y,Z,U,V,W --zone FIELD

  {Colors.BOLD}Extract with custom output file:{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD --output-file results.csv

  {Colors.BOLD}Extract 2D subdomain (X and Y range):{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables U,V \\
      --zone FIELD --xmin -1.0 --xmax 1.0 --ymin -2.0 --ymax 2.0

  {Colors.BOLD}Extract 3D subdomain:{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables X,Y,Z,U,V,W \\
      --zone FIELD --xmin -1.0 --xmax 1.0 --ymin -2.0 --ymax 2.0 --zmin -3.0 --zmax 3.0

  {Colors.BOLD}Extract subdomain with single axis constraint:{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables Y,U \\
      --zone FIELD --xmin 0.0 --xmax 0.5

  {Colors.BOLD}Extract with verbose output:{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD -v

{Colors.BOLD}WORKFLOW:{Colors.RESET}

  1. First, use info command to discover available variables and zones:
     {Colors.YELLOW}flexflow field info CS4SG1U1 --variables --zones{Colors.RESET}

  2. Then extract the desired data:
     {Colors.YELLOW}flexflow field extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD{Colors.RESET}

  3. For subdomain extraction, specify coordinate bounds:
     {Colors.YELLOW}flexflow field extract CS4SG1U1 --timestep 1000 --variables U,V \\
       --zone FIELD --xmin -1 --xmax 1 --ymin -1 --ymax 1{Colors.RESET}

{Colors.BOLD}NOTES:{Colors.RESET}

  - Requires pytecplot library to be installed
  - Falls back to macro-based extraction if pytecplot is not available
  - Subdomain filtering requires pytecplot (not available in macro mode)
  - Output CSV includes metadata comments at the beginning
  - If no points fall within subdomain, an error is reported
  - Coordinate variables are automatically loaded for filtering but only
    included in output if explicitly requested in --variables

""")
