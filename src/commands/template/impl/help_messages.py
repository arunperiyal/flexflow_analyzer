"""Help messages for template command."""

from ....utils.colors import Colors


def print_plot_help():
    """Print template plot help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Template Plot Command{Colors.RESET}

Generate plot configuration templates.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow template plot {Colors.YELLOW}<type>{Colors.RESET} [output_file]

{Colors.BOLD}TEMPLATE TYPES:{Colors.RESET}
    {Colors.CYAN}single{Colors.RESET}     Single plot configuration (time-domain, FFT, trajectories)
    {Colors.CYAN}multi{Colors.RESET}      Multi-case comparison configuration

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--force{Colors.RESET}        Force overwrite if file exists
    {Colors.YELLOW}--verbose, -v{Colors.RESET}  Enable verbose output
    {Colors.YELLOW}--help, -h{Colors.RESET}     Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Creates plot template YAML files that can be edited and used with:
    - flexflow plot --input-file <file>       (single plot template)
    - flexflow compare --input-file <file>    (multi-case comparison template)

{Colors.BOLD}EXAMPLES:{Colors.RESET}

    {Colors.BOLD}Generate single plot template:{Colors.RESET}
        flexflow template plot single
        flexflow template plot single my_plot.yaml

    {Colors.BOLD}Generate multi-case comparison template:{Colors.RESET}
        flexflow template plot multi
        flexflow template plot multi comparison.yaml

    {Colors.BOLD}Use generated template:{Colors.RESET}
        # 1. Edit the YAML file
        vi plot_single.yaml

        # 2. Run the plot command
        flexflow plot --input-file plot_single.yaml

{Colors.BOLD}WORKFLOW:{Colors.RESET}
    1. Generate template:    flexflow template plot single my_config.yaml
    2. Edit configuration:   vi my_config.yaml
    3. Generate plot:        flexflow plot --input-file my_config.yaml
""")


def print_case_help():
    """Print template case help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Template Case Command{Colors.RESET}

Generate case creation configuration templates.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow template case {Colors.YELLOW}<type>{Colors.RESET} [output_file]

{Colors.BOLD}TEMPLATE TYPES:{Colors.RESET}
    {Colors.CYAN}single{Colors.RESET}     Single case configuration
    {Colors.CYAN}multi{Colors.RESET}      Multiple cases (batch generation)

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--force{Colors.RESET}        Force overwrite if file exists
    {Colors.YELLOW}--verbose, -v{Colors.RESET}  Enable verbose output
    {Colors.YELLOW}--help, -h{Colors.RESET}     Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Creates case template YAML files for parametric case generation.
    Templates can define:
    - Geometry parameters (for .geo file placeholders)
    - Solver parameters (for .def file variables)
    - SLURM configuration
    - Processor count and output frequency

{Colors.BOLD}EXAMPLES:{Colors.RESET}

    {Colors.BOLD}Generate single case template:{Colors.RESET}
        flexflow template case single
        flexflow template case single my_case.yaml

    {Colors.BOLD}Generate batch cases template:{Colors.RESET}
        flexflow template case multi
        flexflow template case multi batch_cases.yaml

    {Colors.BOLD}Use generated template:{Colors.RESET}
        # 1. Edit the YAML file
        vi case_single.yaml

        # 2. Create the case
        flexflow case create --from-config case_single.yaml --ref-case ./refCase

{Colors.BOLD}WORKFLOW:{Colors.RESET}

    {Colors.BOLD}For single case:{Colors.RESET}
        1. Generate template:    flexflow template case single my_case.yaml
        2. Edit configuration:   vi my_case.yaml
           - Modify case_name, problem_name
           - Set geo parameters (groove_depth, etc.)
           - Set def parameters (Ur, Re, etc.)
        3. Create case:          flexflow case create --from-config my_case.yaml --ref-case ./refCase

    {Colors.BOLD}For multiple cases:{Colors.RESET}
        1. Generate template:    flexflow template case multi my_cases.yaml
        2. Edit configuration:   vi my_cases.yaml
           - Define parameter variations in the 'cases' list
           - Each case gets unique name and parameters
        3. Create cases:         flexflow case create --from-config my_cases.yaml --ref-case ./refCase
""")


