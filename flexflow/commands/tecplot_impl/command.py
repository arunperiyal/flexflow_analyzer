"""
Tecplot command implementation
"""

import sys
import os
import re
import struct
from pathlib import Path

from ...utils.logger import Logger
from ...utils.colors import Colors


def read_tecplot_variables(filepath):
    """
    Extract variable names from Tecplot binary PLT file
    
    Parameters:
    -----------
    filepath : Path
        Path to PLT file
        
    Returns:
    --------
    list or None
        List of variable names, or None if parsing fails
    """
    try:
        variables = []
        
        with open(filepath, 'rb') as f:
            # Read header
            magic = f.read(8)
            if not magic.startswith(b'#!TDV'):
                return None
            
            # Skip version bytes
            f.read(8)
            
            # Read title (null-terminated wide string)
            title_chars = []
            while True:
                char_bytes = f.read(4)
                if len(char_bytes) < 4:
                    break
                char_val = struct.unpack('<I', char_bytes)[0]
                if char_val == 0:
                    break
                if char_val < 128:
                    title_chars.append(chr(char_val))
            
            # Read number of variables
            num_vars_bytes = f.read(4)
            if len(num_vars_bytes) < 4:
                return None
            num_vars = struct.unpack('<I', num_vars_bytes)[0]
            
            # Read variable names (each as null-terminated wide string)
            for i in range(num_vars):
                var_chars = []
                while True:
                    char_bytes = f.read(4)
                    if len(char_bytes) < 4:
                        break
                    char_val = struct.unpack('<I', char_bytes)[0]
                    if char_val == 0:
                        break
                    if char_val < 128:
                        var_chars.append(chr(char_val))
                variables.append(''.join(var_chars))
        
        return variables if variables else None
    
    except Exception as e:
        return None


def read_tecplot_zones(filepath):
    """
    Extract zone information from Tecplot binary PLT file
    
    Parameters:
    -----------
    filepath : Path
        Path to PLT file
        
    Returns:
    --------
    list or None
        List of zone dictionaries, or None if parsing fails
    """
    try:
        zones = []
        
        with open(filepath, 'rb') as f:
            # Read header
            magic = f.read(8)
            if not magic.startswith(b'#!TDV'):
                return None
            
            # Skip version bytes
            f.read(8)
            
            # Read title (null-terminated wide string)
            while True:
                char_bytes = f.read(4)
                if len(char_bytes) < 4:
                    break
                char_val = struct.unpack('<I', char_bytes)[0]
                if char_val == 0:
                    break
            
            # Read number of variables
            num_vars_bytes = f.read(4)
            if len(num_vars_bytes) < 4:
                return None
            num_vars = struct.unpack('<I', num_vars_bytes)[0]
            
            # Skip variable names
            for i in range(num_vars):
                while True:
                    char_bytes = f.read(4)
                    if len(char_bytes) < 4:
                        return None
                    char_val = struct.unpack('<I', char_bytes)[0]
                    if char_val == 0:
                        break
            
            # Now we should be at zone markers
            # Look for zone marker (299.0 as float)
            zone_marker = struct.pack('<f', 299.0)
            
            while True:
                # Read potential zone marker
                marker_bytes = f.read(4)
                if len(marker_bytes) < 4:
                    break
                
                if marker_bytes == zone_marker:
                    zone_info = {}
                    
                    # Read zone name (null-terminated wide string)
                    zone_name_chars = []
                    while True:
                        char_bytes = f.read(4)
                        if len(char_bytes) < 4:
                            break
                        char_val = struct.unpack('<I', char_bytes)[0]
                        if char_val == 0:
                            break
                        if char_val < 128:
                            zone_name_chars.append(chr(char_val))
                    
                    zone_info['name'] = ''.join(zone_name_chars) if zone_name_chars else 'Unnamed'
                    
                    # Read zone type (0=ORDERED, 1=FELINESEG, 2=FETRIANGLE, 3=FEQUADRILATERAL, 4=FETETRAHEDRON, 5=FEBRICK)
                    zonetype_bytes = f.read(4)
                    if len(zonetype_bytes) < 4:
                        break
                    zonetype = struct.unpack('<i', zonetype_bytes)[0]
                    
                    zonetype_map = {
                        0: 'ORDERED',
                        1: 'FELINESEG',
                        2: 'FETRIANGLE',
                        3: 'FEQUADRILATERAL',
                        4: 'FETETRAHEDRON',
                        5: 'FEBRICK'
                    }
                    zone_info['zonetype'] = zonetype_map.get(zonetype, f'Unknown ({zonetype})')
                    
                    # For ordered zones, read I, J, K dimensions
                    # For FE zones, read nodes and elements
                    # Note: This is a simplified parser - full parsing is complex
                    
                    # Try to read some dimension info (this is approximate)
                    # Skip more complex parsing for now
                    
                    zones.append(zone_info)
                    
                    # For safety, only read first few zones
                    if len(zones) >= 10:
                        break
        
        return zones if zones else None
    
    except Exception as e:
        return None


