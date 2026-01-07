"""
Compare command - migrated to new command pattern
"""

from .base import BaseCommand


class CompareCommand(BaseCommand):
    """Compare multiple cases"""
    
    name = "compare"
    description = "Compare multiple cases"
    category = "Visualization"
    
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
            from .compare_impl import command as compare_cmd
            compare_cmd.execute_compare(args)
    
    def show_help(self):
        """Show help message"""
        from .compare_impl.help_messages import print_compare_help
        print_compare_help()
    
    def show_examples(self):
        """Show usage examples"""
        from .compare_impl.help_messages import print_compare_examples
        print_compare_examples()
