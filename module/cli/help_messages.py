"""Help messages for FlexFlow CLI."""

from module.utils.colors import Colors
from module.commands.info_cmd.help_messages import print_info_help, print_info_examples
from module.commands.plot_cmd.help_messages import print_plot_help, print_plot_examples
from module.commands.compare_cmd.help_messages import print_compare_help, print_compare_examples
from module.commands.template_cmd.help_messages import print_template_help, print_template_examples

def print_main_help():
    """Print main help message."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow - Analysis and Visualization Tool{Colors.RESET}

{Colors.BOLD}USAGE:{Colors.RESET}
    {Colors.GREEN}flexflow{Colors.RESET} {Colors.YELLOW}<command>{Colors.RESET} [options]

{Colors.BOLD}COMMANDS:{Colors.RESET}
    {Colors.CYAN}info{Colors.RESET}        Display case information
    {Colors.CYAN}new{Colors.RESET}         Create a new case directory
    {Colors.CYAN}preview{Colors.RESET}     Preview displacement data in table format
    {Colors.CYAN}statistics{Colors.RESET}  Show statistical analysis of data
    {Colors.CYAN}plot{Colors.RESET}        Plot displacement or force data
    {Colors.CYAN}compare{Colors.RESET}     Compare multiple cases
    {Colors.CYAN}template{Colors.RESET}    Generate template YAML files
    {Colors.CYAN}docs{Colors.RESET}        View documentation

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--install{Colors.RESET}           Install FlexFlow system-wide (includes MS fonts & completion)
    {Colors.YELLOW}--uninstall{Colors.RESET}         Remove FlexFlow from system
    {Colors.YELLOW}--update{Colors.RESET}            Update FlexFlow installation
    {Colors.YELLOW}--completion{Colors.RESET} <shell> Generate completion script (bash|zsh|fish)
    {Colors.YELLOW}--examples{Colors.RESET}          Show usage examples
    {Colors.YELLOW}--help, -h{Colors.RESET}          Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    flexflow info CS4SG1U1
    flexflow new myCase --problem-name test
    flexflow preview CS4SG1U1 --node 24
    flexflow statistics CS4SG1U1 --node 24
    flexflow plot CS4SG1U1 --node 100 --data-type displacement
    flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --data-type displacement

{Colors.BOLD}TAB COMPLETION:{Colors.RESET}
    Press TAB to complete commands, options, and values:
    flexflow <TAB>                      # Show all commands
    flexflow plot --<TAB>               # Show all plot options
    flexflow plot --data-type <TAB>    # Show: displacement force moment pressure

For more help on a specific command:
    flexflow {Colors.YELLOW}<command>{Colors.RESET} --help
""")
