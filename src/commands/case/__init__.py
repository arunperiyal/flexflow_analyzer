"""
Case command group - Manages simulation cases
Subcommands: show, create, run, domain, ...
"""

import argparse
import sys
from ..base import BaseCommand
from src.cli.completers import described, file_flags
from src.cli.context import case_arg, case_flag, context_flag, freq_arg, no_words, time_window
from .common_flags import organise_flags


# `case upload|download [plt|rst|input|history] [case]`: what to carry. Nothing named is
# the directories (--dir) and files (--files) as before.
TRANSFER_MODES = {
    'upload': [('plt', 'The binary PLTs in binary/: every timestep, or just --t1..--t2'),
               ('rst', 'Restart .rst files of every step (or --t1..--t2) in the run directory'),
               ('input', 'The <problem>.def and every File(...) it names (mesh, .nbc, .srf ...)'),
               ('history', 'OTHD/OISD history: archive/, cleaned/, the compiled file (or --archive/--cleaned/--compiled)')],
    'download': [('plt', 'The binary PLTs in binary/: every timestep, or just --t1..--t2 (--freq)'),
                 ('rst', 'Restart .rst files of every step (or --t1..--t2) from the remote run directory'),
                 ('input', 'The remote <problem>.def and every File(...) it names'),
                 ('history', 'The remote OTHD/OISD history (or --archive/--cleaned/--compiled)')],
}


def _mode(args):
    """binary/rst/input/history, or None when the first word is a case (or absent)."""
    what = getattr(args, 'what', None)
    if what == 'plt':
        return 'binary'             # `plt` is the word; `binary` is its old name and the folder
    return what if what in ('binary', 'rst', 'input', 'history') else None


def _stepped(args):
    """The t1/t2/time/freq contexts select timesteps, so they only apply to
    binary/rst (the input files are not per step)."""
    return _mode(args) in ('binary', 'rst')


def _transfer_positionals(parser, direction):
    modes = TRANSFER_MODES[direction]

    def complete(rt, prefix):
        return modes
    parser.add_argument('what', nargs='?', metavar='|'.join(m for m, _ in modes),
                        help='What to carry: ' + '; '.join(f"{m}: {h}" for m, h in modes)
                        ).completer = complete
    case_flag(parser, help=('The local case directory (default: use case:)' if direction == 'upload'
                            else 'The local case directory, the destination (default: use case:)'))
    no_words(parser)
    for name, where in (('archive', 'archive/'), ('cleaned', 'cleaned/'),
                        ('compiled', 'the compiled file')):
        parser.add_argument(f'--{name}', action='store_true',
                            help=f'history: only {where} (combinable; none carries all three)')
    if direction == 'upload':
        parser.add_argument('--live', action='store_true',
                            help="history: the run directory's .othd/.oisd as they are now, "
                                 "while a job is still writing them (a snapshot, not checked)")
    parser.add_argument('--missing', action='store_true',
                        help='binary/rst: only the files the other side lacks (or holds at another size)')
    parser.add_argument('--fit', action='store_true',
                        help='binary: send only the steps that fit in the time the session '
                             'has left (at set transfer_speed)')
    parser.add_argument('--no-time-check', action='store_true',
                        help='binary: do not set the transfer against the session timeout')
    # The old spelling, kept only to point at the new one.
    parser.add_argument('--binary', action='store_true', help=argparse.SUPPRESS)


