"""
OISD File Reader

This module provides the OISDReader class for reading traction and other surface data
from FlexFlow OISD (Output Integrated Surface Data) files.
"""

import numpy as np


class OISDReader:
    """Class for reading and analyzing OISD files."""
    
    def __init__(self, filenames, tsId_filter=None):
        """
        Initialize OISD reader and load data.
        
        Parameters:
        -----------
        filenames : str or list of str
            Path to the OISD file(s). Can be a single file path or a list of file paths.
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
        self.tot_trac = {}  # Total traction vectors
        self.tot_moment = {}  # Total moment vectors
        self.tot_area = {}  # Total surface area
        self.ave_pres = {}  # Average pressure
        self.tsIds = []
        self.tsId_filter = tsId_filter
        self.time_to_index = {}  # Map time to index for overwriting
        self.time_increment = None
        self._load_data()
    
    def _load_data(self):
        """Read OISD file(s) and extract surface data."""
        for filename in self.filenames:
            self._load_single_file(filename)
    
    def _load_single_file(self, filename):
        """Read a single OISD file and extract surface data."""
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
            
            if line.startswith('totArea '):
                if current_time is not None:
                    if self.tsId_filter is None or current_tsId in (self.tsId_filter if isinstance(self.tsId_filter, list) else [self.tsId_filter]):
                        
                        # Check if this time already exists (restart/overwrite scenario)
                        if current_time in self.time_to_index:
                            timestep_idx = self.time_to_index[current_time]
                            self.tsIds[timestep_idx] = current_tsId
                        else:
                            timestep_idx = len(self.times)
                            self.times.append(current_time)
                            self.tsIds.append(current_tsId)
                            self.time_to_index[current_time] = timestep_idx
                        
                        # Store totArea
                        tot_area = float(line.split()[1])
                        self.tot_area[timestep_idx] = tot_area
                        
                i += 1
                continue
            
            if line.startswith('totTrac '):
                if current_time is not None:
                    if self.tsId_filter is None or current_tsId in (self.tsId_filter if isinstance(self.tsId_filter, list) else [self.tsId_filter]):
                        timestep_idx = self.time_to_index[current_time]
                        
                        # Read totTrac data (next line contains 3 components)
                        i += 1
                        trac_line = lines[i].strip().split()
                        tx, ty, tz = float(trac_line[0]), float(trac_line[1]), float(trac_line[2])
                        self.tot_trac[timestep_idx] = [tx, ty, tz]
                        
                i += 1
                continue
            
            if line.startswith('totMoment '):
                if current_time is not None:
                    if self.tsId_filter is None or current_tsId in (self.tsId_filter if isinstance(self.tsId_filter, list) else [self.tsId_filter]):
                        timestep_idx = self.time_to_index[current_time]
                        
                        # Read totMoment data (next line contains 3 components)
                        i += 1
                        moment_line = lines[i].strip().split()
                        mx, my, mz = float(moment_line[0]), float(moment_line[1]), float(moment_line[2])
                        self.tot_moment[timestep_idx] = [mx, my, mz]
                        
                i += 1
                continue
            
            if line.startswith('avePres '):
                if current_time is not None:
                    if self.tsId_filter is None or current_tsId in (self.tsId_filter if isinstance(self.tsId_filter, list) else [self.tsId_filter]):
                        timestep_idx = self.time_to_index[current_time]
                        ave_pres = float(line.split()[1])
                        self.ave_pres[timestep_idx] = ave_pres
                        
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
        self.time_to_index = {t: i for i, t in enumerate(self.times)}
    
    def get_total_traction(self):
        """
        Get total traction time history.
        
        Returns:
        --------
        dict : Dictionary containing:
            - 'times': numpy array of timesteps
            - 'tx': numpy array of x traction
            - 'ty': numpy array of y traction
            - 'tz': numpy array of z traction
            - 'magnitude': numpy array of traction magnitudes
        """
        times = np.array(self.times)
        num_timesteps = len(times)
        
        tx = np.zeros(num_timesteps)
        ty = np.zeros(num_timesteps)
        tz = np.zeros(num_timesteps)
        
        for t_idx in range(num_timesteps):
            if t_idx in self.tot_trac:
                trac = self.tot_trac[t_idx]
                tx[t_idx] = trac[0]
                ty[t_idx] = trac[1]
                tz[t_idx] = trac[2]
        
        magnitude = np.sqrt(tx**2 + ty**2 + tz**2)
        
        return {
            'times': times,
            'tx': tx,
            'ty': ty,
            'tz': tz,
            'magnitude': magnitude
        }
    
    def get_total_moment(self):
        """
        Get total moment time history.
        
        Returns:
        --------
        dict : Dictionary containing moment data
        """
        times = np.array(self.times)
        num_timesteps = len(times)
        
        mx = np.zeros(num_timesteps)
        my = np.zeros(num_timesteps)
        mz = np.zeros(num_timesteps)
        
        for t_idx in range(num_timesteps):
            if t_idx in self.tot_moment:
                moment = self.tot_moment[t_idx]
                mx[t_idx] = moment[0]
                my[t_idx] = moment[1]
                mz[t_idx] = moment[2]
        
        magnitude = np.sqrt(mx**2 + my**2 + mz**2)
        
        return {
            'times': times,
            'mx': mx,
            'my': my,
            'mz': mz,
            'magnitude': magnitude
        }
    
    def get_average_pressure(self):
        """
        Get average pressure time history.
        
        Returns:
        --------
        dict : Dictionary containing:
            - 'times': numpy array of timesteps
            - 'pressure': numpy array of average pressures
        """
        times = np.array(self.times)
        num_timesteps = len(times)
        
        pressure = np.zeros(num_timesteps)
        
        for t_idx in range(num_timesteps):
            if t_idx in self.ave_pres:
                pressure[t_idx] = self.ave_pres[t_idx]
        
        return {
            'times': times,
            'pressure': pressure
        }
    
    def get_total_area(self):
        """
        Get total surface area time history.
        
        Returns:
        --------
        dict : Dictionary containing area data
        """
        times = np.array(self.times)
        num_timesteps = len(times)
        
        area = np.zeros(num_timesteps)
        
        for t_idx in range(num_timesteps):
            if t_idx in self.tot_area:
                area[t_idx] = self.tot_area[t_idx]
        
        return {
            'times': times,
            'area': area
        }
    
    def __repr__(self):
        return f"OISDReader(files={len(self.filenames)}, timesteps={len(self.times)})"
