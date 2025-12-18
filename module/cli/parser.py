"""
Argument parser for FlexFlow CLI
"""

import argparse
import sys


def create_parser():
    """Create and configure the argument parser"""
    
    parser = argparse.ArgumentParser(
        description='FlexFlow - Analyze and visualize FlexFlow simulation data',
        add_help=False
    )
    
    # Global options
    parser.add_argument('--install', action='store_true',
                       help='Install flexflow command globally')
    parser.add_argument('--uninstall', action='store_true',
                       help='Uninstall flexflow command')
    parser.add_argument('--update', action='store_true',
                       help='Update flexflow installation')
    parser.add_argument('--version', action='store_true',
                       help='Show version information')
    parser.add_argument('-h', '--help', action='store_true',
                       help='Show help message')
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Info command
    info_parser = subparsers.add_parser('info', add_help=False,
                                        help='Show case information')
    info_parser.add_argument('case', nargs='?', help='Case directory path')
    info_parser.add_argument('--preview', action='store_true',
                            help='Show first 20 timesteps')
    info_parser.add_argument('-v', '--verbose', action='store_true',
                            help='Enable verbose output')
    info_parser.add_argument('-h', '--help', action='store_true',
                            help='Show help for info command')
    info_parser.add_argument('--examples', action='store_true',
                            help='Show usage examples')
    
    # Plot command
    plot_parser = subparsers.add_parser('plot', add_help=False,
                                       help='Plot simulation data')
    plot_parser.add_argument('case', nargs='?', help='Case directory path')
    plot_parser.add_argument('--node', type=int,
                            help='Node ID to plot')
    plot_parser.add_argument('--data-type', choices=['displacement', 'force', 'moment', 'pressure'],
                            help='Data type to plot')
    plot_parser.add_argument('--component', nargs='+',
                            help='Component to plot (x, y, z, magnitude, all, tx, ty, tz). For trajectories, specify multiple: x y or x y z')
    plot_parser.add_argument('--plot-type', choices=['time', 'fft', 'traj2d', 'traj3d'],
                            help='Plot type (default: time)')
    plot_parser.add_argument('--traj-x', help='X component for trajectory')
    plot_parser.add_argument('--traj-y', help='Y component for trajectory')
    plot_parser.add_argument('--traj-z', help='Z component for trajectory')
    plot_parser.add_argument('--start-time', type=float,
                            help='Start time')
    plot_parser.add_argument('--end-time', type=float,
                            help='End time')
    plot_parser.add_argument('--start-step', type=int,
                            help='Start timestep index')
    plot_parser.add_argument('--end-step', type=int,
                            help='End timestep index')
    plot_parser.add_argument('--plot-style',
                            help='Plot style: color,width,linestyle,marker')
    plot_parser.add_argument('--title', help='Plot title')
    plot_parser.add_argument('--xlabel', help='X-axis label')
    plot_parser.add_argument('--ylabel', help='Y-axis label')
    plot_parser.add_argument('--legend', help='Legend label')
    plot_parser.add_argument('--legend-style', help='Legend style: position|fontsize|frameon|latex (e.g., "best|12|on|False")')
    plot_parser.add_argument('--fontsize', type=int, help='Font size')
    plot_parser.add_argument('--fontname', help='Font name')
    plot_parser.add_argument('--output', help='Output file path')
    plot_parser.add_argument('--no-display', action='store_true',
                            help="Don't display plot (save only)")
    plot_parser.add_argument('--input-file', help='Load config from YAML file')
    plot_parser.add_argument('-v', '--verbose', action='store_true',
                            help='Enable verbose output')
    plot_parser.add_argument('-h', '--help', action='store_true',
                            help='Show help for plot command')
    plot_parser.add_argument('--examples', action='store_true',
                            help='Show usage examples')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', add_help=False,
                                          help='Compare multiple cases')
    compare_parser.add_argument('cases', nargs='*', help='Case directory paths')
    compare_parser.add_argument('--node', type=int,
                               help='Node ID to plot')
    compare_parser.add_argument('--data-type', choices=['displacement', 'force', 'moment', 'pressure'],
                               help='Data type to plot')
    compare_parser.add_argument('--component',
                               help='Component to plot')
    compare_parser.add_argument('--plot-type', choices=['time', 'fft', 'traj2d', 'traj3d'],
                               help='Plot type (default: time)')
    compare_parser.add_argument('--start-time', type=float,
                               help='Start time')
    compare_parser.add_argument('--end-time', type=float,
                               help='End time')
    compare_parser.add_argument('--start-step', type=int,
                               help='Start timestep index')
    compare_parser.add_argument('--end-step', type=int,
                               help='End timestep index')
    compare_parser.add_argument('--title', help='Plot title')
    compare_parser.add_argument('--xlabel', help='X-axis label')
    compare_parser.add_argument('--ylabel', help='Y-axis label')
    compare_parser.add_argument('--legend', help='Legend labels separated by | (e.g., "Case 1|Case 2|Case 3")')
    compare_parser.add_argument('--legend-style', help='Legend style: position|fontsize|frameon|latex (e.g., "best|12|on|False")')
    compare_parser.add_argument('--fontsize', type=int, help='Font size')
    compare_parser.add_argument('--fontname', help='Font name')
    compare_parser.add_argument('--plot-style', 
                               help='Plot styles separated by | (e.g., "blue,2,-,o|red,2,--,s|green,2,-.,^")')
    compare_parser.add_argument('--output', help='Output file path')
    compare_parser.add_argument('--no-display', action='store_true',
                               help="Don't display plot")
    compare_parser.add_argument('--input-file', help='Load config from YAML file')
    compare_parser.add_argument('-v', '--verbose', action='store_true',
                               help='Enable verbose output')
    compare_parser.add_argument('-h', '--help', action='store_true',
                               help='Show help for compare command')
    compare_parser.add_argument('--examples', action='store_true',
                               help='Show usage examples')
    
    # Template command
    template_parser = subparsers.add_parser('template', add_help=False,
                                           help='Generate template YAML files')
    template_parser.add_argument('template_type', nargs='?',
                                choices=['single', 'multi', 'fft'],
                                help='Template type (single, multi, fft)')
    template_parser.add_argument('--output', help='Output file path')
    template_parser.add_argument('--force', action='store_true',
                                help='Overwrite existing file')
    template_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose output')
    template_parser.add_argument('-h', '--help', action='store_true',
                                help='Show help for template command')
    template_parser.add_argument('--examples', action='store_true',
                                help='Show usage examples')
    
    return parser


def parse_args(args=None):
    """
    Parse command line arguments
    
    Parameters:
    -----------
    args : list, optional
        Arguments to parse (defaults to sys.argv[1:])
    
    Returns:
    --------
    argparse.Namespace
        Parsed arguments
    """
    parser = create_parser()
    
    if args is None:
        args = sys.argv[1:]
    
    # Parse arguments
    parsed_args = parser.parse_args(args)
    
    return parsed_args
