"""
OTHD File Reader

This module provides the OTHDReader class for reading displacement data
from FlexFlow OTHD (Output Time History Data) files.
"""

import numpy as np


class OTHDReader:
    """Class for reading and analyzing OTHD files."""
    
    def __init__(self, filenames, tsId_filter=None):
        """
        Initialize OTHD reader and load data.
        
        Parameters:
        -----------
        filenames : str or list of str
            Path to the OTHD file(s). Can be a single file path or a list of file paths.
            Files will be processed in order, with later files overwriting data at duplicate times.
        tsId_filter : int or list of int, optional
            Filter to only read specific time series IDs. If None, reads all.
        """
        # Convert single filename to list for uniform processing
        if isinstance(filenames, str):
            self.filenames = [filenames]
        else:
            self.filenames = filenames
            
        self.times = []
        self.displacements = {}
        self.num_nodes = 0
        self.tsIds = []
        self.tsId_filter = tsId_filter
        self.time_to_index = {}  # Map time to index for overwriting
        self.time_increment = None  # Time increment from .def file if available
        self._load_data()
    
    def _load_data(self):
        """Read OTHD file(s) and extract displacement data."""
        for filename in self.filenames:
            self._load_single_file(filename)
    
    def _load_single_file(self, filename):
        """Read a single OTHD file and extract displacement data."""
        with open(filename, 'r') as f:
            lines = f.readlines()
        
        i = 0
        current_time = None
        current_tsId = None
        
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('tsId '):
                current_tsId = int(line.split()[1])
                i += 1
                continue
            
            if line.startswith('time '):
                current_time = float(line.split()[1])
                i += 1
                continue
            
            if line.startswith('aleDisp '):
                # Check if we should include this tsId
                if current_time is not None:
                    if self.tsId_filter is None or current_tsId in (self.tsId_filter if isinstance(self.tsId_filter, list) else [self.tsId_filter]):
                        
                        # Check if this time already exists (restart/overwrite scenario)
                        if current_time in self.time_to_index:
                            # Overwrite existing data for this time
                            timestep_idx = self.time_to_index[current_time]
                            self.tsIds[timestep_idx] = current_tsId
                        else:
                            # New timestep
                            timestep_idx = len(self.times)
                            self.times.append(current_time)
                            self.tsIds.append(current_tsId)
                            self.time_to_index[current_time] = timestep_idx
                        
                        parts = line.split()
                        num_components = int(parts[1])
                        num_nodes = int(parts[2])
                        
                        if self.num_nodes == 0:
                            self.num_nodes = num_nodes
                        
                        for node_idx in range(num_nodes):
                            i += 1
                            disp_line = lines[i].strip().split()
                            dx, dy, dz = float(disp_line[0]), float(disp_line[1]), float(disp_line[2])
                            self.displacements[(timestep_idx, node_idx)] = [dx, dy, dz]
                        
                        current_time = None
                    else:
                        # Skip this aleDisp section
                        parts = line.split()
                        num_nodes = int(parts[2])
                        i += num_nodes + 1
                        current_time = None
                        continue
                
                i += 1
                continue
            
            i += 1
    
    def recalculate_times(self, time_increment):
        """
        Recalculate time vector using a uniform time increment.
        
        Parameters:
        -----------
        time_increment : float
            Time increment (dt) to use for recalculation
        """
        self.time_increment = time_increment
        num_steps = len(self.times)
        self.times = [time_increment * (i + 1) for i in range(num_steps)]
        # Rebuild time_to_index mapping
        self.time_to_index = {t: i for i, t in enumerate(self.times)}
    
    def get_node_displacements(self, node_id):
        """
        Get displacement time history for a specific node.
        
        Parameters:
        -----------
        node_id : int
            Node number (0-indexed)
            
        Returns:
        --------
        dict : Dictionary containing:
            - 'times': numpy array of timesteps
            - 'dx': numpy array of x displacements
            - 'dy': numpy array of y displacements
            - 'dz': numpy array of z displacements
            - 'magnitude': numpy array of displacement magnitudes
        """
        if node_id >= self.num_nodes:
            raise ValueError(f"Node {node_id} does not exist. File contains {self.num_nodes} nodes (0-{self.num_nodes-1})")
        
        times = np.array(self.times)
        num_timesteps = len(times)
        
        dx = np.zeros(num_timesteps)
        dy = np.zeros(num_timesteps)
        dz = np.zeros(num_timesteps)
        
        for t_idx in range(num_timesteps):
            disp = self.displacements[(t_idx, node_id)]
            dx[t_idx] = disp[0]
            dy[t_idx] = disp[1]
            dz[t_idx] = disp[2]
        
        magnitude = np.sqrt(dx**2 + dy**2 + dz**2)
        
        return {
            'times': times,
            'dx': dx,
            'dy': dy,
            'dz': dz,
            'magnitude': magnitude
        }
    
    def __repr__(self):
        return f"OTHDReader(files={len(self.filenames)}, nodes={self.num_nodes}, timesteps={len(self.times)})"
