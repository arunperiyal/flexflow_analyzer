"""
Field extract command implementation
"""

import sys
from pathlib import Path

from ....utils.logger import Logger


def execute_extract(args):
    """Extract data from PLT files using pytecplot"""
    from .help_messages import print_extract_help

    # Handle help flag
    if hasattr(args, 'help') and args.help:
        print_extract_help()
        return

    logger = Logger(verbose=args.verbose if hasattr(args, 'verbose') else False)

    if not args.case:
        print_extract_help()
        sys.exit(1)

    if not args.variables:
        logger.error("--variables flag is required")
        print()
        print_extract_help()
        sys.exit(1)

    if not args.zone:
        logger.error("--zone flag is required")
        print()
        print_extract_help()
        sys.exit(1)

    if not args.timestep:
        logger.error("--timestep flag is required")
        print()
        print_extract_help()
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
    from src.tecplot.handler import extract_data_pytecplot, extract_data_macro

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
