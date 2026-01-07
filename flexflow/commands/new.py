"""New command - migrated to registry pattern"""
from .base import BaseCommand

class NewCommand(BaseCommand):
    name = "new"
    description = "Create a new case directory"
    category = "File Operations"
    
    def setup_parser(self, subparsers):
        parser = subparsers.add_parser(self.name, add_help=False, help=self.description)
        parser.add_argument('case_name', nargs='?', help='Name of the new case directory')
        parser.add_argument('--ref-case', dest='ref_case', help='Path to reference case directory (default: ./refCase)')
        parser.add_argument('--problem-name', dest='problem_name', help='Override problem name in simflow.config')
        parser.add_argument('--np', type=int, default=36, help='Number of processors (default: 36)')
        parser.add_argument('--freq', type=int, default=50, help='Output frequency (default: 50)')
        parser.add_argument('--from-config', dest='from_config', help='Load configuration from YAML file')
        parser.add_argument('--force', action='store_true', help='Overwrite existing directory if it exists')
        parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
        parser.add_argument('--list-vars', dest='list_vars', action='store_true', help='List all variables found in reference case files')
        parser.add_argument('--dry-run', dest='dry_run', action='store_true', help='Preview changes without creating the case directory')
        parser.add_argument('-h', '--help', action='store_true', help='Show help for new command')
        parser.add_argument('--examples', action='store_true', help='Show usage examples')
        return parser
    
    def execute(self, args):
        if hasattr(args, 'help') and args.help:
            self.show_help()
        elif hasattr(args, 'examples') and args.examples:
            self.show_examples()
        else:
            from .new_impl import command as new_cmd
            new_cmd.execute_new(args)
    
    def show_help(self):
        from .new_impl.help_messages import print_new_help
        print_new_help()
    
    def show_examples(self):
        from .new_impl.help_messages import print_new_examples
        print_new_examples()
