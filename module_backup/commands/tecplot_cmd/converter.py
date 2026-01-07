"""
PLT to HDF5/VTK converter using pytecplot API (preferred) or Tecplot 360 macros (fallback)
"""

import os
import sys
import subprocess
import glob
import re
from pathlib import Path
from ...utils.logger import Logger


class TecplotConverter:
    """Convert Tecplot binary PLT files to HDF5/VTK format"""
    
    def __init__(self, case_dir, verbose=False, use_pytecplot=True):
        """
        Parameters:
        -----------
        case_dir : str
            Case directory containing binary/ subdirectory with PLT files
        verbose : bool
            Enable verbose logging
        use_pytecplot : bool
            Try to use pytecplot API first (recommended, faster and more reliable)
        """
        self.case_dir = Path(case_dir)
        self.binary_dir = self.case_dir / 'binary'
        self.logger = Logger(verbose=verbose)
        self.use_pytecplot = use_pytecplot
        self.tec360_path = self._find_tecplot()
        
    def _find_tecplot(self):
        """Find Tecplot 360 installation and wrapper script"""
        # Check environment variable first
        tec_home = os.environ.get('TEC360HOME')
        if tec_home and os.path.exists(tec_home):
            # Prefer tec360-env wrapper script
            tec360_env = os.path.join(tec_home, 'bin', 'tec360-env')
            if os.path.exists(tec360_env):
                return {'env_wrapper': tec360_env, 'tec360': os.path.join(tec_home, 'bin', 'tec360')}
            
            tec360 = os.path.join(tec_home, 'bin', 'tec360')
            if os.path.exists(tec360):
                return {'env_wrapper': None, 'tec360': tec360}
        
        # Check common installation paths
        common_paths = [
            '/usr/local/tecplot/360ex_2024r1',
            '/usr/local/tecplot/360ex_2022r1',
            '/opt/tecplot/360ex_2024r1',
            '/opt/tecplot/360ex_2022r1',
            '/usr/local/tecplot/360',
        ]
        
        for base_path in common_paths:
            tec360_env = os.path.join(base_path, 'bin', 'tec360-env')
            tec360 = os.path.join(base_path, 'bin', 'tec360')
            
            if os.path.exists(tec360_env) and os.path.exists(tec360):
                return {'env_wrapper': tec360_env, 'tec360': tec360}
            elif os.path.exists(tec360):
                return {'env_wrapper': None, 'tec360': tec360}
        
        # Try to find in PATH
        try:
            result = subprocess.run(['which', 'tec360'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                tec360_path = result.stdout.strip()
                # Try to find wrapper in same directory
                tec360_env = os.path.join(os.path.dirname(tec360_path), 'tec360-env')
                if os.path.exists(tec360_env):
                    return {'env_wrapper': tec360_env, 'tec360': tec360_path}
                return {'env_wrapper': None, 'tec360': tec360_path}
        except:
            pass
        
        return None
    
    def discover_plt_files(self):
        """
        Discover all PLT files in binary directory
        
        Returns:
        --------
        list : List of (timestep, filepath) tuples sorted by timestep
        """
        if not self.binary_dir.exists():
            raise FileNotFoundError(f"Binary directory not found: {self.binary_dir}")
        
        plt_files = []
        pattern = str(self.binary_dir / '*.plt')
        
        for filepath in glob.glob(pattern):
            # Extract timestep from filename (e.g., riser.100.plt -> 100)
            match = re.search(r'\.(\d+)\.plt$', filepath)
            if match:
                timestep = int(match.group(1))
                plt_files.append((timestep, filepath))
        
        return sorted(plt_files)
    
    def _create_macro(self, plt_files, output_format, output_dir, keep_original):
        """
        Create Tecplot macro for batch conversion
        
        Parameters:
        -----------
        plt_files : list
            List of (timestep, filepath) tuples
        output_format : str
            Output format: 'hdf5', 'vtk', or 'netcdf'
        output_dir : Path
            Output directory
        keep_original : bool
            Whether to keep original PLT files
        
        Returns:
        --------
        str : Path to created macro file
        """
        macro_file = self.case_dir / 'convert_plt.mcr'
        
        # Format-specific settings
        format_map = {
            'hdf5': ('HDF5', '.h5', True),  # (format, extension, needs_addon)
            'vtk': ('VTK', '.vtk', False),
            'netcdf': ('NETCDF', '.nc', False)
        }
        
        format_info = format_map.get(output_format.lower(), ('HDF5', '.h5', True))
        tec_format, ext, needs_addon = format_info
        
        # Create macro content
        total_files = len(plt_files)
        macro_lines = [
            '#!MC 1410',
            '',
            '# FlexFlow PLT to {} Conversion Macro'.format(output_format.upper()),
            '# Generated automatically by FlexFlow',
            f'# Total files to convert: {total_files}',
            f'# Output directory: {output_dir}',
            '',
        ]
        
        for idx, (timestep, plt_path) in enumerate(plt_files, 1):
            basename = os.path.basename(plt_path).replace('.plt', '')
            output_file = output_dir / f"{basename}{ext}"
            
            # Calculate progress percentage
            progress_pct = (idx * 100) // total_files
            
            # For HDF5, use the addon loader syntax instead of WriteDataSet
            if needs_addon and tec_format == 'HDF5':
                macro_lines.extend([
                    '',
                    f'# [{idx}/{total_files}] Converting timestep {timestep} ({progress_pct}% complete)',
                    f'# Input:  {basename}.plt',
                    f'# Output: {basename}{ext}',
                    f'$!ReadDataSet "{plt_path}"',
                    f'  ReadDataOption = New',
                    f'$!EXTENDEDCOMMAND',
                    f'  COMMANDPROCESSORID = \'HDF5 Loader\'',
                    f'  COMMAND = \'SaveData "{output_file}"\'',
                    ''
                ])
            else:
                # Standard WriteDataSet for VTK, NetCDF, etc.
                macro_lines.extend([
                    '',
                    f'# [{idx}/{total_files}] Converting timestep {timestep} ({progress_pct}% complete)',
                    f'$!PRINT " "',
                    f'$!PRINT "Converting [{idx}/{total_files}]: {basename}.plt -> {basename}{ext}"',
                    f'$!PRINT "Progress: {progress_pct}%"',
                    f'$!ReadDataSet "{plt_path}"',
                    f'  ReadDataOption = New',
                    f'$!WriteDataSet "{output_file}"',
                    f'# [{idx}/{total_files}] Converting timestep {timestep} ({progress_pct}% complete)',
                    f'# Input:  {basename}.plt',
                    f'# Output: {basename}{ext}',
                    f'$!ReadDataSet "{plt_path}"',
                    f'  ReadDataOption = New',
                    f'$!WriteDataSet "{output_file}"',
                    f'  DataSetWriteFormat = {tec_format}',
                    f'  Binary = Yes',
                    f'  Precision = Double',
                    f'  IncludeText = No',
                    f'  IncludeGeom = No',
                    ''
                ])
        
        # Add completion comment
        macro_lines.extend([
            '',
            f'# Conversion complete!',
            f'# Total files: {total_files}',
            f'# Output location: {output_dir}',
            f'# Format: {output_format.upper()}',
            ''
        ])
        
        # Write macro file
        with open(macro_file, 'w') as f:
            f.write('\n'.join(macro_lines))
        
        self.logger.info(f"Created conversion macro: {macro_file}")
        return str(macro_file)
    
    def convert(self, output_format='hdf5', start_step=None, end_step=None, 
                keep_original=True, output_dir=None):
        """
        Convert PLT files to specified format
        
        Parameters:
        -----------
        output_format : str
            Output format: 'hdf5', 'vtk', or 'netcdf'
        start_step : int, optional
            Start timestep (inclusive)
        end_step : int, optional
            End timestep (inclusive)
        keep_original : bool
            Keep original PLT files after conversion
        output_dir : str, optional
            Output directory (default: binary/converted)
        
        Returns:
        --------
        list : List of converted file paths
        """
        # Try pytecplot first if requested
        if self.use_pytecplot:
            self.logger.info("Attempting pytecplot-based conversion...")
            try:
                from ...tecplot_pytec import convert_plt_to_format, check_python_version
                
                # Check Python version compatibility
                compatible, msg = check_python_version()
                if not compatible:
                    self.logger.warning(msg)
                    self.logger.info("Falling back to macro-based conversion")
                else:
                    # Try pytecplot conversion
                    success, result = convert_plt_to_format(
                        self.case_dir, 
                        output_format=output_format,
                        start_step=start_step,
                        end_step=end_step,
                        keep_original=keep_original,
                        output_dir=output_dir
                    )
                    
                    if success:
                        self.logger.success("PyTecplot conversion completed successfully!")
                        return result
                    else:
                        self.logger.warning(f"PyTecplot conversion failed: {result}")
                        self.logger.info("Falling back to macro-based conversion")
            except ImportError:
                self.logger.warning("pytecplot not installed, using macro-based conversion")
            except Exception as e:
                self.logger.warning(f"PyTecplot error: {e}")
                self.logger.info("Falling back to macro-based conversion")
        
        # Fallback to macro-based conversion
        self.logger.info("Using macro-based conversion...")
        
        # Check Tecplot availability
        if not self.tec360_path:
            raise RuntimeError(
                "Tecplot 360 not found. Please install Tecplot or set TEC360HOME environment variable.\n"
                "Example: export TEC360HOME=/usr/local/tecplot/360ex_2022r1"
            )
        
        tec_info = self.tec360_path
        if isinstance(tec_info, dict):
            if tec_info['env_wrapper']:
                self.logger.info(f"Using Tecplot wrapper: {tec_info['env_wrapper']}")
            else:
                self.logger.info(f"Using Tecplot: {tec_info['tec360']}")
        else:
            self.logger.info(f"Using Tecplot: {tec_info}")
        
        # Discover PLT files
        self.logger.info("Discovering PLT files...")
        all_plt_files = self.discover_plt_files()
        
        if not all_plt_files:
            raise FileNotFoundError(f"No PLT files found in {self.binary_dir}")
        
        self.logger.info(f"Found {len(all_plt_files)} PLT files")
        
        # Show available timestep range
        if all_plt_files:
            first_step = all_plt_files[0][0]
            last_step = all_plt_files[-1][0]
            increment = all_plt_files[1][0] - all_plt_files[0][0] if len(all_plt_files) > 1 else None
            self.logger.info(f"Available timesteps: {first_step} to {last_step}" + 
                           (f" (increment: {increment})" if increment else ""))
        
        # Filter by time range if specified
        if start_step is not None or end_step is not None:
            filtered = []
            for timestep, filepath in all_plt_files:
                if start_step and timestep < start_step:
                    continue
                if end_step and timestep > end_step:
                    continue
                filtered.append((timestep, filepath))
            plt_files = filtered
            self.logger.info(f"Filtered to {len(plt_files)} files (steps {start_step or 'start'} to {end_step or 'end'})")
        else:
            plt_files = all_plt_files
        
        if not plt_files:
            self.logger.error("No files match the specified time range")
            if all_plt_files:
                first_step = all_plt_files[0][0]
                last_step = all_plt_files[-1][0]
                self.logger.error(f"Available range: {first_step} to {last_step}")
                self.logger.error(f"You specified: {start_step or 'start'} to {end_step or 'end'}")
            return []
        
        # Estimate conversion time
        avg_size_mb = 187  # Average PLT file size in MB
        time_per_file_sec = 60  # Estimated ~1 minute per file
        estimated_time_min = (len(plt_files) * time_per_file_sec) / 60
        
        self.logger.info(f"Converting {len(plt_files)} files")
        self.logger.info(f"Estimated time: ~{estimated_time_min:.1f} minutes")
        
        # Determine output directory
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = self.binary_dir / 'converted'
        
        out_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Output directory: {out_dir}")
        
        # Create conversion macro
        self.logger.info("Creating Tecplot macro...")
        macro_file = self._create_macro(plt_files, output_format, out_dir, keep_original)
        
        # Prepare command and environment
        tec_info = self.tec360_path
        env = os.environ.copy()
        
        # Set environment variables to prevent GUI/display issues
        env['DISPLAY'] = ''  # No display
        env['QT_QPA_PLATFORM'] = 'offscreen'  # Qt offscreen
        
        if isinstance(tec_info, dict):
            if tec_info['env_wrapper']:
                # Use tec360-env wrapper - it sets up proper environment
                cmd = [tec_info['env_wrapper'], '--', tec_info['tec360'], '-b', '-mesa', '-p', macro_file]
                self.logger.info("Using tec360-env wrapper with -mesa (offscreen rendering)")
            else:
                # Direct tec360 call with -mesa for offscreen
                cmd = [tec_info['tec360'], '-b', '-mesa', '-p', macro_file]
                self.logger.info("Using tec360 with -mesa (offscreen rendering)")
        else:
            # Legacy path (string)
            cmd = [tec_info, '-b', '-mesa', '-p', macro_file]
        
        # Run Tecplot in batch mode
        self.logger.info("Running Tecplot batch conversion...")
        self.logger.info("This may take several minutes depending on file size...")
        print()  # Blank line before Tecplot output
        
        try:
            # Use Popen to stream output in real-time
            import sys
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                env=env,  # Pass modified environment
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            # Stream output in real-time
            stdout_lines = []
            for line in iter(process.stdout.readline, ''):
                if line:
                    line = line.rstrip()
                    print(line)
                    sys.stdout.flush()  # Force flush for immediate display
                    stdout_lines.append(line)
            
            # Wait for completion
            process.wait(timeout=3600)  # 1 hour timeout
            
            # Check for errors
            if process.returncode != 0:
                self.logger.error("Tecplot conversion failed")
                self.logger.error(f"Return code: {process.returncode}")
                # Print last few lines of output for context
                if stdout_lines:
                    self.logger.error("Last output lines:")
                    for line in stdout_lines[-10:]:
                        self.logger.error(f"  {line}")
                raise RuntimeError("Tecplot conversion failed")
            
            print()  # Blank line after Tecplot output
            self.logger.success("Conversion completed successfully!")
            
            # Verify converted files - define format_map here
            format_map = {
                'hdf5': ('TECPLOTH5', '.h5'),
                'vtk': ('VTK', '.vtk'),
                'netcdf': ('NETCDF', '.nc')
            }
            
            file_ext = format_map[output_format.lower()][1].lstrip('.')
            converted_files = list(out_dir.glob(f"*.{file_ext}"))
            self.logger.info(f"Created {len(converted_files)} converted files")
            
            # Clean up macro
            os.remove(macro_file)
            
            # Delete originals if requested
            if not keep_original:
                self.logger.info("Removing original PLT files...")
                for _, plt_path in plt_files:
                    try:
                        os.remove(plt_path)
                    except Exception as e:
                        self.logger.warning(f"Could not remove {plt_path}: {e}")
                self.logger.success("Original PLT files removed")
            
            return [str(f) for f in converted_files]
            
        except subprocess.TimeoutExpired:
            self.logger.error("Conversion timed out after 1 hour")
            raise
        except Exception as e:
            self.logger.error(f"Conversion error: {e}")
            raise
