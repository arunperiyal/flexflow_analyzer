"""
Help messages for new command
"""

from ...utils.colors import Colors


def print_new_help():
    """Print help message for new command"""
    help_text = f"""
{Colors.bold(Colors.cyan('flexflow new'))} - Create a new case directory

{Colors.bold('USAGE:')}
    flexflow new <case_name> [OPTIONS]

{Colors.bold('ARGUMENTS:')}
    <case_name>              Name of the new case directory to create

{Colors.bold('OPTIONS:')}
    --ref-case PATH          Path to reference case directory (default: ./refCase)
    --problem-name NAME      Override problem name in simflow.config
    --np NUM                 Number of processors (default: 36)
    --freq NUM               Output frequency (default: 50)
    --from-config FILE       Load configuration from YAML file
    --force                  Overwrite existing directory if it exists
    -v, --verbose            Enable verbose output
    -h, --help               Show this help message

{Colors.bold('DESCRIPTION:')}
    Creates a new case directory by copying files from a reference case.
    
    The reference directory must contain these mandatory files:
    - simflow.config
    - <problem>.geo
    - <problem>.def
    - preFlex.sh
    - mainFlex.sh
    - postFlex.sh
    
    Where <problem> is the problem name specified in simflow.config.
    
    The command automatically:
    - Updates SLURM job names in shell scripts to <casename>_<pre|main|post>
    - Sets np and nsg in simflow.config (default: 36)
    - Sets outFreq in simflow.config (default: 50)
    - Updates #SBATCH -n in mainFlex.sh to match --np value
    - Updates OUTFREQ variable in postFlex.sh to match --freq value
    - Updates PROBLEM variable in postFlex.sh to match problem name
    
    YAML Configuration:
    - Use --from-config to load parameters from a YAML file
    - Supports single case or batch case generation
    - Parameters in .geo files: Use #parameter_name (e.g., #groove_depth)
    - Parameters in .def files: Define under 'def' section (e.g., Ur, Re)
    - Command-line flags override YAML values
    
    If --problem-name is provided, the command will also:
    - Update the problem name in the copied simflow.config file
    - Rename the .geo and .def files to match the new problem name

{Colors.bold('EXAMPLES:')}
    # Create new case using default reference directory
    flexflow new myCase

    # Create new case with specific reference directory
    flexflow new myCase --ref-case /path/to/refCase

    # Create new case with custom problem name
    flexflow new myCase --problem-name custom_problem

    # Create case with custom np and frequency
    flexflow new myCase --np 120 --freq 100

    # Complete example with all options
    flexflow new myCase --problem-name cylinder --np 64 --freq 25

    # Create from YAML configuration file
    flexflow new --from-config case_config.yaml

    # Create with config but override some values
    flexflow new --from-config case_config.yaml --np 120 --freq 100

    # Batch case generation from YAML
    flexflow new --from-config batch_cases.yaml --verbose

    # Overwrite existing directory
    flexflow new myCase --force

    # Create with verbose output
    flexflow new myCase --ref-case ./refCase --problem-name test --verbose
"""
    print(help_text)


def print_new_examples():
    """Print examples for new command"""
    examples_text = f"""
{Colors.bold(Colors.cyan('flexflow new - Examples'))}

{Colors.bold('1. Basic Usage:')}
    {Colors.green('flexflow new myCase')}
    Creates a new case directory 'myCase' using the default reference directory.

{Colors.bold('2. Using Custom Reference Directory:')}
    {Colors.green('flexflow new CS4SG3U1 --ref-case /path/to/my_reference')}
    Creates 'CS4SG3U1' using files from custom reference directory.

{Colors.bold('3. Override Problem Name:')}
    {Colors.green('flexflow new myCase --problem-name cylinder')}
    Creates 'myCase' and updates the problem name to 'cylinder'.
    Files will be renamed: cylinder.geo, cylinder.def

{Colors.bold('4. Force Overwrite:')}
    {Colors.green('flexflow new myCase --force')}
    Overwrites 'myCase' if it already exists.

{Colors.bold('5. YAML Configuration - Single Case:')}
    {Colors.green('flexflow new --from-config case_config.yaml')}
    Creates a case from YAML configuration with parametric values.
    Example YAML:
      case_name: myCase
      processors: 80
      output_frequency: 75
      geo:
        groove_depth: 0.06
        groove_width: 0.12
      def:
        Ur: 5.8

{Colors.bold('6. YAML Configuration - Batch Mode:')}
    {Colors.green('flexflow new --from-config batch_config.yaml --verbose')}
    Creates multiple cases from a single YAML file.
    Example YAML with 'cases' section generates multiple cases.

{Colors.bold('7. Override YAML Values with Command-Line:')}
    {Colors.green('flexflow new --from-config case_config.yaml --np 120 --freq 100')}
    Loads config from YAML but overrides np and freq values.

{Colors.bold('8. Complete Example:')}
    {Colors.green('flexflow new experiment_1 --ref-case ./templates/base --problem-name exp1 --np 80 --freq 75 --verbose')}
    Creates 'experiment_1' with problem name 'exp1', 80 processors, frequency 75, with verbose output.

{Colors.bold('6. Multiple Cases with Different Configurations:')}
    {Colors.green('flexflow new case1 --problem-name riser --np 120 --freq 100')}
    {Colors.green('flexflow new case2 --problem-name pipe --np 64 --freq 50')}
    {Colors.green('flexflow new case3 --problem-name cylinder --np 36 --freq 25')}

{Colors.bold('9. Parametric Study with Batch YAML:')}
    Create batch_config.yaml with multiple cases having different parameters
    {Colors.green('flexflow new --from-config batch_config.yaml')}
    Automatically generates all cases with their specific parameters
"""
    print(examples_text)
