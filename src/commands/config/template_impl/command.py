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
    from .help_messages import print_template_help, print_template_examples

    # Handle help and examples flags
    if hasattr(args, 'help') and args.help:
        print_template_help()
        return

    if hasattr(args, 'examples') and args.examples:
        print_template_examples()
        return

    # Show help if no template type provided
    if not args.template_type:
        print_template_help()
        return

    logger = Logger(verbose=args.verbose)
    
    try:
        template_type = args.template_type
        
        # Determine source and destination
        template_dir = os.path.join(Config.get_install_dir(), 'templates')
        
        if template_type == 'single':
            source_file = os.path.join(template_dir, 'example_single_config.yaml')
            default_output = 'single_plot_config.yaml'
            usage_cmd = f'flexflow plot --input-file {{}}'
        elif template_type == 'multi':
            source_file = os.path.join(template_dir, 'example_multi_config.yaml')
            default_output = 'multi_plot_config.yaml'
            usage_cmd = f'flexflow compare --input-file {{}}'
        elif template_type == 'fft':
            source_file = os.path.join(template_dir, 'example_fft_config.yaml')
            default_output = 'fft_plot_config.yaml'
            usage_cmd = f'flexflow plot --input-file {{}}'
        elif template_type == 'case':
            source_file = os.path.join(template_dir, 'example_case_config.yaml')
            default_output = 'case_config.yaml'
            usage_cmd = f'flexflow case create --from-config {{}}'
        else:
            print(f"{Colors.red('Error:')} Invalid template type: {template_type}", file=sys.stderr)
            print(f"Valid types: single, multi, fft, case", file=sys.stderr)
            sys.exit(1)
        
        # Check if source exists
        if not os.path.exists(source_file):
            print(f"{Colors.red('Error:')} Template file not found: {source_file}", file=sys.stderr)
            sys.exit(1)
        
        # Determine output file
        output_file = args.output if args.output else default_output
        
        # Check if output exists
        if os.path.exists(output_file) and not args.force:
            print(f"{Colors.red('Error:')} File already exists: {output_file}", file=sys.stderr)
            print(f"Use --force to overwrite", file=sys.stderr)
            sys.exit(1)
        
        # Copy template
        logger.info(f"Creating template file: {output_file}")
        shutil.copy(source_file, output_file)

        logger.success(f"Template created: {output_file}")
        print(f"\n{Colors.green('✓')} Created {Colors.bold(output_file)}")

        # Show appropriate next steps based on template type
        if template_type == 'case':
            print(f"\nEdit this file to configure your case parameters,")
            print(f"then run: {Colors.cyan(usage_cmd.format(output_file))}")
            print(f"\nYou can also create multiple cases by defining the 'cases' list in the YAML file.")
        else:
            print(f"\nEdit this file to customize your plot configuration,")
            print(f"then run: {Colors.cyan(usage_cmd.format(output_file))}")
        
    except Exception as e:
        logger.error(str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
