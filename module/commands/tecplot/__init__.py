"""
Tecplot command - migrated to new command pattern
"""

from ..base import BaseCommand


class TecplotCommand(BaseCommand):
    """Work with Tecplot PLT files"""
    
    name = "tecplot"
    description = "Work with Tecplot PLT files"
    category = "File Operations"
    
    def setup_parser(self, subparsers):
        """Setup argument parser for tecplot command"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )
        
        # Create subparsers for tecplot subcommands
        tecplot_subparsers = parser.add_subparsers(dest='tecplot_subcommand',
                                                   help='Tecplot subcommands')
        
        # tecplot info
        info_parser = tecplot_subparsers.add_parser('info', add_help=False,
                                                    help='Show PLT file information')
        info_parser.add_argument('case', nargs='?', help='Case directory path')
        info_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose output')
        info_parser.add_argument('-h', '--help', action='store_true',
                                help='Show help for info command')
        info_parser.add_argument('--basic', action='store_true',
                                help='Show only basic file information')
        info_parser.add_argument('--variables', action='store_true',
                                help='Show only variables section')
        info_parser.add_argument('--zones', action='store_true',
                                help='Show only zone information')
        info_parser.add_argument('--checks', action='store_true',
                                help='Show only consistency checks')
        info_parser.add_argument('--stats', action='store_true',
                                help='Show only data statistics')
        info_parser.add_argument('--detailed', action='store_true',
                                help='Show detailed statistics (min/max for all variables)')
        info_parser.add_argument('--sample-file', type=int, metavar='STEP',
                                help='Analyze specific timestep file (default: first)')
        
        # tecplot extract
        extract_parser = tecplot_subparsers.add_parser('extract', add_help=False,
                                                       help='Extract data from PLT files')
        extract_parser.add_argument('case', nargs='?', help='Case directory path')
        extract_parser.add_argument('-v', '--verbose', action='store_true',
                                   help='Enable verbose output')
        extract_parser.add_argument('-h', '--help', action='store_true',
                                   help='Show help for extract command')
        extract_parser.add_argument('--variables', type=str,
                                   help='Comma-separated list of variables to extract (e.g., Y,U,V)')
        extract_parser.add_argument('--zone', type=str,
                                   help='Zone name to extract from (e.g., FIELD)')
        extract_parser.add_argument('--timestep', type=int,
                                   help='Timestep to extract (e.g., 1000)')
        extract_parser.add_argument('--output-file', type=str,
                                   help='Output CSV file path (if not provided, shows preview)')
        extract_parser.add_argument('--xmin', type=float,
                                   help='Minimum X coordinate for subdomain extraction')
        extract_parser.add_argument('--xmax', type=float,
                                   help='Maximum X coordinate for subdomain extraction')
        extract_parser.add_argument('--ymin', type=float,
                                   help='Minimum Y coordinate for subdomain extraction')
        extract_parser.add_argument('--ymax', type=float,
                                   help='Maximum Y coordinate for subdomain extraction')
        extract_parser.add_argument('--zmin', type=float,
                                   help='Minimum Z coordinate for subdomain extraction')
        extract_parser.add_argument('--zmax', type=float,
                                   help='Maximum Z coordinate for subdomain extraction')
        
        # Main tecplot help flags
        parser.add_argument('-v', '--verbose', action='store_true',
                           help='Enable verbose output')
        parser.add_argument('-h', '--help', action='store_true',
                           help='Show help for tecplot command')
        parser.add_argument('--examples', action='store_true',
                           help='Show usage examples')
        
        return parser
    
    def execute(self, args):
        """Execute tecplot command"""
        # Check if there's a subcommand - if so, let execute_tecplot handle help
        if hasattr(args, 'tecplot_subcommand') and args.tecplot_subcommand:
            from ..tecplot_cmd import command as tecplot_cmd
            tecplot_cmd.execute_tecplot(args)
        elif hasattr(args, 'examples') and args.examples:
            self.show_examples()
        elif hasattr(args, 'help') and args.help:
            self.show_help()
        else:
            from ..tecplot_cmd import command as tecplot_cmd
            tecplot_cmd.execute_tecplot(args)
    
    def show_help(self):
        """Show help message"""
        from ..tecplot_cmd.help_messages import print_tecplot_help
        print_tecplot_help()
    
    def show_examples(self):
        """Show usage examples"""
        from ..tecplot_cmd.help_messages import print_tecplot_examples
        print_tecplot_examples()
