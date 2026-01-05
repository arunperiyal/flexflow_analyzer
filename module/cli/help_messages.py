"""Help messages for FlexFlow CLI."""

from module.utils.colors import Colors
from module.commands.info_cmd.help_messages import print_info_help, print_info_examples
from module.commands.plot_cmd.help_messages import print_plot_help, print_plot_examples
from module.commands.compare_cmd.help_messages import print_compare_help, print_compare_examples
from module.commands.template_cmd.help_messages import print_template_help, print_template_examples

def print_main_help():
    """Print main help message with domain-driven structure."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow - Analysis and Visualization Tool{Colors.RESET}

{Colors.BOLD}USAGE:{Colors.RESET}
    {Colors.GREEN}flexflow{Colors.RESET} {Colors.YELLOW}<command>{Colors.RESET} [subcommand] [options]

{Colors.BOLD}DOMAIN-DRIVEN COMMANDS:{Colors.RESET} {Colors.DIM}(Recommended){Colors.RESET}
    {Colors.CYAN}case{Colors.RESET}        Manage simulation cases
                 {Colors.DIM}show{Colors.RESET}     - Display case information
                 {Colors.DIM}create{Colors.RESET}   - Create new case directory
    
    {Colors.CYAN}data{Colors.RESET}        Work with time-series data  
                 {Colors.DIM}show{Colors.RESET}     - Preview data in table format
                 {Colors.DIM}stats{Colors.RESET}    - Statistical analysis
    
    {Colors.CYAN}field{Colors.RESET}       Work with Tecplot PLT files
                 {Colors.DIM}info{Colors.RESET}     - Show PLT file information
                 {Colors.DIM}extract{Colors.RESET}  - Extract data to CSV
    
    {Colors.CYAN}config{Colors.RESET}      Configuration management
                 {Colors.DIM}template{Colors.RESET} - Generate template YAML files

{Colors.BOLD}VISUALIZATION COMMANDS:{Colors.RESET}
    {Colors.CYAN}plot{Colors.RESET}        Plot displacement or force data
    {Colors.CYAN}compare{Colors.RESET}     Compare multiple cases

{Colors.BOLD}UTILITY COMMANDS:{Colors.RESET}
    {Colors.CYAN}docs{Colors.RESET}        View documentation

{Colors.BOLD}LEGACY COMMANDS:{Colors.RESET} {Colors.DIM}(Still supported for backward compatibility){Colors.RESET}
    {Colors.DIM}info, new, preview, statistics, tecplot, template{Colors.RESET}

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--install{Colors.RESET}           Install FlexFlow system-wide (includes MS fonts & completion)
    {Colors.YELLOW}--uninstall{Colors.RESET}         Remove FlexFlow from system
    {Colors.YELLOW}--update{Colors.RESET}            Update FlexFlow installation
    {Colors.YELLOW}--completion{Colors.RESET} <shell> Generate completion script (bash|zsh|fish)
    {Colors.YELLOW}--examples{Colors.RESET}          Show usage examples
    {Colors.YELLOW}--help, -h{Colors.RESET}          Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET} {Colors.DIM}(New Domain-Driven Style){Colors.RESET}
    flexflow case show CS4SG1U1
    flexflow case create myCase --problem-name test
    flexflow data show CS4SG1U1 --node 24
    flexflow data stats CS4SG1U1 --node 100
    flexflow field info CS4SG1U1
    flexflow plot CS4SG1U1 --node 100 --data-type displacement
    flexflow compare CS4SG1U1 CS4SG2U1 --node 100

{Colors.BOLD}TAB COMPLETION:{Colors.RESET}
    Press TAB to complete commands, subcommands, options, and values:
    flexflow <TAB>                   # Show all commands
    flexflow case <TAB>              # Show: show, create
    flexflow data <TAB>              # Show: show, stats
    flexflow plot --data-type <TAB>  # Show: displacement force moment pressure

{Colors.BOLD}GETTING STARTED:{Colors.RESET}
    1. View case information:    flexflow case show CS4SG1U1
    2. Preview data:             flexflow data show CS4SG1U1 --node 24
    3. Create plots:             flexflow plot CS4SG1U1 --node 100
    4. Compare cases:            flexflow compare CS4SG1U1 CS4SG2U1

For more help on a specific command:
    flexflow {Colors.YELLOW}<command>{Colors.RESET} --help
    flexflow {Colors.YELLOW}<command> <subcommand>{Colors.RESET} --help
""")
