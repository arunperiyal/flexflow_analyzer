"""
FlexFlow Case Manager

This module provides the FlexFlowCase class to represent and manage
a FlexFlow simulation case directory.
"""

import os
import glob

from .readers.othd_reader import OTHDReader
from .readers.oisd_reader import OISDReader
from .parsers.def_parser import parse_def_file
from tqdm import tqdm


class FlexFlowCase:
    """
    Represents a FlexFlow simulation case directory.
    
    A FlexFlow case directory contains:
    - simflow.config: Configuration file
    - *.def: Definition file with simulation parameters
    - othd_files/: Directory containing OTHD output files
    - Other simulation files (.geo, .srfs, etc.)
    """
    
    def __init__(self, case_directory, verbose=False):
        """
        Initialize FlexFlow case from directory.
        
        Parameters:
        -----------
        case_directory : str
            Path to FlexFlow case directory
        verbose : bool
            Enable verbose output
        """
        self.case_directory = os.path.abspath(case_directory)
        self.verbose = verbose
        
        if not os.path.isdir(self.case_directory):
            raise ValueError(f"Case directory does not exist: {case_directory}")
        
        # Validate case structure
        self._validate_case()
        
        # Parse configuration
        self.config = {}
        self.def_config = {}
        self._parse_config()
        
        # OTHD reader (lazy loaded)
        self._othd_reader = None
        self._othd_files = None
        
        # OISD reader (lazy loaded)
        self._oisd_reader = None
        self._oisd_files = None
    
    def _validate_case(self):
        """Validate that this is a valid FlexFlow case directory."""
        # Check for simflow.config
        simflow_config = os.path.join(self.case_directory, 'simflow.config')
        if not os.path.exists(simflow_config):
            raise ValueError(f"Not a valid FlexFlow case: simflow.config not found in {self.case_directory}")
        
        # Check for othd_files directory
        self.othd_dir = os.path.join(self.case_directory, 'othd_files')
        if not os.path.isdir(self.othd_dir):
            print(f"Warning: othd_files directory not found in {self.case_directory}")
            self.othd_dir = None
        
        # Check for oisd_files directory
        self.oisd_dir = os.path.join(self.case_directory, 'oisd_files')
        if not os.path.isdir(self.oisd_dir):
            print(f"Warning: oisd_files directory not found in {self.case_directory}")
            self.oisd_dir = None
    
    def _parse_config(self):
        """Parse configuration files."""
        # Parse simflow.config
        simflow_config = os.path.join(self.case_directory, 'simflow.config')
        self.config = self._parse_simflow_config(simflow_config)
        
        # Get problem name
        self.problem_name = self.config.get('problem', None)
        
        # Parse .def file using problem name
        self.def_config = parse_def_file(self.case_directory, self.problem_name)
    
    def _parse_simflow_config(self, config_file):
        """
        Parse simflow.config file.
        
        Parameters:
        -----------
        config_file : str
            Path to simflow.config file
            
        Returns:
        --------
        dict : Parsed configuration
        """
        config = {}
        try:
            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse key = value pairs
                    if '=' in line:
                        parts = line.split('=', 1)
                        key = parts[0].strip()
                        value = parts[1].strip()
                        config[key] = value
        except Exception as e:
            print(f"Warning: Could not parse simflow.config: {e}")
        
        return config
    
    def find_othd_files(self, pattern='*.othd'):
        """
        Find all OTHD files in the case.
        
        Parameters:
        -----------
        pattern : str
            File pattern to match (default: '*.othd')
            
        Returns:
        --------
        list : Sorted list of OTHD file paths
        """
        if self._othd_files is None:
            if self.othd_dir is None:
                self._othd_files = []
            else:
                search_path = os.path.join(self.othd_dir, pattern)
                self._othd_files = sorted(glob.glob(search_path))
        
        return self._othd_files
    
    def find_oisd_files(self, pattern='*.oisd'):
        """
        Find all OISD files in the case.
        
        Parameters:
        -----------
        pattern : str
            File pattern to match (default: '*.oisd')
            
        Returns:
        --------
        list : Sorted list of OISD file paths
        """
        if self._oisd_files is None:
            if self.oisd_dir is None:
                self._oisd_files = []
            else:
                search_path = os.path.join(self.oisd_dir, pattern)
                self._oisd_files = sorted(glob.glob(search_path))
        
        return self._oisd_files
    
    def load_othd_data(self, use_def_time=True, tsId_filter=None):
        """
        Load all OTHD files from the case.
        
        Parameters:
        -----------
        use_def_time : bool
            If True, recalculate time vector using initialTimeIncrement from .def file
        tsId_filter : int or list of int, optional
            Filter to only read specific time series IDs
            
        Returns:
        --------
        OTHDReader : Reader object with all data loaded
        """
        othd_files = self.find_othd_files()
        
        if len(othd_files) == 0:
            raise ValueError(f"No OTHD files found in {self.othd_dir}")
        
        print(f"Loading {len(othd_files)} OTHD file(s) from {self.case_directory}")
        
        # Create reader
        reader = OTHDReader(othd_files, tsId_filter=tsId_filter)
        
        # Recalculate times if requested and initialTimeIncrement is available
        if use_def_time and 'initialTimeIncrement' in self.def_config:
            dt = self.def_config['initialTimeIncrement']
            reader.recalculate_times(dt)
            print(f"Using initialTimeIncrement from .def: {dt}")
        
        self._othd_reader = reader
        
        print(f"Loaded: {reader.num_nodes} nodes, {len(reader.times)} timesteps")
        print(f"Time range: {min(reader.times):.4f} to {max(reader.times):.4f}")
        
        return reader
    
    def load_oisd_data(self, use_def_time=True, tsId_filter=None):
        """
        Load all OISD files from the case.
        
        Parameters:
        -----------
        use_def_time : bool
            If True, recalculate time vector using initialTimeIncrement from .def file
        tsId_filter : int or list of int, optional
            Filter to only read specific time series IDs
            
        Returns:
        --------
        OISDReader : Reader object with all data loaded
        """
        oisd_files = self.find_oisd_files()
        
        if len(oisd_files) == 0:
            raise ValueError(f"No OISD files found in {self.oisd_dir}")
        
        print(f"Loading {len(oisd_files)} OISD file(s) from {self.case_directory}")
        
        # Create reader
        reader = OISDReader(oisd_files, tsId_filter=tsId_filter)
        
        # Recalculate times if requested and initialTimeIncrement is available
        if use_def_time and 'initialTimeIncrement' in self.def_config:
            dt = self.def_config['initialTimeIncrement']
            reader.recalculate_times(dt)
            print(f"Using initialTimeIncrement from .def: {dt}")
        
        self._oisd_reader = reader
        
        print(f"Loaded: {len(reader.times)} timesteps")
        print(f"Time range: {min(reader.times):.4f} to {max(reader.times):.4f}")
        
        return reader
    
    @property
    def othd_reader(self):
        """Get OTHD reader (lazy loaded)."""
        if self._othd_reader is None:
            self.load_othd_data()
        return self._othd_reader
    
    @property
    def oisd_reader(self):
        """Get OISD reader (lazy loaded)."""
        if self._oisd_reader is None:
            self.load_oisd_data()
        return self._oisd_reader
    
    def get_node_displacements(self, node_id):
        """
        Get displacement data for a specific node.
        
        Parameters:
        -----------
        node_id : int
            Node number (0-indexed)
            
        Returns:
        --------
        dict : Node displacement data
        """
        return self.othd_reader.get_node_displacements(node_id)
    
    def get_total_traction(self):
        """
        Get total traction data from OISD files.
        
        Returns:
        --------
        dict : Total traction data
        """
        return self.oisd_reader.get_total_traction()
    
    def get_total_moment(self):
        """Get total moment data from OISD files."""
        return self.oisd_reader.get_total_moment()
    
    def get_average_pressure(self):
        """Get average pressure data from OISD files."""
        return self.oisd_reader.get_average_pressure()
    
    def get_time_increment(self):
        """Get time increment from .def file."""
        return self.def_config.get('initialTimeIncrement', None)
    
    def get_max_timesteps(self):
        """Get maximum timesteps from .def file."""
        return self.def_config.get('maxTimeSteps', None)
    
    def __repr__(self):
        return f"FlexFlowCase('{self.case_directory}')"
    
    def __str__(self):
        lines = [
            f"FlexFlow Case: {os.path.basename(self.case_directory)}",
            f"  Directory: {self.case_directory}",
            f"  Problem: {self.config.get('problem', 'N/A')}",
            f"  Time increment: {self.get_time_increment()}",
            f"  Max timesteps: {self.get_max_timesteps()}",
        ]
        
        if self._othd_reader:
            lines.extend([
                f"  OTHD files: {len(self._othd_files)}",
                f"  Nodes: {self._othd_reader.num_nodes}",
                f"  Timesteps loaded: {len(self._othd_reader.times)}",
            ])
        
        return '\n'.join(lines)
