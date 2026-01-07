"""
Tecplot command implementation
"""

import sys
import os
import re
from pathlib import Path

from ...utils.logger import Logger
from ...utils.colors import Colors


def execute_tecplot(args):
    """
    Execute the tecplot command
    
    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    """
    from .help_messages import print_tecplot_help
    
    # Show help if no subcommand
    if not hasattr(args, 'tecplot_subcommand') or not args.tecplot_subcommand:
        print_tecplot_help()
        return
    
    logger = Logger(verbose=args.verbose)
    
    try:
        if args.tecplot_subcommand == 'info':
            execute_info(args, logger)
        else:
            print_tecplot_help()
    
    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def execute_info(args, logger):
    """Show information about PLT files"""
    
    if not args.case:
        logger.error("Case directory required")
        print("Usage: flexflow tecplot info <case_dir>")
        sys.exit(1)
    
    case_dir = Path(args.case)
    binary_dir = case_dir / 'binary'
    
    if not binary_dir.exists():
        logger.error(f"Binary directory not found: {binary_dir}")
        sys.exit(1)
    
    # Find all PLT files
    plt_files = sorted(binary_dir.glob('*.plt'))
    
    if not plt_files:
        logger.error(f"No PLT files found in {binary_dir}")
        sys.exit(1)
    
    # Extract timesteps from filenames
    timesteps = []
    for plt_file in plt_files:
        match = re.search(r'\.(\d+)\.plt$', plt_file.name)
        if match:
            timesteps.append(int(match.group(1)))
    
    if not timesteps:
        logger.error("Could not extract timesteps from PLT filenames")
        sys.exit(1)
    
    timesteps.sort()
    
    # Calculate statistics
    total_files = len(timesteps)
    first_step = timesteps[0]
    last_step = timesteps[-1]
    
    # Determine increment (most common difference)
    if len(timesteps) > 1:
        increments = [timesteps[i+1] - timesteps[i] for i in range(len(timesteps)-1)]
        increment = max(set(increments), key=increments.count)
    else:
        increment = None
    
    # Calculate total size
    total_size = sum(f.stat().st_size for f in plt_files)
    avg_size = total_size / total_files
    
    # Print information
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}PLT Files Information{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 70}{Colors.RESET}")
    print()
    print(f"{Colors.BOLD}Case Directory:{Colors.RESET} {case_dir}")
    print(f"{Colors.BOLD}Binary Directory:{Colors.RESET} {binary_dir}")
    print()
    print(f"{Colors.BOLD}Total Files:{Colors.RESET} {total_files}")
    print(f"{Colors.BOLD}Timestep Range:{Colors.RESET} {first_step} to {last_step}")
    if increment:
        print(f"{Colors.BOLD}Increment:{Colors.RESET} {increment}")
    print()
    print(f"{Colors.BOLD}Total Size:{Colors.RESET} {format_size(total_size)}")
    print(f"{Colors.BOLD}Average File Size:{Colors.RESET} {format_size(avg_size)}")
    print()
    
    # Show first and last few files
    print(f"{Colors.BOLD}First 5 timesteps:{Colors.RESET}")
    for ts in timesteps[:5]:
        print(f"  • {ts}")
    
    if total_files > 10:
        print(f"  {Colors.DIM}...{Colors.RESET}")
        print(f"{Colors.BOLD}Last 5 timesteps:{Colors.RESET}")
        for ts in timesteps[-5:]:
            print(f"  • {ts}")
    print()
    
    # Check for .def file (FlexFlow definition)
    def_file = case_dir / f"{case_dir.name}.def"
    if def_file.exists():
        print(f"{Colors.GREEN}✓{Colors.RESET} Definition file found: {def_file.name}")
    else:
        print(f"{Colors.YELLOW}⚠{Colors.RESET} Definition file not found (expected: {def_file.name})")
    print()
    
    # Usage suggestions
    print(f"{Colors.BOLD}Next Steps:{Colors.RESET}")
    print()
    print(f"  View data from a specific timestep:")
    print(f"    {Colors.YELLOW}flexflow plot {case_dir.name} --start-step {first_step} --node 1{Colors.RESET}")
    print()
    print(f"  Create visualization macro (coming soon):")
    print(f"    {Colors.YELLOW}flexflow tecplot visualize {case_dir.name} --start-step {first_step} --end-step {last_step}{Colors.RESET}")
    print()


