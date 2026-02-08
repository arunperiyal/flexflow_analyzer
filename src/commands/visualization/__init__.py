"""
Visualization commands - Plot and compare data
Commands: plot, compare
"""

from ..base import BaseCommand


class PlotCommand(BaseCommand):
    """Plot displacement or force data"""

    name = "plot"
    description = "Plot displacement or force data"
    category = "Visualization"

    def setup_parser(self, subparsers):
        """Setup argument parser for plot command"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )
        # Required arguments
        parser.add_argument('case', nargs='?', help='Case directory path')
        parser.add_argument('--input-file', type=str, help='YAML input file')
        parser.add_argument('--node', type=int, help='Node number to plot')
        parser.add_argument('--data-type', type=str, choices=['displacement', 'force'],
                          help='Data type to plot')

        # Plot options
        parser.add_argument('--plot-type', type=str, default='time',
                          choices=['time', 'fft', 'traj2d', 'traj3d'],
                          help='Plot type')
        parser.add_argument('--component', type=str, nargs='+',
                          help='Components to plot (x, y, z)')
        parser.add_argument('--start-time', type=float, help='Start time')
        parser.add_argument('--end-time', type=float, help='End time')
        parser.add_argument('--start-step', type=int, help='Start timestep')
        parser.add_argument('--end-step', type=int, help='End timestep')

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
