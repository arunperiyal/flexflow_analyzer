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
