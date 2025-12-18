"""
FlexFlow OTHD Reader and Plotter

A Python toolkit for reading and plotting displacement data from FlexFlow
simulation OTHD (Output Time History Data) files.
"""

from .flexflow_case import FlexFlowCase
from .othd_reader import OTHDReader
from .oisd_reader import OISDReader
from .def_parser import parse_def_file
from .plot_utils import (
    plot_node_displacements, 
    plot_force_data,
    plot_moment_data,
    plot_pressure_data,
    check_time_continuity
)

__version__ = '1.0.0'
__all__ = [
    'FlexFlowCase',
    'OTHDReader',
    'OISDReader',
    'parse_def_file',
    'plot_node_displacements',
    'plot_force_data',
    'plot_moment_data',
    'plot_pressure_data',
    'check_time_continuity',
]
