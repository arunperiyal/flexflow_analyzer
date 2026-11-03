"""
Plot command implementation
"""

import sys
import os
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager
import yaml

from ....core.case import FlexFlowCase
from ....utils.logger import Logger
from ....utils.colors import Colors
from ....utils import plot_utils

try:
    import plotext as plt_terminal
    HAS_PLOTEXT = True
except ImportError:
    HAS_PLOTEXT = False


def _plotext_where():
    """Where the imported plotext came from: a directory named plotext on
    the path imports as an empty namespace package, with no plot()."""
    where = getattr(plt_terminal, '__file__', None)
    if where is None:
        where = ', '.join(getattr(plt_terminal, '__path__', [])) or '?'
        return f"{where} (a plain directory, not the package)"
    return where


def _pt(*names):
    """The first of these plotext functions this version has (the names
    changed between 4.x and 5.x: clear_plot/clear_figure, figsize/plotsize),
    or None."""
    for name in names:
        fn = getattr(plt_terminal, name, None)
        if callable(fn):
            return fn
    return None


def plot_in_terminal(fig, axes, logger):
    """
    Plot the data in terminal using plotext.

    Parameters:
    -----------
    fig : matplotlib.figure.Figure
        Matplotlib figure
    axes : matplotlib.axes.Axes or list of Axes
        Matplotlib axes
    logger : Logger
        Logger instance
    """
    if not HAS_PLOTEXT:
        logger.error("plotext library not installed. Install with: pip install plotext")
        logger.info("Falling back to regular matplotlib display")
        return False

    # plotext 6.x has no plot(): its figure object takes a matplotlib figure
    convert = _pt('matplotlib')
    if not _pt('plot') and convert and hasattr(plt_terminal, 'figure'):
        if not any(len(line.get_xdata()) for ax in fig.axes for line in ax.get_lines()):
            logger.warning("No data found to plot in terminal")
            return False
        convert(fig).show()
        return True

    if not (_pt('plot') and _pt('show')):
        logger.error(f"plotext imported from {_plotext_where()} has no plot()/show(); "
                     "reinstall it with: pip install -U plotext")
        return False

    # Handle single or multiple axes
    if not isinstance(axes, list):
        axes = [axes]

    clear = _pt('clear_figure', 'clf', 'clear_plot', 'clp')
    size = _pt('plotsize', 'plot_size', 'figsize', 'figure_size')
    # plotext 4.x has no subplots: there each axes is shown on its own
    subplots, subplot = _pt('subplots'), _pt('subplot')
    stacked = len(axes) > 1 and subplots and subplot

    def start():
        if clear:
            clear()
        if size:
            # width, height in characters
            size(100, 30)

    start()
    if stacked:
        subplots(len(axes), 1)
    plots_added = 0

    for idx, ax in enumerate(axes):
        if stacked:
            subplot(idx + 1, 1)
        elif idx > 0:
            plt_terminal.show()
            start()

        # Get all lines from the matplotlib axes
        lines = ax.get_lines()
        logger.debug(f"Found {len(lines)} lines in axes")

        for line in lines:
            xdata = line.get_xdata()
            ydata = line.get_ydata()
            label = line.get_label()

            logger.debug(f"Line label: '{label}', data points: {len(xdata)}")

            # Only plot if we have data
            # Note: We don't filter by label because matplotlib sometimes uses labels starting with '_'
            if len(xdata) > 0:
                # Convert to lists to ensure compatibility
                x_list = xdata.tolist() if hasattr(xdata, 'tolist') else list(xdata)
                y_list = ydata.tolist() if hasattr(ydata, 'tolist') else list(ydata)

                # Use empty label if it starts with '_' (internal matplotlib convention)
                display_label = "" if label.startswith('_') else label

                if line.get_gid() == RESTART_GID:
                    try:
                        plt_terminal.plot(x_list, y_list, color='gray')
                    except TypeError:
                        plt_terminal.plot(x_list, y_list)
                    continue
                plt_terminal.plot(x_list, y_list, label=display_label)
                plots_added += 1
                logger.debug(f"Plotted line with {len(x_list)} points")

        # Set labels
        for text, setter in ((ax.get_xlabel(), 'xlabel'), (ax.get_ylabel(), 'ylabel'),
                             (ax.get_title(), 'title')):
            fn = _pt(setter)
            if text and fn:
                fn(text)

    if plots_added == 0:
        logger.warning("No data found to plot in terminal")
        return False

    logger.info(f"Displaying {plots_added} plot(s) in terminal")

    # Show the terminal plot
    plt_terminal.show()
    return True


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


