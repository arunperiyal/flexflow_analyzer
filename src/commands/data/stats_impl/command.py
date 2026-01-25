"""
Statistics command implementation
"""

import sys
import numpy as np
from ....core.case import FlexFlowCase
from ....utils.logger import Logger
from ....utils.colors import Colors


def print_statistics_table(title, stats_dict):
    """
    Print statistics in a formatted table.
    
    Parameters:
    -----------
    title : str
        Table title
    stats_dict : dict
        Dictionary with component names as keys and their statistics as values
    """
    print(f"\n{Colors.bold(Colors.yellow(title))}")
    print(f"{'Component':<15} {'Mean':>15} {'Std Dev':>15} {'Min':>15} {'Max':>15} {'Range':>15}")
    print("-" * 95)
    
    for component, stats in stats_dict.items():
        print(f"{component:<15} {stats['mean']:>15.6e} {stats['std']:>15.6e} "
              f"{stats['min']:>15.6e} {stats['max']:>15.6e} {stats['range']:>15.6e}")


def execute_statistics(args):
    """
    Execute the statistics command
    
    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    """
    from .help_messages import print_statistics_help
    
    # Show help if no case directory provided
    if not args.case:
        print_statistics_help()
        return
    
    logger = Logger(verbose=args.verbose)
    
    try:
        # Load case
        logger.info(f"Loading case from: {args.case}")
        case = FlexFlowCase(args.case, verbose=args.verbose)
        
        # Print header
        print(f"\n{Colors.bold(Colors.cyan('FlexFlow Case Statistics'))}")
        print(f"{Colors.bold('Case Directory:')} {case.case_directory}")
        print(f"{Colors.bold('Problem Name:')} {case.problem_name}")
        
        if args.node is not None:
            print(f"{Colors.bold('Node:')} {args.node}")
        else:
            print(f"{Colors.bold('Scope:')} All nodes")
        
        # Calculate and display statistics for OTHD data (displacements)
        othd_files = case.find_othd_files()
        if len(othd_files) > 0:
            reader = case.othd_reader
            
            if args.node is not None:
                # Statistics for specific node
                if args.node >= reader.num_nodes:
                    logger.error(f"Node {args.node} does not exist. Available nodes: 0-{reader.num_nodes-1}")
                    sys.exit(1)
                
                print(f"\n{Colors.bold(Colors.green('DISPLACEMENT DATA (OTHD)'))}")
                print(f"Total Timesteps: {len(reader.times)}")
                
                # Get displacement data for this node
                node_data = reader.get_node_displacements(args.node)
                
                stats = {
                    'dx': {
                        'mean': np.mean(node_data['dx']),
                        'std': np.std(node_data['dx']),
                        'min': np.min(node_data['dx']),
                        'max': np.max(node_data['dx']),
                        'range': np.max(node_data['dx']) - np.min(node_data['dx'])
                    },
                    'dy': {
                        'mean': np.mean(node_data['dy']),
                        'std': np.std(node_data['dy']),
                        'min': np.min(node_data['dy']),
                        'max': np.max(node_data['dy']),
                        'range': np.max(node_data['dy']) - np.min(node_data['dy'])
                    },
                    'dz': {
                        'mean': np.mean(node_data['dz']),
                        'std': np.std(node_data['dz']),
                        'min': np.min(node_data['dz']),
                        'max': np.max(node_data['dz']),
                        'range': np.max(node_data['dz']) - np.min(node_data['dz'])
                    },
                    'magnitude': {
                        'mean': np.mean(node_data['magnitude']),
                        'std': np.std(node_data['magnitude']),
                        'min': np.min(node_data['magnitude']),
                        'max': np.max(node_data['magnitude']),
                        'range': np.max(node_data['magnitude']) - np.min(node_data['magnitude'])
                    }
                }
                
                print_statistics_table("Displacement Statistics", stats)
                
            else:
                # Statistics for all nodes
                print(f"\n{Colors.bold(Colors.green('DISPLACEMENT DATA (OTHD)'))}")
                print(f"Total Nodes: {reader.num_nodes}")
                print(f"Total Timesteps: {len(reader.times)}")
                
                # Collect all displacement data
                all_dx, all_dy, all_dz = [], [], []
                for (step, node), disp in reader.displacements.items():
                    all_dx.append(disp[0])
                    all_dy.append(disp[1])
                    all_dz.append(disp[2])
                
                all_dx = np.array(all_dx)
                all_dy = np.array(all_dy)
                all_dz = np.array(all_dz)
                all_mag = np.sqrt(all_dx**2 + all_dy**2 + all_dz**2)
                
                stats = {
                    'dx': {
                        'mean': np.mean(all_dx),
                        'std': np.std(all_dx),
                        'min': np.min(all_dx),
                        'max': np.max(all_dx),
                        'range': np.max(all_dx) - np.min(all_dx)
                    },
                    'dy': {
                        'mean': np.mean(all_dy),
                        'std': np.std(all_dy),
                        'min': np.min(all_dy),
                        'max': np.max(all_dy),
                        'range': np.max(all_dy) - np.min(all_dy)
                    },
                    'dz': {
                        'mean': np.mean(all_dz),
                        'std': np.std(all_dz),
                        'min': np.min(all_dz),
                        'max': np.max(all_dz),
                        'range': np.max(all_dz) - np.min(all_dz)
                    },
                    'magnitude': {
                        'mean': np.mean(all_mag),
                        'std': np.std(all_mag),
                        'min': np.min(all_mag),
                        'max': np.max(all_mag),
                        'range': np.max(all_mag) - np.min(all_mag)
                    }
                }
                
                print_statistics_table("Displacement Statistics", stats)
        
        # Calculate and display statistics for OISD data (forces/tractions)
        oisd_files = case.find_oisd_files()
        if len(oisd_files) > 0:
            reader = case.oisd_reader
            
            print(f"\n{Colors.bold(Colors.green('FORCE/TRACTION DATA (OISD)'))}")
            print(f"Total Timesteps: {len(reader.times)}")
            
            # Note: OISD data is not per-node, so --node flag doesn't apply here
            if args.node is not None:
                print(f"{Colors.yellow('Note: OISD data is integrated over the surface, not per-node.')}")
            
            # Collect traction data
            if reader.tot_trac:
                all_tx, all_ty, all_tz = [], [], []
                for step, trac in reader.tot_trac.items():
                    all_tx.append(trac[0])
                    all_ty.append(trac[1])
                    all_tz.append(trac[2])
                
                all_tx = np.array(all_tx)
                all_ty = np.array(all_ty)
                all_tz = np.array(all_tz)
                all_mag = np.sqrt(all_tx**2 + all_ty**2 + all_tz**2)
                
                trac_stats = {
                    'tx': {
                        'mean': np.mean(all_tx),
                        'std': np.std(all_tx),
                        'min': np.min(all_tx),
                        'max': np.max(all_tx),
                        'range': np.max(all_tx) - np.min(all_tx)
                    },
                    'ty': {
                        'mean': np.mean(all_ty),
                        'std': np.std(all_ty),
                        'min': np.min(all_ty),
                        'max': np.max(all_ty),
                        'range': np.max(all_ty) - np.min(all_ty)
                    },
                    'tz': {
                        'mean': np.mean(all_tz),
                        'std': np.std(all_tz),
                        'min': np.min(all_tz),
                        'max': np.max(all_tz),
                        'range': np.max(all_tz) - np.min(all_tz)
                    },
                    'magnitude': {
                        'mean': np.mean(all_mag),
                        'std': np.std(all_mag),
                        'min': np.min(all_mag),
                        'max': np.max(all_mag),
                        'range': np.max(all_mag) - np.min(all_mag)
                    }
                }
                
                print_statistics_table("Total Traction Statistics", trac_stats)
            
            # Collect moment data
            if reader.tot_moment:
                all_mx, all_my, all_mz = [], [], []
                for step, moment in reader.tot_moment.items():
                    all_mx.append(moment[0])
                    all_my.append(moment[1])
                    all_mz.append(moment[2])
                
                all_mx = np.array(all_mx)
                all_my = np.array(all_my)
                all_mz = np.array(all_mz)
                all_mag = np.sqrt(all_mx**2 + all_my**2 + all_mz**2)
                
                moment_stats = {
                    'mx': {
                        'mean': np.mean(all_mx),
                        'std': np.std(all_mx),
                        'min': np.min(all_mx),
                        'max': np.max(all_mx),
                        'range': np.max(all_mx) - np.min(all_mx)
                    },
                    'my': {
                        'mean': np.mean(all_my),
                        'std': np.std(all_my),
                        'min': np.min(all_my),
                        'max': np.max(all_my),
                        'range': np.max(all_my) - np.min(all_my)
                    },
                    'mz': {
                        'mean': np.mean(all_mz),
                        'std': np.std(all_mz),
                        'min': np.min(all_mz),
                        'max': np.max(all_mz),
                        'range': np.max(all_mz) - np.min(all_mz)
                    },
                    'magnitude': {
                        'mean': np.mean(all_mag),
                        'std': np.std(all_mag),
                        'min': np.min(all_mag),
                        'max': np.max(all_mag),
                        'range': np.max(all_mag) - np.min(all_mag)
                    }
                }
                
                print_statistics_table("Total Moment Statistics", moment_stats)
            
            # Collect pressure data
            if reader.ave_pres:
                all_pres = np.array([reader.ave_pres[step] for step in sorted(reader.ave_pres.keys())])
                
                pres_stats = {
                    'pressure': {
                        'mean': np.mean(all_pres),
                        'std': np.std(all_pres),
                        'min': np.min(all_pres),
                        'max': np.max(all_pres),
                        'range': np.max(all_pres) - np.min(all_pres)
                    }
                }
                
                print_statistics_table("Average Pressure Statistics", pres_stats)
        
        print()
        logger.success("Statistics command completed")
        
    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
