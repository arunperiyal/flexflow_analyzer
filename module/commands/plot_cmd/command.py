"""
Plot command implementation
"""

import sys
import os
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager
import yaml

from ...core.case import FlexFlowCase
from ...utils.logger import Logger
from ...utils.colors import Colors
from ...utils import plot_utils


def ensure_ms_fonts_loaded():
    """
    Ensure Microsoft fonts are loaded into matplotlib's font manager.
    This is needed because matplotlib doesn't always pick them up from fontconfig.
    """
    ms_fonts_dir = '/usr/share/fonts/truetype/msttcorefonts/'
    
    if not os.path.exists(ms_fonts_dir):
        return  # MS fonts not installed
    
    # Check if Times New Roman is already loaded
    times_fonts = [f.name for f in font_manager.fontManager.ttflist if 'Times New Roman' in f.name]
    if times_fonts:
        return  # Already loaded
    
    # Add MS fonts to matplotlib
    try:
        for font_file in os.listdir(ms_fonts_dir):
            if font_file.endswith('.ttf'):
                font_path = os.path.join(ms_fonts_dir, font_file)
                font_manager.fontManager.addfont(font_path)
    except Exception:
        pass  # Silently fail if can't add fonts


def parse_plot_style(style_str):
    """
    Parse plot style string.
    
    Format: color,width,linestyle,marker
    Example: 'red,2,--,o'
    
    Returns dict with style parameters
    """
    if not style_str:
        return {}
    
    parts = style_str.split(',')
    style = {}
    
    if len(parts) > 0 and parts[0].strip():
        style['color'] = parts[0].strip()
    if len(parts) > 1 and parts[1].strip():
        try:
            style['linewidth'] = float(parts[1].strip())
        except ValueError:
            pass
    if len(parts) > 2 and parts[2].strip():
        style['linestyle'] = parts[2].strip()
    if len(parts) > 3 and parts[3].strip():
        marker = parts[3].strip()
        if marker.lower() != 'none':
            style['marker'] = marker
    
    return style


def parse_multiple_plot_styles(style_str):
    """
    Parse multiple plot styles separated by |
    
    Format: "style1|style2|style3|..."
    Example: "blue,2,-,o|red,2,--,s|green,2,-.,^"
    
    Returns list of style dicts
    """
    if not style_str:
        return []
    
    styles = []
    for single_style in style_str.split('|'):
        if single_style.strip():
            styles.append(parse_plot_style(single_style.strip()))
    
    return styles


def parse_legend_style(style_str):
    """
    Parse legend style string.
    
    Format: position|fontsize|frameon|latex
    Examples:
        "best|12|on|False"
        "upper right|14|off|True"
        "northeast|12|on|False"
    
    Returns dict with legend parameters
    """
    if not style_str:
        return {}
    
    # Location mappings (shorthand to matplotlib)
    location_map = {
        'north': 'upper center',
        'south': 'lower center',
        'east': 'center right',
        'west': 'center left',
        'northeast': 'upper right',
        'northwest': 'upper left',
        'southeast': 'lower right',
        'southwest': 'lower left',
        'ne': 'upper right',
        'nw': 'upper left',
        'se': 'lower right',
        'sw': 'lower left',
    }
    
    parts = style_str.split('|')
    style = {}
    
    # Position
    if len(parts) > 0 and parts[0].strip():
        loc = parts[0].strip().lower()
        style['loc'] = location_map.get(loc, loc)
    
    # Font size
    if len(parts) > 1 and parts[1].strip():
        try:
            style['fontsize'] = int(parts[1].strip())
        except ValueError:
            pass
    
    # Frame on/off
    if len(parts) > 2 and parts[2].strip():
        frame = parts[2].strip().lower()
        if frame in ['on', 'true', '1', 'yes']:
            style['frameon'] = True
        elif frame in ['off', 'false', '0', 'no']:
            style['frameon'] = False
    
    # LaTeX rendering
    if len(parts) > 3 and parts[3].strip():
        latex = parts[3].strip().lower()
        if latex in ['true', '1', 'yes', 'latex']:
            style['usetex'] = True
        else:
            style['usetex'] = False
    
    return style


