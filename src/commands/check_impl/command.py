"""
Check command implementation
Inspects FlexFlow data files and displays information
"""

import os
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def execute_check(filepath):
    """
    Execute check command on a file
    
    Parameters:
    -----------
    filepath : str
        Path to the data file
    
    Returns:
    --------
    int : Exit code (0 for success, 1 for error)
    """
    # Check if file exists
    if not os.path.exists(filepath):
        console.print(f"[red]✗ Error: File not found: {filepath}[/red]")
        return 1
    
    # Get file extension
    file_ext = Path(filepath).suffix.lower()
    
    # Route to appropriate handler
    if file_ext == '.othd':
        return check_othd_file(filepath)
    elif file_ext == '.oisd':
        return check_oisd_file(filepath)
    else:
        console.print(f"[red]✗ Error: Unsupported file type: {file_ext}[/red]")
        console.print("[yellow]Supported types: .othd, .oisd[/yellow]")
        return 1


def check_othd_file(filepath):
    """
    Check and display OTHD file information
    
    Parameters:
    -----------
    filepath : str
        Path to the OTHD file
    
    Returns:
    --------
    int : Exit code
    """
    try:
        from src.core.readers.othd_reader import OTHDReader
        
        console.print(f"[cyan]Reading OTHD file:[/cyan] {filepath}")
        
        # Read the file
        reader = OTHDReader(filepath)
        
        # Get file info
        file_size = os.path.getsize(filepath)
        file_size_mb = file_size / (1024 * 1024)
        
        # Get time info
        if len(reader.times) > 0:
            start_time = reader.times[0]
            end_time = reader.times[-1]
            num_timesteps = len(reader.times)
            time_increment = reader.times[1] - reader.times[0] if num_timesteps > 1 else 0
        else:
            start_time = 0
            end_time = 0
            num_timesteps = 0
            time_increment = 0
        
        # Get node info
        num_nodes = reader.num_nodes
        
        # Create info table
        table = Table(title="OTHD File Information", show_header=False, 
                     border_style="cyan", title_style="bold cyan")
        table.add_column("Property", style="yellow", width=20)
        table.add_column("Value", style="white")
        
        table.add_row("File Type", "OTHD (Output Time History Data)")
        table.add_row("File Path", filepath)
        table.add_row("File Size", f"{file_size_mb:.2f} MB")
        table.add_row("", "")  # Separator
        table.add_row("Number of Nodes", f"{num_nodes:,}")
        table.add_row("Number of Time Steps", f"{num_timesteps:,}")
        table.add_row("", "")  # Separator
        table.add_row("Start Time", f"{start_time:.6f}")
        table.add_row("End Time", f"{end_time:.6f}")
        if num_timesteps > 1:
            table.add_row("Time Increment", f"{time_increment:.6f}")
        table.add_row("", "")  # Separator
        table.add_row("Components", "X, Y, Z displacements")
        
        console.print(table)
        console.print("[green]✓ File successfully inspected[/green]")
        
        return 0
        
    except Exception as e:
        console.print(f"[red]✗ Error reading OTHD file: {str(e)}[/red]")
        return 1


def check_oisd_file(filepath):
    """
    Check and display OISD file information
    
    Parameters:
    -----------
    filepath : str
        Path to the OISD file
    
    Returns:
    --------
    int : Exit code
    """
    try:
        from src.core.readers.oisd_reader import OISDReader
        
        console.print(f"[cyan]Reading OISD file:[/cyan] {filepath}")
        
        # Read the file
        reader = OISDReader(filepath)
        
        # Get file info
        file_size = os.path.getsize(filepath)
        file_size_mb = file_size / (1024 * 1024)
        
        # Get time info
        if len(reader.times) > 0:
            start_time = reader.times[0]
            end_time = reader.times[-1]
            num_timesteps = len(reader.times)
            time_increment = reader.times[1] - reader.times[0] if num_timesteps > 1 else 0
        else:
            start_time = 0
            end_time = 0
            num_timesteps = 0
            time_increment = 0
        
        # Get surface info (number of unique surfaces from data keys)
        num_surfaces = len(set([key for key in reader.tot_trac.keys()]))
        
        # Create info table
        table = Table(title="OISD File Information", show_header=False, 
                     border_style="cyan", title_style="bold cyan")
        table.add_column("Property", style="yellow", width=20)
        table.add_column("Value", style="white")
        
        table.add_row("File Type", "OISD (Output Integrated Surface Data)")
        table.add_row("File Path", filepath)
        table.add_row("File Size", f"{file_size_mb:.2f} MB")
        table.add_row("", "")  # Separator
        table.add_row("Number of Surfaces", f"{num_surfaces:,}")
        table.add_row("Number of Time Steps", f"{num_timesteps:,}")
        table.add_row("", "")  # Separator
        table.add_row("Start Time", f"{start_time:.6f}")
        table.add_row("End Time", f"{end_time:.6f}")
        if num_timesteps > 1:
            table.add_row("Time Increment", f"{time_increment:.6f}")
        table.add_row("", "")  # Separator
        table.add_row("Data Fields", "Total Traction, Total Moment, Total Area, Average Pressure")
        
        console.print(table)
        console.print("[green]✓ File successfully inspected[/green]")
        
        return 0
        
    except Exception as e:
        console.print(f"[red]✗ Error reading OISD file: {str(e)}[/red]")
        return 1
