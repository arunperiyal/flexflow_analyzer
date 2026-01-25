"""Tecplot PLT file handling utilities."""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path


def extract_data_pytecplot(case_dir, timestep, zone, variables, output_file=None, subdomain=None):
    """Extract data from PLT file using pytecplot API in batch mode.
    
    This function uses the new pytecplot-based implementation which works
    reliably in batch mode with Python 3.12 or earlier.
    
    NOTE: Python 3.13+ is NOT compatible with Tecplot 360 2024 R1.
          Use Python 3.12 or earlier (e.g., conda activate flexflow_env).
    
    Parameters:
    -----------
    case_dir : str
        Path to case directory
    timestep : int
        Timestep number
    zone : str
        Zone name to extract from
    variables : list
        List of variable names to extract
    output_file : str, optional
        Output CSV file path
    subdomain : dict, optional
        Subdomain bounds for filtering data
        
    Returns:
    --------
    tuple or None
        (success: bool, output_file or error_message) if successful,
        None to fallback to macro-based extraction
    """
    # Try to use the new pytecplot implementation
    try:
        from .tecplot_pytec import extract_data_pytecplot as pytec_extract
        success, result = pytec_extract(case_dir, timestep, zone, variables, output_file, subdomain)
        if success:
            return (success, result)
        else:
            print(f"[WARNING] PyTecplot extraction failed: {result}")
            print("[INFO] Falling back to macro-based extraction")
            return None
    except ImportError:
        print("[INFO] pytecplot module not available, using macro-based extraction")
        return None
    except Exception as e:
        print(f"[WARNING] PyTecplot error: {e}")
        print("[INFO] Falling back to macro-based extraction")
        return None


