"""
Info command - migrated to new command pattern
"""

from .base import BaseCommand


class InfoCommand(BaseCommand):
    """Display case information"""
    
    name = "info"
    description = "Display case information"
    category = "Analysis"
    
    def setup_parser(self, subparsers):
        """Setup argument parser for info command"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )
        parser.add_argument('case', nargs='?', help='Case directory path')
        parser.add_argument('-v', '--verbose', action='store_true',
                          help='Enable verbose output')
        parser.add_argument('-h', '--help', action='store_true',
                          help='Show help for info command')
        parser.add_argument('--examples', action='store_true',
                          help='Show usage examples')
        return parser
    
    def execute(self, args):
        """Execute info command"""
        if hasattr(args, 'help') and args.help:
            self.show_help()
        elif hasattr(args, 'examples') and args.examples:
            self.show_examples()
        else:
            # Import and execute the existing command implementation
            from .info_impl import command as info_cmd
            info_cmd.execute_info(args)
    
    def show_help(self):
        """Show help message"""
        from .info_impl.help_messages import print_info_help
        print_info_help()
    
    def show_examples(self):
        """Show usage examples"""
        from .info_impl.help_messages import print_info_examples
        print_info_examples()
