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

        # data show -- what the data holds, not the data itself
        show_parser = data_subparsers.add_parser('show', add_help=False,
                                                help='What the time-history data holds')
        show_parser.add_argument('case', nargs='?', help='Case directory path')
        show_parser.add_argument('--othd', action='store_true',
                                help='Report on the othd files only')
        show_parser.add_argument('--oisd', action='store_true',
                                help='Report on the oisd files only')
        show_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose output')
        show_parser.add_argument('-h', '--help', action='store_true',
                                help='Show help for show command')
        show_parser.add_argument('--examples', action='store_true',
                                help='Show usage examples')

        # data table -- the numbers, time down the rows
        table_parser = data_subparsers.add_parser('table', add_help=False,
                                                 help='Tabulate variables over time')
        table_parser.add_argument('case', nargs='?', help='Case directory path')
        table_parser.add_argument('--var', '--variable', dest='var', type=str,
                                 action='append', metavar='NAME',
                                 help='Variable or component to tabulate '
                                      '(repeat, or comma-separate)')
        table_parser.add_argument('--t1', type=float, metavar='TSID',
                                 help='First tsId (alone: only that step)')
        table_parser.add_argument('--t2', type=float, metavar='TSID',
                                 help='Last tsId')
        table_parser.add_argument('--node', type=int,
                                 help='Node to read (default: 0; ignored for '
                                      'integrated output)')
        table_parser.add_argument('--output', type=str, metavar='FILE',
                                 help='Write every row to a .csv instead of printing')
        table_parser.add_argument('--head', type=int, metavar='N',
                                 help='Print the first N rows (default: 10)')
        table_parser.add_argument('--tail', type=int, metavar='N',
                                 help='Print the last N rows')
        table_parser.add_argument('--group', type=int, metavar='ID',
                                 help='Output group to read: othId in an othd '
                                      'file, osgId in an oisd (default: the first)')
        table_parser.add_argument('--othd', action='store_true',
                                 help='Take variables from the othd files')
        table_parser.add_argument('--oisd', action='store_true',
                                 help='Take variables from the oisd files')
        table_parser.add_argument('-v', '--verbose', action='store_true',
                                 help='Enable verbose output')
        table_parser.add_argument('-h', '--help', action='store_true',
                                 help='Show help for table command')
        table_parser.add_argument('--examples', action='store_true',
                                 help='Show usage examples')

        # data stats -- one row per variable
        stats_parser = data_subparsers.add_parser('stats', add_help=False,
                                                 help='Summarise variables over a window')
        stats_parser.add_argument('case', nargs='?', help='Case directory path')
        stats_parser.add_argument('--var', '--variable', dest='var', type=str,
                                 action='append', metavar='NAME',
                                 help='Variable or component to summarise '
                                      '(repeat, or comma-separate)')
        stats_parser.add_argument('--func', type=str, action='append', metavar='FUNC',
                                 help='min, max, mean, rms, std, range, maxloc '
                                      '(repeat, or comma-separate)')
        stats_parser.add_argument('--t1', type=float, metavar='TSID',
                                 help='First tsId (alone: only that step)')
        stats_parser.add_argument('--t2', type=float, metavar='TSID',
                                 help='Last tsId')
        stats_parser.add_argument('--node', type=int,
                                 help='Node to read (default: 0; ignored for '
                                      'integrated output)')
        stats_parser.add_argument('--output', type=str, metavar='FILE',
                                 help='Also write the summary to a .csv')
        stats_parser.add_argument('--freq', type=int, metavar='N',
                                 help='PLT output frequency for maxloc '
                                      '(default: outFreq from simflow.config)')
        stats_parser.add_argument('--group', type=int, metavar='ID',
                                 help='Output group to read: othId in an othd '
                                      'file, osgId in an oisd (default: the first)')
        stats_parser.add_argument('--othd', action='store_true',
                                 help='Take variables from the othd files')
        stats_parser.add_argument('--oisd', action='store_true',
                                 help='Take variables from the oisd files')
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
        elif hasattr(args, 'data_subcommand') and args.data_subcommand == 'table':
            from .table_impl import command as table_cmd
            table_cmd.execute_table(args)
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

        table.add_row("show", "What the data holds: files, nodes, span, variables")
        table.add_row("table", "The numbers themselves, time down the rows")
        table.add_row("stats", "min/max/mean/rms/std/range/maxloc over a window")

        console.print("[bold]SUBCOMMANDS:[/bold]")
        console.print(table)
        console.print()
        console.print("[bold]EXAMPLES:[/bold]")
        console.print("    flexflow data show CS4SG1U1")
        console.print("    flexflow data show CS4SG1U1 --oisd")
        console.print("    flexflow data table CS4SG1U1 --var aleDisp_y --node 24 --tail 20")
        console.print("    flexflow data stats CS4SG1U1 --var aleDisp_y --func max,rms")
        console.print("    flexflow data stats CS4SG1U1 --var totTrac_y --func maxloc")
        console.print()


# Create command instance
command = DataCommand()
