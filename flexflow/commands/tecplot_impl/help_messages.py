"""
Help messages for tecplot command
"""

from ...utils.colors import Colors


TECPLOT_HELP = (f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Tecplot Command{Colors.RESET}

Work with Tecplot PLT binary files - view information and extract data.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow tecplot <subcommand> [options]

{Colors.BOLD}SUBCOMMANDS:{Colors.RESET}
    {Colors.YELLOW}info{Colors.RESET}      Show information about PLT files in a case
    {Colors.YELLOW}extract{Colors.RESET}   Extract data from PLT files to CSV format

{Colors.BOLD}GLOBAL OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--help, -h{Colors.RESET}           Show this help message
    {Colors.YELLOW}--verbose, -v{Colors.RESET}        Show detailed information
    {Colors.YELLOW}--examples{Colors.RESET}           Show usage examples

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}Show help for a subcommand:{Colors.RESET}
    flexflow tecplot info --help
    flexflow tecplot extract --help

  {Colors.BOLD}Show PLT file information:{Colors.RESET}
    flexflow tecplot info CS4SG1U1
    flexflow tecplot info CS4SG1U1 --variables --zones
    
  {Colors.BOLD}Extract data from PLT files:{Colors.RESET}
    flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD
    flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables X,Y,Z --zone FIELD --output-file data.csv

{Colors.BOLD}WORKFLOW:{Colors.RESET}

  1. Check available PLT files and variables:
     {Colors.YELLOW}flexflow tecplot info CS4SG1U1 --variables --zones{Colors.RESET}
      
  2. Extract data using pytecplot:
     {Colors.YELLOW}flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD{Colors.RESET}

{Colors.BOLD}NOTES:{Colors.RESET}

  - PLT files are Tecplot binary format containing full 3D field data
  - OTHD files contain time series for specific nodes (used by 'plot' command)
  - Extract command uses pytecplot library to read and extract data
  - Use 'info' command to discover available zones and variables

""")


TECPLOT_INFO_HELP = (f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Tecplot Info Command{Colors.RESET}

Show detailed information about PLT files and perform consistency checks.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow tecplot info <case_dir> [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}case_dir{Colors.RESET}              Path to case directory containing binary/ folder

{Colors.BOLD}SECTION FILTERS:{Colors.RESET}
    {Colors.YELLOW}--basic{Colors.RESET}               Show only basic file information
    {Colors.YELLOW}--variables{Colors.RESET}           Show only variable information
    {Colors.YELLOW}--zones{Colors.RESET}               Show only zone information
    {Colors.YELLOW}--checks{Colors.RESET}              Show only consistency checks
    {Colors.YELLOW}--stats{Colors.RESET}               Show only data statistics
    
    Note: If no section filter is specified, all sections are shown.
          Multiple filters can be combined to show specific sections.

{Colors.BOLD}ADDITIONAL OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--detailed{Colors.RESET}            Show detailed statistics for all variables
    {Colors.YELLOW}--sample-file STEP{Colors.RESET}    Analyze specific timestep file (default: first)
    {Colors.YELLOW}--verbose, -v{Colors.RESET}         Show verbose output including errors
    {Colors.YELLOW}--help, -h{Colors.RESET}            Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}

  {Colors.BOLD}Show all information:{Colors.RESET}
    flexflow tecplot info CS4SG1U1
    
  {Colors.BOLD}Show only variables:{Colors.RESET}
    flexflow tecplot info CS4SG1U1 --variables
    
  {Colors.BOLD}Show consistency checks:{Colors.RESET}
    flexflow tecplot info CS4SG1U1 --checks
    
  {Colors.BOLD}Combine filters:{Colors.RESET}
    flexflow tecplot info CS4SG1U1 --variables --checks --zones
    
  {Colors.BOLD}Show detailed statistics:{Colors.RESET}
    flexflow tecplot info CS4SG1U1 --stats --detailed

{Colors.BOLD}CONSISTENCY CHECKS:{Colors.RESET}

  • Zero-size file detection
  • Naming convention validation
  • Sequential timestep verification
  • File corruption detection (basic header check)
  • Variable consistency across files

""")