RESTART_GID = 'restart'


def restart_times(case_dir, dt):
    """The times the runs in `.restarts` resumed at: step `after` at after*dt,
    the last step kept of the run before (the recorded time of the first new
    step when there is no dt)."""
    from ....core import restarts
    times = []
    for row in restarts.read(case_dir):
        if dt:
            times.append(int(row['after']) * dt)
        elif row.get('time', '-') != '-':
            times.append(float(row['time']))
    return times


def mark_restarts(axes, case_dir, dt, logger):
    """A grey dashed line at each restart within each axes' time range.
    Drawn as ordinary data lines (not axvline, whose y is in axes units) so
    the terminal plots carry them too; the y limits are kept as they were."""
    times = restart_times(case_dir, dt)
    if not times:
        return 0
    marked = set()
    for ax in (axes if isinstance(axes, (list, tuple)) else [axes]):
        x0, x1 = ax.get_xlim()
        ylim = ax.get_ylim()
        for t in times:
            if x0 <= t <= x1:
                ax.plot([t, t], ylim, linestyle='--', linewidth=0.8, color='0.5',
                        label='_restart', gid=RESTART_GID, scalex=False, scaley=False)
                marked.add(t)
        ax.set_ylim(ylim)
    if marked:
        logger.info(f"Marked {len(marked)} restart(s) from .restarts at t = "
                    + ', '.join(f"{t:g}" for t in sorted(marked)))
    return len(marked)


# Pendulum histories are othd lines of their own (pendDisp/pendVel/pendAccel)
# that the series reader behind `data table` does not take, so they are read
# with the OTHD reader: name (lower case) -> its key in get_pendulum_data().
PENDULUM = {
    'penddisp': 'displacement', 'pd': 'displacement',
    'pendvel': 'velocity', 'pv': 'velocity',
    'pendaccel': 'acceleration', 'pa': 'acceleration',
}
PENDULUM_LABEL = {'displacement': 'pendDisp', 'velocity': 'pendVel',
                  'acceleration': 'pendAccel'}


def requested_vars(args):
    """--var as given (repeats and commas), or None."""
    from ...data import shared
    return shared.split_vars(getattr(args, 'var', None))


def select_pendulum(case_dir, args, logger, requested):
    """A Selection of pendulum columns, windowed like any other."""
    import numpy as np
    from ...data import shared
    from ....core.readers.othd_reader import OTHDReader
    files = shared.find_files(case_dir, 'othd')
    if not files:
        raise ValueError(f"No othd files under {case_dir}")
    reader = OTHDReader(files, group=getattr(args, 'othid', None))
    data = reader.get_pendulum_data()
    if data is None:
        raise ValueError("No pendulum data (pendDisp/pendVel/pendAccel) in the othd files")
    tsids = np.asarray(reader.tsIds)
    times = np.asarray(data['times'])
    t1, t2 = getattr(args, 't1', None), getattr(args, 't2', None)
    mask = np.ones(len(tsids), dtype=bool)
    if t1 is not None:
        mask &= tsids >= t1
    if t2 is not None:
        mask &= tsids <= t2
    if not mask.any():
        raise ValueError(f"No pendulum steps in tsId range {t1}..{t2}")
    mask = shared.last_steps(tsids, mask, getattr(args, 'last', None), logger)
    keys = list(dict.fromkeys(PENDULUM[r.lower()] for r in requested))
    values = {PENDULUM_LABEL[k]: np.asarray(data[k])[mask] for k in keys}
    return shared.Selection('othd', None, getattr(args, 'othid', None), None,
                            list(values), times[mask], tsids[mask], values)


