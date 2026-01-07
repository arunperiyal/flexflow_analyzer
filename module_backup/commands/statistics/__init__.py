"""
Statistics command - migrated to new command pattern
"""

from ..base import BaseCommand


class StatisticsCommand(BaseCommand):
    """Show statistical analysis of data"""
    
    name = "statistics"
    description = "Show statistical analysis of data"
    category = "Analysis"
    
    def setup_parser(self, subparsers):
        """Setup argument parser for statistics command"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )
        parser.add_argument('case', nargs='?', help='Case directory path')
        parser.add_argument('--node', type=int, help='Node ID to analyze (default: all nodes)')
        parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
        parser.add_argument('-h', '--help', action='store_true', help='Show help for statistics command')
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
            from ..statistics_cmd import command as statistics_cmd
            statistics_cmd.execute_statistics(args)
    
    def show_help(self):
        """Show help message"""
        from ..statistics_cmd.help_messages import print_statistics_help
        print_statistics_help()
    
    def show_examples(self):
        """Show usage examples"""
        from ..statistics_cmd.help_messages import print_statistics_examples
        print_statistics_examples()
