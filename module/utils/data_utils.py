"""
Data Utilities for FlexFlow

This module provides data manipulation and validation functions.
"""

import numpy as np


def filter_data_by_time_range(data, start_time=None, end_time=None, start_step=None, end_step=None):
    """
    Filter data dictionary by time range or timestep range.
    
    Parameters:
    -----------
    data : dict
        Data dictionary with 'times' key and other component keys
    start_time : float, optional
        Start time (inclusive)
    end_time : float, optional
        End time (inclusive)
    start_step : int, optional
        Start timestep index (inclusive)
    end_step : int, optional
        End timestep index (inclusive)
        
    Returns:
    --------
    dict : Filtered data dictionary
    """
    times = np.array(data['times'])
    
    # Determine indices based on time or step
    if start_step is not None or end_step is not None:
        # Use timestep indices
        start_idx = start_step if start_step is not None else 0
        end_idx = (end_step + 1) if end_step is not None else len(times)
    else:
        # Use time values
        start_idx = 0
        end_idx = len(times)
        
        if start_time is not None:
            start_idx = np.searchsorted(times, start_time, side='left')
        if end_time is not None:
            end_idx = np.searchsorted(times, end_time, side='right')
    
    # Ensure valid range
    start_idx = max(0, start_idx)
    end_idx = min(len(times), end_idx)
    
    # Filter all arrays in data
    filtered_data = {}
    for key, value in data.items():
        if isinstance(value, np.ndarray):
            filtered_data[key] = value[start_idx:end_idx]
        else:
            filtered_data[key] = value
    
    return filtered_data


def check_time_continuity(times):
    """
    Check if time vector has discontinuities.
    
    Parameters:
    -----------
    times : array-like
        Time vector to check
        
    Returns:
    --------
    bool : True if time is continuous (no negative jumps), False otherwise
    """
    times = np.array(times)
    time_diffs = np.diff(times)
    return all(dt > 0 for dt in time_diffs)
