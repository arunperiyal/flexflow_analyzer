#!/usr/bin/env python3
"""
FlexFlow - Main entry point.

This is the application entry point. The app is declared in src/cli/app.py;
the shell itself is shellkit's.

Usage:
    python main.py [--cli | --ui] [options]
    ff                       # interactive shell
    ff case show CS4SG1U1    # run one command and exit
"""

import argparse
import sys
import os

# Add current directory to path for development mode
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cli.app import create_app


def _parse_launch_mode(argv):
    """Split --cli/--ui (and the web app's own options) off argv.

    Everything else is left for the app: a command to run once, or nothing
    for the interactive shell.
    """
    parser = argparse.ArgumentParser(add_help=False)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--cli', action='store_true', help='Start the interactive shell (default)')
    group.add_argument('--ui', action='store_true', help='Start the web UI (src/web)')
    parser.add_argument('--root', default=None, help='--ui: workspace directory holding .cases (default: cwd)')
    parser.add_argument('--host', default='127.0.0.1', help='--ui: bind address (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8080, help='--ui: port to serve on (default: 8080)')

    known, rest = parser.parse_known_args(argv)
    return known, rest


def main() -> int:
    """
    Main entry point for FlexFlow application.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    launch, rest = _parse_launch_mode(sys.argv[1:])

    if launch.ui:
        from src.web.server import run as run_web
        run_web(root=launch.root, host=launch.host, port=launch.port)
        return 0

    if rest and rest[0] in ('--version', '-V'):
        from __version__ import get_full_version_info
        print(get_full_version_info())
        return 0

    return create_app().run(rest)


if __name__ == '__main__':
    sys.exit(main())
