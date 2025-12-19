"""
Compare command implementation
"""

import sys
import os
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager
import yaml
import numpy as np

from ...core.case import FlexFlowCase
from ...utils.logger import Logger
from ...utils.colors import Colors


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


def execute_compare(args):
    """
    Execute the compare command
    
    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    """
    from .help_messages import print_compare_help
    
    # Show help if no arguments provided
    if not args.input_file and (not args.cases or len(args.cases) == 0):
        print_compare_help()
        return
    
    logger = Logger(verbose=args.verbose)
    
    # Use non-interactive backend if no display or output-only mode
    if args.no_display or args.output:
        matplotlib.use('Agg')
    
    # Set PDF font embedding to Type 42 (TrueType) for better quality
    if hasattr(args, 'output') and args.output and args.output.lower().endswith('.pdf'):
        plt.rcParams['pdf.fonttype'] = 42  # TrueType
        plt.rcParams['ps.fonttype'] = 42   # For EPS as well
    
    # Ensure MS fonts are loaded (if installed)
    ensure_ms_fonts_loaded()
    
    # Set font family if specified
    if hasattr(args, 'fontname') and args.fontname:
        matplotlib.rc('font', family=args.fontname)
        
        # Configure mathtext to use serif fonts matching Times New Roman
        if 'Times' in args.fontname or args.fontname == 'serif':
            matplotlib.rc('mathtext', fontset='stix')  # STIX fonts are Times-compatible
    
    try:
        # Check if using input file
        if args.input_file:
            logger.info(f"Loading configuration from: {args.input_file}")
            with open(args.input_file, 'r') as f:
                config = yaml.safe_load(f)
            execute_compare_from_yaml(config, args, logger)
            return
        
        # Validate required arguments for direct command
        if not args.cases or len(args.cases) < 2:
            print(f"{Colors.red('Error:')} At least 2 case directories required", file=sys.stderr)
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
        
        # Parse plot styles
        from module.commands.plot_cmd.command import parse_multiple_plot_styles
        plot_styles = parse_multiple_plot_styles(args.plot_style) if hasattr(args, 'plot_style') and args.plot_style else []
        
        # Parse legend labels
        legend_labels = []
        if hasattr(args, 'legend') and args.legend:
            legend_labels = [label.strip() for label in args.legend.split('|') if label.strip()]
        
        # Default colors if no styles provided
        default_colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
        
        # Create figure based on plot type
        plot_type = args.plot_type if hasattr(args, 'plot_type') and args.plot_type else 'time'
        
        # Parse subplot layout if specified
        use_subplots = False
        subplot_rows, subplot_cols = 1, 1
        if hasattr(args, 'subplot') and args.subplot:
            try:
                parts = args.subplot.split(',')
                if len(parts) == 2:
                    subplot_rows = int(parts[0].strip())
                    subplot_cols = int(parts[1].strip())
                    use_subplots = True
                    if subplot_rows * subplot_cols < len(args.cases):
                        logger.warning(f"Subplot grid ({subplot_rows}x{subplot_cols}) has fewer cells than cases ({len(args.cases)})")
            except ValueError:
                logger.warning(f"Invalid subplot format: {args.subplot}, expected 'rows,cols'")
        
        if use_subplots:
            fig, axes = plt.subplots(subplot_rows, subplot_cols, figsize=(6*subplot_cols, 5*subplot_rows))
            # Make axes always a flat array for easier iteration
            if subplot_rows == 1 and subplot_cols == 1:
                axes = [axes]
            else:
                axes = axes.flatten() if subplot_rows > 1 or subplot_cols > 1 else [axes]
        elif plot_type == 'traj3d':
            from mpl_toolkits.mplot3d import Axes3D
            fig = plt.figure(figsize=(12, 10))
            ax = fig.add_subplot(111, projection='3d')
            axes = [ax]
        else:
            fig, ax = plt.subplots(figsize=(12, 8))
            axes = [ax]  # Single axis wrapped in list for uniform handling
        
        # Process each case
        for i, case_dir in enumerate(args.cases):
            logger.info(f"Loading case {i+1}/{len(args.cases)}: {case_dir}")
            case = FlexFlowCase(case_dir, verbose=args.verbose)
            
            # Select appropriate axis for this case
            if use_subplots:
                if i >= len(axes):
                    logger.warning(f"Not enough subplots for case {i+1}, skipping")
                    continue
                current_ax = axes[i]
            else:
                current_ax = axes[0]  # Use single axis for all cases
            
            # Get data based on type
            if args.data_type == 'displacement':
                if not case.othd_reader:
                    logger.warning(f"No OTHD data in {case_dir}, skipping")
                    continue
                
                data = case.othd_reader.get_node_displacements(args.node)
                times = data['times']
                
                # Get component data
                comp_map = {'x': 'dx', 'y': 'dy', 'z': 'dz', 'magnitude': 'magnitude'}
                values = data[comp_map.get(args.component, 'dy')]
                
            elif args.data_type == 'force':
                if not case.oisd_reader:
                    logger.warning(f"No OISD data in {case_dir}, skipping")
                    continue
                
                data = case.oisd_reader.get_total_traction()
                times = data['times']
                
                # Get component data
                comp_map = {'tx': 'tx', 'ty': 'ty', 'tz': 'tz', 'magnitude': 'magnitude'}
                values = data[comp_map.get(args.component, 'ty')]
            
            else:
                logger.error(f"Unsupported data type: {args.data_type}")
                continue
            
            # Apply time range if specified
            if args.start_step is not None or args.end_step is not None:
                start = args.start_step if args.start_step is not None else 0
                end = args.end_step + 1 if args.end_step is not None else len(times)
                times = times[start:end]
                values = values[start:end]
            elif args.start_time is not None or args.end_time is not None:
                times_arr = np.array(times)
                start_idx = 0 if args.start_time is None else np.searchsorted(times_arr, args.start_time)
                end_idx = len(times) if args.end_time is None else np.searchsorted(times_arr, args.end_time)
                times = times[start_idx:end_idx]
                values = values[start_idx:end_idx]
            
            # Get plot style for this case
            if i < len(plot_styles):
                style = plot_styles[i]
            else:
                # Use default color if no style specified
                style = {'color': default_colors[i % len(default_colors)], 'linewidth': 1.5}
            
            # Get label for this case
            if i < len(legend_labels):
                label = legend_labels[i]
            else:
                label = case.problem_name if hasattr(case, 'problem_name') else case_dir
            
            # Plot based on type
            if plot_type == 'fft':
                # Compute FFT
                from numpy.fft import fft, fftfreq
                dt = case.get_time_increment() if case.get_time_increment() else np.mean(np.diff(times))
                n = len(values)
                yf = fft(values)
                xf = fftfreq(n, dt)[:n//2]
                current_ax.plot(xf, 2.0/n * np.abs(yf[:n//2]), label=label, **style)
            elif plot_type == 'traj2d':
                # Need two components for 2D trajectory
                logger.error("traj2d plot type not fully implemented for direct compare command")
                continue
            elif plot_type == 'traj3d':
                # Need three components for 3D trajectory
                logger.error("traj3d plot type not fully implemented for direct compare command")
                continue
            else:  # time series (default)
                current_ax.plot(times, values, label=label, **style)
            
            # Add grid and legend to each subplot
            if use_subplots:
                current_ax.grid(True, alpha=0.3)
                current_ax.legend(loc='best', fontsize=10)
        
        # Parse and set labels with enhanced format
        from module.commands.plot_cmd.command import parse_label
        
        # Apply labels to all axes
        for idx, current_ax in enumerate(axes[:len(args.cases)]):
            # Set title (different for subplots vs single plot)
            if use_subplots:
                # For subplots, use case name as title
                case_label = legend_labels[idx] if idx < len(legend_labels) else args.cases[idx]
                if args.fontname:
                    current_ax.set_title(case_label, fontfamily=args.fontname)
                else:
                    current_ax.set_title(case_label)
            else:
                # For single plot, use provided title or default
                if args.title:
                    title_info = parse_label(args.title)
                    if title_info:
                        if title_info['usetex']:
                            plt.rc('text', usetex=True)
                        title_kwargs = {}
                        if title_info['fontsize']:
                            title_kwargs['fontsize'] = title_info['fontsize']
                        if args.fontname:
                            title_kwargs['fontfamily'] = args.fontname
                        current_ax.set_title(title_info['text'], **title_kwargs)
                else:
                    title = f'Comparison: {args.data_type.capitalize()} - {args.component.upper()}'
                    if args.fontname:
                        current_ax.set_title(title, fontfamily=args.fontname)
                    else:
                        current_ax.set_title(title)
            
            # Set xlabel
            if args.xlabel:
                xlabel_info = parse_label(args.xlabel)
                if xlabel_info:
                    if xlabel_info['usetex']:
                        plt.rc('text', usetex=True)
                    xlabel_kwargs = {}
                    if xlabel_info['fontsize']:
                        xlabel_kwargs['fontsize'] = xlabel_info['fontsize']
                    if args.fontname:
                        xlabel_kwargs['fontfamily'] = args.fontname
                    current_ax.set_xlabel(xlabel_info['text'], **xlabel_kwargs)
            else:
                xlabel = 'Frequency (Hz)' if plot_type == 'fft' else 'Time'
                if args.fontname:
                    current_ax.set_xlabel(xlabel, fontfamily=args.fontname)
                else:
                    current_ax.set_xlabel(xlabel)
            
            # Set ylabel
            if args.ylabel:
                ylabel_info = parse_label(args.ylabel)
                if ylabel_info:
                    if ylabel_info['usetex']:
                        plt.rc('text', usetex=True)
                    ylabel_kwargs = {}
                    if ylabel_info['fontsize']:
                        ylabel_kwargs['fontsize'] = ylabel_info['fontsize']
                    if args.fontname:
                        ylabel_kwargs['fontfamily'] = args.fontname
                    current_ax.set_ylabel(ylabel_info['text'], **ylabel_kwargs)
            else:
                if plot_type == 'fft':
                    ylabel = f'Amplitude'
                else:
                    ylabel = f'{args.component.upper()} {args.data_type.capitalize()}'
                if args.fontname:
                    current_ax.set_ylabel(ylabel, fontfamily=args.fontname)
                else:
                    current_ax.set_ylabel(ylabel)
            
            # Set tick label fonts
            if args.fontname:
                for label in current_ax.get_xticklabels() + current_ax.get_yticklabels():
                    label.set_fontfamily(args.fontname)
            
            # Add grid and legend for single plot mode (subplots already have this)
            if not use_subplots:
                current_ax.grid(True, alpha=0.3)
                
                # Configure and show legend
                from module.commands.plot_cmd.command import parse_legend_style
                if hasattr(args, 'legend_style') and args.legend_style:
                    legend_style = parse_legend_style(args.legend_style)
                    if legend_style.get('usetex'):
                        plt.rc('text', usetex=True)
                    legend_kwargs = {}
                    if 'loc' in legend_style:
                        legend_kwargs['loc'] = legend_style['loc']
                    if 'fontsize' in legend_style:
                        legend_kwargs['fontsize'] = legend_style['fontsize']
                    if 'frameon' in legend_style:
                        legend_kwargs['frameon'] = legend_style['frameon']
                    if args.fontname:
                        legend_kwargs['prop'] = {'family': args.fontname}
                    current_ax.legend(**legend_kwargs)
                else:
                    current_ax.legend()
        
        # Hide unused subplots
        if use_subplots:
            for idx in range(len(args.cases), len(axes)):
                axes[idx].set_visible(False)
        
        plt.tight_layout()
        
        # Save or display
        if args.output:
            logger.info(f"Saving plot to: {args.output}")
            fig.savefig(args.output, dpi=300, bbox_inches='tight')
            logger.success(f"Plot saved to {args.output}")
        
        # Only show if not in output-only mode and display not disabled
        if not args.output and not args.no_display:
            plt.show()
        
        logger.success("Compare command completed")
        
    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def execute_compare_from_yaml(config, args, logger):
    """Execute compare from YAML configuration"""
    
    # Extract global configuration
    plot_type = config.get('plot_type', 'time')
    plot_props = config.get('plot_properties', {})
    time_range = config.get('time_range', {})
    cases = config.get('cases', [])
    
    if not cases:
        raise ValueError("No cases specified in configuration")
    
    # Create figure
    if plot_type == 'traj3d':
        from mpl_toolkits.mplot3d import Axes3D
        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection='3d')
    else:
        fig, ax = plt.subplots(figsize=(12, 8))
    
    # Process each case
    for case_config in cases:
        case_dir = case_config['case_dir']
        node = case_config.get('node')
        data_type = case_config['data_type']
        component = case_config.get('component', 'y')
        label = case_config.get('label', case_dir)
        style = case_config.get('style', {})
        
        logger.info(f"Processing: {case_dir}")
        
        # Load case
        case = FlexFlowCase(case_dir, verbose=args.verbose)
        
        # Get data
        if data_type == 'displacement':
            if not case.othd_reader:
                logger.warning(f"No OTHD data in {case_dir}, skipping")
                continue
            
            data = case.othd_reader.get_node_displacements(node)
            times = data['times']
            comp_map = {'x': 'dx', 'y': 'dy', 'z': 'dz', 'magnitude': 'magnitude'}
            values = {k: data[comp_map[k]] for k in ['x', 'y', 'z', 'magnitude'] if k in comp_map}
            
        elif data_type == 'force':
            if not case.oisd_reader:
                logger.warning(f"No OISD data in {case_dir}, skipping")
                continue
            
            data = case.oisd_reader.get_total_traction()
            times = data['times']
            values = {'x': data['tx'], 'y': data['ty'], 'z': data['tz'], 'magnitude': data['magnitude']}
        else:
            logger.warning(f"Unsupported data type: {data_type}")
            continue
        
        # Apply time range
        start_step = time_range.get('start_step', 0)
        end_step = time_range.get('end_step', len(times))
        times = np.array(times)[start_step:end_step]
        for k in values:
            values[k] = values[k][start_step:end_step]
        
        # Plot based on type
        if plot_type == 'time':
            comp = component if isinstance(component, str) else component[0]
            ax.plot(times, values[comp],
                   label=label,
                   color=style.get('color'),
                   linewidth=style.get('linewidth', 1.5),
                   linestyle=style.get('linestyle', '-'),
                   marker=style.get('marker'))
        
        elif plot_type == 'fft':
            comp = component if isinstance(component, str) else component[0]
            y_data = values[comp]
            
            # Compute FFT
            from numpy.fft import fft, fftfreq
            dt = case.time_increment if case.time_increment else np.mean(np.diff(times))
            n = len(y_data)
            yf = fft(y_data)
            xf = fftfreq(n, dt)[:n//2]
            
            ax.plot(xf, 2.0/n * np.abs(yf[:n//2]),
                   label=label,
                   color=style.get('color'),
                   linewidth=style.get('linewidth', 1.5),
                   linestyle=style.get('linestyle', '-'))
        
        elif plot_type == 'traj2d':
            comps = component if isinstance(component, list) else ['x', 'y']
            ax.plot(values[comps[0]], values[comps[1]],
                   label=label,
                   color=style.get('color'),
                   linewidth=style.get('linewidth', 1.5),
                   linestyle=style.get('linestyle', '-'))
        
        elif plot_type == 'traj3d':
            comps = component if isinstance(component, list) else ['x', 'y', 'z']
            ax.plot(values[comps[0]], values[comps[1]], values[comps[2]],
                   label=label,
                   color=style.get('color'),
                   linewidth=style.get('linewidth', 2))
    
    # Apply plot properties
    ax.set_title(plot_props.get('title', 'Comparison Plot'))
    ax.set_xlabel(plot_props.get('xlabel', 'X'))
    ax.set_ylabel(plot_props.get('ylabel', 'Y'))
    if plot_type == 'traj3d':
        ax.set_zlabel(plot_props.get('zlabel', 'Z'))
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
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
    
    logger.success("Compare command completed")
