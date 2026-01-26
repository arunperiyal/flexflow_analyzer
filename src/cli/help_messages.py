"""Help messages for FlexFlow CLI."""

from src.utils.colors import Colors

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
  
  {Colors.GREEN}Run SLURM simulation:{Colors.RESET}
    flexflow case run CS4SG1U1
    flexflow case run CS4SG1U1 --no-monitor

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

{Colors.BOLD}{Colors.CYAN}4. Templates{Colors.RESET} - {Colors.YELLOW}flexflow template{Colors.RESET}

  {Colors.GREEN}Plot templates:{Colors.RESET}
    flexflow template plot single my_plot.yaml
    flexflow template plot multi comparison.yaml

  {Colors.GREEN}Case templates:{Colors.RESET}
    flexflow template case single my_case.yaml
    flexflow template case multi batch_cases.yaml

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
  1. Generate template:        flexflow template plot multi batch.yaml
  2. Edit configuration:       vi batch.yaml
  3. Run batch plot:           flexflow compare --input-file batch.yaml

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
                 {Colors.DIM}run{Colors.RESET}      - Submit and monitor SLURM jobs
    
    {Colors.CYAN}data{Colors.RESET}        Work with time-series data  
                 {Colors.DIM}show{Colors.RESET}     - Preview data in table format
                 {Colors.DIM}stats{Colors.RESET}    - Statistical analysis
    
    {Colors.CYAN}field{Colors.RESET}       Work with Tecplot PLT files
                 {Colors.DIM}info{Colors.RESET}     - Show PLT file information
                 {Colors.DIM}extract{Colors.RESET}  - Extract data to CSV
    
    {Colors.CYAN}template{Colors.RESET}    Generate YAML configuration templates
                 {Colors.DIM}plot{Colors.RESET}     - Plot configuration templates
                 {Colors.DIM}case{Colors.RESET}     - Case creation templates

{Colors.BOLD}FILE INSPECTION:{Colors.RESET}
    {Colors.CYAN}check{Colors.RESET}       Inspect data files (OTHD, OISD)

{Colors.BOLD}VISUALIZATION COMMANDS:{Colors.RESET}
    {Colors.CYAN}plot{Colors.RESET}        Plot displacement or force data
    {Colors.CYAN}compare{Colors.RESET}     Compare multiple cases

{Colors.BOLD}UTILITY COMMANDS:{Colors.RESET}
    {Colors.CYAN}agent{Colors.RESET}       AI-powered assistant for FlexFlow
    {Colors.CYAN}docs{Colors.RESET}        View documentation

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--completion{Colors.RESET} <shell> Generate completion script (bash|zsh|fish)
    {Colors.YELLOW}--examples{Colors.RESET}          Show comprehensive usage examples
    {Colors.YELLOW}--version, -v{Colors.RESET}       Show version information
    {Colors.YELLOW}--help, -h{Colors.RESET}          Show this help message

{Colors.BOLD}INSTALLATION:{Colors.RESET}
    To install FlexFlow with conda environment and all dependencies:
    {Colors.YELLOW}./install.sh{Colors.RESET}              Install FlexFlow (creates conda env, sets up aliases)
    {Colors.YELLOW}./install.sh --uninstall{Colors.RESET}  Remove FlexFlow installation

{Colors.BOLD}TAB COMPLETION:{Colors.RESET}
    Press TAB to complete commands, subcommands, options, and values:
    flexflow <TAB>                   # Show all commands
    flexflow case <TAB>              # Show: show, create, run
    flexflow data <TAB>              # Show: show, stats
    flexflow plot --data-type <TAB>  # Show: displacement force moment pressure

{Colors.BOLD}GETTING STARTED:{Colors.RESET}
    1. View case information:    flexflow case show CS4SG1U1
    2. Check data files:         flexflow check riser.othd
    3. Preview data:             flexflow data show CS4SG1U1 --node 24
    4. Create plots:             flexflow plot CS4SG1U1 --node 100
    5. Compare cases:            flexflow compare CS4SG1U1 CS4SG2U1

For more help on a specific command:
    flexflow {Colors.YELLOW}<command>{Colors.RESET} --help
    flexflow {Colors.YELLOW}<command> <subcommand>{Colors.RESET} --help
    flexflow {Colors.YELLOW}--examples{Colors.RESET}              # Show comprehensive examples
""")
