"""
Run commands - Submit and manage SLURM jobs
Commands: check, pre, main, post, list, sq, sb, sc
"""

from ..base import BaseCommand
from src.cli.context import case_flag, context_flag, freq_arg, no_words, time_window


def _complete_sq_mode(rt, prefix):
    return [('watch', 'Refresh the queue every N seconds (default: 10)'),
            ('find', 'Jobs whose name or work directory contains a key')]


def _complete_check_mode(rt, prefix):
    return [('headers', 'SBATCH header info for the job scripts'),
            ('mesh', 'Element counts of the mesh; flags triangles')]


def _complete_main_mode(rt, prefix):
    return [('restart', 'Restart from the last .rst, or from --time TSID'),
            ('reset', 'Comment out restartFlag/restartTsId and start fresh')]


def _complete_list_what(rt, prefix):
    return [('log', 'The slurm-* files, with their job type')]


def _complete_post_mode(rt, prefix):
    return [('full', 'simPlt then simPlt2Bin'),
            ('convert', 'simPlt2Bin only (.plt files must already exist)')]


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
        check_parser.add_argument('mode', nargs='?', metavar='headers|mesh',
                                  help="headers: SBATCH header info; mesh: element counts of "
                                       "the mesh; omit for the whole check"
                                  ).completer = _complete_check_mode
        case_flag(check_parser)
        no_words(check_parser)
        check_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
        check_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # run pre subcommand
        pre_parser = run_subparsers.add_parser(
            'pre',
            add_help=False,
            help='Submit preprocessing job'
        )
        case_flag(pre_parser)
        no_words(pre_parser)
        pre_parser.add_argument('--gmsh', type=str, metavar='PATH', help='Override gmsh executable path (passed to sbatch, does not modify script)')
        pre_parser.add_argument('--convert', action='store_true', help='Skip gmsh meshing; run only simGmshCnvt (mesh must already exist)')
        pre_parser.add_argument('--partition', type=str, metavar='NAME', help='Apply partition header to script')
        pre_parser.add_argument('--account', type=str, metavar='NAME', help='Set SLURM account (passed to sbatch)')
        pre_parser.add_argument('--qos', type=str, metavar='NAME', help='Set SLURM QOS (passed to sbatch)')
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
        main_parser.add_argument('mode', nargs='?', metavar='restart|reset',
                                 help='restart: from the last .rst, or --time TSID; reset: '
                                      'start fresh; omit to submit as it is'
                                 ).completer = _complete_main_mode
        case_flag(main_parser)
        no_words(main_parser)
        main_parser.add_argument('-n', '--np', type=int, metavar='N', help='Set #SBATCH -n/--ntasks in script before submission')
        main_parser.add_argument('--time', type=str, metavar='TSID',
                                 help='With restart: the step to restart from '
                                      '(default: the last written .rst file)')
        main_parser.add_argument('-y', '--yes', action='store_true',
                                 help='With restart: do not ask for confirmation')
        main_parser.add_argument('--dependency', type=str, metavar='JOB_ID', help='Job dependency')
        main_parser.add_argument('--partition', type=str, metavar='NAME', help='Apply partition header to script')
        main_parser.add_argument('--account', type=str, metavar='NAME', help='Set SLURM account (passed to sbatch)')
        main_parser.add_argument('--qos', type=str, metavar='NAME', help='Set SLURM QOS (passed to sbatch)')
        main_parser.add_argument('--wall-time', type=str, metavar='HH:MM:SS', help='Override wall time for this submission only (passed to sbatch)')
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
        post_parser.add_argument('mode', nargs='?', metavar='full|convert',
                                 help="'full' (simPlt, then simPlt2Bin) or 'convert' "
                                      "(simPlt2Bin only)").completer = _complete_post_mode
        case_flag(post_parser)
        no_words(post_parser)
        time_window(post_parser,
                    t1_kwargs=dict(metavar='TSID', help='Process from this timestep (default: 0)'),
                    t2_kwargs=dict(metavar='TSID', help='Process up to this timestep'))
        context_flag(post_parser, 'remote', '--remote', type=str, metavar='REMOTE',
                     help='Send each binary PLT to this remote as soon as it is written '
                          '(or use context with "use remote:name")')
        post_parser.add_argument('--no-remote', action='store_true',
                                 help='Do not send, even with a remote context set')
        freq_arg(post_parser, metavar='N', help='Override output frequency')
        post_parser.add_argument('--dependency', type=str, metavar='JOB_ID', help='Job dependency')
        post_parser.add_argument('--partition', type=str, metavar='NAME', help='Apply partition header to script')
        post_parser.add_argument('--account', type=str, metavar='NAME', help='Set SLURM account (passed to sbatch)')
        post_parser.add_argument('--qos', type=str, metavar='NAME', help='Set SLURM QOS (passed to sbatch)')
        post_parser.add_argument('--cleanup', action='store_true', help='Clean files before processing')
        post_parser.add_argument('--no-cleanup', action='store_true', help='Skip cleanup')
        post_parser.add_argument('--cleanup-only', action='store_true', help='Only run cleanup')
        post_parser.add_argument('--dry-run', action='store_true', help='Show what would be submitted')
        post_parser.add_argument('--show', action='store_true', help='Display script contents')
        post_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
        post_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # run list subcommand (a case's job files)
        list_parser = run_subparsers.add_parser(
            'list',
            add_help=False,
            help="List a case's job files"
        )
        list_parser.add_argument('what', nargs='?', choices=['log'],
                                 help="'log': the slurm-* files, with their job type"
                                 ).completer = _complete_list_what
        case_flag(list_parser)
        no_words(list_parser)
        list_parser.add_argument('--sort', choices=['time', 'type', 'jobid'], default='time',
                                 help='Sort by modification time (default), job type or job ID')
        list_parser.add_argument('-r', '--reverse', action='store_true', help='Reverse the order')
        list_parser.add_argument('--type', action='append', metavar='TYPE',
                                 choices=['pre', 'main', 'post', 'other'],
                                 help='Only this job type (repeatable)')
        list_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # run sq subcommand (job queue status)
        sq_parser = run_subparsers.add_parser(
            'sq',
            add_help=False,
            help='Show SLURM job queue status'
        )
        sq_parser.add_argument('target', nargs='?', metavar='watch|find',
                               help="'watch': refresh the queue; 'find': search it; omit to list it"
                               ).completer = _complete_sq_mode
        sq_parser.add_argument('--job', type=str, metavar='ID', help='Show this job in detail')
        sq_parser.add_argument('--interval', type=float, metavar='SECONDS',
                               help='With watch: refresh every SECONDS (default: 10)')
        sq_parser.add_argument('--key', type=str, metavar='KEY',
                               help='With find: jobs whose name or work directory contains KEY')
        no_words(sq_parser, '--job')
        sq_parser.add_argument('--all', action='store_true', help='Show all users jobs')
        sq_parser.add_argument('--by-dir', action='store_true', help='Group jobs by their work directory')
        sq_parser.add_argument(
            '--sort',
            type=str,
            metavar='COLUMN',
            choices=['id', 'job-id', 'jobid', 'name', 'state', 'time', 'nodes', 'partition',
                     'cpus', 'memory', 'submit', 'submitted', 'reason', 'dependency'],
            help='Sort queue by column'
        )
        sq_parser.add_argument('--out', action='store_true',
                               help='With job_id, print tail of StdOut file')
        sq_parser.add_argument('-n', '--lines', dest='n', type=int, default=20, metavar='N',
                               help='Number of StdOut lines to print with --out (default: 20)')
        sq_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # run sb subcommand (sbatch wrapper)
        sb_parser = run_subparsers.add_parser(
            'sb',
            add_help=False,
            help='Submit a SLURM job script'
        )
        sb_parser.add_argument('--script', type=str, metavar='FILE', help='Path to the batch script')
        sb_parser.add_argument('--sbatch-args', dest='sbatch_args', type=str, metavar='ARGS',
                               help="Extra arguments passed to sbatch, in one string; write it "
                                    "--sbatch-args='--dependency=afterok:123' when it starts with --")
        no_words(sb_parser, '--script')
        sb_parser.add_argument('-h', '--help', action='store_true', help='Show help')

        # run sc subcommand (scancel wrapper)
        sc_parser = run_subparsers.add_parser(
            'sc',
            add_help=False,
            help='Cancel a SLURM job by ID or name'
        )
        sc_parser.add_argument('--job', type=str, metavar='ID', help='Job ID to cancel')
        sc_parser.add_argument('--name', type=str, metavar='NAME', help='Job name to cancel')
        no_words(sc_parser, '--job')
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
        elif subcommand == 'list':
            from .list_impl import command as list_cmd
            list_cmd.execute_list(args)
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
