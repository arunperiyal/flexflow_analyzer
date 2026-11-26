"""
Base command class for FlexFlow CLI commands.

It is shellkit's: commands define name/description/category, setup_parser()
and execute(). execute(self, args) and execute(self, args, ctx) both work.

One addition (.claude/rules/command-design.md, rule 11): a word the command does
not take -- usually the old positional case -- is refused with what to type, never
reinterpreted. The parsers catch such words in a hidden `words` argument
(`src.cli.context.no_words`).
"""

import sys

from shellkit import BaseCommand as _ShellkitCommand

__all__ = ['BaseCommand']


class BaseCommand(_ShellkitCommand):
    def run(self, args, ctx):
        stray = list(getattr(args, 'words', None) or [])
        if stray:
            path = ' '.join(str(v) for k, v in vars(args).items()
                            if (k == 'command' or k.endswith('_subcommand') or k == 'template_domain') and v)
            flag = getattr(args, 'word_flag', '--case')
            what = 'the case' if flag == '--case' else 'that value'
            print(f"Error: {path}: unexpected word '{stray[0]}'; {what} is a flag "
                  f"now: {flag} {stray[0]}", file=sys.stderr)
            return 2
        return super().run(args, ctx)
