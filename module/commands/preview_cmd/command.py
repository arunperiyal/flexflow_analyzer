"""
Preview command implementation
"""

import sys
import numpy as np
from ...core.case import FlexFlowCase
from ...utils.logger import Logger
from ...utils.colors import Colors


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
        
        # Print header
        print(f"\n{Colors.bold(Colors.cyan('FlexFlow Data Preview'))}")
        print(f"{Colors.bold('Case Directory:')} {case.case_directory}")
        print(f"{Colors.bold('Problem Name:')} {case.problem_name}")
        print(f"{Colors.bold('Node:')} {node_id}")
        print(f"{Colors.bold('Time Range:')} {times[start_idx]:.6f} to {times[end_idx]:.6f}")
        print(f"{Colors.bold('Total Steps Shown:')} {end_idx - start_idx + 1}")
        
        # Print table header
        print(f"\n{Colors.bold(Colors.yellow('Displacement Data:'))}")
        print(f"{'Step':<8} {'Time':<15} {'dx':<18} {'dy':<18} {'dz':<18} {'Magnitude':<18}")
        print("-" * 95)
        
        # Print data rows
        for step in range(start_idx, end_idx + 1):
            print(f"{step:<8} {times[step]:<15.6f} {dx[step]:<18.6e} {dy[step]:<18.6e} "
                  f"{dz[step]:<18.6e} {magnitude[step]:<18.6e}")
        
        print()
        logger.success("Preview command completed")
        
    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
