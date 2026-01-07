"""
Plotting Utilities for FlexFlow

This module provides plotting functions for OTHD displacement data.
"""

import numpy as np
import matplotlib.pyplot as plt
from .data_utils import filter_data_by_time_range, check_time_continuity


def plot_node_displacements(reader, node_id, component='all', figsize=(12, 8), use_index=False, plot_style=None, start_time=None, end_time=None):
    """
    Plot displacement time history for a specific node.
    
    Parameters:
    -----------
    reader : OTHDReader
        OTHD reader object with loaded data
    node_id : int
        Node number (0-indexed)
    component : str
        Which displacement component to plot: 'x', 'y', 'z', 'magnitude', or 'all'
        Default is 'all' which plots all components
    figsize : tuple
        Figure size (width, height)
    use_index : bool
        If True, plot against timestep index instead of time values.
        Useful when time has discontinuities (restarts, etc.)
    plot_style : dict
        Plot style dictionary with keys: color, linewidth, linestyle, marker
    start_time : float, optional
        Start time for filtering data
    end_time : float, optional
        End time for filtering data
        
    Returns:
    --------
    fig : matplotlib figure object
    ax : matplotlib axes object(s)
    """
    if plot_style is None:
        plot_style = {}
    data = reader.get_node_displacements(node_id)
    
    # Filter data by time range if specified
    if start_time is not None or end_time is not None:
        data = filter_data_by_time_range(data, start_time=start_time, end_time=end_time)
    
    if use_index:
        x_data = np.arange(len(data['times']))
        x_label = 'Timestep Index'
    else:
        x_data = data['times']
        x_label = 'Time'
    
    dx = data['dx']
    dy = data['dy']
    dz = data['dz']
    magnitude = data['magnitude']
    
    # Default plot style
    default_style = {'linewidth': 1.5}
    default_style.update(plot_style)
    
    if component == 'all':
        fig, axes = plt.subplots(4, 1, figsize=figsize, sharex=True)
        
        # For 'all', use default colors if not specified
        axes[0].plot(x_data, dx, color=plot_style.get('color', 'b'), 
                     linewidth=default_style.get('linewidth', 1.5),
                     linestyle=plot_style.get('linestyle', '-'),
                     marker=plot_style.get('marker', ''))
        axes[0].set_ylabel('X Displacement')
        axes[0].grid(True, alpha=0.3)
        axes[0].set_title(f'Displacement Time History - Node {node_id}')
        
        axes[1].plot(x_data, dy, color=plot_style.get('color', 'r'),
                     linewidth=default_style.get('linewidth', 1.5),
                     linestyle=plot_style.get('linestyle', '-'),
                     marker=plot_style.get('marker', ''))
        axes[1].set_ylabel('Y Displacement')
        axes[1].grid(True, alpha=0.3)
        
        axes[2].plot(x_data, dz, color=plot_style.get('color', 'g'),
                     linewidth=default_style.get('linewidth', 1.5),
                     linestyle=plot_style.get('linestyle', '-'),
                     marker=plot_style.get('marker', ''))
        axes[2].set_ylabel('Z Displacement')
        axes[2].grid(True, alpha=0.3)
        
        axes[3].plot(x_data, magnitude, color=plot_style.get('color', 'k'),
                     linewidth=default_style.get('linewidth', 1.5),
                     linestyle=plot_style.get('linestyle', '-'),
                     marker=plot_style.get('marker', ''))
        axes[3].set_ylabel('Magnitude')
        axes[3].set_xlabel(x_label)
        axes[3].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
    else:
        fig, ax = plt.subplots(figsize=figsize)
        
        # Build plot kwargs
        plot_kwargs = {'linewidth': default_style.get('linewidth', 1.5)}
        if 'color' in plot_style:
            plot_kwargs['color'] = plot_style['color']
        if 'linestyle' in plot_style:
            plot_kwargs['linestyle'] = plot_style['linestyle']
        else:
            plot_kwargs['linestyle'] = '-'
        if 'marker' in plot_style:
            plot_kwargs['marker'] = plot_style['marker']
        
        if component == 'x':
            if 'color' not in plot_kwargs:
                plot_kwargs['color'] = 'b'
            ax.plot(x_data, dx, **plot_kwargs)
            ax.set_ylabel('X Displacement')
            title = f'X Displacement - Node {node_id}'
        elif component == 'y':
            if 'color' not in plot_kwargs:
                plot_kwargs['color'] = 'r'
            ax.plot(x_data, dy, **plot_kwargs)
            ax.set_ylabel('Y Displacement')
            title = f'Y Displacement - Node {node_id}'
        elif component == 'z':
            if 'color' not in plot_kwargs:
                plot_kwargs['color'] = 'g'
            ax.plot(x_data, dz, **plot_kwargs)
            ax.set_ylabel('Z Displacement')
            title = f'Z Displacement - Node {node_id}'
        elif component == 'magnitude':
            if 'color' not in plot_kwargs:
                plot_kwargs['color'] = 'k'
            ax.plot(x_data, magnitude, **plot_kwargs)
            ax.set_ylabel('Displacement Magnitude')
            title = f'Displacement Magnitude - Node {node_id}'
        else:
            raise ValueError("component must be 'x', 'y', 'z', 'magnitude', or 'all'")
        
        ax.set_xlabel(x_label)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        axes = ax
    
    return fig, axes


