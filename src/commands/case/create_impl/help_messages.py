"""
Help messages for new command
"""

from ....utils.colors import Colors


def print_new_help():
    """Print help message for new command"""
    help_text = f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow New Command{Colors.RESET}

Create a new case directory from a reference case template.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow new {Colors.YELLOW}<case_name>{Colors.RESET} [OPTIONS]
    flexflow new {Colors.YELLOW}--from-config{Colors.RESET} <yaml_file>

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}<case_name>{Colors.RESET}              Name of the new case directory to create

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--ref-case{Colors.RESET} PATH          Path to reference case directory (default: ./refCase)
    {Colors.YELLOW}--problem-name{Colors.RESET} NAME      Override problem name in simflow.config
    {Colors.YELLOW}--np{Colors.RESET} NUM                 Number of processors (default: 36)
    {Colors.YELLOW}--freq{Colors.RESET} NUM               Output frequency (default: 50)
    {Colors.YELLOW}--from-config{Colors.RESET} FILE       Load configuration from YAML file
    {Colors.YELLOW}--force{Colors.RESET}                  Overwrite existing directory if it exists
    {Colors.YELLOW}-v, --verbose{Colors.RESET}            Enable verbose output
    {Colors.YELLOW}-h, --help{Colors.RESET}               Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Creates a new case directory by copying files from a reference case.
    
    {Colors.DIM}The reference directory must contain these mandatory files:{Colors.RESET}
    - simflow.config
    - <problem>.geo
    - <problem>.def
    - preFlex.sh
    - mainFlex.sh
    - postFlex.sh
    
    Where <problem> is the problem name specified in simflow.config.
    
    {Colors.BOLD}The command automatically:{Colors.RESET}
    - Updates SLURM job names in shell scripts to {Colors.CYAN}<casename>_<pre|main|post>{Colors.RESET}
    - Sets {Colors.CYAN}np{Colors.RESET} and {Colors.CYAN}nsg{Colors.RESET} in simflow.config (default: 36)
    - Sets {Colors.CYAN}outFreq{Colors.RESET} in simflow.config (default: 50)
    - Updates {Colors.CYAN}#SBATCH -n{Colors.RESET} in mainFlex.sh to match --np value
    - Updates {Colors.CYAN}OUTFREQ{Colors.RESET} variable in postFlex.sh to match --freq value
    - Updates {Colors.CYAN}PROBLEM{Colors.RESET} variable in postFlex.sh to match problem name
    
    {Colors.BOLD}YAML Configuration:{Colors.RESET}
    - Use {Colors.YELLOW}--from-config{Colors.RESET} to load parameters from a YAML file
    - Supports single case or batch case generation
    - Parameters in .geo files: Use {Colors.CYAN}#parameter_name{Colors.RESET} (e.g., #groove_depth)
    - Parameters in .def files: Define under {Colors.CYAN}'def'{Colors.RESET} section (e.g., Ur, Re)
    - Command-line flags override YAML values
    
    {Colors.BOLD}If --problem-name is provided, the command will also:{Colors.RESET}
    - Update the problem name in the copied simflow.config file
    - Rename the .geo and .def files to match the new problem name

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    {Colors.DIM}# Create new case using default reference directory{Colors.RESET}
    {Colors.GREEN}flexflow new myCase{Colors.RESET}

    {Colors.DIM}# Create new case with specific reference directory{Colors.RESET}
    {Colors.GREEN}flexflow new myCase --ref-case /path/to/refCase{Colors.RESET}

    {Colors.DIM}# Create new case with custom problem name{Colors.RESET}
    {Colors.GREEN}flexflow new myCase --problem-name custom_problem{Colors.RESET}

    {Colors.DIM}# Create case with custom np and frequency{Colors.RESET}
    {Colors.GREEN}flexflow new myCase --np 120 --freq 100{Colors.RESET}

    {Colors.DIM}# Complete example with all options{Colors.RESET}
    {Colors.GREEN}flexflow new myCase --problem-name cylinder --np 64 --freq 25{Colors.RESET}

    {Colors.DIM}# Create from YAML configuration file{Colors.RESET}
    {Colors.GREEN}flexflow new --from-config case_config.yaml{Colors.RESET}

    {Colors.DIM}# Create with config but override some values{Colors.RESET}
    {Colors.GREEN}flexflow new --from-config case_config.yaml --np 120 --freq 100{Colors.RESET}

    {Colors.DIM}# Batch case generation from YAML{Colors.RESET}
    {Colors.GREEN}flexflow new --from-config batch_cases.yaml --verbose{Colors.RESET}

    {Colors.DIM}# Overwrite existing directory{Colors.RESET}
    {Colors.GREEN}flexflow new myCase --force{Colors.RESET}

    {Colors.DIM}# Create with verbose output{Colors.RESET}
    {Colors.GREEN}flexflow new myCase --ref-case ./refCase --problem-name test --verbose{Colors.RESET}
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
    {Colors.DIM}Create batch_config.yaml with multiple cases having different parameters{Colors.RESET}
    {Colors.GREEN}flexflow new --from-config batch_config.yaml{Colors.RESET}
    {Colors.DIM}Automatically generates all cases with their specific parameters{Colors.RESET}
"""
    print(examples_text)
