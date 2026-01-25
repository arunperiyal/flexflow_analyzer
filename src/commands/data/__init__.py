"""
Data command group - Work with time-series data
Subcommands: show, stats
"""

from ..base import BaseCommand


class DataCommand(BaseCommand):
    """Data operations (show, stats)"""

    name = "data"
    description = "Data operations (show, stats)"
    category = "Core"

    def setup_parser(self, subparsers):
        """Setup argument parser for data command group"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )

        # Create subparsers for data subcommands
        data_subparsers = parser.add_subparsers(dest='data_subcommand',
                                                help='Data subcommands')

        # data show (was: preview)
        show_parser = data_subparsers.add_parser('show', add_help=False,
                                                help='Show raw data preview')
        show_parser.add_argument('case', nargs='?', help='Case directory path')
        show_parser.add_argument('--node', type=int,
                                help='Node ID to preview (default: 0)')
        show_parser.add_argument('--start-time', type=float,
                                help='Start time for preview')
        show_parser.add_argument('--end-time', type=float,
                                help='End time for preview')
        show_parser.add_argument('--variable', '--variables', type=str, action='append',
                                help='Specify columns to show (can be used multiple times)')
        show_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose output')
        show_parser.add_argument('-h', '--help', action='store_true',
                                help='Show help for show command')
        show_parser.add_argument('--examples', action='store_true',
                                help='Show usage examples')

        # data stats (was: statistics)
        stats_parser = data_subparsers.add_parser('stats', add_help=False,
                                                 help='Show statistical analysis')
        stats_parser.add_argument('case', nargs='?', help='Case directory path')
        stats_parser.add_argument('--node', type=int,
                                 help='Show statistics for specific node')
        stats_parser.add_argument('-v', '--verbose', action='store_true',
                                 help='Enable verbose output')
        stats_parser.add_argument('-h', '--help', action='store_true',
                                 help='Show help for stats command')
        stats_parser.add_argument('--examples', action='store_true',
                                 help='Show usage examples')

        # Main data help flags
        parser.add_argument('-h', '--help', action='store_true',
                           help='Show help for data command')

        return parser

    def execute(self, args):
        """Execute data command"""
        if hasattr(args, 'data_subcommand') and args.data_subcommand == 'show':
            # Delegate to show subcommand
            from .show_impl import command as show_cmd
            show_cmd.execute_preview(args)
        elif hasattr(args, 'data_subcommand') and args.data_subcommand == 'stats':
            # Delegate to stats subcommand
            from .stats_impl import command as stats_cmd
            stats_cmd.execute_statistics(args)
        else:
            # Show help for data group
            self.show_help()

    def show_help(self):
        """Show help message"""
        from rich.console import Console
        from rich.table import Table
        from rich import box

        console = Console()
        console.print()
        console.print("[bold cyan]FlexFlow Data Command[/bold cyan]")
        console.print()
        console.print("Work with time-series data from OTHD/OISD files.")
        console.print()
        console.print("[bold]USAGE:[/bold]")
        console.print("    flexflow data <subcommand> [options]")
        console.print()

        # Create subcommands table
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("Subcommand", style="cyan")
        table.add_column("Description", style="white")

        table.add_row("show", "Preview raw data in table format (was: preview)")
        table.add_row("stats", "Show statistical analysis (was: statistics)")

        console.print("[bold]SUBCOMMANDS:[/bold]")
        console.print(table)
        console.print()
        console.print("[bold]EXAMPLES:[/bold]")
        console.print("    flexflow data show CS4SG1U1 --node 24")
        console.print("    flexflow data stats CS4SG1U1 --node 100")
        console.print()


# Create command instance
command = DataCommand()
