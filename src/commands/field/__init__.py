"""
Field command group - Work with binary PLT field data (Tecplot-free)
Subcommands: info, extract, convert, iso, check
"""

from ..base import BaseCommand


class FieldCommand(BaseCommand):
    """Field data operations from PLT files (info, extract)"""

    name = "field"
    description = "Field data operations (info, extract, convert, iso, check)"
    category = "File Operations"

    def setup_parser(self, subparsers):
        """Setup argument parser for field command group"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )

        # Create subparsers for field subcommands
        field_subparsers = parser.add_subparsers(dest='field_subcommand',
                                                help='Field subcommands')

        # field info (was: tecplot info)
        info_parser = field_subparsers.add_parser('info', add_help=False,
                                                 help='Show PLT file information')
        info_parser.add_argument('case', nargs='?', help='Case directory path')
        info_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose output')
        info_parser.add_argument('-h', '--help', action='store_true',
                                help='Show help for info command')
        info_parser.add_argument('--basic', action='store_true',
                                help='Show only basic file information')
        info_parser.add_argument('--variables', action='store_true',
                                help='Show only variables section')
        info_parser.add_argument('--zones', action='store_true',
                                help='Show only zone information')
        info_parser.add_argument('--checks', action='store_true',
                                help='Show only consistency checks')
        info_parser.add_argument('--stats', action='store_true',
                                help='Show only data statistics')
        info_parser.add_argument('--detailed', action='store_true',
                                help='Show detailed statistics')
        info_parser.add_argument('--sample-file', type=int, metavar='STEP',
                                help='Analyze specific timestep file')

        # field extract (was: tecplot extract)
        extract_parser = field_subparsers.add_parser('extract', add_help=False,
                                                    help='Extract data from PLT files')
        extract_parser.add_argument('case', nargs='?', help='Case directory path')
        extract_parser.add_argument('-v', '--verbose', action='store_true',
                                   help='Enable verbose output')
        extract_parser.add_argument('-h', '--help', action='store_true',
                                   help='Show help for extract command')
        extract_parser.add_argument('--variables', type=str,
                                   help='Comma-separated list of variables to extract')
        extract_parser.add_argument('--zone', type=str,
                                   help='Zone name to extract from')
        extract_parser.add_argument('--timestep', type=int,
                                   help='Single timestep to extract')
        extract_parser.add_argument('--t1', type=float,
                                   help='Start step (alone: that step; with --t2: range start)')
        extract_parser.add_argument('--t2', type=float,
                                   help='End step of a range (consolidated into one output)')
        extract_parser.add_argument('--freq', type=int,
                                   help='With --t1/--t2: keep only steps that are multiples of FREQ')
        extract_parser.add_argument('--output', '--output-file', dest='output_file', type=str,
                                   help='REQUIRED output: .csv / .vtu/.vtk (mesh) / .pvd (series), '
                                        'or a bare NAME -> a directory NAME/ (relative -> under the case dir)')
        extract_parser.add_argument('--xmin', type=float,
                                   help='Minimum X coordinate')
        extract_parser.add_argument('--xmax', type=float,
                                   help='Maximum X coordinate')
        extract_parser.add_argument('--ymin', type=float,
                                   help='Minimum Y coordinate')
        extract_parser.add_argument('--ymax', type=float,
                                   help='Maximum Y coordinate')
        extract_parser.add_argument('--zmin', type=float,
                                   help='Minimum Z coordinate')
        extract_parser.add_argument('--zmax', type=float,
                                   help='Maximum Z coordinate')
        extract_parser.add_argument('--probe', action='append', metavar='X,Y,Z',
                                   help='Sample at a point (nearest node); repeatable, '
                                        'or several separated by ";". Output is .csv '
                                        '(a table is printed when --output is omitted)')
        extract_parser.add_argument('--probe-tol', dest='probe_tol', type=float,
                                   metavar='TOL',
                                   help='Slack on the inside-domain check for probes '
                                        'sitting on a boundary (default 0)')
        extract_parser.add_argument('--interpolate', action='store_true',
                                   help='With --probe: interpolate inside the cell holding '
                                        'the probe instead of taking the nearest node')
        extract_parser.add_argument('--no-progress', dest='no_progress', action='store_true',
                                   help='Do not draw the progress bar')

        # field convert (PLT -> VTU)
        convert_parser = field_subparsers.add_parser('convert', add_help=False,
                                                     help='Convert PLT to VTK .vtu')
        convert_parser.add_argument('case', nargs='?', help='Case directory path')
        convert_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        convert_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for convert command')
        convert_parser.add_argument('--timestep', type=int,
                                    help='Timestep to convert (default: latest)')
        convert_parser.add_argument('--zone', type=str,
                                    help='Zone to export (default: first volume zone)')
        convert_parser.add_argument('--nen', type=int,
                                    help='Force nodes-per-element (e.g. 8 for bricks)')
        convert_parser.add_argument('--output', type=str,
                                    help='Output .vtu path')
        convert_parser.add_argument('--audit-only', action='store_true',
                                    help='Report element type / size consistency only')
        for _ax in ('xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'):
            convert_parser.add_argument(f'--{_ax}', type=float,
                                        help=f'{_ax[0].upper()}{_ax[1:]} for box crop')

        # field iso (isosurface PNGs via pyvista)
        iso_parser = field_subparsers.add_parser('iso', add_help=False,
                                                 help='Render isosurface images')
        iso_parser.add_argument('case', nargs='?', help='Case directory path')
        iso_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose output')
        iso_parser.add_argument('-h', '--help', action='store_true',
                                help='Show help for iso command')
        iso_parser.add_argument('--vtu', type=str, help='Render an existing .vtu directly')
        iso_parser.add_argument('--config', type=str, help='YAML config file')
        iso_parser.add_argument('--write-template', type=str, metavar='PATH',
                                help='Write a YAML config template and exit')
        iso_parser.add_argument('--timestep', type=int,
                                help='Timestep to convert+render (default: latest)')
        iso_parser.add_argument('--zone', type=str, help='Zone to render')
        iso_parser.add_argument('--nen', type=int,
                                help='Force nodes-per-element when converting')
        iso_parser.add_argument('--contour', type=str,
                                help='Scalar to contour (default QCriterion)')
        iso_parser.add_argument('--iso', type=float, nargs='+', help='Isosurface value(s)')
        iso_parser.add_argument('--color', type=str, help='Scalar to colour by')
        iso_parser.add_argument('--out', type=str, help='Output prefix for .vtp + PNGs')

        # field check (validate a produced VTK file)
        check_parser = field_subparsers.add_parser('check', add_help=False,
                                                   help='Validate a VTK (.vtu/.vtk/.vtp) file')
        check_parser.add_argument('file', nargs='?', help='VTK file to validate')
        check_parser.add_argument('-v', '--verbose', action='store_true',
                                  help='Enable verbose output')
        check_parser.add_argument('-h', '--help', action='store_true',
                                  help='Show help for check command')

        # Main field help flags
        parser.add_argument('-h', '--help', action='store_true',
                           help='Show help for field command')

        return parser

    def execute(self, args):
        """Execute field command"""
        # Check if help was requested or no subcommand
        if not hasattr(args, 'field_subcommand') or args.field_subcommand is None:
            if hasattr(args, 'help') and args.help:
                self.show_help()
                return
            else:
                self.show_help()
                return

        # Execute appropriate subcommand
        if args.field_subcommand == 'info':
            from .info_impl.command import execute_info
            execute_info(args)
        elif args.field_subcommand == 'extract':
            from .extract_impl.command import execute_extract
            execute_extract(args)
        elif args.field_subcommand == 'convert':
            from .convert_impl.command import execute_convert
            execute_convert(args)
        elif args.field_subcommand == 'iso':
            from .iso_impl.command import execute_iso
            execute_iso(args)
        elif args.field_subcommand == 'check':
            from .check_impl.command import execute_check
            execute_check(args)
        else:
            self.show_help()

    def show_help(self):
        """Show help message"""
        from rich.console import Console
        from rich.table import Table
        from rich import box

        console = Console()
        console.print()
        console.print("[bold cyan]FlexFlow Field Command[/bold cyan]")
        console.print()
        console.print("Work with binary PLT field data files (Tecplot-free).")
        console.print()
        console.print("[bold]USAGE:[/bold]")
        console.print("    flexflow field <subcommand> [options]")
        console.print()

        # Create subcommands table
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("Subcommand", style="cyan")
        table.add_column("Description", style="white")

        table.add_row("info", "Show PLT file info (variables, zones, element-type audit)")
        table.add_row("extract", "Extract variables to CSV/mesh (x/y/z box or point probes)")
        table.add_row("convert", "Convert PLT volume zone to VTK .vtu (optional box crop)")
        table.add_row("iso", "Render isosurface PNGs (pyvista, YAML config)")
        table.add_row("check", "Validate a produced VTK file (.vtu/.vtk/.vtp)")

        console.print("[bold]SUBCOMMANDS:[/bold]")
        console.print(table)
        console.print()
        console.print("[bold]EXAMPLES:[/bold]")
        console.print("    flexflow field info myCase --checks")
        console.print("    flexflow field extract myCase --variables U,V,Pressure --zone FIELD --timestep 100")
        console.print("    flexflow field extract myCase --variables U,V --zone FIELD --t1 100 --t2 500 --probe 2.5,0,0")
        console.print("    flexflow field convert myCase --timestep 100")
        console.print("    flexflow field iso myCase --timestep 100 --iso 20 --color W")
        console.print("    flexflow field check results.vtk")
        console.print()


# Create command instance
command = FieldCommand()
