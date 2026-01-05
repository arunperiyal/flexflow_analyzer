"""
Preview command implementation
"""

import sys
import numpy as np
from ...core.case import FlexFlowCase
from ...utils.logger import Logger
from ...utils.colors import Colors

# Modern libraries
from rich.console import Console
from rich.table import Table
from rich import box


def execute_preview(args):
    """
    Execute the preview command
    
    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    """
    from .help_messages import print_preview_help
    
    # Show help if no case directory provided
    if not args.case:
        print_preview_help()
        return
    
    logger = Logger(verbose=args.verbose)
    
    try:
        # Load case
        logger.info(f"Loading case from: {args.case}")
        case = FlexFlowCase(args.case, verbose=args.verbose)
        
        if not case.othd_reader:
            print(f"{Colors.red('Error:')} No OTHD data available", file=sys.stderr)
            sys.exit(1)
        
        reader = case.othd_reader
        node_id = args.node if args.node is not None else 0
        
        # Validate node ID
        if node_id >= reader.num_nodes:
            logger.error(f"Node {node_id} does not exist. Available nodes: 0-{reader.num_nodes-1}")
            sys.exit(1)
        
        # Get displacement data for the node
        node_data = reader.get_node_displacements(node_id)
        times = node_data['times']
        dx = node_data['dx']
        dy = node_data['dy']
        dz = node_data['dz']
        magnitude = node_data['magnitude']
        
        # Determine time range
        if args.start_time is not None or args.end_time is not None:
            # Filter by time range
            start_time = args.start_time if args.start_time is not None else times[0]
            end_time = args.end_time if args.end_time is not None else times[-1]
            
            # Find indices within time range
            mask = (times >= start_time) & (times <= end_time)
            indices = np.where(mask)[0]
            
            if len(indices) == 0:
                logger.error(f"No data found in time range [{start_time}, {end_time}]")
                sys.exit(1)
            
            start_idx = indices[0]
            end_idx = indices[-1]
        else:
            # Default: first 10 timesteps
            start_idx = 0
            end_idx = min(9, len(times) - 1)
        
        # Use Rich for better formatting
        console = Console()
        
        # Create header info
        console.print()
        console.print("[bold cyan]FlexFlow Data Preview[/bold cyan]")
        console.print(f"[bold]Case:[/bold] {case.case_directory}")
        console.print(f"[bold]Problem:[/bold] {case.problem_name}")
        console.print(f"[bold]Node:[/bold] {node_id}")
        console.print(f"[bold]Time Range:[/bold] {times[start_idx]:.6f} to {times[end_idx]:.6f} s")
        console.print(f"[bold]Steps Shown:[/bold] {end_idx - start_idx + 1}")
        console.print()
        
        # Create data table with Rich
        table = Table(title="Displacement Data", box=box.SIMPLE, 
                     show_header=True, header_style="bold yellow")
        table.add_column("Step", justify="right", style="cyan")
        table.add_column("Time (s)", justify="right", style="white")
        table.add_column("dx", justify="right", style="green")
        table.add_column("dy", justify="right", style="green")
        table.add_column("dz", justify="right", style="green")
        table.add_column("Magnitude", justify="right", style="magenta")
        
        # Add data rows
        for step in range(start_idx, end_idx + 1):
            table.add_row(
                str(step),
                f"{times[step]:.6f}",
                f"{dx[step]:.6e}",
                f"{dy[step]:.6e}",
                f"{dz[step]:.6e}",
                f"{magnitude[step]:.6e}"
            )
        
        console.print(table)
        console.print()
        
        logger.success("Preview command completed")
        
    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