def execute_tecplot(args):
    """
    Execute the tecplot command
    
    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    """
    from .help_messages import print_tecplot_help, print_tecplot_info_help, print_tecplot_extract_help
    
    # Show help if no subcommand
    if not hasattr(args, 'tecplot_subcommand') or not args.tecplot_subcommand:
        print_tecplot_help()
        return
    
    # Handle help flags for subcommands
    if hasattr(args, 'help') and args.help:
        if args.tecplot_subcommand == 'info':
            print_tecplot_info_help()
        elif args.tecplot_subcommand == 'extract':
            print_tecplot_extract_help()
        else:
            print_tecplot_help()
        return
    
    logger = Logger(verbose=args.verbose)
    
    try:
        if args.tecplot_subcommand == 'info':
            execute_info(args, logger)
        elif args.tecplot_subcommand == 'extract':
            execute_extract(args, logger)
        else:
            print_tecplot_help()
    
    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def execute_info(args, logger):
    """Show information about PLT files with consistency checks"""
    
    if not args.case:
        from .help_messages import print_tecplot_info_help
        print_tecplot_info_help()
        sys.exit(1)
    
    # Determine which sections to show
    # If no flags are set, show all sections
    show_all = not any([args.basic, args.variables, args.zones, args.checks, args.stats])
    
    show_basic = show_all or args.basic
    show_variables = show_all or args.variables
    show_zones = show_all or args.zones
    show_checks = show_all or args.checks
    show_stats = show_all or args.stats
    
    case_dir = Path(args.case)
    binary_dir = case_dir / 'binary'
    
    if not binary_dir.exists():
        logger.error(f"Binary directory not found: {binary_dir}")
        sys.exit(1)
    
    # Get problem name from simflow.config
    simflow_config = case_dir / 'simflow.config'
    problem_name = None
    if simflow_config.exists():
        try:
            with open(simflow_config, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('problem'):
                        parts = line.split('=')
                        if len(parts) == 2:
                            problem_name = parts[1].strip()
                            break
        except Exception as e:
            if args.verbose:
                logger.warning(f"Could not read simflow.config: {e}")
    
    # Find all PLT files
    plt_files = sorted(binary_dir.glob('*.plt'))
    
    if not plt_files:
        logger.error(f"No PLT files found in {binary_dir}")
        sys.exit(1)
    
    # Extract timesteps and file info
    file_info = []
    for plt_file in plt_files:
        match = re.search(r'\.(\d+)\.plt$', plt_file.name)
        if match:
            timestep = int(match.group(1))
            size = plt_file.stat().st_size
            file_info.append({
                'path': plt_file,
                'name': plt_file.name,
                'timestep': timestep,
                'size': size
            })
    
    if not file_info:
        logger.error("Could not extract timesteps from PLT filenames")
        sys.exit(1)
    
    # Sort by timestep
    file_info.sort(key=lambda x: x['timestep'])
    timesteps = [f['timestep'] for f in file_info]
    
    # Calculate basic statistics
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
    total_size = sum(f['size'] for f in file_info)
    avg_size = total_size / total_files
    
    # ========================================================================
    # BASIC INFORMATION
    # ========================================================================
    if show_basic:
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
        
        # Check for .def file using problem name
        if problem_name:
            def_file = case_dir / f"{problem_name}.def"
            if def_file.exists():
                print(f"{Colors.GREEN}✓{Colors.RESET} Definition file found: {def_file.name}")
            else:
                print(f"{Colors.YELLOW}⚠{Colors.RESET} Definition file not found (expected: {def_file.name})")
        else:
            print(f"{Colors.YELLOW}⚠{Colors.RESET} Could not determine problem name from simflow.config")
        print()
    
    # ========================================================================
    # VARIABLES IN PLT FILES
    # ========================================================================
    # Read variables from first file (always needed for checks)
    first_file = file_info[0]['path']
    variables = read_tecplot_variables(first_file)
    
    if show_variables:
        print(f"{Colors.BOLD}{Colors.CYAN}Variables in PLT Files{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 70}{Colors.RESET}")
        print()
        
        if variables:
            print(f"{Colors.BOLD}Total Variables:{Colors.RESET} {len(variables)}")
            print()
            print(f"{Colors.BOLD}Variable List:{Colors.RESET}")
            
            # Display in columns if many variables
            if len(variables) <= 10:
                for i, var in enumerate(variables, 1):
                    print(f"  {i:2}. {var}")
            else:
                # Display in two columns
                mid = (len(variables) + 1) // 2
                for i in range(mid):
                    left = f"  {i+1:2}. {variables[i]}"
                    if i + mid < len(variables):
                        right = f"{i+mid+1:2}. {variables[i+mid]}"
                        print(f"{left:<35} {right}")
                    else:
                        print(left)
            print()
            
            # Categorize variables by type
            coord_vars = [v for v in variables if v.upper() in ['X', 'Y', 'Z']]
            velocity_vars = [v for v in variables if v.upper() in ['U', 'V', 'W']]
            disp_vars = [v for v in variables if 'disp' in v.lower()]
            vor_vars = [v for v in variables if 'vor' in v.lower() or 'vort' in v.lower()]
            
            if coord_vars or velocity_vars or disp_vars or vor_vars:
                print(f"{Colors.BOLD}Variable Categories:{Colors.RESET}")
                if coord_vars:
                    print(f"  {Colors.CYAN}Coordinates:{Colors.RESET} {', '.join(coord_vars)}")
                if velocity_vars:
                    print(f"  {Colors.CYAN}Velocities:{Colors.RESET} {', '.join(velocity_vars)}")
                if disp_vars:
                    print(f"  {Colors.CYAN}Displacements:{Colors.RESET} {', '.join(disp_vars)}")
                if vor_vars:
                    print(f"  {Colors.CYAN}Vorticity:{Colors.RESET} {', '.join(vor_vars)}")
                
                other_vars = [v for v in variables if v not in coord_vars + velocity_vars + disp_vars + vor_vars]
                if other_vars:
                    print(f"  {Colors.CYAN}Other:{Colors.RESET} {', '.join(other_vars)}")
                print()
        else:
            print(f"{Colors.YELLOW}⚠{Colors.RESET} Could not parse variables from PLT file")
            print()
    
    # ========================================================================
    # CONSISTENCY CHECKS
    # ========================================================================
    if show_checks:
        print(f"{Colors.BOLD}{Colors.CYAN}Consistency Checks{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 70}{Colors.RESET}")
        print()
        
        issues = []
        
        # 1. Check for zero-size files
        zero_size_files = [f for f in file_info if f['size'] == 0]
        if zero_size_files:
            print(f"{Colors.RED}✗{Colors.RESET} Zero-size files detected:")
            for f in zero_size_files:
                print(f"    {f['name']}")
                issues.append(f"Zero-size file: {f['name']}")
        else:
            print(f"{Colors.GREEN}✓{Colors.RESET} No zero-size files")
        
        # 2. Check naming convention
        naming_issues = []
        if problem_name:
            expected_pattern = f"{problem_name}.\\d+.plt"
            for f in file_info:
                if not re.match(expected_pattern, f['name']):
                    naming_issues.append(f['name'])
            
            if naming_issues:
                print(f"{Colors.RED}✗{Colors.RESET} Naming convention issues:")
                for name in naming_issues:
                    print(f"    {name} (expected pattern: {problem_name}.NNNN.plt)")
                    issues.append(f"Invalid name: {name}")
            else:
                print(f"{Colors.GREEN}✓{Colors.RESET} All files follow naming convention ({problem_name}.NNNN.plt)")
        else:
            print(f"{Colors.YELLOW}⚠{Colors.RESET} Cannot verify naming convention (problem name unknown)")
        
        # 3. Check sequential timesteps
        missing_steps = []
        if increment and len(timesteps) > 1:
            expected_steps = list(range(first_step, last_step + increment, increment))
            missing_steps = [s for s in expected_steps if s not in timesteps]
            
            if missing_steps:
                print(f"{Colors.YELLOW}⚠{Colors.RESET} Missing timesteps in sequence:")
                # Show first few missing steps
                for step in missing_steps[:5]:
                    print(f"    {step}")
                if len(missing_steps) > 5:
                    print(f"    ... and {len(missing_steps) - 5} more")
                issues.append(f"{len(missing_steps)} missing timesteps")
            else:
                print(f"{Colors.GREEN}✓{Colors.RESET} All timesteps sequential (increment: {increment})")
        else:
            print(f"{Colors.YELLOW}⚠{Colors.RESET} Cannot verify sequence (insufficient data)")
        
        # 4. Check file corruption (basic check - try to open and read header)
        corrupt_files = []
        print(f"{Colors.DIM}Checking files for corruption...{Colors.RESET}", end='', flush=True)
        
        for f in file_info:
            try:
                # Try to open and read first few bytes (basic check)
                with open(f['path'], 'rb') as fp:
                    header = fp.read(100)  # Read first 100 bytes
                    if len(header) == 0:
                        corrupt_files.append(f['name'])
                    # Check for Tecplot magic bytes (starts with "#!TDV" for binary)
                    elif not (header.startswith(b'#!TDV') or header.startswith(b'TITLE') or header.startswith(b'VARIABLES')):
                        corrupt_files.append(f['name'])
            except Exception as e:
                corrupt_files.append(f['name'])
                if args.verbose:
                    print(f"\n    Error reading {f['name']}: {e}")
        
        print(f"\r{' ' * 50}\r", end='')  # Clear progress message
        
        if corrupt_files:
            print(f"{Colors.RED}✗{Colors.RESET} Potentially corrupt files:")
            for name in corrupt_files:
                print(f"    {name}")
                issues.append(f"Corrupt file: {name}")
        else:
            print(f"{Colors.GREEN}✓{Colors.RESET} All files readable (basic check)")
        
        # 5. Check variable consistency (compare first and last file)
        print(f"{Colors.DIM}Checking variable consistency...{Colors.RESET}", end='', flush=True)
        
        var_consistent = True
        
        try:
            # Use the PLT parser to extract variables
            first_file_path = file_info[0]['path']
            last_file_path = file_info[-1]['path']
            
            first_vars = read_tecplot_variables(first_file_path)
            last_vars = read_tecplot_variables(last_file_path)
            
            if first_vars and last_vars:
                if first_vars == last_vars:
                    var_consistent = True
                else:
                    var_consistent = False
                    # Find differences
                    missing_in_last = set(first_vars) - set(last_vars)
                    extra_in_last = set(last_vars) - set(first_vars)
                    if args.verbose and (missing_in_last or extra_in_last):
                        print()
                        if missing_in_last:
                            print(f"    Missing in last file: {', '.join(missing_in_last)}")
                        if extra_in_last:
                            print(f"    Extra in last file: {', '.join(extra_in_last)}")
            else:
                var_consistent = None  # Cannot determine
        except Exception as e:
            if args.verbose:
                print(f"\n    Error checking variables: {e}")
            var_consistent = None
        
        print(f"\r{' ' * 50}\r", end='')  # Clear progress message
        
        if var_consistent is True:
            print(f"{Colors.GREEN}✓{Colors.RESET} Variable consistency verified")
            if variables:
                print(f"    All {len(variables)} variables present in all files")
        elif var_consistent is False:
            print(f"{Colors.RED}✗{Colors.RESET} Variable inconsistency detected")
            print(f"    First and last files have different variables")
            issues.append("Variables differ between files")
        else:
            print(f"{Colors.YELLOW}⚠{Colors.RESET} Cannot verify variable consistency")
        
        print()
        
        # Summary
        if issues:
            print(f"{Colors.BOLD}{Colors.YELLOW}Summary: {len(issues)} issue(s) found{Colors.RESET}")
            if args.verbose:
                for issue in issues:
                    print(f"  • {issue}")
            print()
        else:
            print(f"{Colors.BOLD}{Colors.GREEN}Summary: All consistency checks passed ✓{Colors.RESET}")
            print()
    
    # ========================================================================
    # ZONE INFORMATION
    # ========================================================================
    if show_zones:
        print(f"{Colors.BOLD}{Colors.CYAN}Zone Information{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 70}{Colors.RESET}")
        print()
        
        # Try to read zone info from first file
        zone_info = read_tecplot_zones(first_file)
        
        if zone_info:
            print(f"{Colors.BOLD}Total Zones:{Colors.RESET} {len(zone_info)}")
            print()
            
            for i, zone in enumerate(zone_info, 1):
                print(f"{Colors.BOLD}Zone {i}:{Colors.RESET}")
                print(f"  {Colors.CYAN}Name:{Colors.RESET} {zone.get('name', 'N/A')}")
                print(f"  {Colors.CYAN}Type:{Colors.RESET} {zone.get('zonetype', 'N/A')}")
                
                if 'nodes' in zone:
                    print(f"  {Colors.CYAN}Nodes:{Colors.RESET} {zone['nodes']}")
                if 'elements' in zone:
                    print(f"  {Colors.CYAN}Elements:{Colors.RESET} {zone['elements']}")
                if 'i' in zone:
                    print(f"  {Colors.CYAN}I-dimension:{Colors.RESET} {zone['i']}")
                if 'j' in zone:
                    print(f"  {Colors.CYAN}J-dimension:{Colors.RESET} {zone['j']}")
                if 'k' in zone:
                    print(f"  {Colors.CYAN}K-dimension:{Colors.RESET} {zone['k']}")
                
                print()
        else:
            print(f"{Colors.YELLOW}⚠{Colors.RESET} Could not parse zone information from PLT file")
            print()
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    if show_stats:
        print(f"{Colors.BOLD}{Colors.CYAN}Statistics{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 70}{Colors.RESET}")
        print()
        
        # File size statistics
        file_sizes = [f['size'] for f in file_info]
        min_size = min(file_sizes)
        max_size = max(file_sizes)
        median_size = sorted(file_sizes)[len(file_sizes) // 2]
        
        print(f"{Colors.BOLD}File Size Statistics:{Colors.RESET}")
        print(f"  {Colors.CYAN}Minimum:{Colors.RESET} {format_size(min_size)}")
        print(f"  {Colors.CYAN}Maximum:{Colors.RESET} {format_size(max_size)}")
        print(f"  {Colors.CYAN}Average:{Colors.RESET} {format_size(avg_size)}")
        print(f"  {Colors.CYAN}Median:{Colors.RESET} {format_size(median_size)}")
        print()
        
        # Time increment statistics
        if len(timesteps) > 1:
            increments = [timesteps[i+1] - timesteps[i] for i in range(len(timesteps)-1)]
            min_inc = min(increments)
            max_inc = max(increments)
            avg_inc = sum(increments) / len(increments)
            
            print(f"{Colors.BOLD}Timestep Increment Statistics:{Colors.RESET}")
            print(f"  {Colors.CYAN}Minimum:{Colors.RESET} {min_inc}")
            print(f"  {Colors.CYAN}Maximum:{Colors.RESET} {max_inc}")
            print(f"  {Colors.CYAN}Average:{Colors.RESET} {avg_inc:.1f}")
            print(f"  {Colors.CYAN}Most Common:{Colors.RESET} {increment}")
            
            if min_inc != max_inc:
                print(f"  {Colors.YELLOW}⚠{Colors.RESET} Non-uniform increments detected")
            print()
        
        # Storage estimates
        if increment and total_files > 1:
            files_per_1000_steps = 1000 / increment
            size_per_1000_steps = avg_size * files_per_1000_steps
            
            print(f"{Colors.BOLD}Storage Estimates:{Colors.RESET}")
            print(f"  {Colors.CYAN}Files per 1000 steps:{Colors.RESET} {files_per_1000_steps:.0f}")
            print(f"  {Colors.CYAN}Size per 1000 steps:{Colors.RESET} {format_size(size_per_1000_steps)}")
            print()
    
    # End sections
    
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


def execute_extract(args, logger):
    """Extract data from PLT files using pytecplot"""
    from .help_messages import print_tecplot_extract_help
    
    if not args.case:
        print_tecplot_extract_help()
        sys.exit(1)
    
    if not args.variables:
        logger.error("--variables flag is required")
        print()
        print_tecplot_extract_help()
        sys.exit(1)
    
    if not args.zone:
        logger.error("--zone flag is required")
        print()
        print_tecplot_extract_help()
        sys.exit(1)
    
    if not args.timestep:
        logger.error("--timestep flag is required")
        print()
        print_tecplot_extract_help()
        sys.exit(1)
    
    case_dir = Path(args.case)
    binary_dir = case_dir / 'binary'
    
    if not binary_dir.exists():
        logger.error(f"Binary directory not found: {binary_dir}")
        sys.exit(1)
    
    # Parse variables
    requested_vars = [v.strip() for v in args.variables.split(',')]
    logger.info(f"Extracting variables: {', '.join(requested_vars)}")
    logger.info(f"From zone: {args.zone}")
    logger.info(f"Timestep: {args.timestep}")
    
    # Parse subdomain parameters
    subdomain = {}
    if hasattr(args, 'xmin') and args.xmin is not None:
        subdomain['xmin'] = args.xmin
    if hasattr(args, 'xmax') and args.xmax is not None:
        subdomain['xmax'] = args.xmax
    if hasattr(args, 'ymin') and args.ymin is not None:
        subdomain['ymin'] = args.ymin
    if hasattr(args, 'ymax') and args.ymax is not None:
        subdomain['ymax'] = args.ymax
    if hasattr(args, 'zmin') and args.zmin is not None:
        subdomain['zmin'] = args.zmin
    if hasattr(args, 'zmax') and args.zmax is not None:
        subdomain['zmax'] = args.zmax
    
    if subdomain:
        logger.info(f"Subdomain filter: {subdomain}")
    
    # Use pytecplot-based extraction
    from flexflow.tecplot_handler import extract_data_pytecplot, extract_data_macro
    
    output_file = args.output_file if args.output_file else None
    
    result = extract_data_pytecplot(
        str(case_dir),
        args.timestep,
        args.zone,
        requested_vars,
        output_file,
        subdomain if subdomain else None
    )
    
    if result is None:
        # Fallback to macro-based approach
        logger.info("Attempting macro-based extraction...")
        result = extract_data_macro(
            str(case_dir),
            args.timestep,
            args.zone,
            requested_vars,
            output_file if output_file else str(case_dir / f"extracted_{args.timestep}.csv"),
            subdomain if subdomain else None
        )
    
    if not result:
        logger.error("Data extraction failed")
        sys.exit(1)


def extract_zone_data(plt_file, zone_name, variables):
    """
    DEPRECATED: Use macro-based extraction in execute_extract instead
    """
    return None
