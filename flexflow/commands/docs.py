"""
Docs command - migrated to new command pattern
"""

from .base import BaseCommand


class DocsCommand(BaseCommand):
    """View documentation"""
    
    name = "docs"
    description = "View documentation"
    category = "Utilities"
    
    def setup_parser(self, subparsers):
        """Setup argument parser for docs command"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )
        parser.add_argument('topic', nargs='?',
                           help='Documentation topic (main, plot, compare, info, template)')
        parser.add_argument('-h', '--help', action='store_true',
                           help='Show help for docs command')
        return parser
    
    def execute(self, args):
        """Execute docs command"""
        if hasattr(args, 'help') and args.help:
            self.show_help()
        else:
            from .docs_impl import command as docs_cmd
            docs_cmd.docs_command(args)
    
    def show_help(self):
        """Show help message"""
        from .docs_impl.help_messages import show_docs_help
        show_docs_help()