"""Help messages for template command."""

from flexflow.utils.colors import Colors

def print_template_help():
    """Print template command help."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Template Command{Colors.RESET}

Generate template YAML configuration files.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow template {Colors.YELLOW}<type> <output_file>{Colors.RESET}

{Colors.BOLD}TEMPLATE TYPES:{Colors.RESET}
    {Colors.CYAN}single{Colors.RESET}     Generate single case plot configuration
    {Colors.CYAN}multi{Colors.RESET}      Generate multi-case comparison configuration

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--examples{Colors.RESET}     Show usage examples
    {Colors.YELLOW}--help, -h{Colors.RESET}     Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Creates a template YAML file that can be edited and used with:
    - flexflow plot --input-file <file>
    - flexflow compare --input-file <file>
""")


def print_template_examples():
    """Print template command examples."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}Template Command Examples{Colors.RESET}

{Colors.BOLD}Generate Templates:{Colors.RESET}
    flexflow template single my_plot.yaml
    flexflow template multi comparison.yaml

{Colors.BOLD}Use Generated Templates:{Colors.RESET}
    # Edit the generated YAML file, then use it:
    flexflow plot --input-file my_plot.yaml
    flexflow compare --input-file comparison.yaml
""")
