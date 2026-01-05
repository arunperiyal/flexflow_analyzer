#!/usr/bin/env python3
"""
FlexFlow CLI - Main entry point (Version 2 - Registry Pattern)

This is the new implementation using the command registry pattern.
It runs alongside the old main.py during Phase 1 for testing.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from module.cli.registry import registry
from module.cli.help_messages import print_main_help
from module.installer import install, uninstall, update


def create_parser_v2():
    """Create argument parser with registry pattern"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='FlexFlow - Analyze and visualize FlexFlow simulation data',
        add_help=False
    )
    
    # Global options
    parser.add_argument('--install', action='store_true',
                       help='Install flexflow command globally')
    parser.add_argument('--uninstall', action='store_true',
                       help='Uninstall flexflow command')
    parser.add_argument('--update', action='store_true',
                       help='Update flexflow installation')
    parser.add_argument('--completion', choices=['bash', 'zsh', 'fish'],
                       help='Generate shell completion script')
    parser.add_argument('--version', action='store_true',
                       help='Show version information')
    parser.add_argument('-h', '--help', action='store_true',
                       help='Show help message')
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Let each registered command add its parser
    for command in registry.all():
        command.setup_parser(subparsers)
    
    return parser


def parse_args_v2(args=None):
    """Parse command line arguments"""
    parser = create_parser_v2()
    
    if args is None:
        args = sys.argv[1:]
    
    return parser.parse_args(args)


def main():
    """Main entry point using registry pattern"""
    
    # Import and register commands
    from module.commands.info import InfoCommand
    registry.register(InfoCommand)
    
    # TODO: Register other commands as they are migrated
    # registry.register(NewCommand)
    # registry.register(PlotCommand)
    # ... etc
    
    # Parse arguments
    args = parse_args_v2()
    
    # Handle global flags first
    if args.install:
        install()
        return
    elif args.uninstall:
        uninstall()
        return
    elif args.update:
        update()
        return
    elif args.completion:
        from module.cli.completion import generate_completion_script
        print(generate_completion_script(args.completion))
        return
    
    # Handle commands via registry
    if not args.command:
        print_main_help()
    else:
        command = registry.get(args.command)
        if command:
            command.execute(args)
        else:
            print(f"Error: Unknown command '{args.command}'", file=sys.stderr)
            print("\nAvailable commands:", ", ".join(registry.list_names()))
            print(f"\nRun 'flexflow --help' for more information")
            sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