def parse_label(label_str):
    """
    Parse enhanced label string with format: text|fontsize|latex
    
    Format: "<text>|<fontsize>|<latex>"
    Examples: 
        "Time (s)|14|False"
        "Displacement ($m$)|12|True"
        "Temperature|16"
        "Velocity"
    
    Returns dict with text, fontsize, and latex flag
    """
    if not label_str:
        return None
    
    parts = label_str.split('|')
    result = {
        'text': parts[0].strip() if len(parts) > 0 else '',
        'fontsize': None,
        'usetex': False
    }
    
    # Parse fontsize
    if len(parts) > 1 and parts[1].strip():
        try:
            result['fontsize'] = int(parts[1].strip())
        except ValueError:
            pass
    
    # Parse latex flag
    if len(parts) > 2 and parts[2].strip():
        latex_flag = parts[2].strip().lower()
        result['usetex'] = latex_flag in ('true', '1', 'yes', 'latex')
    
    return result


def apply_plot_properties(fig, axes, args):
    """Apply plot properties like title, labels with enhanced format support"""
    # Handle both single axis and multiple axes
    if not isinstance(axes, list) and not hasattr(axes, '__iter__'):
        axes = [axes]
    elif hasattr(axes, 'flat'):
        axes = list(axes.flat)
    
    # Legacy fontsize support (will be overridden by label-specific fontsize)
    # Note: fontname is now set before plot creation for proper rendering
    if hasattr(args, 'fontsize') and args.fontsize:
        matplotlib.rc('font', size=args.fontsize)
    
    # Get fontname for explicit setting
    fontname = args.fontname if hasattr(args, 'fontname') and args.fontname else None
    
    # Set font for tick labels if fontname specified
    if fontname:
        for ax in axes:
            for label in ax.get_xticklabels() + ax.get_yticklabels():
                label.set_fontfamily(fontname)
    
    # Parse and set title (on first axis)
    if args.title and len(axes) > 0:
        title_info = parse_label(args.title)
        if title_info:
            # Enable LaTeX rendering if requested
            if title_info['usetex']:
                plt.rc('text', usetex=True)
            
            title_kwargs = {}
            if title_info['fontsize']:
                title_kwargs['fontsize'] = title_info['fontsize']
            if fontname:
                title_kwargs['fontfamily'] = fontname
            
            axes[0].set_title(title_info['text'], **title_kwargs)
    
    # Parse and set xlabel (on last axis)
    if args.xlabel and len(axes) > 0:
        xlabel_info = parse_label(args.xlabel)
        if xlabel_info:
            if xlabel_info['usetex']:
                plt.rc('text', usetex=True)
            
            xlabel_kwargs = {}
            if xlabel_info['fontsize']:
                xlabel_kwargs['fontsize'] = xlabel_info['fontsize']
            if fontname:
                xlabel_kwargs['fontfamily'] = fontname
            
            axes[-1].set_xlabel(xlabel_info['text'], **xlabel_kwargs)
    
    # Parse and set ylabel (on all axes)
    if args.ylabel:
        ylabel_info = parse_label(args.ylabel)
        if ylabel_info:
            if ylabel_info['usetex']:
                plt.rc('text', usetex=True)
            
            ylabel_kwargs = {}
            if ylabel_info['fontsize']:
                ylabel_kwargs['fontsize'] = ylabel_info['fontsize']
            if fontname:
                ylabel_kwargs['fontfamily'] = fontname
            
            for ax in axes:
                ax.set_ylabel(ylabel_info['text'], **ylabel_kwargs)
    
    # Set legend if provided
    if hasattr(args, 'legend') and args.legend and len(axes) > 0:
        legend_info = parse_label(args.legend)
        if legend_info:
            axes[0].legend([legend_info['text']])