def plot_force_data(reader, component='all', figsize=(12, 8), use_index=False, plot_style=None, start_time=None, end_time=None):
    """
    Plot total traction/force time history from OISD data.
    
    Parameters:
    -----------
    reader : OISDReader
        OISD reader object with loaded data
    component : str
        Which component to plot: 'tx', 'ty', 'tz', 'magnitude', or 'all'
    figsize : tuple
        Figure size (width, height)
    use_index : bool
        If True, plot against timestep index instead of time
    plot_style : dict
        Plot style dictionary with keys: color, linewidth, linestyle, marker
    start_time : float, optional
        Start time for filtering data
    end_time : float, optional
        End time for filtering data
        
    Returns:
    --------
    fig, axes : matplotlib objects
    """
    if plot_style is None:
        plot_style = {}
    
    default_style = {'linewidth': 1.5}
    default_style.update(plot_style)
    data = reader.get_total_traction()
    
    # Filter data by time range if specified
    if start_time is not None or end_time is not None:
        data = filter_data_by_time_range(data, start_time=start_time, end_time=end_time)
    
    if use_index:
        x_data = np.arange(len(data['times']))
        x_label = 'Timestep Index'
    else:
        x_data = data['times']
        x_label = 'Time (s)'
    
    if component == 'all':
        fig, axes = plt.subplots(4, 1, figsize=figsize, sharex=True)
        
        axes[0].plot(x_data, data['tx'], 'b-', linewidth=1.5)
        axes[0].set_ylabel('TX (N)')
        axes[0].grid(True, alpha=0.3)
        axes[0].set_title('Total Traction Time History')
        
        axes[1].plot(x_data, data['ty'], 'r-', linewidth=1.5)
        axes[1].set_ylabel('TY (N)')
        axes[1].grid(True, alpha=0.3)
        
        axes[2].plot(x_data, data['tz'], 'g-', linewidth=1.5)
        axes[2].set_ylabel('TZ (N)')
        axes[2].grid(True, alpha=0.3)
        
        axes[3].plot(x_data, data['magnitude'], 'k-', linewidth=1.5)
        axes[3].set_ylabel('Magnitude (N)')
        axes[3].set_xlabel(x_label)
        axes[3].grid(True, alpha=0.3)
        
        plt.tight_layout()
    else:
        fig, ax = plt.subplots(figsize=figsize)
        
        comp_map = {
            'tx': ('tx', 'TX Force (N)', 'blue'),
            'ty': ('ty', 'TY Force (N)', 'red'),
            'tz': ('tz', 'TZ Force (N)', 'green'),
            'magnitude': ('magnitude', 'Force Magnitude (N)', 'black')
        }
        
        if component in comp_map:
            key, ylabel, color = comp_map[component]
            ax.plot(x_data, data[key], color=color, linewidth=1.5)
            ax.set_ylabel(ylabel)
            ax.set_title(f'Total Traction - {component.upper()}')
        else:
            raise ValueError(f"Invalid component '{component}'. Use tx, ty, tz, magnitude, or all")
        
        ax.set_xlabel(x_label)
        ax.grid(True, alpha=0.3)
        axes = ax
    
    return fig, axes


