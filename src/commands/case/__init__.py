"""
Case command group - Manages simulation cases
Subcommands: show, create, run, domain, ...
"""

import argparse
import sys
from ..base import BaseCommand
from src.cli.completers import described, file_flags
from src.cli.context import case_arg, context_flag, freq_arg, time_window


# `case upload|download [binary|rst|input] [case]`: what to carry. Nothing named is
# the directories (--dir) and files (--files) as before.
TRANSFER_MODES = {
    'upload': [('binary', 'binary/: every timestep, or just --t1..--t2'),
               ('rst', 'Restart .rst files of every step (or --t1..--t2) in the run directory'),
               ('input', 'The <problem>.def and every File(...) it names (mesh, .nbc, .srf ...)'),
               ('history', 'OTHD/OISD history: archive/, cleaned/, the compiled file (or --archive/--cleaned/--compiled)')],
    'download': [('binary', 'binary/: every timestep, or just --t1..--t2 (--freq)'),
                 ('rst', 'Restart .rst files of every step (or --t1..--t2) from the remote run directory'),
                 ('input', 'The remote <problem>.def and every File(...) it names'),
                 ('history', 'The remote OTHD/OISD history (or --archive/--cleaned/--compiled)')],
}


def _mode(args):
    """binary/rst/input/history, or None when the first word is a case (or absent)."""
    what = getattr(args, 'what', None)
    return what if what in ('binary', 'rst', 'input', 'history') else None


def _stepped(args):
    """The t1/t2/time/freq contexts select timesteps, so they only apply to
    binary/rst (the input files are not per step)."""
    return _mode(args) in ('binary', 'rst')


def _transfer_case(store, ns):
    """The case context, unless the first word was the case itself."""
    what = getattr(ns, 'what', None)
    if what is not None and _mode(ns) is None:
        return None
    return store.get('case') if store.is_set('case') else None


def _transfer_positionals(parser, direction):
    modes = TRANSFER_MODES[direction]

    def complete(rt, prefix):
        return modes
    parser.add_argument('what', nargs='?', metavar='|'.join(m for m, _ in modes),
                        help='What to carry: ' + '; '.join(f"{m}: {h}" for m, h in modes)
                        ).completer = complete
    case_arg(parser, resolve=_transfer_case,
             help=('Local case directory path' if direction == 'upload'
                   else 'Local case directory path (destination)'))
    for name, where in (('archive', 'archive/'), ('cleaned', 'cleaned/'),
                        ('compiled', 'the compiled file')):
        parser.add_argument(f'--{name}', action='store_true',
                            help=f'history: only {where} (combinable; none carries all three)')
    # The old spelling, kept only to point at the new one.
    parser.add_argument('--binary', action='store_true', help=argparse.SUPPRESS)


STATUS_STATES = ('new', 'meshing', 'running', 'stopped', 'done', 'failed', 'archived')


def _status_words(rt, prefix):
    from shellkit.completion import path_candidates
    return [('update', "Edit the notes, or -m TEXT / --state STATE")] + path_candidates(rt, prefix)


def _status_case(store, ns):
    """The case context -- unless the first word was the case itself."""
    what = getattr(ns, 'what', None)
    if what is not None and what != 'update':
        return None
    return store.get('case') if store.is_set('case') else None