def execute_plot(args):
    """
    Execute the plot command
    
    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    """
    from .help_messages import print_plot_help
    
    # Set PDF font embedding to Type 42 (TrueType) for better quality
    # This embeds actual TrueType fonts instead of bitmaps
    if hasattr(args, 'output') and args.output and args.output.lower().endswith('.pdf'):
        plt.rcParams['pdf.fonttype'] = 42  # TrueType
        plt.rcParams['ps.fonttype'] = 42   # For EPS as well
    
    # Show help if no arguments provided
    if not args.input_file and not args.case:
        print_plot_help()
        return
    
    logger = Logger(verbose=args.verbose)
    
    # Use non-interactive backend if no display or output-only mode
    if args.no_display or args.output:
        matplotlib.use('Agg')
    
    try:
        # Check if using input file
        if args.input_file:
            logger.info(f"Loading configuration from: {args.input_file}")
            with open(args.input_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Execute plot from YAML config
            execute_plot_from_yaml(config, args)
            return
        
        # Validate required arguments for direct command
        if not args.case:
            print(f"{Colors.red('Error:')} case_directory is required when not using --input-file", 
                  file=sys.stderr)
            sys.exit(1)
        
        if not args.data_type:
            print(f"{Colors.red('Error:')} --data-type is required", file=sys.stderr)
            sys.exit(1)
        
        if not args.component:
            print(f"{Colors.red('Error:')} --component is required", file=sys.stderr)
            sys.exit(1)
        
        if args.data_type == 'displacement' and args.node is None:
            print(f"{Colors.red('Error:')} --node is required for displacement data", file=sys.stderr)
            sys.exit(1)
        
        # Ensure MS fonts are loaded (if installed)
        ensure_ms_fonts_loaded()
        
        # Set font before creating plots
        if hasattr(args, 'fontname') and args.fontname:
            matplotlib.rc('font', family=args.fontname)
            
            # Configure mathtext to use serif fonts matching Times New Roman
            # When using $math$ mode, matplotlib uses mathtext which has its own font config
            if 'Times' in args.fontname or args.fontname == 'serif':
                matplotlib.rc('mathtext', fontset='stix')  # STIX fonts are Times-compatible
                # Alternative: 'cm' (Computer Modern), 'stix', 'stixsans', 'dejavusans', 'dejavuserif'
            
            logger.info(f"Using font: {args.fontname}")
        
        # Load case
        logger.info(f"Loading case from: {args.case}")
        case = FlexFlowCase(args.case, verbose=args.verbose)
        
        # Parse plot style
        plot_style = parse_plot_style(args.plot_style)
        
        # Parse legend style
        legend_style = {}
        if hasattr(args, 'legend_style') and args.legend_style:
            legend_style = parse_legend_style(args.legend_style)
        
        # Determine plot type
        plot_type = args.plot_type if args.plot_type else 'time'
        
        # Generate plot based on data type and plot type
        if args.data_type == 'displacement':
            fig, axes = generate_displacement_plot(case, args, plot_type, plot_style, logger, legend_style)
        elif args.data_type == 'force':
            fig, axes = generate_force_plot(case, args, plot_type, plot_style, logger)
        elif args.data_type == 'moment':
            fig, axes = generate_moment_plot(case, args, plot_style, logger)
        elif args.data_type == 'pressure':
            fig, axes = generate_pressure_plot(case, args, plot_style, logger)
        else:
            print(f"{Colors.red('Error:')} Invalid data type: {args.data_type}", file=sys.stderr)
            sys.exit(1)
        
        # Apply plot properties
        apply_plot_properties(fig, axes, args)
        
        # Save or display
        if args.output:
            logger.info(f"Saving plot to: {args.output}")
            fig.savefig(args.output, dpi=300, bbox_inches='tight')
            logger.success(f"Plot saved to {args.output}")
        
        # Only show plot if not in output-only mode and display is not disabled
        if not args.output and not args.no_display:
            plt.show()
        
        logger.success("Plot command completed")
        
    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def generate_displacement_plot(case, args, plot_type, plot_style, logger, legend_style=None):
    """Generate displacement plot"""
    if not case.othd_reader:
        raise ValueError("No OTHD data available")
    
    # Handle component as list (new format) or single value (old format)
    component = args.component
    if isinstance(component, list):
        component_single = component[0] if component else None
    else:
        component_single = component
    
    logger.info(f"Generating {plot_type} plot for node {args.node}, component: {component}")
    
    if plot_type == 'time':
        fig, axes = plot_utils.plot_node_displacements(
            case.othd_reader, 
            args.node, 
            component=component_single,
            use_index=False,
            plot_style=plot_style,
            start_time=args.start_time,
            end_time=args.end_time
        )
    elif plot_type == 'fft':
        fig, axes = plot_utils.plot_fft(
            case.othd_reader,
            node_id=args.node,
            component=component_single,
            plot_style=plot_style,
            start_time=args.start_time,
            end_time=args.end_time
        )
    elif plot_type == 'traj2d':
        # Handle --component x y OR --traj-x/--traj-y
        if args.component and len(args.component) >= 2:
            comp_x = args.component[0]
            comp_y = args.component[1]
        else:
            comp_x = args.traj_x if args.traj_x else 'x'
            comp_y = args.traj_y if args.traj_y else 'y'
        
        fig, axes = plot_utils.plot_trajectory_2d(
            case.othd_reader,
            node_id=args.node,
            comp_x=comp_x,
            comp_y=comp_y,
            plot_style=plot_style,
            start_time=args.start_time,
            end_time=args.end_time,
            legend_style=legend_style
        )
    elif plot_type == 'traj3d':
        # Handle --component x y z OR --traj-x/--traj-y/--traj-z
        if args.component and len(args.component) >= 3:
            comp_x = args.component[0]
            comp_y = args.component[1]
            comp_z = args.component[2]
        else:
            comp_x = args.traj_x if args.traj_x else 'x'
            comp_y = args.traj_y if args.traj_y else 'y'
            comp_z = args.traj_z if args.traj_z else 'z'
        
        fig, axes = plot_utils.plot_trajectory_3d(
            case.othd_reader,
            node_id=args.node,
            comp_x=comp_x,
            comp_y=comp_y,
            comp_z=comp_z,
            plot_style=plot_style,
            start_time=args.start_time,
            end_time=args.end_time,
            legend_style=legend_style
        )
    else:
        raise ValueError(f"Invalid plot type: {plot_type}")
    
    return fig, axes


def generate_force_plot(case, args, plot_type, plot_style, logger):
    """Generate force plot"""
    if not case.oisd_reader:
        raise ValueError("No OISD data available")
    
    logger.info(f"Generating force plot, component: {args.component}")
    
    if plot_type == 'time':
        fig, axes = plot_utils.plot_force_data(
            case.oisd_reader,
            component=args.component,
            use_index=False,
            plot_style=plot_style,
            start_time=args.start_time,
            end_time=args.end_time
        )
    else:
        raise ValueError(f"Plot type '{plot_type}' not supported for force data")
    
    return fig, axes


def generate_moment_plot(case, args, plot_style, logger):
    """Generate moment plot"""
    if not case.oisd_reader:
        raise ValueError("No OISD data available")
    
    logger.info(f"Generating moment plot, component: {args.component}")
    
    fig, axes = plot_utils.plot_moment_data(
        case.oisd_reader,
        component=args.component,
        use_index=False
    )
    
    return fig, axes


def generate_pressure_plot(case, args, plot_style, logger):
    """Generate pressure plot"""
    if not case.oisd_reader:
        raise ValueError("No OISD data available")
    
    logger.info("Generating pressure plot")
    
    fig, axes = plot_utils.plot_pressure_data(
        case.oisd_reader,
        use_index=False
    )
    
    return fig, axes


def execute_plot_from_yaml(config, args):
    """Execute plot command from YAML configuration"""
    logger = Logger(verbose=args.verbose)
    
    # Extract configuration
    case_dir = config.get('case_dir') or config.get('case')
    node = config.get('node')
    data_type = config.get('data_type')
    component = config.get('component')
    plot_type = config.get('plot_type', 'time')
    
    # Load case
    logger.info(f"Loading case from: {case_dir}")
    case = FlexFlowCase(case_dir, verbose=args.verbose)
    
    # Parse plot style from config
    plot_style = {}
    if 'plot_style' in config:
        ps = config['plot_style']
        if isinstance(ps, dict):
            plot_style = ps
        elif isinstance(ps, str):
            plot_style = parse_plot_style(ps)
    
    # Extract time range parameters
    start_time = None
    end_time = None
    
    # Check for direct start_time/end_time
    if 'start_time' in config:
        start_time = config['start_time']
    if 'end_time' in config:
        end_time = config['end_time']
    
    # Check for time_range section
    if 'time_range' in config:
        time_range = config['time_range']
        if 'start_time' in time_range:
            start_time = time_range['start_time']
        if 'end_time' in time_range:
            end_time = time_range['end_time']
        
        # Convert step IDs (tsId) to time if needed
        # Note: tsId starts from 1, not 0. Time = tsId * dt
        if 'start_step' in time_range and start_time is None:
            start_step = time_range['start_step']
            if start_step > 0 and case.othd_reader and hasattr(case.othd_reader, 'time_increment'):
                start_time = start_step * case.othd_reader.time_increment
        
        if 'end_step' in time_range and end_time is None:
            end_step = time_range['end_step']
            if end_step > 0 and case.othd_reader and hasattr(case.othd_reader, 'time_increment'):
                end_time = end_step * case.othd_reader.time_increment
    
    # Generate plot
    if data_type == 'displacement':
        if not node:
            raise ValueError("node is required for displacement data")
        
        if plot_type == 'time':
            fig, axes = plot_utils.plot_node_displacements(
                case.othd_reader, node, component=component,
                use_index=False, plot_style=plot_style,
                start_time=start_time, end_time=end_time
            )
        elif plot_type == 'fft':
            fig, axes = plot_utils.plot_fft(
                case.othd_reader, node_id=node,
                component=component, plot_style=plot_style,
                start_time=start_time, end_time=end_time
            )
        elif plot_type == 'traj2d':
            comp_x = config.get('traj_x', 'x')
            comp_y = config.get('traj_y', 'y')
            fig, axes = plot_utils.plot_trajectory_2d(
                case.othd_reader, node_id=node,
                comp_x=comp_x, comp_y=comp_y, plot_style=plot_style,
                start_time=start_time, end_time=end_time
            )
        elif plot_type == 'traj3d':
            comp_x = config.get('traj_x', 'x')
            comp_y = config.get('traj_y', 'y')
            comp_z = config.get('traj_z', 'z')
            fig, axes = plot_utils.plot_trajectory_3d(
                case.othd_reader, node_id=node,
                comp_x=comp_x, comp_y=comp_y, comp_z=comp_z,
                plot_style=plot_style,
                start_time=start_time, end_time=end_time
            )
    elif data_type == 'force':
        fig, axes = plot_utils.plot_force_data(
            case.oisd_reader, component=component,
            use_index=False, plot_style=plot_style,
            start_time=start_time, end_time=end_time
        )
    else:
        raise ValueError(f"Unsupported data type: {data_type}")
    
    # Apply properties from config
    # Check both direct config and plot_properties section
    plot_props = config.get('plot_properties', {})
    
    title = config.get('title') or plot_props.get('title')
    if title and axes:
        if isinstance(axes, list):
            axes[0].set_title(title)
        else:
            axes.set_title(title)
    
    xlabel = config.get('xlabel') or plot_props.get('xlabel')
    if xlabel and axes:
        if isinstance(axes, list):
            axes[-1].set_xlabel(xlabel)
        else:
            axes.set_xlabel(xlabel)
    
    ylabel = config.get('ylabel') or plot_props.get('ylabel')
    if ylabel and axes:
        if isinstance(axes, list):
            for ax in axes:
                ax.set_ylabel(ylabel)
        else:
            axes.set_ylabel(ylabel)
    
    # Save or display
    output_file = config.get('output', args.output)
    if output_file:
        logger.info(f"Saving plot to: {output_file}")
        fig.savefig(output_file, dpi=300, bbox_inches='tight')
        logger.success(f"Plot saved to {output_file}")
    
    # Only show if not in output-only mode and display not disabled
    no_display = args.no_display or config.get('no_display', False)
    if not output_file and not no_display:
        plt.show()
    
    logger.success("Plot command completed")
