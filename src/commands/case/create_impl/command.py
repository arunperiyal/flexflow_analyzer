"""
New command implementation
"""

import os
import sys
import shutil
import yaml
import re
from pathlib import Path
from ....utils.logger import Logger
from ....utils.colors import Colors


def detect_geo_placeholders(geo_file_path):
    """
    Detect all #placeholder variables in a .geo file

    Parameters:
    -----------
    geo_file_path : Path
        Path to .geo file

    Returns:
    --------
    set
        Set of placeholder variable names (without the # prefix)
    """
    placeholders = set()

    if not geo_file_path.exists():
        return placeholders

    # Pattern to match #variable_name (word characters after #)
    pattern = r'#([a-zA-Z_][a-zA-Z0-9_]*)'

    with open(geo_file_path, 'r') as f:
        for line in f:
            matches = re.findall(pattern, line)
            placeholders.update(matches)

    return placeholders


def detect_def_variables(def_file_path):
    """
    Detect all variables defined in define{} blocks in a .def file

    Parameters:
    -----------
    def_file_path : Path
        Path to .def file

    Returns:
    --------
    dict
        Dictionary of variable_name: current_value pairs
    """
    variables = {}

    if not def_file_path.exists():
        return variables

    in_define_block = False
    current_variable = None

    with open(def_file_path, 'r') as f:
        for line in f:
            stripped = line.strip()

            # Detect define block start
            if stripped.startswith('define{'):
                in_define_block = True
                continue

            # Detect define block end
            if in_define_block and stripped == '}':
                in_define_block = False
                current_variable = None
                continue

            # Inside define block, look for variable definitions
            if in_define_block:
                if stripped.startswith('variable'):
                    # Extract variable name
                    parts = stripped.split('=')
                    if len(parts) == 2:
                        current_variable = parts[1].strip()
                elif stripped.startswith('value') and current_variable:
                    # Extract value
                    parts = stripped.split('=')
                    if len(parts) == 2:
                        value = parts[1].strip()
                        variables[current_variable] = value
                        current_variable = None

    return variables


