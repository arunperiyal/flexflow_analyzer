"""
Def command group - inspect and edit .def configuration files.

Handles .def operations: var (more subcommands to follow).
"""

from .base import BaseCommand


class DefCommand(BaseCommand):
    """Inspect and edit a case's .def file (var)"""

    name = "def"
    description = "Inspect and edit .def file parameters (var)"
    category = "Core"

    def setup_parser(self, subparsers):
        """Setup argument parser for def command group"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )

        def_subparsers = parser.add_subparsers(dest='def_subcommand',
                                               help='Def subcommands')

        # def var [name] [value]
        var_parser = def_subparsers.add_parser('var', add_help=False,
                                               help='Show or edit define{} variables')
        var_parser.add_argument('name', nargs='?',
                                help='Variable name (omit to list all variables)')
        var_parser.add_argument('value', nargs='?',
                                help='New value (provide to edit the variable)')
        var_parser.add_argument('-c', '--case', type=str,
                                help='Case directory path (default: current directory)')
        var_parser.add_argument('-h', '--help', action='store_true',
                                help='Show help for var command')

        # Main def help flag
        parser.add_argument('-h', '--help', action='store_true',
                            help='Show help for def command')

        return parser

    def execute(self, args):
        """Execute def command"""
        from .def_impl.help_messages import print_def_help

        subcommand = getattr(args, 'def_subcommand', None)

        if subcommand is None:
            print_def_help()
            return 0

        if getattr(args, 'help', False):
            print_def_help()
            return 0

        if subcommand == 'var':
            from .def_impl.command import execute_var
            return execute_var(args)

        print_def_help()
        return 1

    def show_help(self):
        """Show help message"""
        from .def_impl.help_messages import print_def_help
        print_def_help()


# Create command instance
command = DefCommand()