STATUS_STATES = ('new', 'meshing', 'running', 'stopped', 'done', 'failed', 'archived')


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
        case_flag(show_parser)
        no_words(show_parser)
        show_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose output')
        show_parser.add_argument('-h', '--help', action='store_true',
                                help='Show help for show command')

        # case create (was: new)
        create_parser = case_subparsers.add_parser('create', add_help=False,
                                                   help='Create new case')
        create_parser.add_argument('--name', dest='case_name', type=str, metavar='NAME',
                                   help='Name of the new case')
        no_words(create_parser, '--name')
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

        # case run
        run_parser = case_subparsers.add_parser('run', add_help=False,
                                               help='Submit and monitor SLURM jobs')
        case_flag(run_parser)
        no_words(run_parser)
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

        # case organise
        organise_parser = case_subparsers.add_parser('organise', add_help=False, allow_abbrev=False,
                                                     help='Organize and clean up case directory')
        organise_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for organise command')
        organise_subparsers = organise_parser.add_subparsers(dest='organise_subcommand',
                                                             help='Organise subcommands')

        # case organise history
        history_parser = organise_subparsers.add_parser('history', add_help=False, allow_abbrev=False,
                                    help='OTHD/OISD history: archive/ → cleaned/ → compiled file')
        case_flag(history_parser)
        history_actions = history_parser.add_argument(
            'actions', nargs='*', metavar='ACTION',
            help='What to do, in this order: update (move .othd/.oisd from the run dir into '
                 'archive/, .rcv to rcv_files/), clean [RUNS] (write cleaned/: each run without '
                 'the steps a later run redid; RUNS, e.g. 1,2,3 or 1-3, cleans only those archive '
                 'runs), compile (join cleaned/ into the {problem}.othd|oisd), verify (check '
                 'archive/, cleaned/, the compiled file and missing tsIds), prune (delete '
                 'archive/ once cleaned/ checks out)')
        history_actions.completer = described(
            ('update', 'Move the run dir history into archive/'),
            ('clean', 'Write cleaned/ (RUNS: 1,2,3 or 1-3)'),
            ('compile', 'Join cleaned/ into one file'),
            ('verify', 'Check archive/, cleaned/, the compiled file'),
            ('prune', 'Delete archive/ once cleaned/ checks out'))
        time_window(history_parser,
                    t1_kwargs=dict(metavar='STEP', help='update: only files reaching timesteps >= STEP'),
                    t2_kwargs=dict(metavar='STEP', help='update: only files reaching timesteps <= STEP'))
        organise_flags(history_parser, 'history')

        # case organise out / case organise rst
        for word, what in (('out', '.out files (kept until a PLT stands in for them)'),
                           ('rst', '.rst restart sets (thinned to --keep-freq, the newest kept)')):
            sub = organise_subparsers.add_parser(word, add_help=False, allow_abbrev=False,
                                                 help=f'Delete {what} from the run dir')
            case_flag(sub)
            no_words(sub)
            if word == 'rst':
                sub.add_argument('--keep-freq', type=int, metavar='N',
                                 help='Keep the .rst of steps divisible by N (default: 10 * freq)')
                sub.add_argument('--keep-newest', type=int, metavar='N', default=2,
                                 help='Also keep the N newest complete .rst sets, whatever '
                                      '--keep-freq says (default: 2; 1 keeps only the newest)')
            else:
                context_flag(sub, 'remote', '--remote', type=str, metavar='REMOTE',
                             help='The remote to ask for a verified copy of a binary PLT that '
                                  'is no longer in binary/ (or use context with "use remote:name")')
            time_window(sub,
                        t1_kwargs=dict(metavar='STEP', help='Only target timesteps >= STEP'),
                        t2_kwargs=dict(metavar='STEP', help='Only target timesteps <= STEP'))
            if word == 'out':
                sub.add_argument('--no-verify', action='store_true',
                                 help='Delete every .out in --t1/--t2 without a PLT standing in '
                                      'for it (steps with no PLT lose their field data)')
            organise_flags(sub, 'out/rst')

        # case organise plt
        plt_parser = organise_subparsers.add_parser('plt', add_help=False, allow_abbrev=False,
                                    help='Delete PLT files in the run dir and/or binary/')
        case_flag(plt_parser)
        plt_actions = plt_parser.add_argument(
            'actions', nargs='*', metavar='ACTION',
            help='ascii: delete the ASCII PLT files of the run dir whose binary PLT is whole and '
                 'newer (or verified on the remote); binary: delete the PLT files of binary/ that '
                 'have a copy on the remote with the same md5')
        plt_actions.completer = described(
            ('ascii', 'Delete the run dir ASCII PLTs a whole binary PLT stands in for'),
            ('binary', 'Delete the binary/ PLTs that have a verified copy on the remote'))
        context_flag(plt_parser, 'remote', '--remote', type=str, metavar='REMOTE',
                     help='The remote holding the copies (default: the only one in '
                          '.cases.yml; or use context with "use remote:name")')
        # Plain flags, not the `freq` context: they choose which steps are looked at.
        plt_parser.add_argument('--freq', type=int, metavar='N',
                                    help='Only the steps divisible by N')
        plt_parser.add_argument('--keep-freq', type=int, metavar='N',
                                    help='With binary: keep the steps divisible by N')
        time_window(plt_parser, 
                    t1_kwargs=dict(metavar='STEP', help='Only target timesteps >= STEP'),
                    t2_kwargs=dict(metavar='STEP', help='Only target timesteps <= STEP'))
        plt_parser.add_argument('--no-verify', action='store_true',
                                    help='With binary: do not ask the remote; delete the '
                                         'whole PLT files here (they may have no copy there)')
        organise_flags(plt_parser, 'plt')

        # case organise vtu
        vtu_parser = organise_subparsers.add_parser('vtu', add_help=False, allow_abbrev=False,
                                    help='Delete the .vtu caches field render keeps in binary/')
        case_flag(vtu_parser)
        no_words(vtu_parser)
        vtu_parser.add_argument('--leftovers', action='store_true',
                                    help='Only the .partial/.deriving files a killed render left')
        vtu_parser.add_argument('--orphans', action='store_true',
                                    help='Also the .vtu whose .plt is gone (it cannot be rebuilt)')
        vtu_parser.add_argument('--age-hours', type=float, default=None, metavar='N',
                                    help='Leave a file modified in the last N hours '
                                         '(a render may be writing it)')
        time_window(vtu_parser,
                    t1_kwargs=dict(metavar='STEP', help='Only target timesteps >= STEP'),
                    t2_kwargs=dict(metavar='STEP', help='Only target timesteps <= STEP'))
        organise_flags(vtu_parser, 'vtu')

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
        case_flag(run_check_parser)
        no_words(run_check_parser)
        run_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        run_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for run command')

        # case check history
        history_check_parser = check_subparsers.add_parser('history', add_help=False,
                                    help='Show the time step range of every OTHD/OISD history file')
        case_flag(history_check_parser)
        no_words(history_check_parser)
        history_check_parser.add_argument('--archive', action='store_true',
                                    help='Show only archive/ (combinable; none shows every group)')
        history_check_parser.add_argument('--cleaned', action='store_true',
                                    help='Show only cleaned/ (combinable)')
        history_check_parser.add_argument('--compiled', action='store_true',
                                    help='Show only the compiled file (combinable)')
        history_check_parser.add_argument('--remote', nargs='?', const='', default=None, metavar='NAME',
                         help='Also compare the history files with their copies on the remote, by size and md5 (NAME: else `use remote:`, else the only remote .cases.yml lists)')
        history_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        history_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for history command')

        # case check config
        config_check_parser = check_subparsers.add_parser('config', add_help=False,
                                    help='Validate simflow.config consistency')
        case_flag(config_check_parser)
        no_words(config_check_parser)
        config_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        config_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for config command')

        # case check plt
        plt_check_parser = check_subparsers.add_parser('plt', add_help=False,
                                    help='Check PLT files in binary/ and run dir against expected set')
        case_flag(plt_check_parser)
        no_words(plt_check_parser)
        freq_arg(plt_check_parser, metavar='N',
                 help='PLT output frequency to check against, '
                      'overriding outFreq from simflow.config')
        time_window(plt_check_parser, 
                    t1_kwargs=dict(metavar='STEP', help='Only check timesteps >= STEP'),
                    t2_kwargs=dict(metavar='STEP', help='Only check timesteps <= STEP'))
        # a plain option, not the `remote` context: its being given is what asks for the
        # comparison, so `use remote:` left over from earlier does not turn it on
        plt_check_parser.add_argument('--remote', nargs='?', const='', default=None,
                                      metavar='NAME',
                                      help='Also compare each PLT in binary/ with its copy on '
                                           'the remote, by size and md5 (NAME: else `use remote:`, '
                                           'else the only remote .cases.yml lists)')
        plt_check_parser.add_argument('--adopt', action='store_true',
                                      help='With --remote: record the PLTs that are only on the '
                                           'remote with no record, after reading their header '
                                           'there (nothing is downloaded)')
        plt_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        plt_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for plt command')

        # case check def
        def_check_parser = check_subparsers.add_parser('def', add_help=False,
                                    help='Check that all File() references in the .def file exist')
        case_flag(def_check_parser)
        no_words(def_check_parser)
        def_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        def_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for def command')

        # case check out
        out_check_parser = check_subparsers.add_parser('out', add_help=False,
                                    help='List timesteps for which .out/.rst files are present in the run directory')
        case_flag(out_check_parser)
        no_words(out_check_parser)
        out_check_parser.add_argument('--t1', type=float, metavar='STEP',
                                    help='Only check timesteps >= STEP')
        out_check_parser.add_argument('--t2', type=float, metavar='STEP',
                                    help='Only check timesteps <= STEP')
        # A plain flag, not the `freq` context: that is the PLT frequency, and
        # the .out/.rst files need not be written as often.
        out_check_parser.add_argument('--freq', type=int, metavar='N',
                                    help='Expect a step every N timesteps and list the ones '
                                         'with neither .out nor .rst')
        out_check_parser.add_argument('--remote', nargs='?', const='', default=None, metavar='NAME',
                         help='Also look for the PLT that stands in for each .out here or on the remote (NAME: else `use remote:`, else the only remote .cases.yml lists)')
        out_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        out_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for out command')

        # case check data (was `case status`)
        data_check_parser = check_subparsers.add_parser('data', add_help=False,
                                    help='Check case data file completeness (was: case status)')
        case_flag(data_check_parser)
        no_words(data_check_parser)
        data_check_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='Enable verbose output')
        data_check_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for data command')

        # case check all
        all_check_parser = check_subparsers.add_parser('all', add_help=False,
                                    help='Run every check (run + history + config + plt + def + out)')
        case_flag(all_check_parser)
        no_words(all_check_parser)
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
        status_parser.add_argument('what', nargs='?', metavar='update',
                                   help="'update' to change the notes; without it, show them"
                                   ).completer = described(
            ('update', 'Edit the notes, or -m TEXT / --state STATE'))
        case_flag(status_parser)
        no_words(status_parser)
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
                                                help='Scan a directory and build the .cases.yml registry')
        add_parser.add_argument('--dir', type=str, metavar='PATH',
                               help='Directory to scan (default: current directory)')
        add_parser.add_argument('-h', '--help', action='store_true',
                               help='Show help for add command')

        # case out
        write_parser = case_subparsers.add_parser('out', add_help=False,
                                                  help='Inspect a case\'s declared outputs and map them')
        case_flag(write_parser)
        no_words(write_parser)
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
        # `case domain --case <case> --init` an "invalid choice" error naming the case.
        domain_parser = case_subparsers.add_parser(
            'domain', add_help=False,
            help="Declare what the case's domain is made of, in domain.yml")
        domain_parser.add_argument('target', nargs='?', metavar='TARGET',
                                   help='body or field; omit for a summary of both'
                                   ).completer = described(
            ('body', 'Bodies in the domain'), ('field', 'The continuum they sit in'))
        case_flag(domain_parser)
        no_words(domain_parser)
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
                                  help='Directory containing .cases.yml file (default: current directory)')
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
        context_flag(upload_parser, 'remote', '--remote', dest='to', type=str, metavar='REMOTE',
                     help='Remote machine name (or use context with "use remote:name")')
        upload_parser.add_argument('--remote-path', type=str, metavar='PATH',
                                  help="The folder holding the cases on the remote (default: the remote's folder in "
                                       "the case folder's .cases.yml, else `remote set-path`)")
        time_window(upload_parser, when=_stepped,
                    t1_kwargs=dict(metavar='STEP', help='binary/rst: first timestep to upload (alone: only that step)'),
                    t2_kwargs=dict(metavar='STEP', help='binary/rst: last timestep to upload'))
        freq_arg(upload_parser, metavar='N',
                 resolve=lambda store, ns: (store.get('freq') if _mode(ns) in ('binary', 'rst')
                                            and store.is_set('freq') else None),
                 help='binary/rst: only the timesteps that are multiples of N')
        upload_parser.add_argument('--force', action='store_true',
                                  help='Create remote directories if they do not exist')
        upload_parser.add_argument('--resume', action='store_true',
                                  help='Resume the last interrupted transfer')
        upload_parser.add_argument('-h', '--help', action='store_true',
                                  help='Show help for upload command')

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
        context_flag(download_parser, 'remote', '--remote', dest='from_remote', type=str,
                     metavar='REMOTE',
                     help='Remote machine name (or use context with "use remote:name")')
        download_parser.add_argument('--remote-path', type=str, metavar='PATH',
                                    help="The folder holding the cases on the remote (default: the remote's folder in "
                                       "the case folder's .cases.yml, else `remote set-path`)")
        time_window(download_parser, when=_stepped,
                    t1_kwargs=dict(metavar='STEP', help='binary/rst: first timestep to download (alone: only that step)'),
                    t2_kwargs=dict(metavar='STEP', help='binary/rst: last timestep to download'))
        freq_arg(download_parser, metavar='N',
                 resolve=lambda store, ns: (store.get('freq') if _mode(ns) in ('binary', 'rst')
                                            and store.is_set('freq') else None),
                 help='binary/rst: only the timesteps that are multiples of N')
        download_parser.add_argument('--force', action='store_true',
                                    help='Create the local case directory if it does not exist')
        download_parser.add_argument('--resume', action='store_true',
                                    help='Resume the last interrupted transfer')
        download_parser.add_argument('-h', '--help', action='store_true',
                                    help='Show help for download command')

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
            code = execute_case_check(args)
            if code:
                sys.exit(code)
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
        console.print("    case <subcommand> [options]")
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
        table.add_row("add", "Scan a directory and build the .cases.yml registry")
        table.add_row("report", "Print a compact status table for all registered cases")
        table.add_row("upload", "Upload case directories from local to remote server")
        table.add_row("download", "Download case directories from remote server to local")

        console.print("[bold]SUBCOMMANDS:[/bold]")
        console.print(table)
        console.print()
        console.print("[bold]EXAMPLES:[/bold]")
        console.print("    case show --case CS4SG1U1")
        console.print("    case create myCase --problem-name test")
        console.print("    case run --case CS4SG1U1")
        console.print("    case run --case CS4SG1U1 --no-monitor")
        console.print("    case organise history update --case CS4SG1U1")
        console.print("    case organise history clean compile verify --case CS4SG1U1")
        console.print("    case organise out --case CS4SG1U1")
        console.print("    case organise rst --case CS4SG1U1")
        console.print("    case organise plt ascii --case CS4SG1U1")
        console.print("    case organise plt binary --case CS4SG1U1 --t1 0 --t2 1000")
        console.print("    case organise vtu --case CS4SG1U1")
        console.print("    case check run --case CS4SG1U1")
        console.print("    case check plt --case CS4SG1U1 --t1 0 --t2 1000")
        console.print("    case check out --case CS4SG1U1")
        console.print("    case check all --case CS4SG1U1")
        console.print("    case status --case CS4SG1U1")
        console.print("    case status update --case CS4SG1U1 -m \"resubmitted with np 240\"")
        console.print("    case check data --case CS4SG1U1")
        console.print("    case domain --case CS4SG1U1 --init")
        console.print("    case domain body --list")
        console.print("    case domain body --add --name cyl --type beam")
        console.print("    case add --dir /scratch/me/project")
        console.print("    case report")
        console.print("    case upload --case ./myCase --remote remote-server")
        console.print("    case upload --case ./myCase --remote remote-server --dir othd_files,oisd_files")
        console.print("    case upload --case ./myCase --remote remote-server --dir othd_files --force")
        console.print("    case upload --case ./myCase --remote remote-server --resume")
        console.print("    case download --case ./myCase --remote remote-server")
        console.print("    case download --case ./myCase --remote remote-server --dir othd_files,oisd_files")
        console.print("    case download --case ./myCase --remote remote-server --force")
        console.print("    case download --case ./myCase --remote remote-server --resume")
        console.print()


# Create command instance
command = CaseCommand()
