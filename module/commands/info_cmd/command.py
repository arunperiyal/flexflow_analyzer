"""
Info command implementation
"""

import sys
from ...core.case import FlexFlowCase
from ...utils.logger import Logger
from ...utils.colors import Colors


def execute_info(args):
    """
    Execute the info command
    
    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    """
    from .help_messages import print_info_help
    
    # Show help if no case directory provided
    if not args.case:
        print_info_help()
        return
    
    logger = Logger(verbose=args.verbose)
    
    try:
        # Load case
        logger.info(f"Loading case from: {args.case}")
        case = FlexFlowCase(args.case, verbose=args.verbose)
        
        if not args.preview:
            # Print case summary (always printed, no verbose check)
            print(f"\n{Colors.bold(Colors.cyan('FlexFlow Case Information'))}")
            print(f"{Colors.bold('Case Directory:')} {case.case_directory}")
            print(f"{Colors.bold('Problem Name:')} {case.problem_name}")
            if hasattr(case, 'time_increment') and case.time_increment:
                print(f"{Colors.bold('Time Increment:')} {case.time_increment}")
            
            # Find OTHD files
            othd_files = case.find_othd_files()
            print(f"\n{Colors.bold(Colors.yellow('OTHD Files:'))} {len(othd_files)} file(s)")
            if len(othd_files) > 0:
                # Load OTHD data to get info
                reader = case.othd_reader
                print(f"  Nodes: {reader.num_nodes}")
                print(f"  Timesteps: {len(reader.times)}")
                if len(reader.times) > 0:
                    print(f"  Time Range: {reader.times[0]:.6f} to {reader.times[-1]:.6f}")
            
            # Find OISD files
            oisd_files = case.find_oisd_files()
            if len(oisd_files) > 0:
                print(f"\n{Colors.bold(Colors.yellow('OISD Files:'))} {len(oisd_files)} file(s)")
                # Load OISD data to get info
                reader = case.oisd_reader
                print(f"  Timesteps: {len(reader.times)}")
                if len(reader.times) > 0:
                    print(f"  Time Range: {reader.times[0]:.6f} to {reader.times[-1]:.6f}")
            
            print()
        else:
            # Preview mode
            if not case.othd_reader:
                print(f"{Colors.red('Error:')} No OTHD data available", file=sys.stderr)
                sys.exit(1)
            
            # Show first 20 timesteps
            total_steps = len(case.othd_reader.times)
            start = 0
            end = min(19, total_steps - 1)  # First 20 timesteps (0-19)
            
            # Print preview header (always printed)
            print(f"\n{Colors.bold(Colors.cyan(f'Data Preview (Steps {start} to {end}):'))}")
            print(f"{'Step':<8} {'Time':<12} {'Node 0 - dx':<15} {'Node 0 - dy':<15} {'Node 0 - dz':<15}")
            print("-" * 65)
            
            # Print data for specified range
            for step in range(start, end + 1):
                if step < total_steps:
                    time_val = case.othd_reader.times[step]
                    if (step, 0) in case.othd_reader.displacements:
                        dx, dy, dz = case.othd_reader.displacements[(step, 0)]
                        print(f"{step:<8} {time_val:<12.6f} {dx:<15.6e} {dy:<15.6e} {dz:<15.6e}")
                    else:
                        print(f"{step:<8} {time_val:<12.6f} {'N/A':<15} {'N/A':<15} {'N/A':<15}")
            
            print()
        
        logger.success("Info command completed")
        
    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
