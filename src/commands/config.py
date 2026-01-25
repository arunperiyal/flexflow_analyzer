"""
Config command group - Domain-driven structure
Handles configuration operations: template
"""

from .base import BaseCommand


class ConfigCommand(BaseCommand):
    """Configuration operations (template)"""
    
    name = "config"
    description = "Configuration operations (template)"
    category = "Utilities"
    
    def setup_parser(self, subparsers):
        """Setup argument parser for config command group"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )
        
        # Create subparsers for config subcommands
        config_subparsers = parser.add_subparsers(dest='config_subcommand',
                                                  help='Config subcommands')
        
        # config template (was: template)
        template_parser = config_subparsers.add_parser('template', add_help=False,
                                                      help='Generate configuration templates')
        template_parser.add_argument('template_type', nargs='?',
                                    help='Template type: single, multi, or fft')
        template_parser.add_argument('--output', '-o', type=str,
                                    help='Output file path (default: case_config.yaml or compare_config.yaml)')
        template_parser.add_argument('--force', action='store_true',
                                    help='Force overwrite if file already exists')
        template_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        template_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for template command')
        template_parser.add_argument('--examples', action='store_true',
                                    help='Show usage examples')
        
        # Main config help flags
        parser.add_argument('-h', '--help', action='store_true',
                           help='Show help for config command')
        
        return parser
    
    def execute(self, args):
        """Execute config command"""
        if hasattr(args, 'config_subcommand') and args.config_subcommand == 'template':
            # Delegate to template command
            from .template_impl import command as template_cmd
            template_cmd.execute_template(args)
        else:
            # Show help for config group
            self.show_help()
    
    def show_help(self):
        """Show help message"""
        from rich.console import Console
        from rich.table import Table
        from rich import box
        
        console = Console()
        console.print()
        console.print("[bold cyan]FlexFlow Config Command[/bold cyan]")
        console.print()
        console.print("Manage FlexFlow configuration files.")
        console.print()
        console.print("[bold]USAGE:[/bold]")
        console.print("    flexflow config <subcommand> [options]")
        console.print()
        
        # Create subcommands table
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("Subcommand", style="cyan")
        table.add_column("Description", style="white")
        
        table.add_row("template", "Generate YAML configuration templates (was: template)")
        
        console.print("[bold]SUBCOMMANDS:[/bold]")
        console.print(table)
        console.print()
        console.print("[bold]EXAMPLES:[/bold]")
        console.print("    flexflow config template single output.yaml")
        console.print("    flexflow config template multi compare.yaml")
        console.print()


# Create command instance
command = ConfigCommand()
