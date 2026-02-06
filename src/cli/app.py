"""
FlexFlow application class.

Contains the main application logic, command registration,
argument parsing, and execution flow.
"""

import sys
import argparse
from typing import List, Optional

from src.cli.registry import registry
from src.cli.help_messages import print_main_help, print_main_examples
from src.utils.colors import Colors


class FlexFlowParser(argparse.ArgumentParser):
    """
    Custom argument parser with better error messages.

    Provides enhanced error reporting and help message formatting
    for the FlexFlow CLI.
    """

    def error(self, message: str) -> None:
        """
        Handle parser errors with custom formatting.

        Args:
            message: Error message from argparse
        """
        if 'invalid choice' in message:
            import re

            # Try to extract the invalid choice and what parser it's for
            match = re.search(r"invalid choice: '(\w+)'", message)
            if match:
                invalid_choice = match.group(1)

                # Check if this is a subcommand error by looking at sys.argv or the message
                # If the message mentions specific subcommands, it's a subcommand error
                if 'case_subcommand' in message or (len(sys.argv) > 1 and sys.argv[1] == 'case'):
                    # This is a case subcommand error
                    from src.commands.case import CaseCommand
                    print(
                        f"\n{Colors.RED}✗ Error: Unknown subcommand '{invalid_choice}' for 'case'"
                        f"{Colors.RESET}\n",
                        file=sys.stderr
                    )
                    CaseCommand().show_help()
                    sys.exit(2)
                elif 'data_subcommand' in message or (len(sys.argv) > 1 and sys.argv[1] == 'data'):
                    # This is a data subcommand error
                    from src.commands.data import DataCommand
                    print(
                        f"\n{Colors.RED}✗ Error: Unknown subcommand '{invalid_choice}' for 'data'"
                        f"{Colors.RESET}\n",
                        file=sys.stderr
                    )
                    DataCommand().show_help()
                    sys.exit(2)
                elif 'field_subcommand' in message or (len(sys.argv) > 1 and sys.argv[1] == 'field'):
                    # This is a field subcommand error
                    from src.commands.field import FieldCommand
                    print(
                        f"\n{Colors.RED}✗ Error: Unknown subcommand '{invalid_choice}' for 'field'"
                        f"{Colors.RESET}\n",
                        file=sys.stderr
                    )
                    FieldCommand().show_help()
                    sys.exit(2)
                else:
                    # This is a main command error
                    print(
                        f"\n{Colors.RED}✗ Error: Unknown command '{invalid_choice}'"
                        f"{Colors.RESET}\n",
                        file=sys.stderr
                    )
                    print_main_help()
                    sys.exit(2)
        super().error(message)


class FlexFlowApp:
    """
    Main FlexFlow application.

    Handles command registration, argument parsing, and command execution.
    This class contains all application logic that was previously in main.py.

    Attributes:
        parser: Argument parser for CLI
    """

    def __init__(self) -> None:
        """Initialize FlexFlow application."""
        self.parser: Optional[argparse.ArgumentParser] = None
        self._register_commands()

    def _register_commands(self) -> None:
        """Register all available commands with the registry."""
        # Import all command classes
        from src.commands.case import CaseCommand
        from src.commands.data import DataCommand
        from src.commands.field import FieldCommand
        from src.commands.check import CheckCommand
        from src.commands.visualization import PlotCommand, CompareCommand
        from src.commands.template import TemplateCommand
        from src.commands.utils import DocsCommand

        # Register all commands
        command_classes = [
            # Domain commands
            CaseCommand,
            DataCommand,
            FieldCommand,
            # File inspection
            CheckCommand,
            # Visualization commands
            PlotCommand,
            CompareCommand,
            # Utility commands
            TemplateCommand,
            DocsCommand,
        ]

        for cmd_class in command_classes:
            registry.register(cmd_class)

    def _create_parser(self) -> argparse.ArgumentParser:
        """
        Create argument parser with registry pattern.

        Returns:
            Configured argument parser
        """
        parser = FlexFlowParser(
            description='FlexFlow - Analyze and visualize FlexFlow simulation data',
            add_help=False
        )

        # Global options
        parser.add_argument(
            '--completion',
            choices=['bash', 'zsh', 'fish'],
            help='Generate shell completion script'
        )
        parser.add_argument(
            '--examples',
            action='store_true',
            help='Show comprehensive usage examples'
        )
        parser.add_argument(
            '--version', '-v',
            action='store_true',
            help='Show version information'
        )
        parser.add_argument(
            '-h', '--help',
            action='store_true',
            help='Show help message'
        )

        # Create subparsers for commands
        subparsers = parser.add_subparsers(
            dest='command',
            help='Available commands'
        )

        # Let each registered command add its parser
        for command in registry.all():
            command.setup_parser(subparsers)

        return parser

    def _handle_global_flags(self, args: argparse.Namespace) -> bool:
        """
        Handle global flags (--version, --help, --completion, etc.).

        Args:
            args: Parsed command-line arguments

        Returns:
            True if a global flag was handled and app should exit,
            False otherwise
        """
        if args.completion:
            from src.cli.completion import generate_completion_script
            print(generate_completion_script(args.completion))
            return True

        if hasattr(args, 'examples') and args.examples:
            # Only show main examples if NOT a subcommand
            if not hasattr(args, 'case_subcommand'):
                print_main_examples()
                return True

        if args.version:
            from __version__ import get_full_version_info
            print(get_full_version_info())
            return True

        if not args.command:
            print_main_help()
            return True

        return False

    def _execute_command(self, args: argparse.Namespace) -> None:
        """
        Execute the command specified in args.

        Args:
            args: Parsed command-line arguments
        """
        command = registry.get(args.command)
        if command:
            command.execute(args)
        else:
            print(
                f"{Colors.RED}✗ Error: Unknown command '{args.command}'"
                f"{Colors.RESET}",
                file=sys.stderr
            )
            print("\nRun 'flexflow --help' for available commands")
            sys.exit(1)

    def run(self, argv: Optional[List[str]] = None) -> int:
        """
        Run the FlexFlow application in interactive mode.

        The application now always runs in interactive shell mode,
        providing fast command execution without startup overhead.

        Args:
            argv: Command-line arguments (default: None, runs interactive)

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Create parser (needed for command execution in interactive mode)
            self.parser = self._create_parser()

            # Always run in interactive mode
            from src.cli.interactive import InteractiveShell
            shell = InteractiveShell(app=self)
            return shell.run()

        except KeyboardInterrupt:
            print("\n\nInterrupted by user", file=sys.stderr)
            return 130  # Standard exit code for SIGINT

        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.RESET}", file=sys.stderr)

            # Show traceback in debug mode
            if '--debug' in sys.argv or '-d' in sys.argv:
                import traceback
                traceback.print_exc()

            return 1
