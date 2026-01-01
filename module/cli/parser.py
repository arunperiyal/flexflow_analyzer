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
    parser.add_argument('--completion', choices=['bash', 'zsh', 'fish'],
                       help='Generate shell completion script')
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
    info_parser.add_argument('-v', '--verbose', action='store_true',
                            help='Enable verbose output')
    info_parser.add_argument('-h', '--help', action='store_true',
                            help='Show help for info command')
    info_parser.add_argument('--examples', action='store_true',
                            help='Show usage examples')
    
    # New command
    new_parser = subparsers.add_parser('new', add_help=False,
                                       help='Create a new case directory')
    new_parser.add_argument('case_name', nargs='?', help='Name of the new case directory')
    new_parser.add_argument('--ref-case', dest='ref_case',
                           help='Path to reference case directory (default: ./refCase)')
    new_parser.add_argument('--problem-name', dest='problem_name',
                           help='Override problem name in simflow.config')
    new_parser.add_argument('--np', type=int, default=36,
                           help='Number of processors (default: 36)')
    new_parser.add_argument('--freq', type=int, default=50,
                           help='Output frequency (default: 50)')
    new_parser.add_argument('--force', action='store_true',
                           help='Overwrite existing directory if it exists')
    new_parser.add_argument('-v', '--verbose', action='store_true',
                           help='Enable verbose output')
    new_parser.add_argument('-h', '--help', action='store_true',
                           help='Show help for new command')
    new_parser.add_argument('--examples', action='store_true',
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
    compare_parser.add_argument('--output', help='Output file path (for combined plot mode)')
    compare_parser.add_argument('--no-display', action='store_true',
                               help="Don't display plot")
    compare_parser.add_argument('--subplot', 
                               help='Subplot layout as rows,columns (e.g., "2,2" for 2x2 grid). Each case will be plotted in a separate subplot')
    compare_parser.add_argument('--separate', action='store_true',
                               help='Create separate plot files for each case (overrides --subplot)')
    compare_parser.add_argument('--output-prefix', 
                               help='Output file prefix when using --separate (e.g., "comparison_")')
    compare_parser.add_argument('--output-format', 
                               help='Output file format when using --separate (e.g., "png", "pdf", "svg")')
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
    
    # Docs command
    docs_parser = subparsers.add_parser('docs', add_help=False,
                                       help='View documentation')
    docs_parser.add_argument('topic', nargs='?',
                            help='Documentation topic (main, plot, compare, info, template)')
    docs_parser.add_argument('-h', '--help', action='store_true',
                            help='Show help for docs command')
    
    # Statistics command
    statistics_parser = subparsers.add_parser('statistics', add_help=False,
                                             help='Show statistical analysis of data')
    statistics_parser.add_argument('case', nargs='?', help='Case directory path')
    statistics_parser.add_argument('--node', type=int,
                                   help='Node ID to analyze (default: all nodes)')
    statistics_parser.add_argument('-v', '--verbose', action='store_true',
                                   help='Enable verbose output')
    statistics_parser.add_argument('-h', '--help', action='store_true',
                                   help='Show help for statistics command')
    statistics_parser.add_argument('--examples', action='store_true',
                                   help='Show usage examples')
    
    # Preview command
    preview_parser = subparsers.add_parser('preview', add_help=False,
                                          help='Preview displacement data')
    preview_parser.add_argument('case', nargs='?', help='Case directory path')
    preview_parser.add_argument('--node', type=int,
                               help='Node ID to preview (default: 0)')
    preview_parser.add_argument('--start-time', type=float,
                               help='Start time for preview')
    preview_parser.add_argument('--end-time', type=float,
                               help='End time for preview')
    preview_parser.add_argument('-v', '--verbose', action='store_true',
                               help='Enable verbose output')
    preview_parser.add_argument('-h', '--help', action='store_true',
                               help='Show help for preview command')
    preview_parser.add_argument('--examples', action='store_true',
                               help='Show usage examples')
    
    # Tecplot command
    tecplot_parser = subparsers.add_parser('tecplot', add_help=False,
                                          help='Work with Tecplot PLT files')
    tecplot_subparsers = tecplot_parser.add_subparsers(dest='tecplot_subcommand',
                                                       help='Tecplot subcommands')
    
    # tecplot info
    tecplot_info_parser = tecplot_subparsers.add_parser('info', add_help=False,
                                                        help='Show PLT file information')
    tecplot_info_parser.add_argument('case', nargs='?', help='Case directory path')
    tecplot_info_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
    tecplot_info_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for info command')
    
    # Filtering flags for sections to display
    tecplot_info_parser.add_argument('--basic', action='store_true',
                                    help='Show only basic file information')
    tecplot_info_parser.add_argument('--variables', action='store_true',
                                    help='Show only variables section')
    tecplot_info_parser.add_argument('--zones', action='store_true',
                                    help='Show only zone information')
    tecplot_info_parser.add_argument('--checks', action='store_true',
                                    help='Show only consistency checks')
    tecplot_info_parser.add_argument('--stats', action='store_true',
                                    help='Show only data statistics')
    
    # Additional options
    tecplot_info_parser.add_argument('--detailed', action='store_true',
                                    help='Show detailed statistics (min/max for all variables)')
    tecplot_info_parser.add_argument('--sample-file', type=int, metavar='STEP',
                                    help='Analyze specific timestep file (default: first)')
    
    # tecplot extract
    tecplot_extract_parser = tecplot_subparsers.add_parser('extract', add_help=False,
                                                           help='Extract data from PLT files')
    tecplot_extract_parser.add_argument('case', nargs='?', help='Case directory path')
    tecplot_extract_parser.add_argument('-v', '--verbose', action='store_true',
                                       help='Enable verbose output')
    tecplot_extract_parser.add_argument('-h', '--help', action='store_true',
                                       help='Show help for extract command')
    tecplot_extract_parser.add_argument('--variables', type=str,
                                       help='Comma-separated list of variables to extract (e.g., Y,U,V)')
    tecplot_extract_parser.add_argument('--zone', type=str,
                                       help='Zone name to extract from (e.g., FIELD)')
    tecplot_extract_parser.add_argument('--timestep', type=int,
                                       help='Timestep to extract (e.g., 1000)')
    tecplot_extract_parser.add_argument('--output-file', type=str,
                                       help='Output CSV file path (if not provided, shows preview)')
    tecplot_extract_parser.add_argument('--xmin', type=float,
                                       help='Minimum X coordinate for subdomain extraction')
    tecplot_extract_parser.add_argument('--xmax', type=float,
                                       help='Maximum X coordinate for subdomain extraction')
    tecplot_extract_parser.add_argument('--ymin', type=float,
                                       help='Minimum Y coordinate for subdomain extraction')
    tecplot_extract_parser.add_argument('--ymax', type=float,
                                       help='Maximum Y coordinate for subdomain extraction')
    tecplot_extract_parser.add_argument('--zmin', type=float,
                                       help='Minimum Z coordinate for subdomain extraction')
    tecplot_extract_parser.add_argument('--zmax', type=float,
                                       help='Maximum Z coordinate for subdomain extraction')
    
    # Add main tecplot help flags
    tecplot_parser.add_argument('-v', '--verbose', action='store_true',
                               help='Enable verbose output')
    tecplot_parser.add_argument('-h', '--help', action='store_true',
                               help='Show help for tecplot command')
    tecplot_parser.add_argument('--examples', action='store_true',
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
