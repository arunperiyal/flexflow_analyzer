"""
Update FlexFlow installation to use smart Python 3.12 wrapper.

This updates the flexflow command to automatically detect and use
Python 3.12 for Tecplot operations without manual environment activation.
"""

import os
import sys
import shutil
from pathlib import Path


def update_flexflow_wrapper():
    """Update flexflow wrapper to automatically use Python 3.12 for Tecplot commands"""
    
    print("="*70)
    print("  FlexFlow Automatic Python 3.12 Wrapper Setup")
    print("="*70)
    print()
    
    # Find installation directory
    home = Path.home()
    bin_dir = home / '.local' / 'bin'
    share_dir = home / '.local' / 'share' / 'flexflow'
    
    flexflow_bin = bin_dir / 'flexflow'
    
    if not flexflow_bin.exists():
        print(f"❌ FlexFlow not found at {flexflow_bin}")
        print("   Please install FlexFlow first: python main.py --install")
        return False
    
    print(f"✓ Found FlexFlow installation at {flexflow_bin}")
    
    # Backup current wrapper
    backup = flexflow_bin.with_suffix('.backup')
    shutil.copy2(flexflow_bin, backup)
    print(f"✓ Backed up current wrapper to {backup}")
    
    # Get script directory (where flexflow_wrapper.sh is)
    script_dir = Path(__file__).parent
    wrapper_script = script_dir / 'flexflow_wrapper.sh'
    
    if not wrapper_script.exists():
        print(f"❌ Wrapper script not found: {wrapper_script}")
        return False
    
    # Copy new wrapper
    shutil.copy2(wrapper_script, flexflow_bin)
    os.chmod(flexflow_bin, 0o755)
    
    # Update paths in wrapper
    with open(flexflow_bin, 'r') as f:
        content = f.read()
    
    # Replace generic path with actual installation path
    content = content.replace(
        '/home/arunperiyal/.local/share/flexflow/main.py',
        str(share_dir / 'main.py')
    )
    
    with open(flexflow_bin, 'w') as f:
        f.write(content)
    
    print(f"✓ Updated flexflow wrapper")
    
    # Test Python 3.12 detection
    print("\n" + "="*70)
    print("  Testing Python 3.12 Detection")
    print("="*70)
    
    conda_base = home / 'miniconda3'
    python312_paths = [
        conda_base / 'envs' / 'tecplot312' / 'bin' / 'python',
        Path('/usr/bin/python3.12'),
        Path('/bin/python3.12'),
    ]
    
    python312_found = None
    for path in python312_paths:
        if path.exists():
            python312_found = path
            print(f"✓ Found Python 3.12 at: {path}")
            break
    
    if not python312_found:
        print("\n⚠️  WARNING: Python 3.12 not found!")
        print("   For Tecplot operations, please install:")
        print("   conda create -n tecplot312 python=3.12 -y")
        print("   conda activate tecplot312")
        print("   pip install pytecplot")
    
    print("\n" + "="*70)
    print("  Setup Complete!")
    print("="*70)
    print()
    print("Now you can use FlexFlow commands without activating the environment:")
    print()
    print("  # Non-Tecplot commands (use current Python)")
    print("  flexflow case show CS4SG1U1")
    print("  flexflow plot CS4SG1U1 --node 10 --component y")
    print()
    print("  # Tecplot commands (automatically use Python 3.12)")
    print("  flexflow field extract CS4SG1U1 --timestep 1000 --variables X,Y,Z")
    print("  flexflow tecplot convert CS4SG1U1 --format hdf5")
    print()
    print("✓ The wrapper will automatically detect and use Python 3.12 for")
    print("  Tecplot operations, while using your default Python for everything else.")
    print()
    
    return True


def main():
    """Main entry point"""
    
    if len(sys.argv) > 1 and sys.argv[1] == '--uninstall':
        # Restore backup
        home = Path.home()
        flexflow_bin = home / '.local' / 'bin' / 'flexflow'
        backup = flexflow_bin.with_suffix('.backup')
        
        if backup.exists():
            shutil.copy2(backup, flexflow_bin)
            print(f"✓ Restored original wrapper from backup")
            backup.unlink()
            print(f"✓ Removed backup file")
        else:
            print(f"❌ No backup found")
        return
    
    try:
        success = update_flexflow_wrapper()
        if success:
            print("="*70)
            print()
            sys.exit(0)
        else:
            print("\n❌ Update failed")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