def print_template_examples():
    """Print template command examples."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}Template Command Examples{Colors.RESET}

{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}
{Colors.BOLD}Plot Templates{Colors.RESET}
{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}

{Colors.BOLD}Single Plot Configuration:{Colors.RESET}
    # Generate template
    flexflow template plot single my_plot.yaml

    # Edit to configure:
    #   - Case directory
    #   - Node number
    #   - Data type (displacement/force)
    #   - Plot type (time/fft/traj2d/traj3d)
    #   - Components, time range, styling

    # Use template
    flexflow plot --input-file my_plot.yaml

{Colors.BOLD}Multi-Case Comparison:{Colors.RESET}
    # Generate template
    flexflow template plot multi comparison.yaml

    # Edit to configure:
    #   - Multiple case directories
    #   - Comparison settings
    #   - Legend labels
    #   - Output options

    # Use template
    flexflow compare --input-file comparison.yaml

{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}
{Colors.BOLD}Case Templates{Colors.RESET}
{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}

{Colors.BOLD}Single Case Creation:{Colors.RESET}
    # Generate template
    flexflow template case single my_case.yaml

    # Edit to configure:
    #   - case_name: testCase
    #   - problem_name: riser
    #   - processors: 36
    #   - geo parameters (groove_depth, groove_width, etc.)
    #   - def parameters (Ur, Re, etc.)

    # Create case
    flexflow case create --from-config my_case.yaml --ref-case ./refCase

{Colors.BOLD}Batch Case Generation:{Colors.RESET}
    # Generate template
    flexflow template case multi batch_cases.yaml

    # Edit the 'cases' list to define multiple cases:
    #   cases:
    #     - name: case1_Ur4
    #       geo: {{groove_depth: 0.03}}
    #       def: {{Ur: 4.0}}
    #     - name: case2_Ur5
    #       geo: {{groove_depth: 0.05}}
    #       def: {{Ur: 5.0}}

    # Create all cases
    flexflow case create --from-config batch_cases.yaml --ref-case ./refCase

{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}
{Colors.BOLD}Quick Reference{Colors.RESET}
{Colors.BOLD}═══════════════════════════════════════════════════════════════════{Colors.RESET}

{Colors.BOLD}All Template Commands:{Colors.RESET}
    flexflow template plot single [file]     # Single plot config
    flexflow template plot multi [file]      # Multi-case comparison config
    flexflow template case single [file]     # Single case config
    flexflow template case multi [file]      # Batch cases config

{Colors.BOLD}Default Output Files:{Colors.RESET}
    plot single  → plot_single.yaml
    plot multi   → plot_multi.yaml
    case single  → case_single.yaml
    case multi   → case_multi.yaml

{Colors.BOLD}Common Workflow:{Colors.RESET}
    1. Generate:  flexflow template <domain> <type> my_config.yaml
    2. Edit:      vi my_config.yaml
    3. Use:       flexflow <command> --input-file my_config.yaml
""")


