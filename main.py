#!/usr/bin/env python3
"""
FlexFlow - Main entry point
Analyze and visualize FlexFlow simulation data
"""

import sys
import os

# Add current directory to path for development mode
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cli.registry import registry
from src.cli.help_messages import print_main_help, print_main_examples
from src.utils.colors import Colors


def create_parser():
    """Create argument parser with registry pattern"""
    import argparse
    
    class FlexFlowParser(argparse.ArgumentParser):
        """Custom parser with better error messages"""
        def error(self, message):
            if 'invalid choice' in message:
                import re
                match = re.search(r"invalid choice: '(\w+)'", message)
                if match:
                    cmd = match.group(1)
                    print(f"\n{Colors.RED}✗ Error: Unknown command '{cmd}'{Colors.RESET}\n", file=sys.stderr)
                    print_main_help()
                    sys.exit(2)
            super().error(message)
    
    parser = FlexFlowParser(
        description='FlexFlow - Analyze and visualize FlexFlow simulation data',
        add_help=False
    )
    
    # Global options
    parser.add_argument('--completion', choices=['bash', 'zsh', 'fish'],
                       help='Generate shell completion script')
    parser.add_argument('--examples', action='store_true',
                       help='Show comprehensive usage examples')
    parser.add_argument('--version', '-v', action='store_true',
                       help='Show version information')
    parser.add_argument('-h', '--help', action='store_true',
                       help='Show help message')
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Let each registered command add its parser
    for command in registry.all():
        command.setup_parser(subparsers)
    
    return parser


def main():
    """Main entry point"""
    
    # Import and register all commands
    # Domain commands (groups)
    from src.commands.case import CaseCommand
    from src.commands.data import DataCommand
    from src.commands.field import FieldCommand
    from src.commands.check import CheckCommand

    # Visualization commands
    from src.commands.visualization import PlotCommand, CompareCommand

    # Utility commands
    from src.commands.template import TemplateCommand
    from src.commands.utils import AgentCommand, DocsCommand

    # Register all commands
    for cmd_class in [
        # Domain commands
        CaseCommand, DataCommand, FieldCommand,
        # File inspection
        CheckCommand,
        # Visualization commands
        PlotCommand, CompareCommand,
        # Utility commands
        TemplateCommand, AgentCommand, DocsCommand,
    ]:
        registry.register(cmd_class)
    
    # Parse arguments
    parser = create_parser()
    args = parser.parse_args()
    
    # Handle global flags
    if args.completion:
        from src.cli.completion import generate_completion_script
        print(generate_completion_script(args.completion))
        return
    elif hasattr(args, 'examples') and args.examples and not hasattr(args, 'case_subcommand'):
        # Only show main examples if NOT a subcommand
        print_main_examples()
        return
    elif args.version:
        from __version__ import get_full_version_info
        print(get_full_version_info())
        return
    elif not args.command:
        print_main_help()
        return

    # Let commands handle their own help - don't intercept here
    # Execute command via registry (command will handle its own help)
    command = registry.get(args.command)
    if command:
        command.execute(args)
    else:
        print(f"{Colors.RED}✗ Error: Unknown command '{args.command}'{Colors.RESET}", file=sys.stderr)
        print(f"\nRun 'flexflow --help' for available commands")
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