def time_cut(sel, start_time, end_time):
    """--start-time/--end-time on top of the tsId window."""
    import numpy as np
    if start_time is None and end_time is None:
        return sel
    keep = np.ones(len(sel.times), dtype=bool)
    if start_time is not None:
        keep &= sel.times >= start_time
    if end_time is not None:
        keep &= sel.times <= end_time
    if not keep.any():
        raise ValueError(f"No steps between time {start_time} and {end_time}: the window "
                         f"holds {sel.times.min():.6g}..{sel.times.max():.6g}")
    sel.times, sel.tsids = sel.times[keep], sel.tsids[keep]
    sel.values = {k: v[keep] for k, v in sel.values.items()}
    return sel


def describe(case_dir, sel, requested):
    """The default title: case, variables, and where they came from."""
    where = [sel.kind]
    if sel.meta is not None:
        where.append(f"{sel.meta.group_label} {sel.group}")
        if sel.meta.nodes_of(sel.group) > 1:
            where.append(f"node {sel.node}")
    return f"{case_dir.name}: {', '.join(requested)}  ({', '.join(where)})"


def build_figure(plot_type, sel, plot_style, legend_style, title, logger):
    """The figure for one selection; raises ValueError on a mismatch."""
    from . import series_plot
    labels = list(sel.values)
    if plot_type == 'time':
        return series_plot.time_plot(sel.times, sel.values, plot_style, title)
    if plot_type == 'fft':
        if len(sel.times) < 4:
            raise ValueError(f"{len(sel.times)} step(s) are too few for a spectrum")
        if series_plot.uneven_sampling(sel.times):
            logger.warning("the steps are not evenly spaced; the spectrum takes "
                           "the median step as the sampling interval")
        fig, axes, peaks = series_plot.fft_plot(sel.times, sel.values, plot_style, title)
        for label, peak in peaks.items():
            logger.info(f"{label}: " + ("flat" if peak != peak else f"peak at {peak:.6g} Hz"))
        return fig, axes
    dims = {'traj2d': 2, 'traj3d': 3}.get(plot_type)
    if dims is None:
        raise ValueError(f"Invalid plot type: {plot_type}")
    if len(labels) < dims:
        raise ValueError(f"--plot-type {plot_type} needs {dims} columns, and "
                         f"{', '.join(labels)} is {len(labels)}: give a vector "
                         f"variable (--var d) or {dims} components (--var "
                         + ','.join(['dx', 'dy', 'dz'][:dims]) + ")")
    if len(labels) > dims:
        logger.info(f"{plot_type}: plotting {', '.join(labels[:dims])} "
                    f"(of {', '.join(labels)})")
    return series_plot.trajectory_plot(sel.values, dims, plot_style, title, legend_style)


