"""Help messages for field info command."""

from ....utils.colors import Colors


def print_info_help():
    """Print field info command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Field Info Command{Colors.RESET}

Show detailed information about PLT files and perform consistency checks.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow field info <case_dir> [options]

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
    flexflow field info CS4SG1U1

  {Colors.BOLD}Show only variables:{Colors.RESET}
    flexflow field info CS4SG1U1 --variables

  {Colors.BOLD}Show consistency checks:{Colors.RESET}
    flexflow field info CS4SG1U1 --checks

  {Colors.BOLD}Combine filters:{Colors.RESET}
    flexflow field info CS4SG1U1 --variables --checks --zones

  {Colors.BOLD}Show detailed statistics:{Colors.RESET}
    flexflow field info CS4SG1U1 --stats --detailed

{Colors.BOLD}CONSISTENCY CHECKS:{Colors.RESET}

  • Zero-size file detection
  • Naming convention validation
  • Sequential timestep verification
  • File corruption detection (basic header check)
  • Variable consistency across files

""")