def print_script_help():
    """Print template script help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Template Script Command{Colors.RESET}

Generate SLURM job script templates for FlexFlow simulations.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow template script {Colors.YELLOW}<type>{Colors.RESET} [case_directory]

{Colors.BOLD}SCRIPT TYPES:{Colors.RESET}
    {Colors.CYAN}env{Colors.RESET}      Environment config (executable paths, module loads)
    {Colors.CYAN}pre{Colors.RESET}      Preprocessing script (mesh generation with gmsh + simGmshCnvt)
    {Colors.CYAN}main{Colors.RESET}     Main simulation script (runs mpiSimflow)
    {Colors.CYAN}post{Colors.RESET}     Postprocessing script (simPlt + simPlt2Bin)
    {Colors.CYAN}all{Colors.RESET}      Generate all four files (env + pre + main + post)

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--force{Colors.RESET}        Force overwrite if file exists
    {Colors.YELLOW}--verbose, -v{Colors.RESET}  Enable verbose output
    {Colors.YELLOW}--help, -h{Colors.RESET}     Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Creates SLURM job scripts that source simflow_env.sh for all paths.
    Edit only simflow_env.sh to update executable paths across all scripts.

    {Colors.BOLD}Files generated:{Colors.RESET}
    - simflow_env.sh : Executable paths and module loads (edit this file)
    - preFlex.sh     : Runs gmsh and simGmshCnvt
    - mainFlex.sh    : Runs mpiSimflow with archiving
    - postFlex.sh    : Runs simPlt and simPlt2Bin

{Colors.BOLD}EXAMPLES:{Colors.RESET}

    {Colors.BOLD}Generate environment config only:{Colors.RESET}
        flexflow template script env Case001

    {Colors.BOLD}Generate all scripts:{Colors.RESET}
        flexflow template script all Case001

    {Colors.BOLD}Generate in current directory:{Colors.RESET}
        cd Case001
        flexflow template script all

{Colors.BOLD}USAGE OF GENERATED SCRIPTS:{Colors.RESET}

    {Colors.BOLD}simflow_env.sh:{Colors.RESET}
        # Edit this to set your paths - all job scripts source it
        SIMFLOW_HOME="/path/to/flexflow"
        GMSH="gmsh"
        # module load compiler/openmpi/4.0.2

    {Colors.BOLD}preFlex.sh:{Colors.RESET}
        sbatch preFlex.sh
        # Auto-detects: PROBLEM, GEO_FILE from simflow.config

    {Colors.BOLD}mainFlex.sh:{Colors.RESET}
        sbatch mainFlex.sh
        # Auto-detects: PROBLEM, RUN_DIR from simflow.config

    {Colors.BOLD}postFlex.sh:{Colors.RESET}
        sbatch postFlex.sh [FREQ] [START_TIME] [END_TIME]
        # Auto-detects: PROBLEM, RUN_DIR, FREQ from simflow.config
        # Arguments override config values

        # Examples:
        sbatch postFlex.sh              # Use all defaults from config
        sbatch postFlex.sh 100          # Override frequency to 100
        sbatch postFlex.sh 100 0 5000   # Freq=100, process 0-5000

{Colors.BOLD}WORKFLOW:{Colors.RESET}
    1. Generate scripts:     flexflow template script all Case001
    2. Edit environment:     vi Case001/simflow_env.sh
    3. Submit jobs:
       - run pre             # Or: sbatch preFlex.sh
       - run main            # Or: sbatch mainFlex.sh
       - run post            # Or: sbatch postFlex.sh

{Colors.BOLD}ENVIRONMENT FILE:{Colors.RESET}
    All paths are configured in simflow_env.sh:
        {Colors.CYAN}SIMFLOW_HOME{Colors.RESET}   Path to FlexFlow installation
        {Colors.CYAN}MPISIMFLOW{Colors.RESET}     mpiSimflow executable
        {Colors.CYAN}SIMPLT{Colors.RESET}         simPlt executable
        {Colors.CYAN}SIMPLT2BIN{Colors.RESET}     simPlt2Bin executable
        {Colors.CYAN}SIMGMSHCNVT{Colors.RESET}    simGmshCnvt executable
        {Colors.CYAN}GMSH{Colors.RESET}           gmsh executable

    Example simflow_env.sh:
        export SIMFLOW_HOME="/home/user/FlexFlow"
        export GMSH="gmsh"
        # module load compiler/openmpi/4.0.2

{Colors.BOLD}CUSTOMIZATION:{Colors.RESET}
    - simflow_env.sh  : Executable paths and module loads
    - Job scripts     : SBATCH directives (partition, tasks, time, etc.)
                        Additional pre/post processing steps
""")
