"""
auto - the per-case workflow for a folder of cases (docs/AUTO_PLAN.md §13)

    auto init            write .auto.conf here, for you to edit
    auto show [case]     what auto would do for each case; changes nothing
    auto apply [case]    (not built yet)
    auto log [case]      (not built yet)
"""

from ..base import BaseCommand

SUBCOMMANDS = (('init', 'Write .auto.conf in this folder, for you to edit'),
               ('show', 'What auto would do for each case in this folder (changes nothing)'),
               ('apply', 'Carry it out (not built yet)'),
               ('log', 'What earlier runs did (not built yet)'))


def _complete_sub(rt, prefix):
    return list(SUBCOMMANDS)


class AutoCommand(BaseCommand):
    """Check every case of a folder and do its next safe step"""

    name = "auto"
    description = "Check every case in this folder: post jobs, uploads, clean-up"
    category = "Execution"

    def setup_parser(self, subparsers):
        parser = subparsers.add_parser(self.name, add_help=False, help=self.description)
        parser.add_argument('what', nargs='?', metavar='init|show|apply|log',
                            help='; '.join(f"{n}: {h}" for n, h in SUBCOMMANDS)).completer = _complete_sub
        parser.add_argument('case', nargs='?', help='Only this case (a name from .cases)')
        parser.add_argument('--force', action='store_true',
                            help='init: replace an existing .auto.conf')
        parser.add_argument('-h', '--help', action='store_true', help='Show help')
        return parser

    def execute(self, args):
        what = getattr(args, 'what', None)
        if getattr(args, 'help', False) or what is None:
            from .help_messages import print_auto_help
            print_auto_help()
            return 0
        if what == 'init':
            from .init import execute_init
            return execute_init(args)
        if what == 'show':
            from .show import execute_show
            return execute_show(args)
        if what in ('apply', 'log'):
            print(f"auto {what} is not built yet; `auto show` shows the plan.")
            return 2
        print(f"Unknown subcommand: {what} (init, show, apply, log)")
        return 2
