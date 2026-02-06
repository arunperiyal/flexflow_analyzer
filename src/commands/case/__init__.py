"""
Case command group - Manages simulation cases
Subcommands: show, create, run
"""

from ..base import BaseCommand


class CaseCommand(BaseCommand):
    """Case operations (show, create, run)"""

    name = "case"
    description = "Case operations (show, create, run)"
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
        create_parser.add_argument('--np', type=int, default=36,
                                  help='Number of processors (default: 36)')
        create_parser.add_argument('--freq', type=int, default=50,
                                  help='Output frequency (default: 50)')
        create_parser.add_argument('--from-config', type=str,
                                  help='Create from YAML config file')
        create_parser.add_argument('--force', action='store_true',
                                  help='Force overwrite if case already exists')
        create_parser.add_argument('--list-vars', action='store_true',
                                  help='List available variables in reference case')
        create_parser.add_argument('--dry-run', action='store_true',
                                  help='Show what would be created without actually creating')
        create_parser.add_argument('-v', '--verbose', action='store_true',
                                  help='Enable verbose output')
        create_parser.add_argument('-h', '--help', action='store_true',
                                  help='Show help for create command')
        create_parser.add_argument('--examples', action='store_true',
                                  help='Show usage examples')

        # case run
        run_parser = case_subparsers.add_parser('run', add_help=False,
                                               help='Submit and monitor SLURM jobs')
        run_parser.add_argument('case', nargs='?', help='Case directory path')
        run_parser.add_argument('--no-monitor', action='store_true',
                               help='Submit jobs without monitoring')
        run_parser.add_argument('--clean', action='store_true',
                               help='Clean start (remove existing OTHD files)')
        run_parser.add_argument('--from-step', type=int,
                               help='Restart from specific timestep')
        run_parser.add_argument('--dry-run', action='store_true',
                               help='Show what would be done without submitting jobs')
        run_parser.add_argument('-v', '--verbose', action='store_true',
                               help='Enable verbose output')
        run_parser.add_argument('-h', '--help', action='store_true',
                               help='Show help for run command')
        run_parser.add_argument('--examples', action='store_true',
                               help='Show usage examples')

        # case organise
        organise_parser = case_subparsers.add_parser('organise', add_help=False,
                                                     help='Organize and clean up case directory')
        organise_parser.add_argument('case', nargs='?', help='Case directory path')
        organise_parser.add_argument('--dry-run', action='store_true',
                                    help='Preview changes without deleting')
        organise_parser.add_argument('--freq', type=int,
                                    help='Override frequency from simflow.config')
        organise_parser.add_argument('--keep-every', type=int, default=10,
                                    help='Keep every Nth output (default: 10)')
        organise_parser.add_argument('--clean-othd', action='store_true',
                                    help='Clean OTHD files only')
        organise_parser.add_argument('--clean-oisd', action='store_true',
                                    help='Clean OISD files only')
        organise_parser.add_argument('--clean-output', action='store_true',
                                    help='Clean output directory only')
        organise_parser.add_argument('--log', action='store_true',
                                    help='Create log file of deletions')
        organise_parser.add_argument('--no-confirm', action='store_true',
                                    help='Skip confirmation prompts')
        organise_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        organise_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for organise command')
        organise_parser.add_argument('--examples', action='store_true',
                                    help='Show usage examples')

        # Main case help flags
        parser.add_argument('-h', '--help', action='store_true',
                           help='Show help for case command')

        return parser

    def execute(self, args):
        """Execute case command"""
        if hasattr(args, 'case_subcommand') and args.case_subcommand == 'show':
            # Delegate to show subcommand
            from .show_impl import command as show_cmd
            show_cmd.execute_info(args)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'create':
            # Delegate to create subcommand
            from .create_impl import command as create_cmd
            create_cmd.execute_new(args)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'run':
            # Delegate to run subcommand
            from .run import execute_case_run
            execute_case_run(args)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'organise':
            # Delegate to organise subcommand
            from .organise_impl import command as organise_cmd
            organise_cmd.execute_organise(args)
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
        table.add_row("run", "Submit and monitor SLURM simulation jobs")
        table.add_row("organise", "Organize and clean up case directory")

        console.print("[bold]SUBCOMMANDS:[/bold]")
        console.print(table)
        console.print()
        console.print("[bold]EXAMPLES:[/bold]")
        console.print("    flexflow case show CS4SG1U1")
        console.print("    flexflow case create myCase --problem-name test")
        console.print("    flexflow case run CS4SG1U1")
        console.print("    flexflow case run CS4SG1U1 --no-monitor")
        console.print("    flexflow case organise CS4SG1U1 --dry-run")
        console.print()


# Create command instance
command = CaseCommand()
