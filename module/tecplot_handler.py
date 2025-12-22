"""Tecplot PLT file handling utilities."""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path


def extract_data_pytecplot(case_dir, timestep, zone, variables, output_file=None, subdomain=None):
    """Extract data from PLT file using pytecplot via tec360-env wrapper.
    
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
        Subdomain bounds as {'xmin': val, 'xmax': val, 'ymin': val, 'ymax': val, 'zmin': val, 'zmax': val}
    """
    import subprocess
    import tempfile
    
    # Check if tec360-env exists
    tec360_env = '/usr/local/tecplot/360ex_2024r1/bin/tec360-env'
    if not os.path.exists(tec360_env):
        print(f"[WARNING] tec360-env not found at {tec360_env}")
        print("Falling back to macro-based extraction...")
        return None  # Signal to try macro approach
    
    #Find the PLT file
    plt_file = Path(case_dir) / "binary" / f"riser.{timestep}.plt"
    if not plt_file.exists():
        print(f"[ERROR] PLT file not found: {plt_file}")
        return False
    
    print(f"Using pytecplot (via tec360-env) for extraction...")
    print(f"Loading PLT file: {plt_file}")
    
    if subdomain:
        print(f"Subdomain filter: {subdomain}")
    
    # Prepare subdomain string for script
    subdomain_str = str(subdomain) if subdomain else 'None'
    
    # Create a Python script that will run with tec360-env
    script_content = f"""
import tecplot as tp
import pandas as pd
import numpy as np

# Load the PLT file
plt_file = r"{plt_file}"
dataset = tp.data.load_tecplot(plt_file)

# Find the zone
target_zone = None
for z in dataset.zones():
    if z.name == "{zone}":
        target_zone = z
        break

if target_zone is None:
    print(f"[ERROR] Zone '{zone}' not found")
    available_zones = [z.name for z in dataset.zones()]
    print(f"Available zones: {{', '.join(available_zones)}}")
    exit(1)

print(f"Extracting zone: {{target_zone.name}}")
print(f"Zone type: {{target_zone.zone_type}}")
print(f"Variables: {variables}")

# Subdomain filtering parameters
subdomain = {subdomain_str}

# Extract data (including coordinates if subdomain filtering needed)
data = {{}}
needs_coordinates = subdomain is not None

# If subdomain is specified, we need X, Y, Z for filtering
coord_vars = []
if needs_coordinates:
    for coord in ['X', 'Y', 'Z']:
        try:
            var = dataset.variable(coord)
            coord_vars.append(coord)
            data[coord] = target_zone.values(var).as_numpy_array()
        except:
            pass  # Coordinate not available

# Extract requested variables
for var_name in {variables}:
    try:
        var = dataset.variable(var_name)
        data[var_name] = target_zone.values(var).as_numpy_array()
    except Exception as e:
        print(f"[WARNING] Could not extract variable '{{var_name}}': {{e}}")

if not data:
    print("[ERROR] No data extracted")
    exit(1)

# Create DataFrame
df = pd.DataFrame(data)
total_points_before = len(df)

# Apply subdomain filtering
if subdomain:
    print(f"\\nApplying subdomain filter...")
    mask = np.ones(len(df), dtype=bool)
    
    if 'xmin' in subdomain and 'X' in df.columns:
        mask &= (df['X'] >= subdomain['xmin'])
        print(f"  X >= {{subdomain['xmin']}}")
    if 'xmax' in subdomain and 'X' in df.columns:
        mask &= (df['X'] <= subdomain['xmax'])
        print(f"  X <= {{subdomain['xmax']}}")
    if 'ymin' in subdomain and 'Y' in df.columns:
        mask &= (df['Y'] >= subdomain['ymin'])
        print(f"  Y >= {{subdomain['ymin']}}")
    if 'ymax' in subdomain and 'Y' in df.columns:
        mask &= (df['Y'] <= subdomain['ymax'])
        print(f"  Y <= {{subdomain['ymax']}}")
    if 'zmin' in subdomain and 'Z' in df.columns:
        mask &= (df['Z'] >= subdomain['zmin'])
        print(f"  Z >= {{subdomain['zmin']}}")
    if 'zmax' in subdomain and 'Z' in df.columns:
        mask &= (df['Z'] <= subdomain['zmax'])
        print(f"  Z <= {{subdomain['zmax']}}")
    
    df = df[mask].copy()
    print(f"\\nFiltered: {{total_points_before}} points -> {{len(df)}} points")
    
    # Check if any points remain
    if len(df) == 0:
        print("[ERROR] No points found within specified subdomain")
        exit(1)
    
    # Remove coordinate columns if they weren't requested
    requested_vars = {variables}
    for coord in coord_vars:
        if coord not in requested_vars:
            df = df.drop(columns=[coord])

# Reset index after filtering
df = df.reset_index(drop=True)

# Output
output_file = {"'" + output_file + "'" if output_file else "None"}
if output_file:
    # Write metadata as comments at the beginning
    with open(output_file, 'w') as f:
        f.write(f"# Tecplot data extraction\\n")
        f.write(f"# Source: {plt_file}\\n")
        f.write(f"# Zone: {zone}\\n")
        f.write(f"# Timestep: {timestep}\\n")
        f.write(f"# Variables: {{', '.join(requested_vars)}}\\n")
        if subdomain:
            f.write(f"# Subdomain: {{subdomain}}\\n")
        f.write(f"# Total points: {{len(df)}}\\n")
        f.write(f"#\\n")
    
    # Append the data
    df.to_csv(output_file, mode='a', index=False)
    print(f"✓ Data saved to: {{output_file}}")
    print(f"  Rows: {{len(df)}}")
    print(f"  Columns: {{list(df.columns)}}")
else:
    print(f"\\nData preview (first 10 rows of {{len(df)}} total):")
    print(df.head(10).to_string(index=False))
    if len(df) > 10:
        print(f"\\n... ({{len(df) - 10}} more rows)")
"""
    
    # Write script to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script_content)
        script_file = f.name
    
    try:
        # Run with tec360-env
        result = subprocess.run(
            [tec360_env, '--', 'python3', script_file],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        return result.returncode == 0
    
    except Exception as e:
        print(f"[ERROR] Failed to extract data: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        os.unlink(script_file)


def extract_data_macro(case_dir, timestep, zone, variables, output_file, subdomain=None):
    """Extract data from PLT file using Tecplot macro.
    
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
    """
    from .config_handler import load_simflow_config
    
    if subdomain:
        print("[WARNING] Subdomain filtering is not fully supported in macro-based extraction")
        print("          Please use pytecplot-based extraction for subdomain filtering")
    
    case_path = Path(case_dir)
    config = load_simflow_config(case_path)
    problem_name = config.get('problem', 'riser')
    
    # Find PLT file
    plt_file = case_path / "binary" / f"{problem_name}.{timestep}.plt"
    if not plt_file.exists():
        print(f"[ERROR] PLT file not found: {plt_file}")
        return False
    
    # Default output file
    if not output_file:
        output_file = case_path / f"{problem_name}.{timestep}.dat"
    else:
        output_file = Path(output_file)
    
    # Create macro
    macro_file = case_path / "extract_data.mcr"
    
    var_list = " ".join([f'"{v}"' for v in variables])
    
    macro_content = f"""#!MC 1410
$!READDATASET  '{plt_file}' 
  READDATAOPTION = NEW
  RESETSTYLE = YES
$!EXPORTSETUP EXPORTFORMAT = TECPLOT
$!EXPORTSETUP EXPORTFNAME = '{output_file}'
$!EXPORTSETUP INCLUDETEXT = NO
$!EXPORTSETUP INCLUDEGEOM = NO
$!EXPORTSETUP INCLUDECUSTOMLABELS = NO
$!EXPORTSETUP INCLUDEDATA = YES
$!EXPORTSETUP ZONELIST = ["{zone}"]
$!EXPORTSETUP VARLIST = [{var_list}]
$!EXPORT
$!QUIT
"""
    
    macro_file.write_text(macro_content)
    print(f"Created macro: {macro_file}")
    
    # Execute macro
    import subprocess
    cmd = ['tec360', '-b', '--osmesa', '-p', str(macro_file)]
    print(f"Executing: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0 and output_file.exists():
        print(f"✓ Data extracted to: {output_file}")
        
        # Show preview
        try:
            df = pd.read_csv(output_file, delim_whitespace=True, skiprows=1)
            print(f"\nData preview (first 10 rows of {len(df)} total):")
            print(df.head(10).to_string(index=False))
        except Exception as e:
            print(f"[WARNING] Could not preview data: {e}")
        
        # Cleanup macro
        macro_file.unlink()
        return True
    else:
        print(f"[ERROR] Extraction failed")
        if result.stderr:
            print(result.stderr)
        return False
