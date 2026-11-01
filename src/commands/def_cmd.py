"""
Def command group - inspect and edit .def configuration files.

Handles .def operations: var, time, freq.
"""

from .base import BaseCommand
from src.cli.completers import described


class DefCommand(BaseCommand):
    """Inspect and edit a case's .def file (var, time, freq)"""

    name = "def"
    description = "Inspect and edit .def file parameters (var, time, freq)"
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

        # def time [maxTime|inc] [value]
        # Not validated with choices= here: argparse's rejection would surface
        # as "invalid choice", which points at the wrong thing when what's
        # actually wrong is a typo in the field name, not the subcommand.
        time_parser = def_subparsers.add_parser('time', add_help=False,
                                                 help='Show or edit timeSteppingControl values (maxTime, inc)')
        time_parser.add_argument('kind', nargs='?',
                                 help="'maxTime' (maxTimeSteps) or 'inc' (initialTimeIncrement); "
                                      "omit to show all timeSteppingControl values"
                                 ).completer = described(('maxTime', 'maxTimeSteps'),
                                                         ('inc', 'initialTimeIncrement'))
        time_parser.add_argument('value', nargs='?',
                                 help='New value (provide to edit the field)')
        time_parser.add_argument('-c', '--case', type=str,
                                 help='Case directory path (default: current directory)')
        time_parser.add_argument('-h', '--help', action='store_true',
                                 help='Show help for time command')

        # def freq [out|rst] [value]
        freq_parser = def_subparsers.add_parser('freq', add_help=False,
                                                help='Show or edit the output and restart '
                                                     'frequencies (outFreq)')
        freq_parser.add_argument('kind', nargs='?',
                                 help="'out' (outputSimulation) or 'rst' (outputRestart); "
                                      "omit to show both"
                                 ).completer = described(('out', 'outputSimulation outFreq'),
                                                         ('rst', 'outputRestart outFreq'))
        freq_parser.add_argument('value', nargs='?',
                                 help='New frequency in steps (provide to edit it)')
        freq_parser.add_argument('-c', '--case', type=str,
                                 help='Case directory path (default: current directory)')
        freq_parser.add_argument('-h', '--help', action='store_true',
                                 help='Show help for freq command')

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

        if subcommand == 'time':
            from .def_impl.command import execute_time
            return execute_time(args)

        if subcommand == 'freq':
            from .def_impl.command import execute_freq
            return execute_freq(args)

        print_def_help()
        return 1

    def show_help(self):
        """Show help message"""
        from .def_impl.help_messages import print_def_help
        print_def_help()


# Create command instance
command = DefCommand()
