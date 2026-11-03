"""
Visualization commands - Plot and compare data
Commands: plot, compare
"""

from ..base import BaseCommand
from src.cli.context import (case_arg, context_flag, last_arg, node_arg, osgid_arg,
                              othid_arg, time_window)


def _step(text):
    """A step: '3000' or the context's '3000.0'."""
    value = float(text)
    if not value.is_integer():
        raise ValueError(f"not a whole step: {text}")
    return int(value)


class PlotCommand(BaseCommand):
    """Plot the history of a variable (--var, or use var:)"""

    name = "plot"
    description = "Plot the history of a variable (--var, or use var:)"
    category = "Visualization"

    def setup_parser(self, subparsers):
        """Setup argument parser for plot command"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )
        # Required arguments
        case_arg(parser, help='Case directory path')
        parser.add_argument('--input-file', type=str, help='YAML input file')
        context_flag(parser, 'var', '--var', '--variable', dest='var', type=str,
                     action='append', metavar='NAME',
                     help='Variable or component to plot, as in data table '
                          '(repeat, or comma-separate; default: use var:)')
        node_arg(parser, help='Node to read (default: 0)')
        othid_arg(parser, help='othId (probe set) in the othd files (default: the first)')
        osgid_arg(parser, help='osgId (surface group) in the oisd files (default: the first)')
        parser.add_argument('--group', type=int, metavar='ID',
                            help='The group id, whichever kind the variables are in')
        parser.add_argument('--othd', action='store_true', help='Look only in the othd files')
        parser.add_argument('--oisd', action='store_true', help='Look only in the oisd files')

        # Plot options
        parser.add_argument('--plot-type', type=str, default='time',
                          choices=['time', 'fft', 'traj2d', 'traj3d'],
                          help='Plot type')
        # t1/t2 are tsIds, as in data table
        time_window(parser, ('--t1', '--start-step'), ('--t2', '--end-step'),
                    t1_kwargs=dict(type=_step, metavar='TSID', help='First tsId'),
                    t2_kwargs=dict(type=_step, metavar='TSID', help='Last tsId'))
        last_arg(parser, help='Only the last N steps (of the --t1/--t2 window)')
        parser.add_argument('--start-time', type=float, help='Start time (on top of the tsIds)')
        parser.add_argument('--end-time', type=float, help='End time')

        # Styling options
        parser.add_argument('--plot-style', type=str, help='Plot style string')
        parser.add_argument('--title', type=str, help='Plot title')
        parser.add_argument('--xlabel', type=str, help='X-axis label')
        parser.add_argument('--ylabel', type=str, help='Y-axis label')
        parser.add_argument('--legend', type=str, help='Legend label')
        parser.add_argument('--legend-style', type=str, help='Legend style')
        parser.add_argument('--fontsize', type=int, help='Font size')
        parser.add_argument('--fontname', type=str, help='Font name')

        # Output options
        parser.add_argument('--output', type=str, help='Output file path (supports .png, .pdf, .svg, .eps)')
        parser.add_argument('--restart', action='store_true',
                          help='Mark the restarts in .restarts with dashed lines')
        parser.add_argument('--gnu', action='store_true',
                          help='Display plot in terminal (gnuplot-style, useful for HPC)')
        parser.add_argument('--no-display', action='store_true',
                          help='Do not display plot')
        parser.add_argument('-v', '--verbose', action='store_true',
                          help='Enable verbose output')
        parser.add_argument('-h', '--help', action='store_true',
                          help='Show help for plot command')
        parser.add_argument('--examples', action='store_true',
                          help='Show usage examples')
        return parser

    def execute(self, args):
        """Execute plot command"""
        if hasattr(args, 'help') and args.help:
            self.show_help()
        elif hasattr(args, 'examples') and args.examples:
            self.show_examples()
        else:
            from .plot_impl import command as plot_cmd
            plot_cmd.execute_plot(args)

    def show_help(self):
        """Show help message"""
        from .plot_impl.help_messages import print_plot_help
        print_plot_help()

    def show_examples(self):
        """Show usage examples"""
        from .plot_impl.help_messages import print_plot_examples
        print_plot_examples()


class CompareCommand(BaseCommand):
    """Compare multiple cases"""

    name = "compare"
    description = "Compare multiple cases"
    category = "Visualization"

    def setup_parser(self, subparsers):
        """Setup argument parser for compare command"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )
        parser.add_argument('--config', type=str, help='YAML configuration file')
        parser.add_argument('-v', '--verbose', action='store_true',
                          help='Enable verbose output')
        parser.add_argument('-h', '--help', action='store_true',
                          help='Show help for compare command')
        parser.add_argument('--examples', action='store_true',
                          help='Show usage examples')
        return parser

    def execute(self, args):
        """Execute compare command"""
        if hasattr(args, 'help') and args.help:
            self.show_help()
        elif hasattr(args, 'examples') and args.examples:
            self.show_examples()
        else:
            from .compare_impl import command as compare_cmd
            compare_cmd.execute_compare(args)

    def show_help(self):
        """Show help message"""
        from .compare_impl.help_messages import print_compare_help
        print_compare_help()

    def show_examples(self):
        """Show usage examples"""
        from .compare_impl.help_messages import print_compare_examples
        print_compare_examples()


# Create command instances - export as classes not instances
plot_command = PlotCommand
compare_command = CompareCommand
