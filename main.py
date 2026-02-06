#!/usr/bin/env python3
"""
FlexFlow - Main entry point.

This is the application entry point. All application logic
is in src/cli/app.py to keep this file minimal and clean.

Usage:
    python main.py <command> [options]
    ff <command> [options]
"""

import sys
import os

# Add current directory to path for development mode
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cli.app import FlexFlowApp


def main() -> int:
    """
    Main entry point for FlexFlow application.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    app = FlexFlowApp()
    return app.run()


if __name__ == '__main__':
    sys.exit(main())