def parse_simflow_config(config_path):
    """
    Parse simflow.config file to extract problem name
    
    Parameters:
    -----------
    config_path : str or Path
        Path to simflow.config file
    
    Returns:
    --------
    str
        Problem name from config file
    """
    with open(config_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if line.startswith('#') or not line:
                continue
            # Look for problem = <name>
            if line.startswith('problem'):
                parts = line.split('=')
                if len(parts) == 2:
                    problem_name = parts[1].strip()
                    return problem_name
    
    raise ValueError("Could not find 'problem' definition in simflow.config")


def update_simflow_config(config_path, new_problem_name):
    """
    Update problem name in simflow.config file
    
    Parameters:
    -----------
    config_path : str or Path
        Path to simflow.config file
    new_problem_name : str
        New problem name to set
    """
    lines = []
    updated = False
    
    with open(config_path, 'r') as f:
        for line in f:
            if line.strip().startswith('problem') and '=' in line and not line.strip().startswith('#'):
                # Update the problem line
                lines.append(f"problem = {new_problem_name}\n")
                updated = True
            else:
                lines.append(line)
    
    if not updated:
        raise ValueError("Could not update problem name in simflow.config")
    
    # Write back
    with open(config_path, 'w') as f:
        f.writelines(lines)


def update_simflow_np_freq(config_path, np_value=None, freq_value=None):
    """
    Update np, nsg, and outFreq values in simflow.config file
    
    Parameters:
    -----------
    config_path : str or Path
        Path to simflow.config file
    np_value : int, optional
        Number of processors (updates both np and nsg)
    freq_value : int, optional
        Output frequency
    """
    lines = []
    
    with open(config_path, 'r') as f:
        for line in f:
            stripped = line.strip()
            
            # Update np value
            if np_value is not None and stripped.startswith('np') and '=' in line and not stripped.startswith('#'):
                # Preserve formatting
                lines.append(f"np\t= {np_value}\n")
            # Update nsg value
            elif np_value is not None and stripped.startswith('nsg') and '=' in line and not stripped.startswith('#'):
                lines.append(f"nsg \t= {np_value}\n")
            # Update outFreq value
            elif freq_value is not None and stripped.startswith('outFreq') and '=' in line and not stripped.startswith('#'):
                lines.append(f"outFreq\t= {freq_value}\n")
            else:
                lines.append(line)
    
    # Write back
    with open(config_path, 'w') as f:
        f.writelines(lines)


def validate_reference_case(ref_case_path, problem_name, logger):
    """
    Validate that reference case has all mandatory files
    
    Parameters:
    -----------
    ref_case_path : Path
        Path to reference case directory
    problem_name : str
        Problem name to validate
    logger : Logger
        Logger instance for messages
    
    Returns:
    --------
    bool
        True if valid, False otherwise
    """
    mandatory_files = [
        'simflow.config',
        f'{problem_name}.geo',
        f'{problem_name}.def',
        'preFlex.sh',
        'mainFlex.sh',
        'postFlex.sh'
    ]
    
    missing_files = []
    for filename in mandatory_files:
        file_path = ref_case_path / filename
        if not file_path.exists():
            missing_files.append(filename)
    
    if missing_files:
        logger.error("Missing mandatory files in reference case:")
        for filename in missing_files:
            logger.error(f"  - {filename}")
        return False
    
    return True


def update_slurm_jobname(script_path, job_name):
    """
    Update SLURM job name in shell script
    
    Parameters:
    -----------
    script_path : Path
        Path to shell script file
    job_name : str
        New job name to set
    """
    lines = []
    with open(script_path, 'r') as f:
        for line in f:
            # Look for SLURM job name directive
            if line.strip().startswith('#SBATCH -J'):
                # Replace the job name
                lines.append(f"#SBATCH -J {job_name}\n")
            else:
                lines.append(line)
    
    # Write back
    with open(script_path, 'w') as f:
        f.writelines(lines)


def update_mainFlex_np(script_path, np_value):
    """
    Update number of processors in mainFlex.sh
    
    Parameters:
    -----------
    script_path : Path
        Path to mainFlex.sh file
    np_value : int
        Number of processors
    """
    lines = []
    with open(script_path, 'r') as f:
        for line in f:
            # Look for SBATCH -n directive
            if line.strip().startswith('#SBATCH -n'):
                lines.append(f"#SBATCH -n {np_value}\n")
            else:
                lines.append(line)
    
    # Write back
    with open(script_path, 'w') as f:
        f.writelines(lines)


def update_postFlex_problem_freq(script_path, problem_name=None, freq_value=None):
    """
    Update problem name and output frequency in postFlex.sh
    
    Parameters:
    -----------
    script_path : Path
        Path to postFlex.sh file
    problem_name : str, optional
        Problem name to set
    freq_value : int, optional
        Output frequency value
    """
    lines = []
    with open(script_path, 'r') as f:
        for line in f:
            stripped = line.strip()
            
            # Update PROBLEM variable
            if problem_name is not None and stripped.startswith('PROBLEM='):
                lines.append(f"PROBLEM={problem_name}\n")
            # Update OUTFREQ variable
            elif freq_value is not None and stripped.startswith('OUTFREQ='):
                lines.append(f"OUTFREQ={freq_value}\n")
            # Replace ${RISER} with ${PROBLEM} for consistency
            elif '${RISER}' in line:
                lines.append(line.replace('${RISER}', '${PROBLEM}'))
            else:
                lines.append(line)
    
    # Write back
    with open(script_path, 'w') as f:
        f.writelines(lines)


def load_yaml_config(config_path):
    """
    Load YAML configuration file
    
    Parameters:
    -----------
    config_path : Path
        Path to YAML config file
    
    Returns:
    --------
    dict
        Configuration dictionary
    """
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML config: {e}")
    except Exception as e:
        raise ValueError(f"Error reading config file: {e}")


def substitute_geo_parameters(geo_file_path, parameters, logger=None):
    """
    Substitute parameters in .geo file
    Replaces #parameter_name with actual values
    Warns about unassigned placeholders

    Parameters:
    -----------
    geo_file_path : Path
        Path to .geo file
    parameters : dict
        Dictionary of parameter_name: value pairs
    logger : Logger, optional
        Logger instance for warnings

    Returns:
    --------
    list
        List of unassigned placeholder names
    """
    # Detect all placeholders in the file
    all_placeholders = detect_geo_placeholders(geo_file_path)

    # Find unassigned placeholders
    provided_params = set(parameters.keys()) if parameters else set()
    unassigned = all_placeholders - provided_params

    # Warn about unassigned placeholders
    if unassigned and logger:
        logger.warning(f"Unassigned .geo placeholders in {geo_file_path.name}: {', '.join(sorted(unassigned))}")
        logger.warning("These will remain as #variable_name in the output file")

    if not parameters:
        return list(unassigned)

    lines = []
    with open(geo_file_path, 'r') as f:
        for line in f:
            modified_line = line
            # Look for #parameter_name patterns
            for param_name, param_value in parameters.items():
                placeholder = f"#{param_name}"
                if placeholder in line:
                    # Replace #parameter_name with the value
                    modified_line = modified_line.replace(placeholder, str(param_value))
            lines.append(modified_line)

    # Write back
    with open(geo_file_path, 'w') as f:
        f.writelines(lines)

    return list(unassigned)


def substitute_def_parameters(def_file_path, parameters):
    """
    Substitute parameters in .def file
    Updates variable definitions
    
    Parameters:
    -----------
    def_file_path : Path
        Path to .def file
    parameters : dict
        Dictionary of variable_name: value pairs
    """
    if not parameters:
        return
    
    lines = []
    in_define_block = False
    current_variable = None
    
    with open(def_file_path, 'r') as f:
        for line in f:
            stripped = line.strip()
            
            # Detect define block start
            if stripped.startswith('define{'):
                in_define_block = True
                lines.append(line)
                continue
            
            # Detect define block end
            if in_define_block and stripped == '}':
                in_define_block = False
                lines.append(line)
                continue
            
            # Inside define block, look for variable definitions
            if in_define_block:
                if stripped.startswith('variable'):
                    # Extract variable name
                    parts = stripped.split('=')
                    if len(parts) == 2:
                        current_variable = parts[1].strip()
                    lines.append(line)
                elif stripped.startswith('value') and current_variable:
                    # Check if we need to replace this variable's value
                    if current_variable in parameters:
                        # Replace the value
                        indent = len(line) - len(line.lstrip())
                        lines.append(' ' * indent + f"value    = {parameters[current_variable]}\n")
                        current_variable = None
                    else:
                        lines.append(line)
                        current_variable = None
                else:
                    lines.append(line)
            else:
                lines.append(line)
    
    # Write back
    with open(def_file_path, 'w') as f:
        f.writelines(lines)


def list_reference_case_variables(ref_case_path, logger):
    """
    List all variables found in reference case .geo and .def files

    Parameters:
    -----------
    ref_case_path : Path
        Path to reference case directory
    logger : Logger
        Logger instance

    Returns:
    --------
    tuple
        (geo_placeholders, def_variables, problem_name)
    """
    # Get problem name from simflow.config
    config_path = ref_case_path / 'simflow.config'
    if not config_path.exists():
        logger.error(f"simflow.config not found in: {ref_case_path}")
        return set(), {}, None

    try:
        problem_name = parse_simflow_config(config_path)
    except ValueError as e:
        logger.error(str(e))
        return set(), {}, None

    # Detect .geo placeholders
    geo_file = ref_case_path / f"{problem_name}.geo"
    geo_placeholders = detect_geo_placeholders(geo_file) if geo_file.exists() else set()

    # Detect .def variables
    def_file = ref_case_path / f"{problem_name}.def"
    def_variables = detect_def_variables(def_file) if def_file.exists() else {}

    return geo_placeholders, def_variables, problem_name


def create_case_from_config(case_config, ref_case_path, logger, force=False, dry_run=False):
    """
    Create a single case from configuration dictionary

    Parameters:
    -----------
    case_config : dict
        Case configuration dictionary
    ref_case_path : Path
        Path to reference case directory
    logger : Logger
        Logger instance
    force : bool
        Whether to overwrite existing directory
    dry_run : bool
        If True, only preview changes without creating files

    Returns:
    --------
    bool
        True if successful, False otherwise
    """
    # Extract configuration
    case_name = case_config.get('case_name', case_config.get('name'))
    if not case_name:
        logger.error("Case name not specified in configuration")
        return False
    
    problem_name = case_config.get('problem_name')
    np_value = case_config.get('processors', 36)
    freq_value = case_config.get('output_frequency', 50)
    geo_params = case_config.get('geo', {})
    def_params = case_config.get('def', {})
    
    if dry_run:
        logger.info(f"\n{Colors.bold(Colors.cyan('[DRY RUN]'))} Preview for case: {case_name}")
    else:
        logger.info(f"\nCreating case: {case_name}")
    logger.info(f"  Problem: {problem_name if problem_name else 'from reference'}")
    logger.info(f"  Processors: {np_value}")
    logger.info(f"  Output Frequency: {freq_value}")
    
    # Check simflow.config exists
    config_path = ref_case_path / 'simflow.config'
    if not config_path.exists():
        logger.error(f"simflow.config not found in reference case: {ref_case_path}")
        return False
    
    # Parse problem name from config if not specified
    try:
        original_problem_name = parse_simflow_config(config_path)
        if not problem_name:
            problem_name = original_problem_name
    except ValueError as e:
        logger.error(str(e))
        return False
    
    # Validate reference case has all mandatory files
    if not validate_reference_case(ref_case_path, original_problem_name, logger):
        return False
    
    # Setup target path
    target_path = Path(case_name).resolve()
    
    # Check if target directory exists
    if target_path.exists():
        if not force and not dry_run:
            logger.error(f"Target directory already exists: {target_path}")
            logger.error("Use --force flag to overwrite")
            return False
        elif force and not dry_run:
            logger.warning(f"Removing existing directory: {target_path}")
            shutil.rmtree(target_path)
        elif target_path.exists() and dry_run:
            logger.warning(f"Target directory already exists: {target_path}")

    # Create target directory
    if dry_run:
        logger.info(f"Would create case directory: {target_path}")
    else:
        logger.info(f"Creating case directory: {target_path}")
        target_path.mkdir(parents=True, exist_ok=True)
    
    # Copy files
    if dry_run:
        logger.info("Would copy files from reference case:")
    else:
        logger.info("Copying files from reference case...")

    files_to_copy = [
        'simflow.config',
        f'{original_problem_name}.geo',
        f'{original_problem_name}.def',
        'preFlex.sh',
        'mainFlex.sh',
        'postFlex.sh'
    ]

    for filename in files_to_copy:
        src = ref_case_path / filename

        # Handle renaming if problem name changed
        if problem_name != original_problem_name and (filename.endswith('.geo') or filename.endswith('.def')):
            extension = filename.split('.')[-1]
            dest_filename = f"{problem_name}.{extension}"
            dest = target_path / dest_filename
            logger.info(f"  {'Would copy' if dry_run else 'Copying'} and renaming: {filename} -> {dest_filename}")
        else:
            dest = target_path / filename
            logger.info(f"  {'Would copy' if dry_run else 'Copying'}: {filename}")

        if not dry_run:
            shutil.copy2(src, dest)

            # Make shell scripts executable
            if filename.endswith('.sh'):
                os.chmod(dest, 0o755)
    
    # Update simflow.config if problem name changed
    if problem_name != original_problem_name:
        logger.info(f"{'Would update' if dry_run else 'Updating'} problem name in simflow.config to: {problem_name}")
        if not dry_run:
            target_config = target_path / 'simflow.config'
            update_simflow_config(target_config, problem_name)

    # Update np and freq values in simflow.config
    logger.info(f"{'Would update' if dry_run else 'Updating'} simflow.config with np={np_value}, freq={freq_value}")
    if not dry_run:
        target_config = target_path / 'simflow.config'
        update_simflow_np_freq(target_config, np_value=np_value, freq_value=freq_value)

    # Update SLURM job names in shell scripts
    logger.info(f"{'Would update' if dry_run else 'Updating'} SLURM job names in shell scripts...")
    slurm_scripts = {
        'preFlex.sh': f"{case_name}_pre",
        'mainFlex.sh': f"{case_name}_main",
        'postFlex.sh': f"{case_name}_post"
    }

    for script_name, job_name in slurm_scripts.items():
        script_path = target_path / script_name
        if dry_run or script_path.exists():
            if not dry_run:
                update_slurm_jobname(script_path, job_name)
            logger.info(f"  {'Would update' if dry_run else 'Updated'} {script_name}: job name set to '{job_name}'")

    # Update mainFlex.sh with np value
    mainFlex_path = target_path / 'mainFlex.sh'
    if dry_run or mainFlex_path.exists():
        logger.info(f"{'Would update' if dry_run else 'Updating'} mainFlex.sh: setting #SBATCH -n to {np_value}")
        if not dry_run:
            update_mainFlex_np(mainFlex_path, np_value)

    # Update postFlex.sh with problem name and freq
    postFlex_path = target_path / 'postFlex.sh'
    if dry_run or postFlex_path.exists():
        logger.info(f"{'Would update' if dry_run else 'Updating'} postFlex.sh: PROBLEM={problem_name}, OUTFREQ={freq_value}")
        if not dry_run:
            update_postFlex_problem_freq(postFlex_path, problem_name=problem_name, freq_value=freq_value)

    # Apply geometry parameter substitutions
    if dry_run:
        # In dry-run, check reference case file for warnings
        ref_geo_file = ref_case_path / f"{original_problem_name}.geo"
        if ref_geo_file.exists():
            if geo_params:
                logger.info(f"Would apply geometry parameters: {geo_params}")
            # Show what placeholders would be unassigned
            all_placeholders = detect_geo_placeholders(ref_geo_file)
            provided_params = set(geo_params.keys()) if geo_params else set()
            unassigned = all_placeholders - provided_params
            if unassigned:
                logger.warning(f"Unassigned .geo placeholders: {', '.join(sorted(unassigned))}")
    else:
        geo_file = target_path / f"{problem_name}.geo"
        if geo_file.exists():
            if geo_params:
                logger.info(f"Applying geometry parameters: {geo_params}")
            substitute_geo_parameters(geo_file, geo_params, logger)

    # Apply def parameter substitutions
    if def_params:
        if dry_run:
            logger.info(f"Would apply flow parameters: {def_params}")
        else:
            def_file = target_path / f"{problem_name}.def"
            if def_file.exists():
                logger.info(f"Applying flow parameters: {def_params}")
                substitute_def_parameters(def_file, def_params)

    if dry_run:
        logger.success(f"Dry run complete for case: {case_name}")
    else:
        logger.success(f"Successfully created case: {case_name}")
    return True


def execute_new(args):
    """
    Execute the new command
    
    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    """
    from .help_messages import print_new_help
    
    logger = Logger(verbose=args.verbose)
    
    try:
        # Determine reference case path
        if args.ref_case:
            ref_case_path = Path(args.ref_case).resolve()
        else:
            ref_case_path = Path('./refCase').resolve()
        
        logger.info(f"Reference case: {ref_case_path}")
        
        # Check if reference case exists
        if not ref_case_path.exists():
            logger.error(f"Reference case directory does not exist: {ref_case_path}")
            sys.exit(1)
        
        if not ref_case_path.is_dir():
            logger.error(f"Reference case path is not a directory: {ref_case_path}")
            sys.exit(1)

        # Handle --list-vars flag
        if args.list_vars:
            geo_placeholders, def_variables, problem_name = list_reference_case_variables(ref_case_path, logger)

            if problem_name:
                print(f"\n{Colors.bold(Colors.cyan('Reference Case Variables:'))}")
                print(f"  {Colors.bold('Problem name:')} {problem_name}")
                print()

                if geo_placeholders:
                    print(f"{Colors.bold(Colors.green('.geo file placeholders:'))}")
                    for placeholder in sorted(geo_placeholders):
                        print(f"  #{placeholder}")
                    print()
                else:
                    print(f"{Colors.bold(Colors.green('.geo file placeholders:'))} None found")
                    print()

                if def_variables:
                    print(f"{Colors.bold(Colors.green('.def file variables:'))}")
                    for var_name, var_value in sorted(def_variables.items()):
                        print(f"  {var_name:20s} = {var_value}")
                    print()
                else:
                    print(f"{Colors.bold(Colors.green('.def file variables:'))} None found")
                    print()

            return

        # Handle YAML configuration
        if args.from_config:
            # Load YAML config
            config_file = Path(args.from_config)
            if not config_file.is_absolute():
                # Try relative to ref case first
                config_file = ref_case_path / args.from_config
                if not config_file.exists():
                    # Try relative to current directory
                    config_file = Path(args.from_config).resolve()
            
            if not config_file.exists():
                logger.error(f"Configuration file not found: {args.from_config}")
                sys.exit(1)
            
            logger.info(f"Loading configuration from: {config_file}")
            config = load_yaml_config(config_file)
            
            # Check for batch cases
            if 'cases' in config:
                # Batch mode
                cases = config['cases']
                logger.info(f"Batch mode: Creating {len(cases)} cases")
                
                success_count = 0
                for case_config in cases:
                    # Override with command-line flags if provided
                    if args.problem_name:
                        case_config['problem_name'] = args.problem_name
                    if args.np != 36:  # Check if np was explicitly set
                        case_config['processors'] = args.np
                    if args.freq != 50:  # Check if freq was explicitly set
                        case_config['output_frequency'] = args.freq
                    
                    if create_case_from_config(case_config, ref_case_path, logger, args.force, args.dry_run):
                        success_count += 1
                    else:
                        logger.warning(f"Failed to create case: {case_config.get('name', 'unknown')}")
                
                if args.dry_run:
                    print(f"\n{Colors.bold(Colors.cyan('[DRY RUN] Batch Preview Summary:'))}")
                else:
                    print(f"\n{Colors.bold(Colors.cyan('Batch Creation Summary:'))}")
                print(f"  {Colors.bold('Total cases:')} {len(cases)}")
                print(f"  {Colors.bold('Successful:')} {success_count}")
                print(f"  {Colors.bold('Failed:')} {len(cases) - success_count}")
                print()
                
            else:
                # Single case mode from config
                # Override config with command-line flags
                if args.case_name:
                    config['case_name'] = args.case_name
                if args.problem_name:
                    config['problem_name'] = args.problem_name
                if args.np != 36:
                    config['processors'] = args.np
                if args.freq != 50:
                    config['output_frequency'] = args.freq
                
                if not config.get('case_name'):
                    logger.error("Case name not specified in config or command line")
                    sys.exit(1)
                
                if create_case_from_config(config, ref_case_path, logger, args.force, args.dry_run):
                    if args.dry_run:
                        print(f"\n{Colors.bold(Colors.cyan('[DRY RUN] Case Preview:'))}")
                    else:
                        print(f"\n{Colors.bold(Colors.cyan('Case Created:'))}")
                    print(f"  {Colors.bold('Location:')} {Path(config['case_name']).resolve()}")
                    print(f"  {Colors.bold('Problem:')} {config.get('problem_name', 'from reference')}")
                    if not args.dry_run:
                        print(f"  {Colors.bold('Files copied:')} 6")
                    print()
                else:
                    sys.exit(1)
            
            return
        
        # Original command-line only mode
        if not args.case_name:
            print_new_help()
            return
        
        case_name = args.case_name
        target_path = Path(case_name).resolve()
        
        # Check simflow.config exists
        config_path = ref_case_path / 'simflow.config'
        if not config_path.exists():
            logger.error(f"simflow.config not found in reference case: {ref_case_path}")
            sys.exit(1)
        
        # Parse problem name from config
        try:
            original_problem_name = parse_simflow_config(config_path)
            logger.info(f"Original problem name: {original_problem_name}")
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)
        
        # Determine final problem name
        if args.problem_name:
            problem_name = args.problem_name
            logger.info(f"Overriding with problem name: {problem_name}")
        else:
            problem_name = original_problem_name
        
        # Validate reference case has all mandatory files
        if not validate_reference_case(ref_case_path, original_problem_name, logger):
            sys.exit(1)
        
        # Check if target directory exists
        if target_path.exists():
            if not args.force and not args.dry_run:
                logger.error(f"Target directory already exists: {target_path}")
                logger.error("Use --force flag to overwrite")
                sys.exit(1)
            elif args.force and not args.dry_run:
                logger.warning(f"Removing existing directory: {target_path}")
                shutil.rmtree(target_path)
            elif target_path.exists() and args.dry_run:
                logger.warning(f"Target directory already exists: {target_path}")

        # Create target directory
        if args.dry_run:
            logger.info(f"{Colors.bold(Colors.cyan('[DRY RUN]'))} Would create case directory: {target_path}")
        else:
            logger.info(f"Creating case directory: {target_path}")
            target_path.mkdir(parents=True, exist_ok=True)

        # Copy files
        if args.dry_run:
            logger.info("Would copy files from reference case:")
        else:
            logger.info("Copying files from reference case...")
        
        # List of files to copy
        files_to_copy = [
            'simflow.config',
            f'{original_problem_name}.geo',
            f'{original_problem_name}.def',
            'preFlex.sh',
            'mainFlex.sh',
            'postFlex.sh'
        ]
        
        for filename in files_to_copy:
            src = ref_case_path / filename

            # Handle renaming if problem name changed
            if args.problem_name and (filename.endswith('.geo') or filename.endswith('.def')):
                # Rename to new problem name
                extension = filename.split('.')[-1]
                dest_filename = f"{problem_name}.{extension}"
                dest = target_path / dest_filename
                logger.info(f"  {'Would copy' if args.dry_run else 'Copying'} and renaming: {filename} -> {dest_filename}")
            else:
                dest = target_path / filename
                logger.info(f"  {'Would copy' if args.dry_run else 'Copying'}: {filename}")

            if not args.dry_run:
                shutil.copy2(src, dest)

                # Make shell scripts executable
                if filename.endswith('.sh'):
                    os.chmod(dest, 0o755)

        # Update simflow.config if problem name changed
        if args.problem_name:
            logger.info(f"{'Would update' if args.dry_run else 'Updating'} problem name in simflow.config to: {problem_name}")
            if not args.dry_run:
                target_config = target_path / 'simflow.config'
                update_simflow_config(target_config, problem_name)

        # Update np and freq values in simflow.config
        logger.info(f"{'Would update' if args.dry_run else 'Updating'} simflow.config with np={args.np}, freq={args.freq}")
        if not args.dry_run:
            target_config = target_path / 'simflow.config'
            update_simflow_np_freq(target_config, np_value=args.np, freq_value=args.freq)
        
        # Update SLURM job names in shell scripts
        logger.info(f"{'Would update' if args.dry_run else 'Updating'} SLURM job names in shell scripts...")
        slurm_scripts = {
            'preFlex.sh': f"{case_name}_pre",
            'mainFlex.sh': f"{case_name}_main",
            'postFlex.sh': f"{case_name}_post"
        }

        for script_name, job_name in slurm_scripts.items():
            script_path = target_path / script_name
            if args.dry_run or script_path.exists():
                if not args.dry_run:
                    update_slurm_jobname(script_path, job_name)
                logger.info(f"  {'Would update' if args.dry_run else 'Updated'} {script_name}: job name set to '{job_name}'")

        # Update mainFlex.sh with np value
        mainFlex_path = target_path / 'mainFlex.sh'
        if args.dry_run or mainFlex_path.exists():
            logger.info(f"{'Would update' if args.dry_run else 'Updating'} mainFlex.sh: setting #SBATCH -n to {args.np}")
            if not args.dry_run:
                update_mainFlex_np(mainFlex_path, args.np)

        # Update postFlex.sh with problem name and freq
        postFlex_path = target_path / 'postFlex.sh'
        if args.dry_run or postFlex_path.exists():
            logger.info(f"{'Would update' if args.dry_run else 'Updating'} postFlex.sh: PROBLEM={problem_name}, OUTFREQ={args.freq}")
            if not args.dry_run:
                update_postFlex_problem_freq(postFlex_path, problem_name=problem_name, freq_value=args.freq)

        if args.dry_run:
            logger.success(f"\nDry run complete for case directory: {target_path}")
        else:
            logger.success(f"\nSuccessfully created case directory: {target_path}")
        logger.success(f"Problem name: {problem_name}")

        # Print summary
        if args.dry_run:
            print(f"\n{Colors.bold(Colors.cyan('[DRY RUN] Case Preview:'))}")
        else:
            print(f"\n{Colors.bold(Colors.cyan('Case Created:'))}")
        print(f"  {Colors.bold('Location:')} {target_path}")
        print(f"  {Colors.bold('Problem:')} {problem_name}")
        if not args.dry_run:
            print(f"  {Colors.bold('Files copied:')} {len(files_to_copy)}")
        print()
        
    except Exception as e:
        logger.error(f"Failed to create case: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
