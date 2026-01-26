"""
Help messages for check command
"""

from src.utils.colors import Colors


def print_check_help():
    """Print help message for check command"""
    help_text = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║                         FlexFlow Check Command                       ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝{Colors.RESET}

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Inspect and display information about FlexFlow data files.
    Automatically detects file type by extension and shows relevant metadata.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow check <file>
    ff check <file>

{Colors.BOLD}SUPPORTED FILE TYPES:{Colors.RESET}
    {Colors.GREEN}• .othd{Colors.RESET}  - Output Time History Data (node displacements)
    {Colors.GREEN}• .oisd{Colors.RESET}  - Output Integrated Surface Data (tractions, moments)

{Colors.BOLD}OPTIONS:{Colors.RESET}
    -h, --help          Show this help message
    --examples          Show usage examples

{Colors.BOLD}DISPLAYED INFORMATION:{Colors.RESET}

    {Colors.YELLOW}For OTHD files:{Colors.RESET}
      • File size
      • Number of nodes
      • Number of time steps
      • Time range (start/end)
      • Time increment
      • Available components (X, Y, Z displacements)

    {Colors.YELLOW}For OISD files:{Colors.RESET}
      • File size
      • Number of surfaces
      • Number of time steps
      • Time range (start/end)
      • Time increment
      • Available data fields (traction, moment, area, pressure)

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    {Colors.GREEN}# Check OTHD file{Colors.RESET}
    ff check riser.othd
    
    {Colors.GREEN}# Check OISD file{Colors.RESET}
    ff check riser.oisd
    
    {Colors.GREEN}# Check file with full path{Colors.RESET}
    ff check /path/to/case/riser.othd

{Colors.BOLD}SEE ALSO:{Colors.RESET}
    ff data show      - Preview time-series data in table format
    ff data stats     - Statistical analysis of data
    ff field info     - Show Tecplot PLT file information
"""
    print(help_text)


def print_check_examples():
    """Print examples for check command"""
    examples = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║                     FlexFlow Check - Examples                        ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝{Colors.RESET}

{Colors.BOLD}BASIC USAGE:{Colors.RESET}

  {Colors.GREEN}1. Check OTHD file (displacement data):{Colors.RESET}
     $ ff check riser.othd
     
     Output shows:
     - Number of nodes
     - Time range and steps
     - File size
     - Available displacement components

  {Colors.GREEN}2. Check OISD file (surface data):{Colors.RESET}
     $ ff check riser.oisd
     
     Output shows:
     - Number of surfaces
     - Time range and steps
     - File size
     - Available data fields

{Colors.BOLD}WORKFLOW EXAMPLES:{Colors.RESET}

  {Colors.GREEN}3. Quick file inspection before analysis:{Colors.RESET}
     $ ff check case1/riser.othd
     $ ff data show case1/riser.othd --node 10

  {Colors.GREEN}4. Verify file after simulation:{Colors.RESET}
     $ ff check latest_run/riser.oisd
     
     Confirms file is readable and shows time coverage

  {Colors.GREEN}5. Compare file metadata:{Colors.RESET}
     $ ff check run1/riser.othd
     $ ff check run2/riser.othd
     
     Check if both runs have same number of nodes/timesteps

{Colors.BOLD}ERROR HANDLING:{Colors.RESET}

  {Colors.YELLOW}File not found:{Colors.RESET}
     $ ff check nonexistent.othd
     {Colors.RED}✗ Error: File not found: nonexistent.othd{Colors.RESET}

  {Colors.YELLOW}Unsupported file type:{Colors.RESET}
     $ ff check data.txt
     {Colors.RED}✗ Error: Unsupported file type: .txt{Colors.RESET}
     {Colors.YELLOW}Supported types: .othd, .oisd{Colors.RESET}

{Colors.BOLD}TIPS:{Colors.RESET}
  • Use check before running data analysis commands
  • Verify file integrity after long simulations
  • Check time coverage matches expected simulation duration
  • Confirm node count matches geometry definition

{Colors.BOLD}FUTURE SUPPORT:{Colors.RESET}
  Coming soon:
  • .plt (Tecplot) file support
  • .def (definition) file support
  • Multiple file checking
  • Directory scanning
"""
    print(examples)
