#!/usr/bin/env python3
"""
FlexFlow - Main entry point.

This is the application entry point. All application logic
is in src/cli/app.py to keep this file minimal and clean.

Usage:
    python main.py [--cli | --ui] [options]
    ff [--cli | --ui] [options]
"""

import argparse
import sys
import os

# Add current directory to path for development mode
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cli.app import FlexFlowApp


def _parse_launch_mode(argv):
    """Split --cli/--ui (and the web app's own options) off argv.

    Everything else is left untouched so the interactive shell's own
    argument handling is unaffected.
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

    app = FlexFlowApp()
    return app.run()


if __name__ == '__main__':
    sys.exit(main())
