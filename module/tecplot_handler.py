"""Tecplot PLT file handling utilities."""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path


def extract_data_pytecplot(case_dir, timestep, zone, variables, output_file=None):
    """Extract data from PLT file using pytecplot via tec360-env wrapper."""
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
    
    # Create a Python script that will run with tec360-env
    script_content = f"""
import tecplot as tp
import pandas as pd

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

# Extract data
data = {{}}
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

# Output
output_file = {"'" + output_file + "'" if output_file else "None"}
if output_file:
    df.to_csv(output_file, index=False)
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


def extract_data_macro(case_dir, timestep, zone, variables, output_file):
    """Extract data from PLT file using Tecplot macro."""
    from .config_handler import load_simflow_config
    
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
