"""
HDF5 Field Data Reader for converted Tecplot files
"""

import h5py
import numpy as np
from pathlib import Path
import glob
import re
from ....utils.logger import Logger


class HDF5FieldReader:
    """Reader for HDF5 field data converted from Tecplot PLT files"""
    
    def __init__(self, case_dir, verbose=False):
        """
        Parameters:
        -----------
        case_dir : str
            Case directory containing binary/converted/ with HDF5 files
        verbose : bool
            Enable verbose logging
        """
        self.case_dir = Path(case_dir)
        self.hdf5_dir = self.case_dir / 'binary' / 'converted'
        self.logger = Logger(verbose=verbose)
        self._discover_files()
    
    def _discover_files(self):
        """Discover available HDF5 files and timesteps"""
        if not self.hdf5_dir.exists():
            self.timesteps = []
            self.files = {}
            return
        
        self.files = {}
        pattern = str(self.hdf5_dir / '*.h5')
        
        for filepath in glob.glob(pattern):
            # Extract timestep from filename
            match = re.search(r'_?(\d+)\.h5$', filepath)
            if match:
                timestep = int(match.group(1))
                self.files[timestep] = filepath
        
        self.timesteps = sorted(self.files.keys())
    
    def get_available_timesteps(self):
        """Get list of available timesteps"""
        return self.timesteps
    
    def get_file_info(self, timestep):
        """
        Get information about HDF5 file
        
        Parameters:
        -----------
        timestep : int
            Timestep number
        
        Returns:
        --------
        dict : Information about the file
        """
        if timestep not in self.files:
            raise ValueError(f"Timestep {timestep} not found. Available: {self.timesteps}")
        
        filepath = self.files[timestep]
        
        with h5py.File(filepath, 'r') as f:
            # Get variable names (dataset names)
            variables = list(f.keys())
            
            # Get dimensions from first variable
            if variables:
                first_var = f[variables[0]]
                shape = first_var.shape
                dtype = first_var.dtype
            else:
                shape = None
                dtype = None
            
            info = {
                'timestep': timestep,
                'filepath': filepath,
                'variables': variables,
                'shape': shape,
                'dtype': str(dtype),
                'num_points': shape[0] if shape else 0
            }
        
        return info
    
    def read_variable(self, timestep, variable):
        """
        Read a single variable from HDF5 file
        
        Parameters:
        -----------
        timestep : int
            Timestep number
        variable : str
            Variable name (e.g., 'Pressure', 'U', 'V', 'W')
        
        Returns:
        --------
        numpy.ndarray : Variable data
        """
        if timestep not in self.files:
            raise ValueError(f"Timestep {timestep} not found")
        
        filepath = self.files[timestep]
        
        with h5py.File(filepath, 'r') as f:
            if variable not in f:
                available = list(f.keys())
                raise ValueError(
                    f"Variable '{variable}' not found. Available variables: {available}"
                )
            
            data = f[variable][:]
        
        return data
    
    def read_timestep(self, timestep, variables=None):
        """
        Read multiple variables from a timestep
        
        Parameters:
        -----------
        timestep : int
            Timestep number
        variables : list, optional
            List of variable names. If None, reads all variables.
        
        Returns:
        --------
        dict : Dictionary mapping variable names to numpy arrays
        """
        if timestep not in self.files:
            raise ValueError(f"Timestep {timestep} not found")
        
        filepath = self.files[timestep]
        data = {}
        
        with h5py.File(filepath, 'r') as f:
            if variables is None:
                variables = list(f.keys())
            
            for var in variables:
                if var in f:
                    data[var] = f[var][:]
                else:
                    self.logger.warning(f"Variable '{var}' not found, skipping")
        
        return data
    
    def get_coordinates(self, timestep):
        """
        Get coordinate arrays (X, Y, Z)
        
        Parameters:
        -----------
        timestep : int
            Timestep number
        
        Returns:
        --------
        tuple : (X, Y, Z) numpy arrays
        """
        data = self.read_timestep(timestep, variables=['X', 'Y', 'Z'])
        return data.get('X'), data.get('Y'), data.get('Z')
    
    def get_velocity(self, timestep):
        """
        Get velocity components (U, V, W)
        
        Parameters:
        -----------
        timestep : int
            Timestep number
        
        Returns:
        --------
        tuple : (U, V, W) numpy arrays
        """
        data = self.read_timestep(timestep, variables=['U', 'V', 'W'])
        return data.get('U'), data.get('V'), data.get('W')
    
    def get_displacement(self, timestep):
        """
        Get displacement components (dispX, dispY, dispZ)
        
        Parameters:
        -----------
        timestep : int
            Timestep number
        
        Returns:
        --------
        tuple : (dispX, dispY, dispZ) numpy arrays
        """
        data = self.read_timestep(timestep, variables=['dispX', 'dispY', 'dispZ'])
        return data.get('dispX'), data.get('dispY'), data.get('dispZ')
    
    def get_statistics(self, timestep, variable):
        """
        Get statistics for a variable
        
        Parameters:
        -----------
        timestep : int
            Timestep number
        variable : str
            Variable name
        
        Returns:
        --------
        dict : Statistics (min, max, mean, std, etc.)
        """
        data = self.read_variable(timestep, variable)
        
        stats = {
            'variable': variable,
            'timestep': timestep,
            'shape': data.shape,
            'min': float(np.min(data)),
            'max': float(np.max(data)),
            'mean': float(np.mean(data)),
            'std': float(np.std(data)),
            'median': float(np.median(data))
        }
        
        return stats
