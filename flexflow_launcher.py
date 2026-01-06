#!/usr/bin/env python3
"""
FlexFlow launcher with automatic Python 3.12 detection for Tecplot operations.

This wrapper automatically uses Python 3.12 for Tecplot commands while
using the default Python for everything else.
"""

import sys
import os
import subprocess

def is_tecplot_command(args):
    """Check if this is a Tecplot-related command"""
    if not args:
        return False
    
    # Commands that need Tecplot
    tecplot_commands = ['field', 'tecplot']
    
    # Check if first argument is a Tecplot command
    if args[0] in tecplot_commands:
        return True
    
    # Check for legacy flat commands
    tecplot_legacy = ['convert', 'extract']
    if args[0] in tecplot_legacy:
        return True
    
    # Check for subcommands
    if len(args) >= 2:
        if args[0] == 'field' or args[0] == 'tecplot':
            return True
    
    return False

def find_python312():
    """Find Python 3.12 installation"""
    
    # Check conda environment
    conda_base = os.path.expanduser('~/miniconda3')
    tecplot_env = os.path.join(conda_base, 'envs', 'tecplot312', 'bin', 'python')
    
    if os.path.exists(tecplot_env):
        return tecplot_env
    
    # Check system python3.12
    for path in ['/usr/bin/python3.12', '/bin/python3.12']:
        if os.path.exists(path):
            # Verify it's actually 3.12
            try:
                result = subprocess.run([path, '--version'], 
                                      capture_output=True, text=True)
                if '3.12' in result.stdout:
                    return path
            except:
                pass
    
    return None

def get_python_version(python_path):
    """Get Python version as tuple"""
    try:
        result = subprocess.run([python_path, '-c', 
                               'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'],
                               capture_output=True, text=True, timeout=2)
        version_str = result.stdout.strip()
        major, minor = version_str.split('.')
        return (int(major), int(minor))
    except:
        return (0, 0)

def main():
    """Main entry point with automatic Python version selection"""
    
    # Get command arguments (skip script name)
    args = sys.argv[1:]
    
    # Path to main.py
    main_script = os.path.join(os.path.dirname(__file__), 'main.py')
    
    # Check if this is a Tecplot command
    if is_tecplot_command(args):
        # Check current Python version
        current_version = (sys.version_info.major, sys.version_info.minor)
        
        if current_version >= (3, 13):
            # Need Python 3.12 for Tecplot
            python312 = find_python312()
            
            if python312:
                # Re-execute with Python 3.12
                print(f"[FlexFlow] Using Python 3.12 for Tecplot operations...", file=sys.stderr)
                cmd = [python312, main_script] + args
                result = subprocess.run(cmd)
                sys.exit(result.returncode)
            else:
                print("[FlexFlow] WARNING: Python 3.12 not found!", file=sys.stderr)
                print("[FlexFlow] Tecplot operations require Python 3.12 or earlier.", file=sys.stderr)
                print("[FlexFlow] Please run: conda activate tecplot312", file=sys.stderr)
                print("[FlexFlow] Attempting to continue with current Python...\n", file=sys.stderr)
    
    # Use current Python (for non-Tecplot commands or if 3.12 not needed)
    # Import and run main directly
    sys.path.insert(0, os.path.dirname(main_script))
    import main as flexflow_main
    flexflow_main.main()

if __name__ == '__main__':
    main()
