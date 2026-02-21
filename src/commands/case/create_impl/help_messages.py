"""
Help messages for new command
"""

from ....utils.colors import Colors


def print_new_help():
    """Print help message for new command"""
    help_text = f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Case Create Command{Colors.RESET}

Create a new case directory from a reference case template.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case create {Colors.YELLOW}<case_name>{Colors.RESET} [OPTIONS]
    flexflow case create {Colors.YELLOW}--from-config{Colors.RESET} <yaml_file>

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}<case_name>{Colors.RESET}              Name of the new case directory to create

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--ref-case{Colors.RESET} {Colors.CYAN}<path>{Colors.RESET}        Path to reference case directory
    {Colors.YELLOW}--problem-name{Colors.RESET} {Colors.CYAN}<name>{Colors.RESET}    Override problem name in simflow.config
    {Colors.YELLOW}--np{Colors.RESET} {Colors.CYAN}<number>{Colors.RESET}            Number of processors (default: 36)
    {Colors.YELLOW}--freq{Colors.RESET} {Colors.CYAN}<number>{Colors.RESET}          Output frequency (default: 50)
    {Colors.YELLOW}--from-config{Colors.RESET} {Colors.CYAN}<file>{Colors.RESET}    Load configuration from YAML file
    {Colors.YELLOW}--force{Colors.RESET}                  Overwrite existing directory if it exists
    {Colors.YELLOW}--dry-run{Colors.RESET}                Show what would be created without creating
    {Colors.YELLOW}-v, --verbose{Colors.RESET}            Enable verbose output
    {Colors.YELLOW}-h, --help{Colors.RESET}               Show this help message
    {Colors.YELLOW}--examples{Colors.RESET}               Show usage examples

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Creates a new case directory by copying files from a reference case template.
    The reference template should contain all necessary simulation files and scripts.
    
    {Colors.DIM}Required files in reference directory:{Colors.RESET}
    - simflow.config          {Colors.DIM}# Simulation configuration{Colors.RESET}
    - {Colors.CYAN}<problem>{Colors.RESET}.geo           {Colors.DIM}# Gmsh geometry file{Colors.RESET}
    - {Colors.CYAN}<problem>{Colors.RESET}.def           {Colors.DIM}# FlexFlow definition file{Colors.RESET}
    - preFlex.sh              {Colors.DIM}# Pre-processing script{Colors.RESET}
    - mainFlex.sh             {Colors.DIM}# Main simulation script{Colors.RESET}
    - postFlex.sh             {Colors.DIM}# Post-processing script{Colors.RESET}
    
    {Colors.DIM}Optional files that will be copied if present:{Colors.RESET}
    - config.sh               {Colors.DIM}# Script configuration{Colors.RESET}
    - common.sh               {Colors.DIM}# Reusable functions{Colors.RESET}
    - case_config.yaml        {Colors.DIM}# FlexFlow case config{Colors.RESET}
    
    {Colors.BOLD}The command automatically updates:{Colors.RESET}
    - SLURM job names to {Colors.CYAN}<casename>_<pre|main|post>{Colors.RESET}
    - Processor count ({Colors.CYAN}np{Colors.RESET}, {Colors.CYAN}nsg{Colors.RESET}) in simflow.config
    - Output frequency ({Colors.CYAN}outFreq{Colors.RESET}) in simflow.config
    - {Colors.CYAN}#SBATCH -n{Colors.RESET} in mainFlex.sh to match --np value
    - Variable values in config.sh (PROBLEM, OUTFREQ, etc.)
    
    {Colors.BOLD}YAML Configuration Mode:{Colors.RESET}
    Use {Colors.YELLOW}--from-config{Colors.RESET} to load parameters from YAML:
    - Supports single case or batch case generation
    - Geometry parameters: {Colors.CYAN}#parameter_name{Colors.RESET} in .geo files
    - Definition parameters: under {Colors.CYAN}'def'{Colors.RESET} section in YAML
    - Command-line flags override YAML values
    
    {Colors.BOLD}If --problem-name is specified:{Colors.RESET}
    - Updates problem name in simflow.config
    - Renames .geo and .def files to match new problem name

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    {Colors.DIM}# Create from standard template{Colors.RESET}
    {Colors.GREEN}flexflow case create myCase --ref-case examples/standard{Colors.RESET}

    {Colors.DIM}# Create with custom parameters{Colors.RESET}
    {Colors.GREEN}flexflow case create CS1 --ref-case examples/standard --problem-name riser --np 80 --freq 100{Colors.RESET}

    {Colors.DIM}# Create from YAML configuration{Colors.RESET}
    {Colors.GREEN}flexflow case create --from-config case_config.yaml{Colors.RESET}

    {Colors.DIM}# Batch generation from YAML{Colors.RESET}
    {Colors.GREEN}flexflow case create --from-config batch_cases.yaml --verbose{Colors.RESET}

    {Colors.DIM}# Preview without creating{Colors.RESET}
    {Colors.GREEN}flexflow case create myCase --ref-case examples/standard --dry-run{Colors.RESET}

    {Colors.DIM}# Force overwrite existing case{Colors.RESET}
    {Colors.GREEN}flexflow case create myCase --ref-case examples/standard --force{Colors.RESET}

{Colors.BOLD}SEE ALSO:{Colors.RESET}
    flexflow case create --examples    {Colors.DIM}# More detailed examples{Colors.RESET}
    examples/standard/README.md        {Colors.DIM}# Template documentation{Colors.RESET}
