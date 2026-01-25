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
    from .help_messages import print_plot_help, print_case_help

    # Handle help flags
    if hasattr(args, 'help') and args.help:
        if args.template_domain == 'plot':
            print_plot_help()
        elif args.template_domain == 'case':
            print_case_help()
        return

    logger = Logger(verbose=args.verbose if hasattr(args, 'verbose') else False)

    try:
        domain = args.template_domain

        if domain == 'plot':
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
        if os.path.exists(output_file) and not args.force:
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
