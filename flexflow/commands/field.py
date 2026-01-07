"""
Field command group - Domain-driven structure
Handles field data operations: info, extract
"""

from .base import BaseCommand


class FieldCommand(BaseCommand):
    """Field data operations from PLT files (info, extract)"""
    
    name = "field"
    description = "Field data operations (info, extract)"
    category = "File Operations"
    
    def setup_parser(self, subparsers):
        """Setup argument parser for field command group"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )
        
        # Create subparsers for field subcommands
        field_subparsers = parser.add_subparsers(dest='field_subcommand',
                                                help='Field subcommands')
        
        # field info (was: tecplot info)
        info_parser = field_subparsers.add_parser('info', add_help=False,
                                                 help='Show PLT file information')
        info_parser.add_argument('case', nargs='?', help='Case directory path')
        info_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose output')
        info_parser.add_argument('-h', '--help', action='store_true',
                                help='Show help for info command')
        info_parser.add_argument('--basic', action='store_true',
                                help='Show only basic file information')
        info_parser.add_argument('--variables', action='store_true',
                                help='Show only variables section')
        info_parser.add_argument('--zones', action='store_true',
                                help='Show only zone information')
        info_parser.add_argument('--checks', action='store_true',
                                help='Show only consistency checks')
        info_parser.add_argument('--stats', action='store_true',
                                help='Show only data statistics')
        info_parser.add_argument('--detailed', action='store_true',
                                help='Show detailed statistics')
        info_parser.add_argument('--sample-file', type=int, metavar='STEP',
                                help='Analyze specific timestep file')
        
        # field extract (was: tecplot extract)
        extract_parser = field_subparsers.add_parser('extract', add_help=False,
                                                    help='Extract data from PLT files')
        extract_parser.add_argument('case', nargs='?', help='Case directory path')
        extract_parser.add_argument('-v', '--verbose', action='store_true',
                                   help='Enable verbose output')
        extract_parser.add_argument('-h', '--help', action='store_true',
                                   help='Show help for extract command')
        extract_parser.add_argument('--variables', type=str,
                                   help='Comma-separated list of variables to extract')
        extract_parser.add_argument('--zone', type=str,
                                   help='Zone name to extract from')
        extract_parser.add_argument('--timestep', type=int,
                                   help='Timestep to extract')
        extract_parser.add_argument('--output-file', type=str,
                                   help='Output CSV file path')
        extract_parser.add_argument('--xmin', type=float,
                                   help='Minimum X coordinate')
        extract_parser.add_argument('--xmax', type=float,
                                   help='Maximum X coordinate')
        extract_parser.add_argument('--ymin', type=float,
                                   help='Minimum Y coordinate')
        extract_parser.add_argument('--ymax', type=float,
                                   help='Maximum Y coordinate')
        extract_parser.add_argument('--zmin', type=float,
                                   help='Minimum Z coordinate')
        extract_parser.add_argument('--zmax', type=float,
                                   help='Maximum Z coordinate')
        
        # Main field help flags
        parser.add_argument('-h', '--help', action='store_true',
                           help='Show help for field command')
        
        return parser
    
    def execute(self, args):
        """Execute field command"""
        # Check if help was requested or no subcommand
        if not hasattr(args, 'field_subcommand') or args.field_subcommand is None:
            if hasattr(args, 'help') and args.help:
                self.show_help()
                return
            else:
                self.show_help()
                return
        
        # Map to tecplot_subcommand for compatibility
        args.tecplot_subcommand = args.field_subcommand
        
        # Delegate to tecplot command
        from flexflow.commandstecplot import TecplotCommand
        tecplot = TecplotCommand()
        tecplot.execute(args)
    
    def show_help(self):
        """Show help message"""
        from rich.console import Console
        from rich.table import Table
        from rich import box
        
        console = Console()
        console.print()
        console.print("[bold cyan]FlexFlow Field Command[/bold cyan]")
        console.print()
        console.print("Work with Tecplot PLT field data files.")
        console.print()
        console.print("[bold]USAGE:[/bold]")
        console.print("    flexflow field <subcommand> [options]")
        console.print()
        
        # Create subcommands table
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("Subcommand", style="cyan")
        table.add_column("Description", style="white")
        
        table.add_row("info", "Show PLT file information (was: tecplot info)")
        table.add_row("extract", "Extract data from PLT to CSV (was: tecplot extract)")
        
        console.print("[bold]SUBCOMMANDS:[/bold]")
        console.print(table)
        console.print()
        console.print("[bold]EXAMPLES:[/bold]")
        console.print("    flexflow field info CS4SG1U1")
        console.print("    flexflow field extract CS4SG1U1 --variables X,Y,U --zone FIELD")
        console.print()


# Create command instance
command = FieldCommand()
