"""
Base command class for FlexFlow CLI commands.

It is shellkit's: commands define name/description/category, setup_parser()
and execute(). execute(self, args) and execute(self, args, ctx) both work.
"""

from shellkit import BaseCommand

__all__ = ['BaseCommand']
