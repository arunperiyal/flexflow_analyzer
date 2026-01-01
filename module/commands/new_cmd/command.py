"""
New command implementation
"""

import os
import sys
import shutil
from pathlib import Path
from ...utils.logger import Logger
from ...utils.colors import Colors


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


def execute_new(args):
    """
    Execute the new command
    
    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    """
    from .help_messages import print_new_help
    
    # Show help if no case name provided
    if not args.case_name:
        print_new_help()
        return
    
    logger = Logger(verbose=args.verbose)
    
    try:
        # Setup paths
        case_name = args.case_name
        target_path = Path(case_name).resolve()
        
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
            if not args.force:
                logger.error(f"Target directory already exists: {target_path}")
                logger.error("Use --force flag to overwrite")
                sys.exit(1)
            else:
                logger.warning(f"Removing existing directory: {target_path}")
                shutil.rmtree(target_path)
        
        # Create target directory
        logger.info(f"Creating case directory: {target_path}")
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Copy files
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
                logger.info(f"  Copying and renaming: {filename} -> {dest_filename}")
            else:
                dest = target_path / filename
                logger.info(f"  Copying: {filename}")
            
            shutil.copy2(src, dest)
            
            # Make shell scripts executable
            if filename.endswith('.sh'):
                os.chmod(dest, 0o755)
        
        # Update simflow.config if problem name changed
        if args.problem_name:
            logger.info(f"Updating problem name in simflow.config to: {problem_name}")
            target_config = target_path / 'simflow.config'
            update_simflow_config(target_config, problem_name)
        
        # Update np and freq values in simflow.config
        logger.info(f"Updating simflow.config with np={args.np}, freq={args.freq}")
        target_config = target_path / 'simflow.config'
        update_simflow_np_freq(target_config, np_value=args.np, freq_value=args.freq)
        
        # Update SLURM job names in shell scripts
        logger.info("Updating SLURM job names in shell scripts...")
        slurm_scripts = {
            'preFlex.sh': f"{case_name}_pre",
            'mainFlex.sh': f"{case_name}_main",
            'postFlex.sh': f"{case_name}_post"
        }
        
        for script_name, job_name in slurm_scripts.items():
            script_path = target_path / script_name
            if script_path.exists():
                update_slurm_jobname(script_path, job_name)
                logger.info(f"  Updated {script_name}: job name set to '{job_name}'")
        
        # Update mainFlex.sh with np value
        mainFlex_path = target_path / 'mainFlex.sh'
        if mainFlex_path.exists():
            logger.info(f"Updating mainFlex.sh: setting #SBATCH -n to {args.np}")
            update_mainFlex_np(mainFlex_path, args.np)
        
        # Update postFlex.sh with problem name and freq
        postFlex_path = target_path / 'postFlex.sh'
        if postFlex_path.exists():
            logger.info(f"Updating postFlex.sh: PROBLEM={problem_name}, OUTFREQ={args.freq}")
            update_postFlex_problem_freq(postFlex_path, problem_name=problem_name, freq_value=args.freq)
        
        logger.success(f"\nSuccessfully created case directory: {target_path}")
        logger.success(f"Problem name: {problem_name}")
        
        # Print summary
        print(f"\n{Colors.bold(Colors.cyan('Case Created:'))}")
        print(f"  {Colors.bold('Location:')} {target_path}")
        print(f"  {Colors.bold('Problem:')} {problem_name}")
        print(f"  {Colors.bold('Files copied:')} {len(files_to_copy)}")
        print()
        
    except Exception as e:
        logger.error(f"Failed to create case: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
