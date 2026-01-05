"""
Case command group - Domain-driven structure
Handles case operations: show, create
"""

from ..base import BaseCommand


class CaseCommand(BaseCommand):
    """Case operations (show, create)"""
    
    name = "case"
    description = "Case operations (show, create)"
    category = "Core"
    
    def setup_parser(self, subparsers):
        """Setup argument parser for case command group"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )
        
        # Create subparsers for case subcommands
        case_subparsers = parser.add_subparsers(dest='case_subcommand',
                                                help='Case subcommands')
        
        # case show (was: info)
        show_parser = case_subparsers.add_parser('show', add_help=False,
                                                 help='Show case information')
        show_parser.add_argument('case', nargs='?', help='Case directory path')
        show_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose output')
        show_parser.add_argument('-h', '--help', action='store_true',
                                help='Show help for show command')
        show_parser.add_argument('--examples', action='store_true',
                                help='Show usage examples')
        
        # case create (was: new)
        create_parser = case_subparsers.add_parser('create', add_help=False,
                                                   help='Create new case')
        create_parser.add_argument('case_name', nargs='?', help='Name of the new case')
        create_parser.add_argument('--ref-case', type=str, default='./refCase',
                                  help='Path to reference case directory')
        create_parser.add_argument('--problem-name', type=str,
                                  help='Problem name to set in simflow.config')
        create_parser.add_argument('--np', type=int,
                                  help='Number of processors')
        create_parser.add_argument('--from-config', type=str,
                                  help='Create from YAML config file')
        create_parser.add_argument('-v', '--verbose', action='store_true',
                                  help='Enable verbose output')
        create_parser.add_argument('-h', '--help', action='store_true',
                                  help='Show help for create command')
        create_parser.add_argument('--examples', action='store_true',
                                  help='Show usage examples')
        
        # Main case help flags
        parser.add_argument('-h', '--help', action='store_true',
                           help='Show help for case command')
        
        return parser
    
    def execute(self, args):
        """Execute case command"""
        if hasattr(args, 'case_subcommand') and args.case_subcommand == 'show':
            # Delegate to info command
            from ..info_cmd import command as info_cmd
            info_cmd.execute_info(args)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'create':
            # Delegate to new command
            from ..new_cmd import command as new_cmd
            new_cmd.execute_new(args)
        else:
            # Show help for case group
            self.show_help()
    
    def show_help(self):
        """Show help message"""
        from rich.console import Console
        from rich.table import Table
        from rich import box
        
        console = Console()
        console.print()
        console.print("[bold cyan]FlexFlow Case Command[/bold cyan]")
        console.print()
        console.print("Manage FlexFlow simulation cases.")
        console.print()
        console.print("[bold]USAGE:[/bold]")
        console.print("    flexflow case <subcommand> [options]")
        console.print()
        
        # Create subcommands table
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("Subcommand", style="cyan")
        table.add_column("Description", style="white")
        
        table.add_row("show", "Display case information (was: info)")
        table.add_row("create", "Create new case from template (was: new)")
        
        console.print("[bold]SUBCOMMANDS:[/bold]")
        console.print(table)
        console.print()
        console.print("[bold]EXAMPLES:[/bold]")
        console.print("    flexflow case show CS4SG1U1")
        console.print("    flexflow case create myCase --problem-name test")
        console.print()


# Create command instance
command = CaseCommand()
