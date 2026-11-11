"""
auto - the per-case workflow for a folder of cases (docs/AUTO_PLAN.md §13)

    auto init [--remote NAME] [--path DIR] [--keep-rst N] [--disk-alert SIZE]
                         set a remote's folder and auto's settings in .cases.yml
    auto show [case] [--remote NAME] [--detail] [--only SECTIONS]
                         what auto would do: labelled sections for a case; the summary
                         table for several (case:*), each in full with --detail
    auto commands [case] just the commands to run, numbered, as plain text
    auto status [case]   one line per case
    auto apply [case] [--remote NAME] [--only history,upload,post] [--dry-run] [--yes]
                         organise history, upload (checked, never deleting), submit post jobs
    auto log [case]      (not built yet)
"""

from ..base import BaseCommand
from src.cli.context import case_arg, context_flag

SUBCOMMANDS = (('init', "Set a remote's folder and auto's settings in .cases.yml"),
               ('show', 'What auto would do for a case, or every case with case:* (changes nothing)'),
               ('commands', 'Just the commands to run, numbered, as plain text'),
               ('status', 'One line per case: state, steps, jobs, what is next'),
               ('apply', 'Organise history, upload (checked), submit post jobs; deletes nothing'),
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
        parser.add_argument('what', nargs='?', metavar='init|show|commands|status|apply|log',
                            help='; '.join(f"{n}: {h}" for n, h in SUBCOMMANDS)).completer = _complete_sub
        case_arg(parser, help="show: the case folder (default: use case:); '*' for every case in .cases.yml")
        context_flag(parser, 'remote', '--remote', type=str, metavar='NAME',
                     help='the remote (or use remote:NAME); `local` for a folder')
        parser.add_argument('--path', metavar='DIR',
                            help="init: the folder on the remote (default: the remote's "
                                 "`remote set-path`)")
        parser.add_argument('--keep-rst', type=int, metavar='N',
                            help='init: keep the .rst of the steps divisible by N when thinning')
        parser.add_argument('--disk-alert', metavar='SIZE',
                            help='init: flag running cases whose run directory is bigger (e.g. 200G)')
        parser.add_argument('--detail', action='store_true',
                            help='show: every case in full, not only the summary table')
        parser.add_argument('--only', metavar='SECTIONS',
                            help='show: only these sections (state, needs, flags, history, '
                                 'plt, out, rst, inputs); apply: only these steps '
                                 '(history, upload, post); comma-separated')
        parser.add_argument('--dry-run', action='store_true',
                            help='apply: list what would be done, do nothing')
        parser.add_argument('--yes', action='store_true',
                            help='apply: do not ask before starting')
        parser.add_argument('--force', action='store_true',
                            help="init: replace the remote's folder already in .cases.yml")
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
        if what == 'commands':
            from .show import execute_commands
            return execute_commands(args)
        if what == 'status':
            from .show import execute_status
            return execute_status(args)
        if what == 'apply':
            from .apply import execute_apply
            return execute_apply(args)
        if what == 'log':
            print("auto log is not built yet; the log of each apply run is in auto_logs/.")
            return 2
        print(f"Unknown subcommand: {what} (init, show, commands, status, apply, log)")
        return 2
