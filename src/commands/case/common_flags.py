"""The flags every `case organise` subcommand takes, defined once so that they are
spelled, worded and ordered the same everywhere (docs/development/PLAN.md, Phase 31):

    --log        a file listing what was deleted
    -y, --yes    do not ask first
    --dry-run    list what would be done, change nothing
    -v           more output
    -h           this command's help, with its examples
"""


import argparse


def organise_flags(sub, what: str) -> None:
    sub.add_argument('--log', action='store_true', help='Write a log file of what is deleted')
    sub.add_argument('-y', '--yes', action='store_true', help='Do not ask before deleting')
    sub.add_argument('--dry-run', action='store_true',
                     help='List what would be done; change nothing')
    sub.add_argument('-v', '--verbose', action='store_true', help='More output')
    sub.add_argument('--result', metavar='FILE', default=None, help=argparse.SUPPRESS)
    sub.add_argument('-h', '--help', action='store_true', help=f'Show help for {what}')
