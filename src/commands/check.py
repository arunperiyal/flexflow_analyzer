"""
Check command - Top-level command to inspect FlexFlow data files
Supports: .othd, .oisd files
"""

from .base import BaseCommand


class CheckCommand(BaseCommand):
    """Check and inspect FlexFlow data files"""
    
    name = "check"
    description = "Inspect FlexFlow data files (OTHD, OISD)"
    category = "Core"
    
    def setup_parser(self, subparsers):
        """Setup argument parser for check command"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )
        
        parser.add_argument('file', nargs='?', 
                          help='Path to data file (.othd, .oisd)')
        parser.add_argument('-h', '--help', action='store_true',
                          help='Show help for check command')
        parser.add_argument('--examples', action='store_true',
                          help='Show usage examples')
        
        return parser
    
    def execute(self, args):
        """Execute check command"""
        from .check_impl.command import execute_check
        from .check_impl.help_messages import print_check_help, print_check_examples
        
        if args.help:
            print_check_help()
            return 0
        
        if args.examples:
            print_check_examples()
            return 0
        
        if not args.file:
            print_check_help()
            return 1
        
        return execute_check(args.file)