TECPLOT_EXTRACT_HELP = (f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Tecplot Extract Command{Colors.RESET}

Extract data from Tecplot PLT binary files to CSV format using pytecplot.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow tecplot extract <case_dir> [options]

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
    flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD
    
  {Colors.BOLD}Extract multiple variables:{Colors.RESET}
    flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables X,Y,Z,U,V,W --zone FIELD
    
  {Colors.BOLD}Extract with custom output file:{Colors.RESET}
    flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD --output-file results.csv
    
  {Colors.BOLD}Extract 2D subdomain (X and Y range):{Colors.RESET}
    flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables U,V \\
      --zone FIELD --xmin -1.0 --xmax 1.0 --ymin -2.0 --ymax 2.0
    
  {Colors.BOLD}Extract 3D subdomain:{Colors.RESET}
    flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables X,Y,Z,U,V,W \\
      --zone FIELD --xmin -1.0 --xmax 1.0 --ymin -2.0 --ymax 2.0 --zmin -3.0 --zmax 3.0
    
  {Colors.BOLD}Extract subdomain with single axis constraint:{Colors.RESET}
    flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y,U \\
      --zone FIELD --xmin 0.0 --xmax 0.5
    
  {Colors.BOLD}Extract with verbose output:{Colors.RESET}
    flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD -v

{Colors.BOLD}WORKFLOW:{Colors.RESET}

  1. First, use info command to discover available variables and zones:
     {Colors.YELLOW}flexflow tecplot info CS4SG1U1 --variables --zones{Colors.RESET}
     
  2. Then extract the desired data:
     {Colors.YELLOW}flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD{Colors.RESET}
     
  3. For subdomain extraction, specify coordinate bounds:
     {Colors.YELLOW}flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables U,V \\
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


def print_tecplot_help():
    """Print tecplot help message"""
    print(TECPLOT_HELP)


def print_tecplot_info_help():
    """Print tecplot info help message"""
    print(TECPLOT_INFO_HELP)


def print_tecplot_extract_help():
    """Print tecplot extract help message"""
    print(TECPLOT_EXTRACT_HELP)


def print_tecplot_examples():
    """Print tecplot examples"""
    examples = f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Tecplot Examples{Colors.RESET}

{Colors.BOLD}INFO COMMAND:{Colors.RESET}

  {Colors.BOLD}1. View all PLT file information:{Colors.RESET}
     flexflow tecplot info CS4SG1U1

  {Colors.BOLD}2. Check only consistency:{Colors.RESET}
     flexflow tecplot info CS4SG1U1 --checks

  {Colors.BOLD}3. View variables and zones:{Colors.RESET}
     flexflow tecplot info CS4SG1U1 --variables --zones

  {Colors.BOLD}4. View statistics with details:{Colors.RESET}
     flexflow tecplot info CS4SG1U1 --stats --detailed

{Colors.BOLD}EXTRACT COMMAND:{Colors.RESET}

  {Colors.BOLD}1. Extract single variable:{Colors.RESET}
     flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD

  {Colors.BOLD}2. Extract multiple variables:{Colors.RESET}
     flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables X,Y,Z,U,V,W --zone FIELD

  {Colors.BOLD}3. Extract with custom output:{Colors.RESET}
     flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD --output-file data.csv

  {Colors.BOLD}4. Extract with verbose logging:{Colors.RESET}
     flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD -v

{Colors.BOLD}TYPICAL WORKFLOW:{Colors.RESET}

  {Colors.BOLD}Step 1: Discover what's available{Colors.RESET}
     flexflow tecplot info CS4SG1U1 --variables --zones
     
  {Colors.BOLD}Step 2: Extract the data you need{Colors.RESET}
     flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y,U,V --zone FIELD

"""
    print(examples)
