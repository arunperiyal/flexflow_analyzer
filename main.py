#!/usr/bin/env python3
"""
FlexFlow CLI - Main entry point
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from module.cli.parser import parse_args
from module.cli.help_messages import *
from module.commands import info, plot, compare, template, docs, statistics, preview, show_docs_help
from module.installer import install, uninstall, update


def main():
    args = parse_args()
    
    # Handle global flags first
    if args.install:
        install()
        return
    elif args.uninstall:
        uninstall()
        return
    elif args.update:
        update()
        return
    
    # Handle commands
    if not args.command:
        print_main_help()
    elif args.command == 'info':
        if hasattr(args, 'examples') and args.examples:
            print_info_examples()
        elif hasattr(args, 'help') and args.help:
            print_info_help()
        else:
            info.execute_info(args)
    elif args.command == 'plot':
        if hasattr(args, 'examples') and args.examples:
            print_plot_examples()
        elif hasattr(args, 'help') and args.help:
            print_plot_help()
        else:
            plot.execute_plot(args)
    elif args.command == 'compare':
        if hasattr(args, 'examples') and args.examples:
            print_compare_examples()
        elif hasattr(args, 'help') and args.help:
            print_compare_help()
        else:
            compare.execute_compare(args)
    elif args.command == 'template':
        if hasattr(args, 'examples') and args.examples:
            print_template_examples()
        elif hasattr(args, 'help') and args.help:
            print_template_help()
        else:
            template.execute_template(args)
    elif args.command == 'docs':
        if hasattr(args, 'help') and args.help:
            show_docs_help()
        else:
            docs.docs_command(args)
    elif args.command == 'statistics':
        if hasattr(args, 'examples') and args.examples:
            from module.commands.statistics_cmd.help_messages import print_statistics_examples
            print_statistics_examples()
        elif hasattr(args, 'help') and args.help:
            from module.commands.statistics_cmd.help_messages import print_statistics_help
            print_statistics_help()
        else:
            statistics.execute_statistics(args)
    elif args.command == 'preview':
        if hasattr(args, 'examples') and args.examples:
            from module.commands.preview_cmd.help_messages import print_preview_examples
            print_preview_examples()
        elif hasattr(args, 'help') and args.help:
            from module.commands.preview_cmd.help_messages import print_preview_help
            print_preview_help()
        else:
            preview.execute_preview(args)
    else:
        print_main_help()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