def plot_moment_data(reader, component='all', figsize=(12, 8), use_index=False):
    """
    Plot total moment time history from OISD data.
    
    Parameters:
    -----------
    reader : OISDReader
        OISD reader object with loaded data
    component : str
        Which component to plot: 'mx', 'my', 'mz', 'magnitude', or 'all'
    figsize : tuple
        Figure size (width, height)
    use_index : bool
        If True, plot against timestep index instead of time
        
    Returns:
    --------
    fig, axes : matplotlib objects
    """
    data = reader.get_total_moment()
    
    if use_index:
        x_data = np.arange(len(data['times']))
        x_label = 'Timestep Index'
    else:
        x_data = data['times']
        x_label = 'Time (s)'
    
    if component == 'all':
        fig, axes = plt.subplots(4, 1, figsize=figsize, sharex=True)
        
        axes[0].plot(x_data, data['mx'], 'b-', linewidth=1.5)
        axes[0].set_ylabel('MX (N·m)')
        axes[0].grid(True, alpha=0.3)
        axes[0].set_title('Total Moment Time History')
        
        axes[1].plot(x_data, data['my'], 'r-', linewidth=1.5)
        axes[1].set_ylabel('MY (N·m)')
        axes[1].grid(True, alpha=0.3)
        
        axes[2].plot(x_data, data['mz'], 'g-', linewidth=1.5)
        axes[2].set_ylabel('MZ (N·m)')
        axes[2].grid(True, alpha=0.3)
        
        axes[3].plot(x_data, data['magnitude'], 'k-', linewidth=1.5)
        axes[3].set_ylabel('Magnitude (N·m)')
        axes[3].set_xlabel(x_label)
        axes[3].grid(True, alpha=0.3)
        
        plt.tight_layout()
    else:
        fig, ax = plt.subplots(figsize=figsize)
        
        comp_map = {
            'mx': ('mx', 'MX Moment (N·m)', 'blue'),
            'my': ('my', 'MY Moment (N·m)', 'red'),
            'mz': ('mz', 'MZ Moment (N·m)', 'green'),
            'magnitude': ('magnitude', 'Moment Magnitude (N·m)', 'black')
        }
        
        if component in comp_map:
            key, ylabel, color = comp_map[component]
            ax.plot(x_data, data[key], color=color, linewidth=1.5)
            ax.set_ylabel(ylabel)
            ax.set_title(f'Total Moment - {component.upper()}')
        else:
            raise ValueError(f"Invalid component '{component}'. Use mx, my, mz, magnitude, or all")
        
        ax.set_xlabel(x_label)
        ax.grid(True, alpha=0.3)
        axes = ax
    
    return fig, axes


def plot_pressure_data(reader, figsize=(12, 5), use_index=False):
    """
    Plot average pressure time history from OISD data.
    
    Parameters:
    -----------
    reader : OISDReader
        OISD reader object with loaded data
    figsize : tuple
        Figure size (width, height)
    use_index : bool
        If True, plot against timestep index instead of time
        
    Returns:
    --------
    fig, ax : matplotlib objects
    """
    data = reader.get_average_pressure()
    
    if use_index:
        x_data = np.arange(len(data['times']))
        x_label = 'Timestep Index'
    else:
        x_data = data['times']
        x_label = 'Time (s)'
    
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(x_data, data['pressure'], 'purple', linewidth=1.5)
    ax.set_xlabel(x_label)
    ax.set_ylabel('Average Pressure (Pa)')
    ax.set_title('Average Surface Pressure')
    ax.grid(True, alpha=0.3)
    
    return fig, ax


