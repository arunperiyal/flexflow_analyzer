"""Help messages for template command."""

from src.utils.colors import Colors

def print_template_help():
    """Print template command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Config Template Command{Colors.RESET}

Generate template YAML configuration files.

{Colors.BOLD}USAGE:{Colors.RESET}
    config template {Colors.YELLOW}<type> <output_file>{Colors.RESET}

{Colors.BOLD}TEMPLATE TYPES:{Colors.RESET}
    {Colors.CYAN}single{Colors.RESET}     Generate single case plot configuration
    {Colors.CYAN}multi{Colors.RESET}      Generate multi-case comparison configuration
    {Colors.CYAN}case{Colors.RESET}       Generate case creation configuration (for batch case creation)

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--examples{Colors.RESET}     Show usage examples
    {Colors.YELLOW}--help, -h{Colors.RESET}     Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Creates a template YAML file that can be edited and used with:
    - plot --input-file <file>       (single plot template)
    - compare --input-file <file>    (multi-case comparison template)
    - case create --from-config <file>  (case creation template)
""")


def print_template_examples():
    """Print template command examples."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}Template Command Examples{Colors.RESET}

{Colors.BOLD}Generate Templates:{Colors.RESET}
    config template single my_plot.yaml
    config template multi comparison.yaml
    config template case batch_cases.yaml

{Colors.BOLD}Use Generated Templates:{Colors.RESET}
    # Edit the generated YAML file, then use it:
    plot --input-file my_plot.yaml
    compare --input-file comparison.yaml
    case create --from-config batch_cases.yaml --ref-case ./refCase

{Colors.BOLD}Case Template Workflow:{Colors.RESET}
    # 1. Generate case configuration template
    config template case my_cases.yaml

    # 2. Edit my_cases.yaml to define your case parameters
    #    - Single case: modify the top-level case_name, geo, def sections
    #    - Multiple cases: uncomment and edit the 'cases' section

    # 3. Create case(s) from the configuration
    case create --from-config my_cases.yaml --ref-case ./refCase
""")