def execute_plot(args):
    """
    Execute the plot command: the --var columns (from `use var:` when not
    typed) of one case, read as `data table` reads them.
    """
    from pathlib import Path
    from .help_messages import print_plot_help
    from ...data import shared

    if getattr(args, 'output', None) and args.output.lower().endswith(('.pdf', '.eps')):
        plt.rcParams['pdf.fonttype'] = 42  # embed TrueType, not bitmaps
        plt.rcParams['ps.fonttype'] = 42

    if not args.input_file and not args.case:
        print_plot_help()
        return

    logger = Logger(verbose=args.verbose)
    if args.no_display or args.output or getattr(args, 'gnu', False):
        matplotlib.use('Agg')

    try:
        if args.input_file:
            logger.info(f"Loading configuration from: {args.input_file}")
            with open(args.input_file, 'r') as f:
                config = yaml.safe_load(f)
            execute_plot_from_yaml(config, args)
            return

        requested = requested_vars(args)
        if not requested:
            print(f"{Colors.red('Error:')} --var says what to plot (or `use var:dy`); "
                  f"`data show` lists the variables of a case.", file=sys.stderr)
            sys.exit(1)

        case_dir = Path(args.case)
        if not case_dir.is_dir():
            raise ValueError(f"Case directory not found: {case_dir}")

        ensure_ms_fonts_loaded()
        if getattr(args, 'fontname', None):
            matplotlib.rc('font', family=args.fontname)
            if 'Times' in args.fontname or args.fontname == 'serif':
                matplotlib.rc('mathtext', fontset='stix')  # Times-compatible maths
            logger.info(f"Using font: {args.fontname}")

        pendulum = [r for r in requested if r.lower() in PENDULUM]
        if pendulum and len(pendulum) < len(requested):
            raise ValueError("pendulum variables (pendDisp, pendVel, pendAccel) are "
                             "read on their own: plot them apart from "
                             + ', '.join(r for r in requested if r not in pendulum))
        if pendulum:
            sel = select_pendulum(case_dir, args, logger, requested)
        else:
            sel = shared.select(case_dir, args, logger, requested)
        sel = time_cut(sel, getattr(args, 'start_time', None), getattr(args, 'end_time', None))
        logger.info(f"{len(sel.times)} step(s): tsId {sel.tsids.min()}..{sel.tsids.max()}, "
                    f"time {sel.times.min():.6g}..{sel.times.max():.6g}")

        plot_style = parse_plot_style(args.plot_style)
        legend_style = parse_legend_style(args.legend_style) if getattr(args, 'legend_style', None) else {}
        plot_type = args.plot_type or 'time'
        title = None if args.title else describe(case_dir, sel, requested)
        fig, axes = build_figure(plot_type, sel, plot_style, legend_style, title, logger)

        apply_plot_properties(fig, axes, args)

        if plot_type == 'time' and getattr(args, 'restart', False):
            mark_restarts(axes, str(case_dir), _time_increment(case_dir), logger)

        if getattr(args, 'gnu', False):
            plot_in_terminal(fig, axes, logger)

        if args.output:
            logger.info(f"Saving plot to: {args.output}")
            fig.savefig(args.output, dpi=300, bbox_inches='tight')
            logger.success(f"Plot saved to {args.output}")

        if not args.output and not args.no_display and not getattr(args, 'gnu', False):
            plt.show()

        logger.success("Plot command completed")

    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _time_increment(case_dir):
    """initialTimeIncrement of the case's .def, or None."""
    try:
        from ....core.def_config import DefConfig
        from ....core.simflow_config import SimflowConfig
        simflow = SimflowConfig(case_dir / 'simflow.config')
        return DefConfig.find(case_dir, simflow.problem if simflow.exists else None) \
            .initial_time_increment
    except Exception:
        return None


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
    
    if (data_type == 'force' or plot_type == 'time') \
            and (config.get('restarts', False) or getattr(args, 'restart', False)):
        mark_restarts(axes, case_dir, case.get_time_increment(), logger)

    # Terminal output (--gnu flag)
    if hasattr(args, 'gnu') and args.gnu:
        plot_in_terminal(fig, axes, logger)

    # Save or display
    output_file = config.get('output', args.output)
    if output_file:
        logger.info(f"Saving plot to: {output_file}")
        fig.savefig(output_file, dpi=300, bbox_inches='tight')
        logger.success(f"Plot saved to {output_file}")

    # Only show if not in output-only mode and display not disabled
    no_display = args.no_display or config.get('no_display', False)
    gnu_mode = hasattr(args, 'gnu') and args.gnu
    if not output_file and not no_display and not gnu_mode:
        plt.show()

    logger.success("Plot command completed")
