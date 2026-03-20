"""
OTHD File Reader

This module provides the OTHDReader class for reading displacement data
from FlexFlow OTHD (Output Time History Data) files.
"""

import numpy as np
from tqdm import tqdm


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
        self.pendulum_data = {}  # Store pendulum displacement, velocity, acceleration
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
        current_timestep_idx = None  # Track the current timestep index
        
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('tsId '):
                current_tsId = int(line.split()[1])
                i += 1
                continue
            
            if line.startswith('time '):
                current_time = float(line.split()[1])
                current_timestep_idx = None  # Reset for new time
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
                        
                        current_timestep_idx = timestep_idx  # Track for pendulum data
                        
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
                    else:
                        # Skip this aleDisp section
                        parts = line.split()
                        num_nodes = int(parts[2])
                        i += num_nodes + 1
                        continue
                
                i += 1
                continue
            
            # Read pendulum data fields
            if line.startswith('pendDisp ') or line.startswith('pendVel ') or line.startswith('pendAccel '):
                if current_timestep_idx is not None:
                    field_type = line.split()[0]  # pendDisp, pendVel, or pendAccel
                    i += 1
                    value_line = lines[i].strip()
                    value = float(value_line)
                    
                    if current_timestep_idx not in self.pendulum_data:
                        self.pendulum_data[current_timestep_idx] = {}
                    self.pendulum_data[current_timestep_idx][field_type] = value
                
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
    
    def get_pendulum_data(self):
        """
        Get pendulum time history data.
        
        Returns:
        --------
        dict : Dictionary containing:
            - 'times': numpy array of timesteps
            - 'displacement': numpy array of pendulum displacements
            - 'velocity': numpy array of pendulum velocities
            - 'acceleration': numpy array of pendulum accelerations
        Returns None if no pendulum data is available.
        """
        if not self.pendulum_data:
            return None
        
        times = np.array(self.times)
        num_timesteps = len(times)
        
        displacement = np.zeros(num_timesteps)
        velocity = np.zeros(num_timesteps)
        acceleration = np.zeros(num_timesteps)
        
        for t_idx in range(num_timesteps):
            if t_idx in self.pendulum_data:
                pend_data = self.pendulum_data[t_idx]
                displacement[t_idx] = pend_data.get('pendDisp', 0.0)
                velocity[t_idx] = pend_data.get('pendVel', 0.0)
                acceleration[t_idx] = pend_data.get('pendAccel', 0.0)
        
        return {
            'times': times,
            'displacement': displacement,
            'velocity': velocity,
            'acceleration': acceleration
        }
    
    def __repr__(self):
        return f"OTHDReader(files={len(self.filenames)}, nodes={self.num_nodes}, timesteps={len(self.times)})"
