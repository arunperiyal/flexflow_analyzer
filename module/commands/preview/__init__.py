"""
Preview command - migrated to new command pattern
"""

from ..base import BaseCommand


class PreviewCommand(BaseCommand):
    """Preview displacement data in table format"""
    
    name = "preview"
    description = "Preview displacement data in table format"
    category = "Analysis"
    
    def setup_parser(self, subparsers):
        """Setup argument parser for preview command"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )
        parser.add_argument('case', nargs='?', help='Case directory path')
        parser.add_argument('--node', type=int, help='Node ID to preview (default: 0)')
        parser.add_argument('--start-time', type=float, help='Start time for preview')
        parser.add_argument('--end-time', type=float, help='End time for preview')
        parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
        parser.add_argument('-h', '--help', action='store_true', help='Show help for preview command')
        parser.add_argument('--examples', action='store_true', help='Show usage examples')
        return parser
    
    def execute(self, args):
        """Execute info command"""
        if hasattr(args, 'help') and args.help:
            self.show_help()
        elif hasattr(args, 'examples') and args.examples:
            self.show_examples()
        else:
            # Import and execute the existing command implementation
            from ..preview_cmd import command as preview_cmd
            preview_cmd.execute_preview(args)
    
    def show_help(self):
        """Show help message"""
        from ..preview_cmd.help_messages import print_preview_help
        print_preview_help()
    
    def show_examples(self):
        """Show usage examples"""
        from ..preview_cmd.help_messages import print_preview_examples
        print_preview_examples()
