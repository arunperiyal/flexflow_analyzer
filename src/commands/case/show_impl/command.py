"""
Info command implementation
"""

import os
import sys
from ....core.case import FlexFlowCase
from ....utils.logger import Logger
from ....utils.colors import Colors

# Modern libraries
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box


def execute_info(args):
    """
    Execute the info command

    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    """
    from .help_messages import print_info_help, print_info_examples

    # Handle help flag
    if hasattr(args, 'help') and args.help:
        print_info_help()
        return

    # Handle examples flag
    if hasattr(args, 'examples') and args.examples:
        print_info_examples()
        return

    # Show help if no case directory provided
    if not args.case:
        print_info_help()
        return
    
    logger = Logger(verbose=args.verbose)
    console = Console()
    
    try:
        # Load case
        logger.info(f"Loading case from: {args.case}")
        case = FlexFlowCase(args.case, verbose=args.verbose)
        
        # Create main info table
        table = Table(title="FlexFlow Case Information", box=box.ROUNDED, 
                     title_style="bold cyan", show_header=True, header_style="bold")
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")
        
        # Basic info
        table.add_row("Case Directory", case.case_directory)
        table.add_row("Problem Name", case.problem_name)

        # Output directory from simflow.config
        if 'dir' in case.config:
            output_dir = case.config['dir']
            # Resolve relative paths
            if not os.path.isabs(output_dir):
                output_dir_full = os.path.join(case.case_directory, output_dir)
            else:
                output_dir_full = output_dir

            # Check if it exists
            exists_marker = "✓" if os.path.exists(output_dir_full) else "✗"
            table.add_row("Output Directory", f"{output_dir} [{exists_marker}]")

        if hasattr(case, 'time_increment') and case.time_increment:
            table.add_row("Time Increment", f"{case.time_increment:.6f} s")
        
        # Find OTHD files
        othd_files = case.find_othd_files()
        table.add_row("OTHD Files", f"{len(othd_files)} file(s)")
        
        if len(othd_files) > 0:
            # Load OTHD data to get info
            reader = case.othd_reader
            table.add_row("Nodes", f"{reader.num_nodes:,}")
            table.add_row("Timesteps", f"{len(reader.times):,}")
            if len(reader.times) > 0:
                table.add_row("Time Range", f"{reader.times[0]:.4f} → {reader.times[-1]:.4f} s")
        
        # Find OISD files
        oisd_files = case.find_oisd_files()
        if len(oisd_files) > 0:
            table.add_row("OISD Files", f"{len(oisd_files)} file(s)")
            # Load OISD data to get info
            reader = case.oisd_reader
            if len(reader.times) > 0:
                table.add_row("OISD Time Range", f"{reader.times[0]:.4f} → {reader.times[-1]:.4f} s")
        
        console.print()
        console.print(table)
        console.print()
        
        # Status indicator
        console.print("[green]✓[/green] [bold]Valid case structure[/bold]")
        console.print()
        
        logger.success("Info command completed")
        
    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