def format_size(size_bytes):
    """Format bytes to human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"
    """Execute conversion of PLT files"""
    
    if not args.case:
        logger.error("Case directory required")
        print("Usage: flexflow tecplot convert <case_dir> [options]")
        sys.exit(1)
    
    # Get parameters
    case_dir = args.case
    output_format = args.format if hasattr(args, 'format') and args.format else 'hdf5'
    delete_original = args.delete_original if hasattr(args, 'delete_original') else False
    keep_original = not delete_original  # Invert: keep by default, delete if flag specified
    start_step = args.start_step if hasattr(args, 'start_step') and args.start_step else None
    end_step = args.end_step if hasattr(args, 'end_step') and args.end_step else None
    output_dir = args.output_dir if hasattr(args, 'output_dir') and args.output_dir else None
    gui_mode = args.gui_mode if hasattr(args, 'gui_mode') else False
    
    logger.info(f"Converting PLT files from: {case_dir}")
    logger.info(f"Output format: {output_format.upper()}")
    
    # Create converter
    converter = TecplotConverter(case_dir, verbose=args.verbose)
    
    if gui_mode:
        # GUI mode: Just create the macro and give instructions
        from pathlib import Path
        
        # Discover files
        all_files = converter.discover_plt_files()
        if not all_files:
            logger.error(f"No PLT files found in {case_dir}/binary")
            sys.exit(1)
        
        # Filter if needed
        if start_step or end_step:
            filtered = []
            for ts, fp in all_files:
                if start_step and ts < start_step:
                    continue
                if end_step and ts > end_step:
                    continue
                filtered.append((ts, fp))
            files_to_convert = filtered
        else:
            files_to_convert = all_files
        
        if not files_to_convert:
            logger.error("No files match the specified range")
            sys.exit(1)
        
        # Create output directory
        out_dir = Path(output_dir) if output_dir else Path(case_dir) / 'binary' / 'converted'
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Create macro
        macro_file = converter._create_macro(files_to_convert, output_format, out_dir, keep_original)
        
        # Print instructions
        print()
        logger.success(f"Macro created: {macro_file}")
        print()
        print(f"{Colors.BOLD}{Colors.CYAN}Next Steps:{Colors.RESET}")
        print()
        print(f"  1. Open Tecplot GUI:")
        print(f"     {Colors.YELLOW}$ /usr/local/tecplot/360ex_2022r1/bin/tec360{Colors.RESET}")
        print()
        print(f"  2. In Tecplot menu:")
        print(f"     {Colors.GREEN}Scripting → Play Macro...{Colors.RESET}")
        print()
        print(f"  3. Select macro file:")
        print(f"     {Colors.YELLOW}{macro_file}{Colors.RESET}")
        print()
        print(f"  4. Conversion will happen!")
        print(f"     Files will be created in: {Colors.CYAN}{out_dir}{Colors.RESET}")
        print()
        print(f"  Files to convert: {Colors.BOLD}{len(files_to_convert)}{Colors.RESET}")
        print()
        
    else:
        # Batch mode: Try to run conversion
        converted_files = converter.convert(
            output_format=output_format,
            start_step=start_step,
            end_step=end_step,
            keep_original=keep_original,
            output_dir=output_dir
        )
        
        if converted_files:
            logger.success(f"Converted {len(converted_files)} files")
            logger.info(f"Files saved to: {converter.binary_dir / 'converted'}")
        else:
            logger.warning("No files were converted")
            logger.info("If batch mode doesn't work, try:")
            logger.info(f"  flexflow tecplot convert {case_dir} --gui-mode")

def execute_read(args, logger):
    """Execute reading of converted HDF5 files"""
    
    if not args.case:
        logger.error("Case directory required")
        print("Usage: flexflow tecplot read <case_dir> --timestep <step> [options]")
        sys.exit(1)
    
    if not hasattr(args, 'timestep') or args.timestep is None:
        logger.error("--timestep required")
        sys.exit(1)
    
    case_dir = args.case
    timestep = args.timestep
    variable = args.variable if hasattr(args, 'variable') and args.variable else None
    
    logger.info(f"Reading data from: {case_dir}")
    logger.info(f"Timestep: {timestep}")
    
    # Create reader
    reader = HDF5FieldReader(case_dir, verbose=args.verbose)
    
    # Check if files exist
    available_steps = reader.get_available_timesteps()
    if not available_steps:
        logger.error("No converted HDF5 files found")
        logger.info("Run 'flexflow tecplot convert' first")
        sys.exit(1)
    
    if timestep not in available_steps:
        logger.error(f"Timestep {timestep} not available")
        logger.info(f"Available timesteps: {available_steps[:10]}..." if len(available_steps) > 10 else f"Available timesteps: {available_steps}")
        sys.exit(1)
    
    # Get file info
    info = reader.get_file_info(timestep)
    
    print(f"\n{Colors.BOLD}Timestep {timestep} Information:{Colors.RESET}")
    print(f"  File: {info['filepath']}")
    print(f"  Points: {info['num_points']:,}")
    print(f"  Variables: {len(info['variables'])}")
    
    if variable:
        # Read specific variable
        logger.info(f"Reading variable: {variable}")
        stats = reader.get_statistics(timestep, variable)
        
        print(f"\n{Colors.BOLD}Variable: {variable}{Colors.RESET}")
        print(f"  Shape: {stats['shape']}")
        print(f"  Min: {stats['min']:.6e}")
        print(f"  Max: {stats['max']:.6e}")
        print(f"  Mean: {stats['mean']:.6e}")
        print(f"  Std: {stats['std']:.6e}")
        print(f"  Median: {stats['median']:.6e}")
    else:
        # Show all variables
        print(f"\n{Colors.BOLD}Available Variables:{Colors.RESET}")
        for var in info['variables']:
            print(f"  - {var}")
        
        print(f"\n{Colors.CYAN}Tip:{Colors.RESET} Use --variable <name> to see statistics")


def execute_info(args, logger):
    """Show information about PLT and converted files"""
    
    if not args.case:
        logger.error("Case directory required")
        print("Usage: flexflow tecplot info <case_dir>")
        sys.exit(1)
    
    case_dir = Path(args.case)
    binary_dir = case_dir / 'binary'
    converted_dir = binary_dir / 'converted'
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}Tecplot Data Status: {case_dir.name}{Colors.RESET}\n")
    
    # Check for PLT files
    if binary_dir.exists():
        import glob
        plt_files = glob.glob(str(binary_dir / '*.plt'))
        if plt_files:
            print(f"{Colors.GREEN}✓{Colors.RESET} PLT Files: {Colors.BOLD}{len(plt_files)}{Colors.RESET} files found")
            print(f"  Location: {binary_dir}")
            
            # Show timestep range
            import re
            timesteps = []
            for f in plt_files:
                match = re.search(r'\.(\d+)\.plt$', f)
                if match:
                    timesteps.append(int(match.group(1)))
            if timesteps:
                timesteps.sort()
                print(f"  Timesteps: {timesteps[0]} to {timesteps[-1]} ({len(timesteps)} files)")
        else:
            print(f"{Colors.YELLOW}⚠{Colors.RESET} No PLT files found in {binary_dir}")
    else:
        print(f"{Colors.RED}✗{Colors.RESET} Binary directory not found: {binary_dir}")
    
    # Check for converted files
    print()
    if converted_dir.exists():
        import glob
        h5_files = glob.glob(str(converted_dir / '*.h5'))
        vtk_files = glob.glob(str(converted_dir / '*.vtk'))
        nc_files = glob.glob(str(converted_dir / '*.nc'))
        
        total_converted = len(h5_files) + len(vtk_files) + len(nc_files)
        
        if total_converted > 0:
            print(f"{Colors.GREEN}✓{Colors.RESET} Converted Files: {Colors.BOLD}{total_converted}{Colors.RESET} files")
            print(f"  Location: {converted_dir}")
            if h5_files:
                print(f"  - HDF5: {len(h5_files)} files")
            if vtk_files:
                print(f"  - VTK: {len(vtk_files)} files")
            if nc_files:
                print(f"  - NetCDF: {len(nc_files)} files")
            
            # Try to read one file to show variables
            if h5_files:
                try:
                    reader = HDF5FieldReader(case_dir, verbose=False)
                    steps = reader.get_available_timesteps()
                    if steps:
                        info = reader.get_file_info(steps[0])
                        print(f"\n  Available Variables ({len(info['variables'])}):")
                        for var in info['variables']:
                            print(f"    - {var}")
                except:
                    pass
        else:
            print(f"{Colors.YELLOW}⚠{Colors.RESET} No converted files found")
            print(f"{Colors.CYAN}Tip:{Colors.RESET} Run 'flexflow tecplot convert {case_dir.name}' to convert PLT files")
    else:
        print(f"{Colors.YELLOW}⚠{Colors.RESET} Converted directory not found: {converted_dir}")
        print(f"{Colors.CYAN}Tip:{Colors.RESET} Run 'flexflow tecplot convert {case_dir.name}' to convert PLT files")
    
    print()
