"""
PyTecplot-based utilities for Tecplot PLT file operations.

This module provides Python 3.12 compatible pytecplot functions
for batch mode data extraction and file conversion.

NOTE: Requires Python 3.12 or earlier (Python 3.13 is not compatible with Tecplot 2024 R1)
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import box

# Import Colors for non-rich output
try:
    from src.utils.colors import Colors
except ImportError:
    # Fallback if running standalone
    class Colors:
        BOLD = '\033[1m'
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        RESET = '\033[0m'
        DIM = '\033[2m'


def check_python_version():
    """Check if current Python version is compatible with pytecplot"""
    if sys.version_info >= (3, 13):
        return False, "Python 3.13+ is not compatible with Tecplot 360 2024 R1. Use Python 3.12 or earlier."
    return True, "OK"


def initialize_tecplot_batch():
    """
    Initialize Tecplot in batch mode.
    
    Returns:
    --------
    tuple : (success: bool, tecplot_module or error_message)
    """
    # Check Python version first
    compatible, msg = check_python_version()
    if not compatible:
        return False, msg
    
    try:
        import tecplot as tp
        from tecplot.exception import TecplotSystemError
        
        # Check if already connected
        try:
            # Try a simple operation to test connection
            _ = tp.__version__
            return True, tp
        except:
            pass
        
        # Not connected, return module for caller to handle connection
        return True, tp
        
    except ImportError as e:
        return False, f"pytecplot not installed: {e}"
    except Exception as e:
        return False, f"Failed to import tecplot: {e}"


def extract_data_pytecplot(case_dir, timestep, zone=None, variables=None, output_file=None, subdomain=None):
    """
    Extract data from PLT file using pytecplot API in batch mode.
    
    This is the recommended approach for Python-based data extraction.
    
    Parameters:
    -----------
    case_dir : str or Path
        Path to case directory
    timestep : int
        Timestep number
    zone : str or int, optional
        Zone name or index to extract from (1-based). If None, extracts all zones.
    variables : list, optional
        List of variable names to extract. If None, extracts all variables.
    output_file : str or Path, optional
        Output CSV file path. If None, generates default name.
    subdomain : dict, optional
        Subdomain bounds for filtering data: {'xmin': 0, 'xmax': 10, ...}
        
    Returns:
    --------
    tuple : (success: bool, output_file_path or error_message)
    """
    case_path = Path(case_dir)
    
    # Parse simflow.config to get problem name
    from src.core.simflow_config import SimflowConfig
    problem_name = SimflowConfig.find(case_path).problem or 'riser'
    
    # Find PLT file
    plt_file = case_path / "binary" / f"{problem_name}.{timestep}.plt"
    if not plt_file.exists():
        return False, f"PLT file not found: {plt_file}"
    
    # Initialize tecplot
    success, result = initialize_tecplot_batch()
    if not success:
        return False, result
    
    tp = result
    
    try:
        console = Console()

        # Header
        console.print()
        console.print(f"[bold cyan]{'='*70}[/bold cyan]")
        console.print(f"[bold cyan]Field Data Extraction[/bold cyan]")
        console.print(f"[bold cyan]{'='*70}[/bold cyan]")
        console.print()

        # Loading message
        console.print(f"[dim]Loading PLT file:[/dim] [yellow]{plt_file.name}[/yellow]")

        # Load the dataset
        dataset = tp.data.load_tecplot(str(plt_file), read_data_option=tp.constant.ReadDataOption.Replace)

        console.print(f"[green]✓[/green] [bold]Dataset loaded successfully[/bold]")
        console.print(f"  [cyan]Zones:[/cyan] {dataset.num_zones}")
        console.print(f"  [cyan]Variables:[/cyan] {dataset.num_variables}")
        console.print()

        # Show available zones and variables in a table
        zone_names = [z.name for z in dataset.zones()]
        var_names = [v.name for v in dataset.variables()]

        # Zones table
        zones_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        zones_table.add_column("Label", style="cyan bold")
        zones_table.add_column("Value", style="white")
        zones_table.add_row("Available Zones", ", ".join(f"[yellow]{z}[/yellow]" for z in zone_names))
        console.print(zones_table)

        # Variables in columns
        console.print(f"\n[cyan bold]Available Variables ({len(var_names)}):[/cyan bold]")
        # Display in 4 columns
        cols = 4
        var_table = Table(box=None, show_header=False, padding=(0, 2))
        for _ in range(cols):
            var_table.add_column(style="yellow")

        for i in range(0, len(var_names), cols):
            row_vars = var_names[i:i+cols]
            var_table.add_row(*row_vars)

        console.print(var_table)
        console.print()
        
        # Determine which zone to extract
        if zone is None:
            # Extract all zones
            zones_to_extract = list(range(dataset.num_zones))
        elif isinstance(zone, int):
            # Zone index (0-based in pytecplot)
            zones_to_extract = [zone - 1] if zone > 0 else [zone]
        else:
            # Zone name
            zones_to_extract = []
            for i, z in enumerate(dataset.zones()):
                if z.name == zone or z.name.upper() == zone.upper():
                    zones_to_extract.append(i)
                    break
            if not zones_to_extract:
                return False, f"Zone '{zone}' not found. Available: {', '.join(zone_names)}"
        
        # Determine which variables to extract
        if variables is None:
            var_indices = list(range(dataset.num_variables))
        else:
            var_indices = []
            missing = []
            for var in variables:
                found = False
                for i, v in enumerate(dataset.variables()):
                    if v.name == var or v.name.upper() == var.upper():
                        var_indices.append(i)
                        found = True
                        break
                if not found:
                    missing.append(var)
            
            if missing:
                print(f"[WARNING] Variables not found: {', '.join(missing)}")
            
            if not var_indices:
                return False, f"No valid variables to extract"
        
        # Extract data
        all_data = []

        console.print(f"[bold cyan]Extraction Details:[/bold cyan]")
        console.print()

        for zone_idx in zones_to_extract:
            zone_obj = dataset.zone(zone_idx)

            # Create extraction info table
            extract_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
            extract_table.add_column("Label", style="cyan")
            extract_table.add_column("Value", style="white")
            extract_table.add_row("Zone", f"[yellow]{zone_obj.name}[/yellow] (#{zone_idx + 1})")
            extract_table.add_row("Points", f"{zone_obj.num_points:,}")

            # Build data dictionary
            data_dict = {}
            extracted_vars = []
            for var_idx in var_indices:
                var_obj = dataset.variable(var_idx)
                var_name = var_obj.name
                extracted_vars.append(var_name)

                # Get data as numpy array
                var_data = zone_obj.values(var_idx)[:]
                data_dict[var_name] = var_data

            extract_table.add_row("Variables", f"[yellow]{', '.join(extracted_vars)}[/yellow]")

            # Create DataFrame
            df = pd.DataFrame(data_dict)

            # Apply subdomain filter if specified
            if subdomain:
                original_len = len(df)
                mask = pd.Series([True] * len(df))

                coord_map = {'X': 'xmin', 'Y': 'ymin', 'Z': 'zmin'}
                bounds_applied = []
                for coord, bound_prefix in coord_map.items():
                    min_key = f'{bound_prefix[0]}min'
                    max_key = f'{bound_prefix[0]}max'

                    if min_key in subdomain and coord in df.columns:
                        mask &= df[coord] >= subdomain[min_key]
                        bounds_applied.append(f"{coord} ≥ {subdomain[min_key]}")
                    if max_key in subdomain and coord in df.columns:
                        mask &= df[coord] <= subdomain[max_key]
                        bounds_applied.append(f"{coord} ≤ {subdomain[max_key]}")

                df = df[mask]
                extract_table.add_row("Subdomain", f"[yellow]{', '.join(bounds_applied)}[/yellow]")
                extract_table.add_row("Filtered", f"{original_len:,} → [green]{len(df):,}[/green] points")

            console.print(extract_table)
            console.print()

            all_data.append(df)

        # Combine all zones
        if len(all_data) > 1:
            combined_df = pd.concat(all_data, ignore_index=True)
            console.print(f"[green]✓[/green] Combined {len(all_data)} zones: [bold]{len(combined_df):,}[/bold] total points")
        else:
            combined_df = all_data[0]
        
        # Determine output file
        if output_file is None:
            if subdomain:
                output_file = case_path / f"{problem_name}_{timestep}_filtered.csv"
            else:
                output_file = case_path / f"{problem_name}_{timestep}_extracted.csv"
        else:
            output_file = Path(output_file)
        
        # Save to CSV
        combined_df.to_csv(output_file, index=False)

        # Output summary
        console.print()
        console.print(f"[bold cyan]{'='*70}[/bold cyan]")
        console.print(f"[bold cyan]Extraction Complete[/bold cyan]")
        console.print(f"[bold cyan]{'='*70}[/bold cyan]")
        console.print()

        # Summary table
        summary_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        summary_table.add_column("Label", style="cyan bold")
        summary_table.add_column("Value", style="white")
        summary_table.add_row("Output File", f"[yellow]{output_file}[/yellow]")
        summary_table.add_row("Total Points", f"[green bold]{len(combined_df):,}[/green bold]")
        summary_table.add_row("Variables", f"[yellow]{', '.join(combined_df.columns)}[/yellow]")
        console.print(summary_table)
        console.print()

        # Show data preview in a nice table
        if len(combined_df) > 0:
            console.print(f"[bold cyan]Data Preview:[/bold cyan]")
            console.print()

            # Create data preview table
            preview_rows = min(10, len(combined_df))
            preview_df = combined_df.head(preview_rows)

            data_table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold yellow")

            # Add columns
            for col in preview_df.columns:
                data_table.add_column(col, style="white", justify="right")

            # Add rows
            for _, row in preview_df.iterrows():
                formatted_values = []
                for val in row:
                    if isinstance(val, (int, np.integer)):
                        formatted_values.append(f"{val:,}")
                    elif isinstance(val, (float, np.floating)):
                        # Format with appropriate precision
                        if abs(val) < 1e-3 or abs(val) > 1e6:
                            formatted_values.append(f"{val:.6e}")
                        else:
                            formatted_values.append(f"{val:.6f}")
                    else:
                        formatted_values.append(str(val))
                data_table.add_row(*formatted_values)

            console.print(data_table)

            if len(combined_df) > preview_rows:
                console.print(f"\n[dim]... and {len(combined_df) - preview_rows:,} more rows[/dim]")

            console.print()

        return True, str(output_file)
        
    except Exception as e:
        import traceback
        error_msg = f"Error extracting data: {e}\n{traceback.format_exc()}"
        return False, error_msg


def convert_plt_to_format(case_dir, output_format='hdf5', start_step=None, end_step=None, 
                          keep_original=True, output_dir=None):
    """
    Convert PLT files to specified format using pytecplot API.
    
    Parameters:
    -----------
    case_dir : str or Path
        Path to case directory containing binary/ subdirectory
    output_format : str
        Output format: 'hdf5', 'szplt', or 'dat'
    start_step : int, optional
        Start timestep (inclusive)
    end_step : int, optional
        End timestep (inclusive)
    keep_original : bool
        Keep original PLT files after conversion
    output_dir : str or Path, optional
        Output directory (default: binary/converted)
        
    Returns:
    --------
    tuple : (success: bool, list_of_converted_files or error_message)
    """
    case_path = Path(case_dir)
    binary_dir = case_path / 'binary'
    
    if not binary_dir.exists():
        return False, f"Binary directory not found: {binary_dir}"
    
    # Initialize tecplot
    success, result = initialize_tecplot_batch()
    if not success:
        return False, result
    
    tp = result
    
    # Find PLT files
    import glob
    import re
    
    plt_files = []
    for filepath in glob.glob(str(binary_dir / '*.plt')):
        match = re.search(r'\.(\d+)\.plt$', filepath)
        if match:
            timestep = int(match.group(1))
            if start_step and timestep < start_step:
                continue
            if end_step and timestep > end_step:
                continue
            plt_files.append((timestep, filepath))
    
    plt_files.sort()
    
    if not plt_files:
        return False, "No PLT files found matching criteria"
    
    print(f"Found {len(plt_files)} PLT files to convert")
    
    # Determine output directory
    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = binary_dir / 'converted'
    
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Format extension mapping and save methods
    format_info = {
        'hdf5': ('.h5', 'szplt'),  # HDF5 uses szplt format
        'szplt': ('.szplt', 'szplt'),
        'szl': ('.szl', 'szl'),
        'plt': ('.plt', 'plt'),
        'dat': ('.dat', 'ascii')
    }
    
    if output_format.lower() not in format_info:
        return False, f"Unsupported format: {output_format}. Supported: {', '.join(format_info.keys())}"
    
    ext, save_method = format_info[output_format.lower()]
    
    converted_files = []
    
    try:
        for i, (timestep, plt_path) in enumerate(plt_files, 1):
            print(f"\n[{i}/{len(plt_files)}] Converting timestep {timestep}...")
            
            # Load PLT file
            dataset = tp.data.load_tecplot(plt_path, read_data_option=tp.constant.ReadDataOption.Replace)
            
            # Generate output filename
            basename = Path(plt_path).stem
            output_file = out_dir / f"{basename}{ext}"
            
            # Save in specified format
            if save_method == 'szplt':
                # SZPLT is the compressed HDF5-based format
                tp.data.save_tecplot_szl(str(output_file))
            elif save_method == 'szl':
                tp.data.save_tecplot_szl(str(output_file))
            elif save_method == 'plt':
                tp.data.save_tecplot_plt(str(output_file))
            elif save_method == 'ascii':
                tp.data.save_tecplot_ascii(str(output_file))
            else:
                return False, f"Unsupported save method: {save_method}"
            
            converted_files.append(str(output_file))
            print(f"  ✓ Saved: {output_file.name}")
            
            # Clean up if requested
            if not keep_original:
                os.remove(plt_path)
                print(f"  ✓ Removed: {Path(plt_path).name}")
        
        print(f"\n✓ Successfully converted {len(converted_files)} files")
        return True, converted_files
        
    except Exception as e:
        import traceback
        error_msg = f"Conversion error: {e}\n{traceback.format_exc()}"
        return False, error_msg


def get_plt_info(plt_file):
    """
    Get information about a PLT file without full extraction.
    
    Parameters:
    -----------
    plt_file : str or Path
        Path to PLT file
        
    Returns:
    --------
    dict : Information about the file (zones, variables, etc.)
    """
    # Initialize tecplot
    success, result = initialize_tecplot_batch()
    if not success:
        return {'error': result}
    
    tp = result
    
    try:
        dataset = tp.data.load_tecplot(str(plt_file), read_data_option=tp.constant.ReadDataOption.Replace)
        
        info = {
            'num_zones': dataset.num_zones,
            'num_variables': dataset.num_variables,
            'zones': [],
            'variables': [v.name for v in dataset.variables()]
        }
        
        for zone in dataset.zones():
            zone_info = {
                'name': zone.name,
                'zone_type': str(zone.zone_type),
                'num_points': zone.num_points,
                'num_elements': zone.num_elements if hasattr(zone, 'num_elements') else 0
            }
            info['zones'].append(zone_info)
        
        return info
        
    except Exception as e:
        return {'error': str(e)}
