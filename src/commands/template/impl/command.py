"""
Template command implementation
"""

import sys
import os
import shutil

from ....utils.logger import Logger
from ....utils.colors import Colors
from ....utils.config import Config


def execute_template(args):
    """
    Execute the template command

    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    """
    from .help_messages import print_plot_help, print_case_help, print_script_help

    # Handle help flags
    if hasattr(args, 'help') and args.help:
        if args.template_domain == 'plot':
            print_plot_help()
        elif args.template_domain == 'case':
            print_case_help()
        elif args.template_domain == 'script':
            print_script_help()
        return

    logger = Logger(verbose=args.verbose if hasattr(args, 'verbose') else False)

    try:
        domain = args.template_domain

        if domain == 'script':
            # Handle script template generation
            generate_script_templates(args, logger)
            return

        elif domain == 'plot':
            # Get plot type
            if not hasattr(args, 'plot_type') or not args.plot_type:
                print_plot_help()
                return

            plot_type = args.plot_type
            # Normalize 'multiple' to 'multi'
            if plot_type == 'multiple':
                plot_type = 'multi'

            # Determine source and output files
            template_dir = os.path.join(Config.get_install_dir(), 'templates')

            if plot_type == 'single':
                source_file = os.path.join(template_dir, 'example_single_config.yaml')
                default_output = 'plot_single.yaml'
                usage_cmd = 'flexflow plot --input-file {}'
            elif plot_type == 'multi':
                source_file = os.path.join(template_dir, 'example_multi_config.yaml')
                default_output = 'plot_multi.yaml'
                usage_cmd = 'flexflow compare --input-file {}'
            else:
                logger.error(f"Invalid plot type: {plot_type}")
                print_plot_help()
                return

        elif domain == 'case':
            # Get case type
            if not hasattr(args, 'case_type') or not args.case_type:
                print_case_help()
                return

            case_type = args.case_type
            # Normalize 'multiple' to 'multi'
            if case_type == 'multiple':
                case_type = 'multi'

            # Determine source and output files
            template_dir = os.path.join(Config.get_install_dir(), 'templates')

            if case_type == 'single':
                source_file = os.path.join(template_dir, 'example_case_single.yaml')
                default_output = 'case_single.yaml'
            elif case_type == 'multi':
                source_file = os.path.join(template_dir, 'example_case_multi.yaml')
                default_output = 'case_multi.yaml'
            else:
                logger.error(f"Invalid case type: {case_type}")
                print_case_help()
                return

            usage_cmd = 'flexflow case create --from-config {} --ref-case ./refCase'

        else:
            logger.error(f"Invalid domain: {domain}")
            return

        # Check if source exists
        if not os.path.exists(source_file):
            logger.error(f"Template file not found: {source_file}")
            sys.exit(1)

        # Determine output file
        output_file = args.output if hasattr(args, 'output') and args.output else default_output

        # Check if output exists
        if os.path.exists(output_file) and not getattr(args, 'force', False):
            logger.error(f"File already exists: {output_file}")
            print(f"Use --force to overwrite", file=sys.stderr)
            sys.exit(1)

        # Copy template
        logger.info(f"Creating template file: {output_file}")
        shutil.copy(source_file, output_file)

        logger.success(f"Template created: {output_file}")
        print(f"\n{Colors.green('✓')} Created {Colors.bold(output_file)}")

        # Show appropriate next steps
        print(f"\nEdit this file to configure your {domain} parameters,")
        print(f"then run: {Colors.cyan(usage_cmd.format(output_file))}")

        if domain == 'case':
            if case_type == 'single':
                print(f"\n{Colors.bold('Template:')} Single case configuration")
                print(f"  - Edit case_name, problem_name, processors, output_frequency")
                print(f"  - Modify geo and def parameters as needed")
            elif case_type == 'multi':
                print(f"\n{Colors.bold('Template:')} Multiple cases (batch generation)")
                print(f"  - Edit the 'cases' list to define parameter variations")
                print(f"  - Each case will be created as a separate directory")

    except Exception as e:
        logger.error(str(e))
        if hasattr(args, 'verbose') and args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def generate_script_templates(args, logger):
    """
    Generate SLURM job script templates

    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command arguments
    logger : Logger
        Logger instance
    """
    from pathlib import Path

    # Get script type
    if not hasattr(args, 'script_type') or not args.script_type:
        from .help_messages import print_script_help
        print_script_help()
        return

    script_type = args.script_type

    # Get case directory (default to current directory)
    if hasattr(args, 'case_dir') and args.case_dir:
        case_dir = Path(args.case_dir)
    else:
        case_dir = Path.cwd()

    # Create case directory if it doesn't exist
    if not case_dir.exists():
        logger.info(f"Creating case directory: {case_dir}")
        case_dir.mkdir(parents=True, exist_ok=True)

    # Resolve to absolute path
    case_dir = case_dir.resolve()

    # Use directory name as case name (for job names like preCS4SG4U1P0)
    case_name = case_dir.name

    # Determine template directory
    template_dir = os.path.join(Config.get_install_dir(), 'templates', 'scripts')

    # Scripts to generate
    scripts_to_generate = [script_type]

    # Generate scripts
    generated = []

    for script in scripts_to_generate:
        # Determine source and output files
        if script == 'env':
            source_file = os.path.join(template_dir, 'simflow_env.sh')
            output_file = case_dir / 'simflow_env.sh'
            description = "environment config (executable paths, modules)"
        elif script == 'pre':
            source_file = os.path.join(template_dir, 'preFlex.sh')
            output_file = case_dir / 'preFlex.sh'
            description = "preprocessing (mesh generation)"
        elif script == 'main':
            source_file = os.path.join(template_dir, 'mainFlex.sh')
            output_file = case_dir / 'mainFlex.sh'
            description = "main simulation"
        elif script == 'post':
            source_file = os.path.join(template_dir, 'postFlex.sh')
            output_file = case_dir / 'postFlex.sh'
            description = "postprocessing"
        else:
            logger.error(f"Invalid script type: {script}")
            continue

        # Check if source exists
        if not os.path.exists(source_file):
            logger.error(f"Template file not found: {source_file}")
            continue

        # Check if output exists
        if output_file.exists() and not getattr(args, 'force', False):
            logger.error(f"File already exists: {output_file}")
            print(f"Use --force to overwrite", file=sys.stderr)
            continue

        # Read template
        with open(source_file, 'r') as f:
            content = f.read()

        # Replace placeholders
        content = content.replace('{CASE_NAME}', case_name)

        # Apply --simflow-home override (env script only)
        simflow_home = getattr(args, 'simflow_home', None)
        if script == 'env' and simflow_home:
            import re
            content = re.sub(
                r'^(export SIMFLOW_HOME=).*$',
                f'\\1"{simflow_home}"',
                content,
                flags=re.MULTILINE,
            )

        # Apply --gmsh-path override (env script only)
        gmsh_path = getattr(args, 'gmsh_path', None)
        if script == 'env' and gmsh_path:
            import re
            content = re.sub(
                r'^(export GMSH=).*$',
                f'\\1"{gmsh_path}"',
                content,
                flags=re.MULTILINE,
            )

        # Apply --partition override (all scripts except env)
        partition_override = getattr(args, 'partition', None)
        if script != 'env' and partition_override:
            header_file = Path(template_dir) / 'headers' / f'{partition_override}.header'
            if header_file.exists():
                # Determine script_type for {SCRIPT_TYPE} substitution
                script_type_placeholder = script  # 'pre', 'main', 'post'

                # Replace the full #SBATCH block with the header template
                header_block = header_file.read_text()
                header_block = header_block.replace('{CASE_NAME}', case_name)
                header_block = header_block.replace('{SCRIPT_TYPE}', script_type_placeholder)

                lines = content.splitlines(keepends=True)
                sbatch_start = sbatch_end = None
                for i, line in enumerate(lines):
                    if line.strip().startswith('#SBATCH'):
                        if sbatch_start is None:
                            sbatch_start = i
                        sbatch_end = i
                if sbatch_start is not None:
                    content = ''.join(
                        lines[:sbatch_start]
                        + [header_block if header_block.endswith('\n') else header_block + '\n']
                        + lines[sbatch_end + 1:]
                    )
            else:
                # No header file: fall back to replacing just the -p / --partition line
                import re
                content = re.sub(
                    r'^(#SBATCH\s+(?:-p\s+|--partition[=\s]+))\S+',
                    f'\\g<1>{partition_override}',
                    content,
                    flags=re.MULTILINE,
                )

        # Apply --wall-time override (all scripts except env) — rewrite #SBATCH -t / --time line
        wall_time = getattr(args, 'wall_time', None)
        if script != 'env' and wall_time:
            import re
            content = re.sub(
                r'^(#SBATCH\s+(?:-t\s+|--time[=\s]+))\S+',
                f'\\g<1>{wall_time}',
                content,
                flags=re.MULTILINE,
            )

        # Write output
        logger.info(f"Creating {script} script: {output_file}")
        with open(output_file, 'w') as f:
            f.write(content)

        # Make executable
        os.chmod(output_file, 0o755)

        # Annotate description with active overrides
        if script == 'env' and getattr(args, 'simflow_home', None):
            description += f' [SIMFLOW_HOME={args.simflow_home}]'
        if script == 'env' and getattr(args, 'gmsh_path', None):
            description += f' [GMSH={args.gmsh_path}]'
        if script != 'env' and getattr(args, 'partition', None):
            description += f' [partition={args.partition}]'
        if script != 'env' and wall_time:
            description += f' [wall-time={wall_time}]'

        generated.append((output_file.name, description))

    # Show summary
    if generated:
        print(f"\n{Colors.green('✓')} Generated {len(generated)} script(s) in: {Colors.bold(str(case_dir))}")
        print()

        for script_name, desc in generated:
            print(f"  {Colors.cyan(script_name)}")
            print(f"    {Colors.dim(desc)}")

        print()
        print(f"{Colors.bold('Next steps:')}")
        print(f"  1. Edit {Colors.cyan('simflow_env.sh')} to set executable paths:")
        print(f"     {Colors.cyan('SIMFLOW_HOME')}, {Colors.cyan('GMSH')}, modules, etc.")
        print(f"  2. Submit jobs:")
        print(f"     {Colors.cyan('run pre')}   # Preprocessing")
        print(f"     {Colors.cyan('run main')}  # Main simulation")
        print(f"     {Colors.cyan('run post')}  # Postprocessing")
    else:
        logger.error("No scripts were generated")
        sys.exit(1)