"""
    print(help_text)


def print_new_examples():
    """Print examples for new command"""
    examples_text = f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow New - Examples{Colors.RESET}

{Colors.BOLD}1. Basic Usage:{Colors.RESET}
    {Colors.GREEN}flexflow new myCase{Colors.RESET}
    {Colors.DIM}Creates a new case directory 'myCase' using the default reference directory.{Colors.RESET}

{Colors.BOLD}2. Using Custom Reference Directory:{Colors.RESET}
    {Colors.GREEN}flexflow new CS4SG3U1 --ref-case /path/to/my_reference{Colors.RESET}
    {Colors.DIM}Creates 'CS4SG3U1' using files from custom reference directory.{Colors.RESET}

{Colors.BOLD}3. Override Problem Name:{Colors.RESET}
    {Colors.GREEN}flexflow new myCase --problem-name cylinder{Colors.RESET}
    {Colors.DIM}Creates 'myCase' and updates the problem name to 'cylinder'.{Colors.RESET}
    {Colors.DIM}Files will be renamed: cylinder.geo, cylinder.def{Colors.RESET}

{Colors.BOLD}4. Force Overwrite:{Colors.RESET}
    {Colors.GREEN}flexflow new myCase --force{Colors.RESET}
    {Colors.DIM}Overwrites 'myCase' if it already exists.{Colors.RESET}

{Colors.BOLD}5. YAML Configuration - Single Case:{Colors.RESET}
    {Colors.GREEN}flexflow new --from-config case_config.yaml{Colors.RESET}
    {Colors.DIM}Creates a case from YAML configuration with parametric values.{Colors.RESET}
    {Colors.DIM}Example YAML:{Colors.RESET}
      {Colors.CYAN}case_name:{Colors.RESET} myCase
      {Colors.CYAN}processors:{Colors.RESET} 80
      {Colors.CYAN}output_frequency:{Colors.RESET} 75
      {Colors.CYAN}geo:{Colors.RESET}
        {Colors.CYAN}groove_depth:{Colors.RESET} 0.06
        {Colors.CYAN}groove_width:{Colors.RESET} 0.12
      {Colors.CYAN}def:{Colors.RESET}
        {Colors.CYAN}Ur:{Colors.RESET} 5.8
      {Colors.CYAN}time:{Colors.RESET}
        {Colors.CYAN}maxsteps:{Colors.RESET} 16000
        {Colors.CYAN}dt:{Colors.RESET} 0.05

{Colors.BOLD}6. YAML Configuration - Batch Mode:{Colors.RESET}
    {Colors.GREEN}flexflow new --from-config batch_config.yaml --verbose{Colors.RESET}
    {Colors.DIM}Creates multiple cases from a single YAML file.{Colors.RESET}
    {Colors.DIM}Example YAML with 'cases' section generates multiple cases.{Colors.RESET}

{Colors.BOLD}7. Override YAML Values with Command-Line:{Colors.RESET}
    {Colors.GREEN}flexflow new --from-config case_config.yaml --np 120 --freq 100{Colors.RESET}
    {Colors.DIM}Loads config from YAML but overrides np and freq values.{Colors.RESET}

{Colors.BOLD}8. Complete Example:{Colors.RESET}
    {Colors.GREEN}flexflow new experiment_1 --ref-case ./templates/base --problem-name exp1 --np 80 --freq 75 --verbose{Colors.RESET}
    {Colors.DIM}Creates 'experiment_1' with problem name 'exp1', 80 processors, frequency 75, with verbose output.{Colors.RESET}

{Colors.BOLD}6. Multiple Cases with Different Configurations:{Colors.RESET}
    {Colors.GREEN}flexflow new case1 --problem-name riser --np 120 --freq 100{Colors.RESET}
    {Colors.GREEN}flexflow new case2 --problem-name pipe --np 64 --freq 50{Colors.RESET}
    {Colors.GREEN}flexflow new case3 --problem-name cylinder --np 36 --freq 25{Colors.RESET}

{Colors.BOLD}9. Parametric Study with Batch YAML:{Colors.RESET}
    {Colors.DIM}Create batch_config.yaml with global defaults and per-case overrides:{Colors.RESET}
      {Colors.CYAN}problem_name:{Colors.RESET} riser
      {Colors.CYAN}processors:{Colors.RESET} 120
      {Colors.CYAN}output_frequency:{Colors.RESET} 50
      {Colors.CYAN}time:{Colors.RESET}
        {Colors.CYAN}maxsteps:{Colors.RESET} 16000
        {Colors.CYAN}dt:{Colors.RESET} 0.05
      {Colors.CYAN}cases:{Colors.RESET}
        - {Colors.CYAN}name:{Colors.RESET} Case005
          {Colors.CYAN}processors:{Colors.RESET} 60
          {Colors.CYAN}def:{Colors.RESET}
            {Colors.CYAN}Ur:{Colors.RESET} 4.0
          {Colors.CYAN}time:{Colors.RESET}
            {Colors.CYAN}maxsteps:{Colors.RESET} 20000
        - {Colors.CYAN}name:{Colors.RESET} Case010
          {Colors.CYAN}def:{Colors.RESET}
            {Colors.CYAN}Ur:{Colors.RESET} 8.0
    {Colors.GREEN}flexflow new --from-config batch_config.yaml{Colors.RESET}
    {Colors.DIM}Case-specific values override global defaults. Case010 inherits all globals.{Colors.RESET}
"""
    print(examples_text)
