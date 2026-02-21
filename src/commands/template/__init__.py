"""
Template command - Generate configuration templates
Subcommands: plot, case
"""

from ..base import BaseCommand


class TemplateCommand(BaseCommand):
    """Generate YAML configuration templates"""

    name = "template"
    description = "Generate YAML configuration templates"
    category = "Utilities"

    def setup_parser(self, subparsers):
        """Setup argument parser for template command group"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )

        # Create subparsers for template subcommands
        template_subparsers = parser.add_subparsers(dest='template_domain',
                                                     help='Template domain (plot, case, or script)')

        # template plot
        plot_parser = template_subparsers.add_parser('plot', add_help=False,
                                                     help='Generate plot templates')
        plot_parser.add_argument('plot_type', nargs='?',
                                choices=['single', 'multi', 'multiple'],
                                help='Plot template type: single or multi')
        plot_parser.add_argument('output', nargs='?', type=str,
                                help='Output file path (optional)')
        plot_parser.add_argument('--force', action='store_true',
                                help='Force overwrite if file exists')
        plot_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose output')
        plot_parser.add_argument('-h', '--help', action='store_true',
                                help='Show help for template plot command')

        # template case
        case_parser = template_subparsers.add_parser('case', add_help=False,
                                                     help='Generate case templates')
        case_parser.add_argument('case_type', nargs='?',
                                choices=['single', 'multi', 'multiple'],
                                help='Case template type: single or multi')
        case_parser.add_argument('output', nargs='?', type=str,
                                help='Output file path (optional)')
        case_parser.add_argument('--force', action='store_true',
                                help='Force overwrite if file exists')
        case_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose output')
        case_parser.add_argument('-h', '--help', action='store_true',
                                help='Show help for template case command')

        # template script (NEW: for job scripts)
        script_parser = template_subparsers.add_parser('script', add_help=False,
                                                       help='Generate SLURM job script templates')
        script_parser.add_argument('script_type', nargs='?',
                                   choices=['pre', 'main', 'post', 'env'],
                                   help='Script type: pre, main, post, or env')
        script_parser.add_argument('case_dir', nargs='?', type=str,
                                  help='Case directory to create scripts in (optional)')
        script_parser.add_argument('--simflow-home', type=str, metavar='PATH',
                                  help='Set SIMFLOW_HOME path in the generated simflow_env.sh')
        script_parser.add_argument('--partition', type=str, metavar='NAME',
                                  help='Override partition header in the generated script')
        script_parser.add_argument('--wall-time', type=str, metavar='HH:MM:SS',
                                  help='Override wall time in the generated script')
        script_parser.add_argument('--gmsh-path', type=str, metavar='PATH',
                                  help='Set GMSH path in the generated simflow_env.sh')
        script_parser.add_argument('--load-by-module', type=str, metavar='MODULE',
                                  help='Uncomment and set module load in simflow_env.sh (e.g., flexflow)')
        script_parser.add_argument('--force', action='store_true',
                                  help='Force overwrite if file exists')
        script_parser.add_argument('-v', '--verbose', action='store_true',
                                  help='Enable verbose output')
        script_parser.add_argument('-h', '--help', action='store_true',
                                  help='Show help for template script command')

        # Main template help flags
        parser.add_argument('-h', '--help', action='store_true',
                           help='Show help for template command')
        parser.add_argument('--examples', action='store_true',
                           help='Show usage examples')

        return parser

    def execute(self, args):
        """Execute template command"""
        # Handle main help/examples
        if hasattr(args, 'help') and args.help and not hasattr(args, 'template_domain'):
            self.show_help()
            return

        if hasattr(args, 'examples') and args.examples:
            self.show_examples()
            return

        # Check if domain is specified
        if not hasattr(args, 'template_domain') or not args.template_domain:
            self.show_help()
            return

        # Delegate to appropriate implementation
        from .impl import command as template_cmd
        template_cmd.execute_template(args)

    def show_help(self):
        """Show help message"""
        from rich.console import Console
        from rich.table import Table
        from rich import box

        console = Console()
        console.print()
        console.print("[bold cyan]FlexFlow Template Command[/bold cyan]")
        console.print()
        console.print("Generate YAML configuration templates for plots and cases.")
        console.print()
        console.print("[bold]USAGE:[/bold]")
        console.print("    flexflow template <domain> <type> [output_file]")
        console.print()

        # Create domains table
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("Domain", style="cyan")
        table.add_column("Types", style="white")
        table.add_column("Description", style="dim")

        table.add_row("plot", "single, multi", "Plot configuration templates")
        table.add_row("case", "single, multi", "Case creation templates")
        table.add_row("script", "pre, main, post, env", "SLURM job script templates")

        console.print("[bold]DOMAINS:[/bold]")
        console.print(table)
        console.print()
        console.print("[bold]EXAMPLES:[/bold]")
        console.print("    flexflow template plot single my_plot.yaml")
        console.print("    flexflow template plot multi comparison.yaml")
        console.print("    flexflow template case single my_case.yaml")
        console.print("    flexflow template case multi batch_cases.yaml")
        console.print("    flexflow template script post Case001")
        console.print("    flexflow template script post Case001 --partition shared")
        console.print("    flexflow template script main Case001 --partition medium")
        console.print()
        console.print("[bold]OPTIONS:[/bold]")
        console.print("    --force         Force overwrite existing file")
        console.print("    --examples      Show detailed examples")
        console.print("    --help, -h      Show this help message")
        console.print()

    def show_examples(self):
        """Show usage examples"""
        from .impl.help_messages import print_template_examples
        print_template_examples()


# Create command instance
command = TemplateCommand()
