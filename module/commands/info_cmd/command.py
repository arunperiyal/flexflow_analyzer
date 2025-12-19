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
        
        logger.success("Info command completed")
        
    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
