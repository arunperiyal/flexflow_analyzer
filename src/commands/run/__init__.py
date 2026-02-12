"""
Run commands - Submit and manage SLURM jobs
Commands: check, pre, main, post, sq, sb, sc
"""

from ..base import BaseCommand


class RunCommand(BaseCommand):
    """Run SLURM jobs for FlexFlow simulations"""

    name = "run"
    description = "Submit and manage SLURM jobs"
    category = "Execution"

    def setup_parser(self, subparsers):
        """Setup argument parser for run command"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )

        # Create subparsers for run subcommands
        run_subparsers = parser.add_subparsers(
            dest='run_subcommand',
            help='Run subcommands'
        )

        # run check subcommand
        check_parser = run_subparsers.add_parser(
            'check',
            add_help=False,
            help='Validate case directory structure'
        )
        check_parser.add_argument('case', nargs='?', help='Case directory')
        check_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
        check_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # run pre subcommand
        pre_parser = run_subparsers.add_parser(
            'pre',
            add_help=False,
            help='Submit preprocessing job'
        )
        pre_parser.add_argument('case', nargs='?', help='Case directory')
        pre_parser.add_argument('--dry-run', action='store_true', help='Show what would be submitted')
        pre_parser.add_argument('--show', action='store_true', help='Display script contents')
        pre_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
        pre_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # run main subcommand
        main_parser = run_subparsers.add_parser(
            'main',
            add_help=False,
            help='Submit main simulation job'
        )
        main_parser.add_argument('case', nargs='?', help='Case directory')
        main_parser.add_argument('--restart', type=int, metavar='TSID', help='Restart from specific timestep')
        main_parser.add_argument('--dependency', type=str, metavar='JOB_ID', help='Job dependency')
        main_parser.add_argument('--dry-run', action='store_true', help='Show what would be submitted')
        main_parser.add_argument('--show', action='store_true', help='Display script contents')
        main_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
        main_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # run post subcommand
        post_parser = run_subparsers.add_parser(
            'post',
            add_help=False,
            help='Submit postprocessing job'
        )
        post_parser.add_argument('case', nargs='?', help='Case directory')
        post_parser.add_argument('--upto', type=int, metavar='TSID', help='Process up to timestep')
        post_parser.add_argument('--last', type=int, metavar='N', help='Process last N timesteps')
        post_parser.add_argument('--freq', type=int, metavar='N', help='Output frequency')
        post_parser.add_argument('--cleanup', action='store_true', help='Clean files before processing')
        post_parser.add_argument('--no-cleanup', action='store_true', help='Skip cleanup')
        post_parser.add_argument('--cleanup-only', action='store_true', help='Only run cleanup')
        post_parser.add_argument('--dry-run', action='store_true', help='Show what would be submitted')
        post_parser.add_argument('--show', action='store_true', help='Display script contents')
        post_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
        post_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # run sq subcommand (job queue status)
        sq_parser = run_subparsers.add_parser(
            'sq',
            add_help=False,
            help='Show SLURM job queue status'
        )
        sq_parser.add_argument('job_id', nargs='?', help='Show detail for a specific job ID')
        sq_parser.add_argument('--all', action='store_true', help='Show all users jobs')
        sq_parser.add_argument('--watch', action='store_true', help='Watch mode (refresh every 10s)')
        sq_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # run sb subcommand (sbatch wrapper)
        sb_parser = run_subparsers.add_parser(
            'sb',
            add_help=False,
            help='Submit a SLURM job script'
        )
        sb_parser.add_argument('script', nargs='?', help='Path to the batch script')
        sb_parser.add_argument('extra', nargs='*', help='Extra arguments passed to sbatch')
        sb_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # run sc subcommand (scancel wrapper)
        sc_parser = run_subparsers.add_parser(
            'sc',
            add_help=False,
            help='Cancel a SLURM job by ID or name'
        )
        sc_parser.add_argument('target', nargs='?', help='Job ID or job name to cancel')
        sc_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # General help for run command
        parser.add_argument('-h', '--help', action='store_true', help='Show help')

        return parser

    def execute(self, args):
        """Execute run command"""
        if hasattr(args, 'help') and args.help and not hasattr(args, 'run_subcommand'):
            self.show_help()
            return

        # Get subcommand
        subcommand = getattr(args, 'run_subcommand', None)

        if not subcommand:
            self.show_help()
            return

        # Route to appropriate subcommand handler
        if subcommand == 'check':
            from .check_impl import command as check_cmd
            check_cmd.execute_check(args)
        elif subcommand == 'pre':
            from .pre_impl import command as pre_cmd
            pre_cmd.execute_pre(args)
        elif subcommand == 'main':
            from .main_impl import command as main_cmd
            main_cmd.execute_main(args)
        elif subcommand == 'post':
            from .post_impl import command as post_cmd
            post_cmd.execute_post(args)
        elif subcommand == 'sq':
            from .sq_impl import command as sq_cmd
            sq_cmd.execute_sq(args)
        elif subcommand == 'sb':
            from .sb_impl import command as sb_cmd
            sb_cmd.execute_sb(args)
        elif subcommand == 'sc':
            from .sc_impl import command as sc_cmd
            sc_cmd.execute_sc(args)
        else:
            print(f"Unknown subcommand: {subcommand}")
            self.show_help()

    def show_help(self):
        """Show help message"""
        from .help_messages import print_run_help
        print_run_help()


# Export command class
run_command = RunCommand