class CaseCommand(BaseCommand):
    """Case operations (show, create, run)"""

    name = "case"
    description = "Case operations (show, create, run)"
    category = "Core"

    def setup_parser(self, subparsers):
        """Setup argument parser for case command group"""
        parser = subparsers.add_parser(
            self.name,
            add_help=False,
            help=self.description
        )

        # Create subparsers for case subcommands
        case_subparsers = parser.add_subparsers(dest='case_subcommand',
                                                help='Case subcommands')

        # case show (was: info)
        show_parser = case_subparsers.add_parser('show', add_help=False,
                                                 help='Show case information')
        case_arg(show_parser, help='Case directory path')
        show_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose output')
        show_parser.add_argument('-h', '--help', action='store_true',
                                help='Show help for show command')
        show_parser.add_argument('--examples', action='store_true',
                                help='Show usage examples')

        # case create (was: new)
        create_parser = case_subparsers.add_parser('create', add_help=False,
                                                   help='Create new case')
        create_parser.add_argument('case_name', nargs='?', help='Name of the new case')
        create_parser.add_argument('--ref-case', type=str, default='./refCase',
                                  help='Path to reference case directory')
        create_parser.add_argument('--problem-name', type=str,
                                  help='Problem name to set in simflow.config')
        create_parser.add_argument('--np', type=int, default=36,
                                  help='Number of processors (default: 36)')
        create_parser.add_argument('--freq', type=int, default=50,
                                  help='Output frequency (default: 50)')
        create_parser.add_argument('--from-config', type=str,
                                  help='Create from YAML config file')
        create_parser.add_argument('--force', action='store_true',
                                  help='Force overwrite if case already exists')
        create_parser.add_argument('--list-vars', action='store_true',
                                  help='List available variables in reference case')
        create_parser.add_argument('--dry-run', action='store_true',
                                  help='Show what would be created without actually creating')
        create_parser.add_argument('-v', '--verbose', action='store_true',
                                  help='Enable verbose output')
        create_parser.add_argument('-h', '--help', action='store_true',
                                  help='Show help for create command')
        create_parser.add_argument('--examples', action='store_true',
                                  help='Show usage examples')

        # case run
        run_parser = case_subparsers.add_parser('run', add_help=False,
                                               help='Submit and monitor SLURM jobs')
        case_arg(run_parser, help='Case directory path')
        run_parser.add_argument('--no-monitor', action='store_true',
                               help='Submit jobs without monitoring')
        run_parser.add_argument('--clean', action='store_true',
                               help='Clean start (remove existing OTHD files)')
        run_parser.add_argument('--from-step', type=int,
                               help='Restart from specific timestep')
        run_parser.add_argument('--dry-run', action='store_true',
                               help='Show what would be done without submitting jobs')
        run_parser.add_argument('-v', '--verbose', action='store_true',
                               help='Enable verbose output')
        run_parser.add_argument('-h', '--help', action='store_true',
                               help='Show help for run command')
        run_parser.add_argument('--examples', action='store_true',
                               help='Show usage examples')

        # case organise
        organise_parser = case_subparsers.add_parser('organise', add_help=False,
                                                     help='Organize and clean up case directory')
        organise_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for organise command')
        organise_parser.add_argument('--examples', action='store_true',
                                    help='Show usage examples')
        organise_subparsers = organise_parser.add_subparsers(dest='organise_subcommand',
                                                             help='Organise subcommands')

        # case organise history
        history_parser = organise_subparsers.add_parser('history', add_help=False,
                                    help='OTHD/OISD history: archive/ → cleaned/ → compiled file')
        case_arg(history_parser, help='Case directory path')
        history_parser.add_argument('--update', action='store_true',
                                    help='Move .othd/.oisd from the run dir into {othd,oisd}_files/archive/ (.rcv to rcv_files/)')
        history_parser.add_argument('--clean', action='store_true',
                                    help='Write cleaned/: each run without the steps a later run redid')
        history_parser.add_argument('--compile', action='store_true',
                                    help='Join cleaned/ into {othd,oisd}_files/{problem}.othd|oisd')
        history_parser.add_argument('--verify', action='store_true',
                                    help='Check archive/, cleaned/ and the compiled file, and for missing tsIds')
        history_parser.add_argument('--prune', action='store_true',
                                    help='Delete archive/ once cleaned/ checks out and is up to date')
        time_window(history_parser,
                    t1_kwargs=dict(metavar='STEP', help='Only --update files reaching timesteps >= STEP'),
                    t2_kwargs=dict(metavar='STEP', help='Only --update files reaching timesteps <= STEP'))
        history_parser.add_argument('--log', action='store_true',
                                    help='Create log file of deletions')
        history_parser.add_argument('--no-confirm', action='store_true',
                                    help='Skip confirmation prompts')
        history_parser.add_argument('--dry-run', action='store_true',
                                    help='Show what would be done without changing anything')
        history_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        history_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for history command')
        history_parser.add_argument('--examples', action='store_true',
                                    help='Show usage examples')

        # case organise output
        output_parser = organise_subparsers.add_parser('output', add_help=False,
                                    help='Remove intermediate .out/.rst files from run dir')
        case_arg(output_parser, help='Case directory path')
        output_parser.add_argument('--keep-freq', type=int, metavar='N',
                                    help='Keep the .rst of steps divisible by N (default: 10 * freq); .out go once their step has a .plt')
        output_parser.add_argument('--all-out', action='store_true',
                                    help='Delete every .out in range, even steps with no .plt '
                                         '(their field data is then gone for good)')
        time_window(output_parser, 
                    t1_kwargs=dict(metavar='STEP', help='Only target timesteps >= STEP'),
                    t2_kwargs=dict(metavar='STEP', help='Only target timesteps <= STEP'))
        output_parser.add_argument('--log', action='store_true',
                                    help='Create log file of deletions')
        output_parser.add_argument('--no-confirm', action='store_true',
                                    help='Skip confirmation prompts')
        output_parser.add_argument('--dry-run', action='store_true',
                                    help='Show what would be deleted without deleting anything')
        output_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        output_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for output command')
        output_parser.add_argument('--examples', action='store_true',
                                    help='Show usage examples')

        # case organise plt
        plt_parser = organise_subparsers.add_parser('plt', add_help=False,
                                    help='Delete PLT files in the run dir and/or binary/')
        case_arg(plt_parser, help='Case directory path')
        plt_parser.add_argument('--delete-ascii', action='store_true',
                                    help='Delete PLT files from run dir where binary/ has a newer copy')
        plt_parser.add_argument('--delete-binary', action='store_true',
                                    help='Delete PLT files from binary/ within --t1/--t2 '
                                         '(unconditional; omitting both deletes all)')
        # Plain flags, not the `freq` context: they choose what --delete-binary removes.
        plt_parser.add_argument('--freq', type=int, metavar='N',
                                    help='With --delete-binary: only the steps divisible by N')
        plt_parser.add_argument('--keep-freq', type=int, metavar='N',
                                    help='With --delete-binary: keep the steps divisible by N')
        time_window(plt_parser, 
                    t1_kwargs=dict(metavar='STEP', help='Only target timesteps >= STEP'),
                    t2_kwargs=dict(metavar='STEP', help='Only target timesteps <= STEP'))
        plt_parser.add_argument('--log', action='store_true',
                                    help='Create log file of deletions')
        plt_parser.add_argument('--no-confirm', action='store_true',
                                    help='Skip confirmation prompts')
        plt_parser.add_argument('--dry-run', action='store_true',
                                    help='Show what would be deleted without deleting anything')
        plt_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        plt_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for plt command')
        plt_parser.add_argument('--examples', action='store_true',
                                    help='Show usage examples')

        # case organise vtu
        vtu_parser = organise_subparsers.add_parser('vtu', add_help=False,
                                    help='List or delete the .vtu caches field render keeps in binary/')
        case_arg(vtu_parser, help='Case directory path')
        vtu_parser.add_argument('--clean', action='store_true',
                                    help='Delete them (within --t1/--t2); without it they are only listed')
        time_window(vtu_parser,
                    t1_kwargs=dict(metavar='STEP', help='Only target timesteps >= STEP'),
                    t2_kwargs=dict(metavar='STEP', help='Only target timesteps <= STEP'))
        vtu_parser.add_argument('--log', action='store_true',
                                    help='Create log file of deletions')
        vtu_parser.add_argument('--no-confirm', action='store_true',
                                    help='Skip confirmation prompts')
        vtu_parser.add_argument('--dry-run', action='store_true',
                                    help='Show what would be deleted without deleting anything')
        vtu_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        vtu_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for vtu command')
        vtu_parser.add_argument('--examples', action='store_true',
                                    help='Show usage examples')

        # case check
        check_parser = case_subparsers.add_parser('check', add_help=False,
                                                  help='Inspect OTHD/OISD ranges and validate config')
        check_parser.add_argument('-h', '--help', action='store_true',
                                  help='Show help for check command')
        check_subparsers = check_parser.add_subparsers(dest='check_subcommand',
                                                        help='Check subcommands')

        # case check run
        run_check_parser = check_subparsers.add_parser('run', add_help=False,
                                    help='Check .othd/.oisd in the active run directory')
        case_arg(run_check_parser, help='Case directory path')
        run_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        run_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for run command')

        # case check history
        history_check_parser = check_subparsers.add_parser('history', add_help=False,
                                    help='Show the time step range of every OTHD/OISD history file')
        case_arg(history_check_parser, help='Case directory path')
        history_check_parser.add_argument('--archive', action='store_true',
                                    help='Show only archive/ (combinable; none shows every group)')
        history_check_parser.add_argument('--cleaned', action='store_true',
                                    help='Show only cleaned/ (combinable)')
        history_check_parser.add_argument('--compiled', action='store_true',
                                    help='Show only the compiled file (combinable)')
        history_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        history_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for history command')

        # case check config
        config_check_parser = check_subparsers.add_parser('config', add_help=False,
                                    help='Validate simflow.config consistency')
        case_arg(config_check_parser, help='Case directory path')
        config_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        config_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for config command')

        # case check plt
        plt_check_parser = check_subparsers.add_parser('plt', add_help=False,
                                    help='Check PLT files in binary/ and run dir against expected set')
        case_arg(plt_check_parser, help='Case directory path')
        freq_arg(plt_check_parser, metavar='N',
                 help='PLT output frequency to check against, '
                      'overriding outFreq from simflow.config')
        time_window(plt_check_parser, 
                    t1_kwargs=dict(metavar='STEP', help='Only check timesteps >= STEP'),
                    t2_kwargs=dict(metavar='STEP', help='Only check timesteps <= STEP'))
        plt_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        plt_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for plt command')

        # case check def
        def_check_parser = check_subparsers.add_parser('def', add_help=False,
                                    help='Check that all File() references in the .def file exist')
        case_arg(def_check_parser, help='Case directory path')
        def_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        def_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for def command')

        # case check out
        out_check_parser = check_subparsers.add_parser('out', add_help=False,
                                    help='List timesteps for which .out/.rst files are present in the run directory')
        case_arg(out_check_parser, help='Case directory path')
        out_check_parser.add_argument('--t1', type=float, metavar='STEP',
                                    help='Only check timesteps >= STEP')
        out_check_parser.add_argument('--t2', type=float, metavar='STEP',
                                    help='Only check timesteps <= STEP')
        # A plain flag, not the `freq` context: that is the PLT frequency, and
        # the .out/.rst files need not be written as often.
        out_check_parser.add_argument('--freq', type=int, metavar='N',
                                    help='Expect a step every N timesteps and list the ones '
                                         'with neither .out nor .rst')
        out_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        out_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for out command')

        # case check data (was `case status`)
        data_check_parser = check_subparsers.add_parser('data', add_help=False,
                                    help='Check case data file completeness (was: case status)')
        case_arg(data_check_parser, help='Case directory path')
        data_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        data_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for data command')

        # case check all
        all_check_parser = check_subparsers.add_parser('all', add_help=False,
                                    help='Run every check (run + history + config + plt + def + out)')
        case_arg(all_check_parser, help='Case directory path')
        freq_arg(all_check_parser, metavar='N',
                 help='PLT output frequency to check against, '
                      'overriding outFreq from simflow.config')
        all_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        all_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for all command')

        # case status [update] [case]
        status_parser = case_subparsers.add_parser('status', add_help=False,
                                                   help="The case's notes (.casestatus.md) and where it is")
        status_parser.add_argument('what', nargs='?', metavar='update|case',
                                   help="'update' to change the notes, else the case"
                                   ).completer = _status_words
        case_arg(status_parser, resolve=_status_case, help='Case directory path')
        status_parser.add_argument('-m', '--message', metavar='TEXT',
                                   help='update: add a timestamped line to the log')
        status_parser.add_argument('--state', choices=STATUS_STATES,
                                   help='update: set the state (logged too)')
        status_parser.add_argument('--no-create', action='store_true',
                                   help='Do not write .casestatus.md if it is not there')
        status_parser.add_argument('-h', '--help', action='store_true',
                                  help='Show help for status command')

        # case add
        add_parser = case_subparsers.add_parser('add', add_help=False,
                                                help='Scan a directory and build the .cases registry')
        add_parser.add_argument('--dir', type=str, metavar='PATH',
                               help='Directory to scan (default: current directory)')
        add_parser.add_argument('-h', '--help', action='store_true',
                               help='Show help for add command')

        # case out
        write_parser = case_subparsers.add_parser('out', add_help=False,
                                                  help='Inspect a case\'s declared outputs and map them')
        case_arg(write_parser, help='Case directory path')
        write_parser.add_argument('--list', action='store_true',
                                  help='Table of the outputTimeHistory blocks: name, input '
                                       'file, predicted othId, type, map file and probe')
        write_parser.add_argument('--map', dest='map', nargs='?',
                                  const=True, default=False, metavar='NAME',
                                  help='Write a map per outputTimeHistory block (a node '
                                       'map) and outputSurface block (its mesh); NAME '
                                       'selects one by block or node/point/surface-set name')
        # Validated in the command, not with choices=: argparse's rejection surfaces
        # here as "Unknown subcommand", which points at the wrong thing entirely.
        write_parser.add_argument('--probe-type', dest='probe_type', type=str,
                                  metavar='TYPE',
                                  help='Declare how the probe set should be read: '
                                       'point, line, helix, surface or cloud. Recorded '
                                       'in the map; it cannot be derived from the '
                                       'coordinates')
        write_parser.add_argument('--closed', action='store_true',
                                  help='With --probe-type line or helix: the curve '
                                       'joins up (a ring), which needs different '
                                       'arc-length handling from an open curve')
        write_parser.add_argument('-v', '--verbose', action='store_true',
                                  help='Enable verbose output')
        write_parser.add_argument('-h', '--help', action='store_true',
                                  help='Show help for write command')

        # case domain
        # `body`/`field` and the case share the two positional slots and are told
        # apart in the command, not here: making them a sub-parser would make
        # `case domain <case> --init` an "invalid choice" error naming the case.
        domain_parser = case_subparsers.add_parser(
            'domain', add_help=False,
            help="Declare what the case's domain is made of, in domain.yml")
        domain_parser.add_argument('target', nargs='?', metavar='TARGET',
                                   help='body or field; omit for a summary of both'
                                   ).completer = described(
            ('body', 'Bodies in the domain'), ('field', 'The continuum they sit in'))
        domain_parser.add_argument('case', nargs='?', help='Case directory path')
        domain_parser.add_argument('--init', action='store_true',
                                   help='Write domain.yml from the case .def and PLT zones')
        domain_parser.add_argument('--check', action='store_true',
                                   help='Check every name, tag and type against the '
                                        'case files')
        domain_parser.add_argument('--path', action='store_true',
                                   help="Print domain.yml's path and stop")
        domain_parser.add_argument('--list', action='store_true',
                                   help='Table of what is declared')
        domain_parser.add_argument('--show', nargs='?', const=True, default=None,
                                   metavar='NAME',
                                   help='One entry in full, with its geometry files')
        domain_parser.add_argument('--add', action='store_true',
                                   help='Declare a new body or field (needs --name, --type)')
        domain_parser.add_argument('--remove', type=str, metavar='NAME',
                                   help='Remove a body')
        domain_parser.add_argument('--name', type=str, metavar='NAME',
                                   help='Which body to edit, or the name for a new one')
        domain_parser.add_argument('--set', action='append', metavar='KEY=VALUE',
                                   help='Set any key; repeatable, dotted keys reach '
                                        'inside (geometry.radius=0.5)')
        domain_parser.add_argument('--type', dest='type', type=str, metavar='TYPE',
                                   help='beam, rigid or fixed for a body; fluid for '
                                        'the field')
        domain_parser.add_argument('--geotag', type=str, metavar='TAG',
                                   help='Token in the geometry file names (riser.<TAG>.srf)')
        domain_parser.add_argument('--plttag', type=str, metavar='TAG',
                                   help='Zone name inside a .plt')
        domain_parser.add_argument('--velocity', type=str, metavar='X,Y,Z',
                                   help='Field only: the free-stream velocity '
                                        '(direction and magnitude)')
        domain_parser.add_argument('--radius', type=str, metavar='R',
                                   help='Body radius (= --set geometry.radius=R)')
        domain_parser.add_argument('--length', type=str, metavar='L',
                                   help='Body length (= --set geometry.length=L)')
        domain_parser.add_argument('--origin', type=str, metavar='X,Y,Z',
                                   help='Body origin (= --set geometry.origin=[X,Y,Z])')
        domain_parser.add_argument('--axis', type=str, metavar='AXIS',
                                   help="Body axis: +x -x +y -y +z -z, or '[1, 0, 0]'")
        domain_parser.add_argument('--force', action='store_true',
                                   help='With --init: derive again over an existing file')
        domain_parser.add_argument('-v', '--verbose', action='store_true',
                                   help='Enable verbose output')
        domain_parser.add_argument('-h', '--help', action='store_true',
                                   help='Show help for domain command')

        # case report
        report_parser = case_subparsers.add_parser('report', add_help=False,
                                                   help='Print a compact status table for all registered cases')
        report_parser.add_argument('--dir', type=str, metavar='PATH',
                                  help='Directory containing .cases file (default: current directory)')
        report_parser.add_argument('--run', action='store_true',
                                  help='Add column with last timestep from run directory')
        report_parser.add_argument('--size', action='store_true',
                                  help='Add column with total disk usage of each case')
        report_parser.add_argument('--update', action='store_true',
                                  help='Recompute everything instead of reading .case_report')
        report_parser.add_argument('-h', '--help', action='store_true',
                                  help='Show help for report command')

        # case upload
        upload_parser = case_subparsers.add_parser('upload', add_help=False,
                                                   help='Upload case directories from local to remote server')
        _transfer_positionals(upload_parser, 'upload')
        upload_parser.add_argument('--dir', type=str, metavar='DIRS',
                                  help='Directories to upload (comma-separated, default: othd_files,oisd_files,binary)')
        upload_parser.add_argument('--files', nargs='?', const=True, default=None,
                                  metavar='PATTERNS',
                                  help='Also upload loose files from the case root '
                                       '(comma-separated globs; default: '
                                       'simflow.config,*.def,*.geo,*.map). Given without '
                                       '--dir it uploads only those files')
        context_flag(upload_parser, 'remote', '--to', type=str, metavar='REMOTE',
                     help='Remote machine name (or use context with "use remote:name")')
        upload_parser.add_argument('--remote-path', type=str, metavar='PATH',
                                  help='Override remote base path (default: use remote config)')
        time_window(upload_parser, when=_stepped,
                    t1_kwargs=dict(metavar='STEP', help='binary/rst: first timestep to upload (alone: only that step)'),
                    t2_kwargs=dict(metavar='STEP', help='binary/rst: last timestep to upload'))
        upload_parser.add_argument('--force', action='store_true',
                                  help='Create remote directories if they do not exist')
        upload_parser.add_argument('--resume', action='store_true',
                                  help='Resume the last interrupted transfer')
        upload_parser.add_argument('-h', '--help', action='store_true',
                                  help='Show help for upload command')
        upload_parser.add_argument('--examples', action='store_true',
                                  help='Show usage examples')

        # case download
        download_parser = case_subparsers.add_parser('download', add_help=False,
                                                     help='Download case directories from remote to local')
        _transfer_positionals(download_parser, 'download')
        download_parser.add_argument('--dir', type=str, metavar='DIRS',
                                    help='Directories to download (comma-separated, default: othd_files,oisd_files,binary)')
        download_parser.add_argument('--files', nargs='?', const=True, default=None,
                                    metavar='PATTERNS',
                                    help='Also download loose files from the remote case root '
                                         '(comma-separated globs; default: '
                                         'simflow.config,*.def,*.geo,*.map). Given without '
                                         '--dir it downloads only those files')
        context_flag(download_parser, 'remote', '--from', dest='from_remote', type=str,
                     metavar='REMOTE',
                     help='Remote machine name (or use context with "use remote:name")')
        download_parser.add_argument('--remote-path', type=str, metavar='PATH',
                                    help='Override remote base path (default: use remote config)')
        time_window(download_parser, when=_stepped,
                    t1_kwargs=dict(metavar='STEP', help='binary/rst: first timestep to download (alone: only that step)'),
                    t2_kwargs=dict(metavar='STEP', help='binary/rst: last timestep to download'))
        freq_arg(download_parser, metavar='N',
                 resolve=lambda store, ns: (store.get('freq') if _mode(ns) == 'binary'
                                            and store.is_set('freq') else None),
                 help='binary: only the timesteps that are multiples of N')
        download_parser.add_argument('--force', action='store_true',
                                    help='Create the local case directory if it does not exist')
        download_parser.add_argument('--resume', action='store_true',
                                    help='Resume the last interrupted transfer')
        download_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for download command')
        download_parser.add_argument('--examples', action='store_true',
                                    help='Show usage examples')

        file_flags(create_parser, {'--ref-case': (), '--from-config': ('.yml', '.yaml')})

        # Main case help flags
        parser.add_argument('-h', '--help', action='store_true',
                           help='Show help for case command')

        return parser

    def execute(self, args):
        """Execute case command"""
        if hasattr(args, 'case_subcommand') and args.case_subcommand == 'show':
            # Delegate to show subcommand
            from .show_impl import command as show_cmd
            show_cmd.execute_info(args)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'create':
            # Delegate to create subcommand
            from .create_impl import command as create_cmd
            create_cmd.execute_new(args)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'run':
            # Delegate to run subcommand
            from .run import execute_case_run
            execute_case_run(args)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'organise':
            # Delegate to organise subcommand
            from .organise_impl import command as organise_cmd
            organise_cmd.execute_organise(args)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'check':
            from .check_impl.command import execute_case_check
            execute_case_check(args)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'status':
            from .status_impl import execute_status
            code = execute_status(args)
            if code:
                sys.exit(code)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'add':
            from .add_impl import execute_add
            execute_add(args)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'out':
            from .out_impl.command import execute_out
            execute_out(args)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'domain':
            from .domain_impl import execute_domain
            execute_domain(args)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'report':
            from .report_impl import execute_report
            execute_report(args)
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'upload':
            from .download_impl.command import execute_upload
            sys.exit(execute_upload(args))
        elif hasattr(args, 'case_subcommand') and args.case_subcommand == 'download':
            from .download_impl.command import execute_download
            sys.exit(execute_download(args))
        else:
            # Show help for case group
            self.show_help()

    def show_help(self):
        """Show help message"""
        from rich.console import Console
        from rich.table import Table
        from rich import box

        console = Console()
        console.print()
        console.print("[bold cyan]FlexFlow Case Command[/bold cyan]")
        console.print()
        console.print("Manage FlexFlow simulation cases.")
        console.print()
        console.print("[bold]USAGE:[/bold]")
        console.print("    flexflow case <subcommand> [options]")
        console.print()

        # Create subcommands table
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("Subcommand", style="cyan")
        table.add_column("Description", style="white")

        table.add_row("show", "Display case information (was: info)")
        table.add_row("create", "Create new case from template (was: new)")
        table.add_row("run", "Submit and monitor SLURM simulation jobs")
        table.add_row("organise", "Organize and clean up case directory")
        table.add_row("check", "Inspect OTHD/OISD ranges and validate config")
        table.add_row("status", "The case's notes (.casestatus.md) and where it is")
        table.add_row("out", "Inspect a case's declared outputs and write othd node maps")
        table.add_row("domain", "Declare the field and bodies the domain is made of")
        table.add_row("add", "Scan a directory and build the .cases registry")
        table.add_row("report", "Print a compact status table for all registered cases")
        table.add_row("upload", "Upload case directories from local to remote server")
        table.add_row("download", "Download case directories from remote server to local")

        console.print("[bold]SUBCOMMANDS:[/bold]")
        console.print(table)
        console.print()
        console.print("[bold]EXAMPLES:[/bold]")
        console.print("    flexflow case show CS4SG1U1")
        console.print("    flexflow case create myCase --problem-name test")
        console.print("    flexflow case run CS4SG1U1")
        console.print("    flexflow case run CS4SG1U1 --no-monitor")
        console.print("    flexflow case organise history CS4SG1U1 --update")
        console.print("    flexflow case organise history CS4SG1U1 --clean --compile --verify")
        console.print("    flexflow case organise output CS4SG1U1")
        console.print("    flexflow case organise plt CS4SG1U1 --delete-ascii")
        console.print("    flexflow case organise plt CS4SG1U1 --delete-binary --t1 0 --t2 1000")
        console.print("    flexflow case organise vtu CS4SG1U1 --clean")
        console.print("    flexflow case check run CS4SG1U1")
        console.print("    flexflow case check plt CS4SG1U1 --t1 0 --t2 1000")
        console.print("    flexflow case check out CS4SG1U1")
        console.print("    flexflow case check all CS4SG1U1")
        console.print("    flexflow case status CS4SG1U1")
        console.print("    flexflow case status update CS4SG1U1 -m \"resubmitted with np 240\"")
        console.print("    flexflow case check data CS4SG1U1")
        console.print("    flexflow case domain CS4SG1U1 --init")
        console.print("    flexflow case domain body --list")
        console.print("    flexflow case domain body --add --name cyl --type beam")
        console.print("    flexflow case add --dir /scratch/me/project")
        console.print("    flexflow case report")
        console.print("    flexflow case upload ./myCase --to remote-server")
        console.print("    flexflow case upload ./myCase --to remote-server --dir othd_files,oisd_files")
        console.print("    flexflow case upload ./myCase --to remote-server --dir othd_files --force")
        console.print("    flexflow case upload ./myCase --to remote-server --resume")
        console.print("    flexflow case download ./myCase --from remote-server")
        console.print("    flexflow case download ./myCase --from remote-server --dir othd_files,oisd_files")
        console.print("    flexflow case download ./myCase --from remote-server --force")
        console.print("    flexflow case download ./myCase --from remote-server --resume")
        console.print()


# Create command instance
command = CaseCommand()
