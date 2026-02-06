"""
Case organise command implementation

Cleans up redundant OTHD/OISD files and output directory files.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from ....core.case import FlexFlowCase
from ....utils.logger import Logger
from ....utils.colors import Colors

# Modern libraries
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box


def execute_organise(args):
    """
    Execute the organise command

    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    """
    from .help_messages import print_organise_help, print_organise_examples

    # Handle help flag
    if hasattr(args, 'help') and args.help:
        print_organise_help()
        return

    # Handle examples flag
    if hasattr(args, 'examples') and args.examples:
        print_organise_examples()
        return

    # Show help if no case directory provided
    if not args.case:
        print_organise_help()
        return

    logger = Logger(verbose=args.verbose)
    console = Console()

    try:
        # Load case
        logger.info(f"Loading case from: {args.case}")
        case = FlexFlowCase(args.case, verbose=args.verbose)

        # Initialize organizer
        from .organizer import CaseOrganizer
        organizer = CaseOrganizer(case, args, logger, console)

        # Run organization
        organizer.organize()

        logger.success("Organise command completed")

    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
