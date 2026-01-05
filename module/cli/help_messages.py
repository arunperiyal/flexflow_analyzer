"""Help messages for FlexFlow CLI."""

from module.utils.colors import Colors
from module.commands.info_cmd.help_messages import print_info_help, print_info_examples
from module.commands.plot_cmd.help_messages import print_plot_help, print_plot_examples
from module.commands.compare_cmd.help_messages import print_compare_help, print_compare_examples
from module.commands.template_cmd.help_messages import print_template_help, print_template_examples

def print_main_examples():
    """Print comprehensive examples for all commands."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow - Comprehensive Usage Examples{Colors.RESET}

{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}
{Colors.BOLD}DOMAIN-DRIVEN COMMANDS (Recommended){Colors.RESET}
{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}

{Colors.BOLD}{Colors.CYAN}1. Case Management{Colors.RESET} - {Colors.YELLOW}flexflow case{Colors.RESET}

  {Colors.GREEN}Display case information:{Colors.RESET}
    flexflow case show CS4SG1U1
    flexflow case show CS4SG1U1 --verbose
  
  {Colors.GREEN}Create new case:{Colors.RESET}
    flexflow case create myCase --problem-name test --np 64
    flexflow case create myCase --ref-case refCase --problem-name riser

{Colors.BOLD}{Colors.CYAN}2. Data Operations{Colors.RESET} - {Colors.YELLOW}flexflow data{Colors.RESET}

  {Colors.GREEN}Preview time-series data:{Colors.RESET}
    flexflow data show CS4SG1U1 --node 24
    flexflow data show CS4SG1U1 --node 24 --component y
    flexflow data show CS4SG1U1 --node 24 --start-step 100 --end-step 200
  
  {Colors.GREEN}Statistical analysis:{Colors.RESET}
    flexflow data stats CS4SG1U1 --node 100
    flexflow data stats CS4SG1U1 --node 100 --component x,y,z

{Colors.BOLD}{Colors.CYAN}3. Field Data{Colors.RESET} - {Colors.YELLOW}flexflow field{Colors.RESET}

  {Colors.GREEN}PLT file information:{Colors.RESET}
    flexflow field info CS4SG1U1
    flexflow field info CS4SG1U1 --variables --zones
  
  {Colors.GREEN}Extract to CSV:{Colors.RESET}
    flexflow field extract CS4SG1U1 --timestep 1000 --variables X,Y,U
    flexflow field extract CS4SG1U1 --timestep 1000 --variables X,Y,Z --zone FIELD --output data.csv

{Colors.BOLD}{Colors.CYAN}4. Configuration{Colors.RESET} - {Colors.YELLOW}flexflow config{Colors.RESET}

  {Colors.GREEN}Generate templates:{Colors.RESET}
    flexflow config template single plot_config.yaml
    flexflow config template multi compare_config.yaml
    flexflow config template fft fft_config.yaml

{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}
{Colors.BOLD}VISUALIZATION COMMANDS{Colors.RESET}
{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}

{Colors.BOLD}{Colors.CYAN}5. Plotting{Colors.RESET} - {Colors.YELLOW}flexflow plot{Colors.RESET}

  {Colors.GREEN}Time-domain plots:{Colors.RESET}
    flexflow plot CS4SG1U1 --node 100 --data-type displacement --component y
    flexflow plot CS4SG1U1 --node 100 --data-type force --plot-type time
  
  {Colors.GREEN}Frequency analysis (FFT):{Colors.RESET}
    flexflow plot CS4SG1U1 --node 100 --plot-type fft --component y
  
  {Colors.GREEN}2D/3D trajectories:{Colors.RESET}
    flexflow plot CS4SG1U1 --node 100 --plot-type traj2d --component x,y
    flexflow plot CS4SG1U1 --node 100 --plot-type traj3d --component x,y,z
  
  {Colors.GREEN}Save to file (server mode):{Colors.RESET}
    flexflow plot CS4SG1U1 --node 100 --component y --output plot.png
    flexflow plot CS4SG1U1 --node 100 --component y --output plot.pdf

{Colors.BOLD}{Colors.CYAN}6. Comparison{Colors.RESET} - {Colors.YELLOW}flexflow compare{Colors.RESET}

  {Colors.GREEN}Compare cases:{Colors.RESET}
    flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --data-type displacement
    flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --component y --subplot
  
  {Colors.GREEN}Separate plots:{Colors.RESET}
    flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --separate --output-prefix case_

{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}
{Colors.BOLD}ADVANCED WORKFLOWS{Colors.RESET}
{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}

{Colors.BOLD}{Colors.CYAN}Workflow 1: Quick Case Analysis{Colors.RESET}
  1. Check case info:          flexflow case show CS4SG1U1
  2. Preview data:             flexflow data show CS4SG1U1 --node 24
  3. Statistical analysis:     flexflow data stats CS4SG1U1 --node 24
  4. Create plots:             flexflow plot CS4SG1U1 --node 24 --component y

{Colors.BOLD}{Colors.CYAN}Workflow 2: Multi-Case Study{Colors.RESET}
  1. Check both cases:         flexflow case show CS4SG1U1
                               flexflow case show CS4SG2U1
  2. Compare on same plot:     flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --component y
  3. Separate comparison:      flexflow compare CS4SG1U1 CS4SG2U1 --node 100 --separate

{Colors.BOLD}{Colors.CYAN}Workflow 3: Field Data Analysis{Colors.RESET}
  1. Check PLT files:          flexflow field info CS4SG1U1 --variables --zones
  2. Extract specific data:    flexflow field extract CS4SG1U1 --timestep 1000 --variables U,V,W
  3. Process with other tools: Use extracted CSV with pandas, Excel, etc.

{Colors.BOLD}{Colors.CYAN}Workflow 4: Batch Processing with YAML{Colors.RESET}
  1. Generate template:        flexflow config template multi batch.yaml
  2. Edit configuration:       vi batch.yaml
  3. Run batch plot:           flexflow plot --input-file batch.yaml

{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}
{Colors.BOLD}LEGACY COMMANDS (Backward Compatible){Colors.RESET}
{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}

{Colors.DIM}Old commands still work for backward compatibility:{Colors.RESET}

  flexflow info CS4SG1U1              {Colors.DIM}→ Use:{Colors.RESET} flexflow case show CS4SG1U1
  flexflow new myCase                 {Colors.DIM}→ Use:{Colors.RESET} flexflow case create myCase
  flexflow preview CS4 --node 24      {Colors.DIM}→ Use:{Colors.RESET} flexflow data show CS4 --node 24
  flexflow statistics CS4 --node 24   {Colors.DIM}→ Use:{Colors.RESET} flexflow data stats CS4 --node 24
  flexflow tecplot info CS4           {Colors.DIM}→ Use:{Colors.RESET} flexflow field info CS4
  flexflow tecplot extract CS4        {Colors.DIM}→ Use:{Colors.RESET} flexflow field extract CS4
  flexflow template single out.yaml   {Colors.DIM}→ Use:{Colors.RESET} flexflow config template single out.yaml

{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}

{Colors.BOLD}For command-specific examples:{Colors.RESET}
  flexflow {Colors.YELLOW}<command>{Colors.RESET} --examples
  flexflow {Colors.YELLOW}<command> <subcommand>{Colors.RESET} --examples

{Colors.BOLD}For detailed help:{Colors.RESET}
  flexflow --help
  flexflow {Colors.YELLOW}<command>{Colors.RESET} --help
""")

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
    {Colors.YELLOW}--examples{Colors.RESET}          Show comprehensive usage examples
    {Colors.YELLOW}--help, -h{Colors.RESET}          Show this help message

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
    flexflow {Colors.YELLOW}--examples{Colors.RESET}              # Show comprehensive examples
""")