def extract_data_macro(case_dir, timestep, zone, variables, output_file, subdomain=None):
    """Extract data from PLT file using Tecplot macro.
    
    NOTE: Due to Tecplot licensing and batch mode limitations, this approach may not work
    reliably in all environments. Alternative approaches:
    
    1. Use 'flexflow data show' command to extract from HDF5 files (recommended)
    2. Open Tecplot GUI and manually export data
    3. Convert PLT to HDF5 first, then use flexflow data commands
    
    Parameters:
    -----------
    case_dir : str
        Path to case directory
    timestep : int
        Timestep number
    zone : str
        Zone name to extract from
    variables : list
        List of variable names to extract
    output_file : str
        Output file path
    subdomain : dict, optional
        Subdomain bounds (Note: subdomain filtering in macros is limited)
    
    Returns:
    --------
    bool
        True if extraction succeeded, False otherwise
    """
    print("\n" + "="*70)
    print("NOTE: PLT extraction has known limitations in batch mode")
    print("="*70)
    print("Recommended alternatives:")
    print("  1. Use 'flexflow data show <case>' to extract from HDF5 files")
    print("  2. Open Tecplot GUI and manually export data")
    print(f"  3. Convert {os.path.basename(case_dir)} to HDF5 format first")
    print("="*70 + "\n")
    
    # Check if HDF5 files exist
    case_path = Path(case_dir)
    hdf5_dir = case_path / 'output'
    if hdf5_dir.exists() and any(hdf5_dir.glob('*.h5')):
        print(f"✓ HDF5 files detected in {hdf5_dir}")
        print(f"  Try: flexflow data show {case_path.name} --timestep {timestep} --variables {','.join(variables)}")
        print()
        return False  # Don't attempt macro extraction if HDF5 available
    
    print("Attempting macro-based PLT extraction...")
    print("(This may not work reliably due to licensing/batch mode issues)\n")
    
    if subdomain:
        print("[WARNING] Subdomain filtering is not fully supported in macro-based extraction")
        print("          Consider post-processing the CSV output for filtering")
    
    case_path = Path(case_dir)
    
    # Parse simflow.config to get problem name
    config_file = case_path / 'simflow.config'
    problem_name = 'riser'  # default
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('problem') and '=' in line and not line.startswith('#'):
                        problem_name = line.split('=')[1].strip()
                        break
        except Exception:
            pass
    
    # Find PLT file
    plt_file = case_path / "binary" / f"{problem_name}.{timestep}.plt"
    if not plt_file.exists():
        print(f"[ERROR] PLT file not found: {plt_file}")
        return False
    
    # Default output file
    if not output_file:
        output_file = case_path / f"{problem_name}_{timestep}_extracted.csv"
    else:
        output_file = Path(output_file)
    
    # Force CSV extension (most compatible format)
    output_file = output_file.with_suffix('.csv')
    
    # Read available variables from PLT file
    from src.commands.field.info_impl.command import read_tecplot_variables
    available_vars = read_tecplot_variables(plt_file)
    
    if not available_vars:
        print("[WARNING] Could not read variables from PLT file, using standard mapping")
        # Use standard variable list
        available_vars = ['X', 'Y', 'Z', 'U', 'V', 'W', 'Pressure', 'dispX', 'dispY', 'dispZ',
                         'eddy', 'xVor', 'yVor', 'zVor', 'QCriterion', 'orderPar']
    
    # Map variable names to indices (1-based for Tecplot)
    var_indices = []
    missing_vars = []
    
    for v in variables:
        try:
            idx = available_vars.index(v) + 1  # 1-based indexing
            var_indices.append(str(idx))
        except ValueError:
            # Try case-insensitive match
            found = False
            for i, av in enumerate(available_vars):
                if av.upper() == v.upper():
                    var_indices.append(str(i + 1))
                    found = True
                    break
            if not found:
                missing_vars.append(v)
    
    if missing_vars:
        print(f"[WARNING] Variables not found in PLT file: {', '.join(missing_vars)}")
        print(f"Available variables: {', '.join(available_vars)}")
    
    if not var_indices:
        print("[ERROR] No valid variables to extract")
        return False
    
    var_list = " ".join(var_indices)
    
    # Create macro file
    macro_file = case_path / f"extract_{timestep}.mcr"
    
    # Use EXPORT with CSV format - most reliable for batch mode
    macro_content = f"""#!MC 1410
$!READDATASET  '{plt_file}' 
  READDATAOPTION = NEW
  RESETSTYLE = YES
$!EXPORTSETUP EXPORTFORMAT = CSV
$!EXPORTSETUP EXPORTFNAME = '{output_file}'
$!EXPORTSETUP INCLUDETEXT = NO
$!EXPORTSETUP INCLUDEGEOM = NO
$!EXPORTSETUP INCLUDECUSTOMLABELS = NO
$!EXPORTSETUP INCLUDEDATA = YES
$!EXPORTSETUP CSVOVERRIDE{{COLUMNHEADERS}} = YES
$!EXPORTSETUP ZONELIST = [1]
$!EXPORTSETUP VARLIST = [{var_list}]
$!EXPORT 
  EXPORTREGION = ALLZONES
$!QUIT
"""
    
    macro_file.write_text(macro_content)
    print(f"Created extraction macro: {macro_file.name}")
    
    # Execute macro with Tecplot 360 in batch mode
    import subprocess
    tec360 = '/usr/local/tecplot/360ex_2024r1/bin/tec360'
    if not os.path.exists(tec360):
        print(f"[ERROR] tec360 not found at {tec360}")
        print("Please ensure Tecplot 360 is installed and the path is correct")
        return False
    
    cmd = [tec360, '-b', '--mesa', '--disable-FBOs', '-p', str(macro_file)]
    print(f"Executing Tecplot 360 in batch mode...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        # Check for success
        if result.returncode == 0 and output_file.exists():
            print(f"✓ Data extracted to: {output_file}")
            
            # Show preview
            try:
                df = pd.read_csv(output_file)
                print(f"\nData preview (first 10 rows of {len(df)} total):")
                print(df.head(10).to_string(index=False))
                if len(df) > 10:
                    print(f"... ({len(df) - 10} more rows)")
                
                # Apply subdomain filtering if requested (post-processing)
                if subdomain:
                    print("\nApplying subdomain filter...")
                    original_len = len(df)
                    mask = pd.Series([True] * len(df))
                    
                    if 'xmin' in subdomain and 'X' in df.columns:
                        mask &= df['X'] >= subdomain['xmin']
                    if 'xmax' in subdomain and 'X' in df.columns:
                        mask &= df['X'] <= subdomain['xmax']
                    if 'ymin' in subdomain and 'Y' in df.columns:
                        mask &= df['Y'] >= subdomain['ymin']
                    if 'ymax' in subdomain and 'Y' in df.columns:
                        mask &= df['Y'] <= subdomain['ymax']
                    if 'zmin' in subdomain and 'Z' in df.columns:
                        mask &= df['Z'] >= subdomain['zmin']
                    if 'zmax' in subdomain and 'Z' in df.columns:
                        mask &= df['Z'] <= subdomain['zmax']
                    
                    df = df[mask]
                    print(f"  Filtered: {original_len} → {len(df)} points")
                    
                    # Save filtered data
                    filtered_output = output_file.with_stem(output_file.stem + '_filtered')
                    df.to_csv(filtered_output, index=False)
                    print(f"✓ Filtered data saved to: {filtered_output}")
                
            except Exception as e:
                print(f"[WARNING] Could not preview data: {e}")
                if os.path.getsize(output_file) > 0:
                    print(f"File size: {os.path.getsize(output_file)} bytes")
            
            # Cleanup macro
            macro_file.unlink()
            return True
        else:
            print(f"[ERROR] Extraction failed")
            if result.stderr:
                print(f"Stderr: {result.stderr}")
            if result.stdout:
                print(f"Stdout (last 500 chars): {result.stdout[-500:]}")
            print(f"Macro file kept for debugging: {macro_file}")
            return False
            
    except subprocess.TimeoutExpired:
        print("[ERROR] Extraction timed out after 120 seconds")
        print(f"Macro file kept for debugging: {macro_file}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
