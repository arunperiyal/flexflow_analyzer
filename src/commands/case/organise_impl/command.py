"""
Case organise command implementation

Cleans up redundant OTHD/OISD files and output directory files.
Supports wildcard mode for batch operations on all cases.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from ....core.case import FlexFlowCase
from ....utils.logger import Logger
from ....utils.colors import Colors
from ...case_iteration import is_wildcard_case, load_cases_from_directory

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

    # No action flags → show help
    do_archive = getattr(args, 'archive', False)
    do_organise = getattr(args, 'clean_archive', False)
    do_clean_output = getattr(args, 'clean_output', False)
    do_clean_plt = getattr(args, 'clean_plt', False)

    if not do_archive and not do_organise and not do_clean_output and not do_clean_plt:
        print_organise_help()
        return

    logger = Logger(verbose=args.verbose)
    console = Console()

    # Check if wildcard case - if so, iterate over all cases
    if is_wildcard_case(args.case):
        _execute_organise_on_all_cases(args, logger, console,
                                       do_archive, do_organise, do_clean_output, do_clean_plt)
        return

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


def _execute_organise_on_all_cases(args, logger, console, do_archive, do_organise, 
                                   do_clean_output, do_clean_plt):
    """
    Execute organise on all cases from .cases file.
    
    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    logger : Logger
        Logger instance
    console : Console
        Rich console instance
    do_archive : bool
        Archive files
    do_organise : bool
        Organize/deduplicate files
    do_clean_output : bool
        Clean output files
    do_clean_plt : bool
        Clean PLT files
    """
    import json
    from pathlib import Path
    
    # Get base directory (current directory)
    base_dir = Path.cwd()
    cases_file = base_dir / '.cases'
    
    if not cases_file.exists():
        logger.error(f"No .cases file found in {base_dir}")
        return
    
    try:
        with open(cases_file) as f:
            cases_data = json.load(f)
    except Exception as e:
        logger.error(f"Could not load .cases file: {e}")
        return
    
    if not cases_data:
        logger.warning("No cases found in .cases file")
        return
    
    # Display header
    console.print()
    console.print(Panel(
        f"[bold cyan]Running organise on {len(cases_data)} case(s)[/bold cyan]",
        border_style="cyan",
        box=box.ROUNDED
    ))
    console.print()
    
    completed = 0
    failed = 0
    
    # Execute on each case
    for case_info in cases_data:
        case_name = case_info.get('name', 'Unknown')
        case_path = case_info.get('path')
        
        if not case_path:
            logger.warning(f"Skipping case {case_name}: No path in .cases file")
            continue
        
        case_dir = Path(case_path)
        if not case_dir.exists():
            logger.warning(f"Skipping case {case_name}: Directory not found at {case_path}")
            continue
        
        console.print(f"[bold]Processing:[/bold] {case_name}")
        
        try:
            # Load case
            case = FlexFlowCase(str(case_dir), verbose=args.verbose)
            
            # Initialize organizer
            from .organizer import CaseOrganizer
            organizer = CaseOrganizer(case, args, logger, console)
            
            # Run organization
            organizer.organize()
            
            logger.success(f"✓ Completed: {case_name}")
            completed += 1
            
        except Exception as e:
            logger.error(f"✗ Failed to organise {case_name}: {str(e)}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            failed += 1
        
        console.print()
    
    # Final summary
    console.print(Panel(
        f"[bold green]Organise Complete![/bold green]\n"
        f"Completed: {completed}\n"
        f"Failed: {failed}",
        border_style="green",
        box=box.ROUNDED
    ))
    console.print()