def plot_fft(reader, node_id=10, component='y', use_index=False, plot_style=None, start_time=None, end_time=None):
    """
    Plot FFT (frequency domain) of displacement data.
    
    Parameters:
    -----------
    reader : OTHDReader
        OTHD data reader
    node_id : int
        Node ID to plot
    component : str
        Component to analyze: 'x', 'y', 'z', 'magnitude'
    use_index : bool
        Not used for FFT (time series required)
    plot_style : dict
        Plot style dictionary with keys: color, linewidth, linestyle, marker
    start_time : float, optional
        Start time for filtering data
    end_time : float, optional
        End time for filtering data
        
    Returns:
    --------
    fig, ax : matplotlib figure and axis
    """
    if plot_style is None:
        plot_style = {}
    data = reader.get_node_displacements(node_id)
    
    # Filter data by time range if specified
    if start_time is not None or end_time is not None:
        data = filter_data_by_time_range(data, start_time=start_time, end_time=end_time)
    
    times = data['times']
    
    # Get the component data
    comp_map = {'x': 'dx', 'y': 'dy', 'z': 'dz', 'magnitude': 'magnitude'}
    comp_key = comp_map.get(component, 'dy')
    values = data[comp_key]
    
    # Calculate time step (assume uniform)
    dt = np.mean(np.diff(times))
    
    # Perform FFT using numpy
    n = len(values)
    yf = np.fft.fft(values)
    xf = np.fft.fftfreq(n, dt)[:n//2]
    power = 2.0/n * np.abs(yf[0:n//2])
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Build plot kwargs
    plot_kwargs = {
        'linewidth': plot_style.get('linewidth', 1),
        'color': plot_style.get('color', 'b'),
        'linestyle': plot_style.get('linestyle', '-')
    }
    if 'marker' in plot_style:
        plot_kwargs['marker'] = plot_style['marker']
    
    ax.plot(xf, power, **plot_kwargs)
    ax.set_xlabel('Frequency (Hz)', fontsize=12)
    ax.set_ylabel(f'Amplitude', fontsize=12)
    ax.set_title(f'FFT - Node {node_id}, Component: {component.upper()}', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(left=0)
    
    return fig, ax


def plot_trajectory_2d(reader, node_id=10, comp_x='x', comp_y='y', plot_style=None, start_time=None, end_time=None, legend_style=None):
    """
    Plot 2D trajectory of displacement.
    
    Parameters:
    -----------
    reader : OTHDReader
        OTHD data reader
    node_id : int
        Node ID to plot
    comp_x : str
        X-axis component: 'x', 'y', 'z', 'magnitude'
    comp_y : str
        Y-axis component: 'x', 'y', 'z', 'magnitude'
    plot_style : dict
        Plot style dictionary. For trajectory, linewidth applies to trajectory line.
    start_time : float, optional
        Start time for filtering data
    end_time : float, optional
        End time for filtering data
        
    Returns:
    --------
    fig, ax : matplotlib figure and axis
    """
    if plot_style is None:
        plot_style = {}
    data = reader.get_node_displacements(node_id)
    
    # Filter data by time range if specified
    if start_time is not None or end_time is not None:
        data = filter_data_by_time_range(data, start_time=start_time, end_time=end_time)
    
    # Get the component data
    comp_map = {'x': 'dx', 'y': 'dy', 'z': 'dz', 'magnitude': 'magnitude'}
    x_key = comp_map.get(comp_x, 'dx')
    y_key = comp_map.get(comp_y, 'dy')
    x_vals = data[x_key]
    y_vals = data[y_key]
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Plot trajectory as simple line
    color = plot_style.get('color', 'blue')
    linewidth = plot_style.get('linewidth', 2)
    linestyle = plot_style.get('linestyle', '-')
    
    ax.plot(x_vals, y_vals, color=color, linewidth=linewidth, 
            linestyle=linestyle, alpha=0.8, label='Trajectory')
    
    # Mark start and end
    ax.plot(x_vals[0], y_vals[0], 'go', markersize=10, label='Start', zorder=5)
    ax.plot(x_vals[-1], y_vals[-1], 'ro', markersize=10, label='End', zorder=5)
    
    ax.set_xlabel(f'{comp_x.upper()} Displacement', fontsize=12)
    ax.set_ylabel(f'{comp_y.upper()} Displacement', fontsize=12)
    ax.set_title(f'2D Trajectory - Node {node_id}', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Configure legend
    if legend_style:
        legend_kwargs = {}
        if 'loc' in legend_style:
            legend_kwargs['loc'] = legend_style['loc']
        if 'fontsize' in legend_style:
            legend_kwargs['fontsize'] = legend_style['fontsize']
        if 'frameon' in legend_style:
            legend_kwargs['frameon'] = legend_style['frameon']
        ax.legend(**legend_kwargs)
    else:
        ax.legend()
    
    ax.axis('equal')
    ax.autoscale()
    
    return fig, ax


def plot_trajectory_3d(reader, node_id=10, comp_x='x', comp_y='y', comp_z='z', plot_style=None, start_time=None, end_time=None, legend_style=None):
    """
    Plot 3D trajectory of displacement.
    
    Parameters:
    -----------
    reader : OTHDReader
        OTHD data reader
    node_id : int
        Node ID to plot
    comp_x : str
        X-axis component
    comp_y : str
        Y-axis component
    comp_z : str
        Z-axis component
    plot_style : dict
        Plot style dictionary. For 3D trajectory, linewidth applies to trajectory line.
    start_time : float, optional
        Start time for filtering data
    end_time : float, optional
        End time for filtering data
        
    Returns:
    --------
    fig, ax : matplotlib figure and 3D axis
    """
    if plot_style is None:
        plot_style = {}
    from mpl_toolkits.mplot3d import Axes3D
    
    data = reader.get_node_displacements(node_id)
    
    # Filter data by time range if specified
    if start_time is not None or end_time is not None:
        data = filter_data_by_time_range(data, start_time=start_time, end_time=end_time)
    
    # Get the component data
    comp_map = {'x': 'dx', 'y': 'dy', 'z': 'dz', 'magnitude': 'magnitude'}
    x_key = comp_map.get(comp_x, 'dx')
    y_key = comp_map.get(comp_y, 'dy')
    z_key = comp_map.get(comp_z, 'dz')
    x_vals = data[x_key]
    y_vals = data[y_key]
    z_vals = data[z_key]
    
    # Create 3D plot
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')
    
    # Plot trajectory as simple line
    color = plot_style.get('color', 'blue')
    linewidth = plot_style.get('linewidth', 2)
    linestyle = plot_style.get('linestyle', '-')
    
    ax.plot(x_vals, y_vals, z_vals, color=color, linewidth=linewidth,
            linestyle=linestyle, alpha=0.8, label='Trajectory')
    
    # Mark start and end
    ax.scatter(x_vals[0], y_vals[0], z_vals[0], c='green', s=100, label='Start', zorder=5)
    ax.scatter(x_vals[-1], y_vals[-1], z_vals[-1], c='red', s=100, label='End', zorder=5)
    
    ax.set_xlabel(f'{comp_x.upper()} Displacement', fontsize=12)
    ax.set_ylabel(f'{comp_y.upper()} Displacement', fontsize=12)
    ax.set_zlabel(f'{comp_z.upper()} Displacement', fontsize=12)
    ax.set_title(f'3D Trajectory - Node {node_id}', fontsize=14, fontweight='bold')
    
    # Configure legend
    if legend_style:
        legend_kwargs = {}
        if 'loc' in legend_style:
            legend_kwargs['loc'] = legend_style['loc']
        if 'fontsize' in legend_style:
            legend_kwargs['fontsize'] = legend_style['fontsize']
        if 'frameon' in legend_style:
            legend_kwargs['frameon'] = legend_style['frameon']
        ax.legend(**legend_kwargs)
    else:
        ax.legend()
    
    return fig, ax

