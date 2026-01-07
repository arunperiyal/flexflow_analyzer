"""
FlexFlow .def File Parser

This module provides utilities to parse FlexFlow .def configuration files.
"""

import os
import glob
import re


def find_def_file(case_directory, problem_name=None):
    """
    Find the .def file in a FlexFlow case directory.
    
    Parameters:
    -----------
    case_directory : str
        Path to FlexFlow case directory
    problem_name : str, optional
        Problem name from simflow.config. If provided, looks for <problem>.def
        
    Returns:
    --------
    str : Path to .def file, or None if not found
    """
    if problem_name:
        # Look for specific problem.def file
        def_file = os.path.join(case_directory, f'{problem_name}.def')
        if os.path.exists(def_file):
            return def_file
    
    # Fall back to finding any .def file
    def_files = glob.glob(os.path.join(case_directory, '*.def'))
    return def_files[0] if def_files else None


def parse_time_stepping_control(def_file_path):
    """
    Parse timeSteppingControl block from .def file.
    
    Parameters:
    -----------
    def_file_path : str
        Path to .def file
        
    Returns:
    --------
    dict : Dictionary with time stepping parameters
    """
    config = {}
    
    try:
        with open(def_file_path, 'r') as f:
            content = f.read()
            
        # Extract timeSteppingControl block
        match = re.search(r'timeSteppingControl\s*\{([^}]*)\}', content, re.DOTALL)
        if match:
            block = match.group(1)
            
            # Parse individual parameters
            params = {
                'initialTimeIncrement': r'initialTimeIncrement\s*=\s*([\d.eE+-]+)',
                'maxTimeSteps': r'maxTimeSteps\s*=\s*(\d+)',
                'order': r'order\s*=\s*(\w+)',
                'highFrequencyDampingFactor': r'highFrequencyDampingFactor\s*=\s*([\d.eE+-]+)'
            }
            
            for param_name, pattern in params.items():
                param_match = re.search(pattern, block)
                if param_match:
                    value = param_match.group(1)
                    # Convert to appropriate type
                    if param_name in ['initialTimeIncrement', 'highFrequencyDampingFactor']:
                        config[param_name] = float(value)
                    elif param_name == 'maxTimeSteps':
                        config[param_name] = int(value)
                    else:
                        config[param_name] = value
                        
    except Exception as e:
        print(f"Warning: Could not parse .def file: {e}")
    
    return config


def parse_def_file(case_directory, problem_name=None):
    """
    Parse FlexFlow .def file and extract all relevant configuration.
    
    Parameters:
    -----------
    case_directory : str
        Path to FlexFlow case directory
    problem_name : str, optional
        Problem name from simflow.config
        
    Returns:
    --------
    dict : Dictionary with parsed parameters
    """
    def_file = find_def_file(case_directory, problem_name)
    
    if not def_file:
        return {}
    
    config = parse_time_stepping_control(def_file)
    config['def_file'] = def_file
    
    return config
