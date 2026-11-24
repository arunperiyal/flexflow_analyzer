"""
Case organise command implementation

Keeps the OTHD/OISD history (archive/ → cleaned/ → compiled) and cleans output files.
Supports wildcard mode for batch operations on all cases.
"""

import os
import re
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
        print_organise_examples()
        return

    # No subcommand (history/out/rst/plt/vtu) → show help
    subcommand = getattr(args, 'organise_subcommand', None)
    if not subcommand:
        print_organise_help()
        return

    problem = _read_actions(args, subcommand)
    if problem:
        print(f"Error: {problem}", file=sys.stderr)
        sys.exit(2)

    # Show help if no case directory provided
    if not args.case:
        print_organise_help()
        return

    problem = _check_keep_flags(args, subcommand)
    if problem:
        print(f"Error: {problem}", file=sys.stderr)
        sys.exit(2)

    logger = Logger(verbose=args.verbose)
    console = Console()

    # Check if wildcard case - if so, iterate over all cases
    if is_wildcard_case(args.case):
        _execute_organise_on_all_cases(args, logger, console, subcommand)
        return

    try:
        # Load case
        logger.info(f"Loading case from: {args.case}")
        case = FlexFlowCase(args.case, verbose=args.verbose)

        # Initialize organizer
        from .organizer import CaseOrganizer
        organizer = CaseOrganizer(case, args, logger, console)

        # Run organization
        organizer.organize(subcommand)

        logger.success("Organise command completed")

    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# What `plt` and `history` are told to do is said in words after the case:
#   case organise plt CASE ascii binary      case organise history CASE update clean 1-3 compile
ACTIONS = {'plt': {'ascii': 'delete_ascii', 'binary': 'delete_binary'},
           'history': {'update': 'update', 'clean': 'clean', 'compile': 'compile',
                       'verify': 'verify', 'prune': 'prune'}}


def _read_actions(args, subcommand):
    """Set the flags the organizer reads (delete_ascii, update, ...) from the action
    words; what is wrong with them, or None. With the case from `use case:` the first
    word lands in `case`: an action word there is an action."""
    allowed = ACTIONS.get(subcommand)
    if allowed is None:
        return None
    for attr in allowed.values():
        setattr(args, attr, False)
    words = list(getattr(args, 'actions', None) or [])
    if getattr(args, 'case', None) in allowed:
        from src.cli.context import current_case
        words.insert(0, args.case)
        args.case = current_case()
    i = 0
    while i < len(words):
        word = words[i]
        if word not in allowed:
            return (f"case organise {subcommand}: '{word}' is not an action "
                    f"({', '.join(allowed)})")
        if word == 'clean' and i + 1 < len(words) and re.fullmatch(r'[\d,\-]+', words[i + 1]):
            args.clean = words[i + 1]         # the archive runs to clean: 1,2,3 or 1-3
            i += 1
        else:
            setattr(args, allowed[word], True)
        i += 1
    return None


def _check_keep_flags(args, subcommand):
    """What is wrong with --freq/--keep-freq, or None."""
    for flag in ('freq', 'keep_freq'):
        value = getattr(args, flag, None)
        if value is not None and value < 1:
            return f"--{flag.replace('_', '-')} must be 1 or more"
    if subcommand == 'plt' and not getattr(args, 'delete_binary', False):
        if getattr(args, 'keep_freq', None) is not None:
            return "--keep-freq only applies to `binary`"
    if subcommand == 'out' and getattr(args, 'no_verify', False):
        if getattr(args, 't1', None) is None and getattr(args, 't2', None) is None:
            return ("--no-verify deletes .out without a PLT, so it needs a range: "
                    "give --t1 and/or --t2")
    return None


def _execute_organise_on_all_cases(args, logger, console, subcommand):
    """
    Execute organise on all cases from .cases.yml file.

    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    logger : Logger
        Logger instance
    console : Console
        Rich console instance
    subcommand : str
        'history', 'out', 'rst', 'plt' or 'vtu'
    """
    from pathlib import Path
    from src.core import cases_file

    # Get base directory (current directory)
    base_dir = Path.cwd()
    try:
        cases_data = cases_file.read(base_dir).cases
    except cases_file.CasesFileError as e:
        logger.error(str(e))
        return

    if not cases_data:
        logger.warning("No cases found in .cases.yml file")
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
            logger.warning(f"Skipping case {case_name}: No path in .cases.yml file")
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
            organizer.organize(subcommand)
            
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
