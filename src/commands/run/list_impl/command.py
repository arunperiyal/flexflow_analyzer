"""Execute run list log - the slurm-* files of a case, with the job type of each.

The type comes from the file itself: the job scripts are named pre<case>,
main<case> and post<case> (`#SBATCH -J`), which the job prints as
SLURM_JOB_NAME, and each script prints its own banner ("FlexFlow
Preprocessing Job", ...). A file that shows neither is `other`.
"""

import re
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.table import Table

JOB_TYPES = ('pre', 'main', 'post')
SORT_KEYS = ('time', 'type', 'jobid')

# How much of the start of a file to read for the job name / banner
HEAD_BYTES = 8192

_JOB_NAME = re.compile(r'^SLURM_JOB_NAME\s*=\s*(\S+)', re.MULTILINE)
_BANNERS = {
    'FlexFlow Preprocessing Job': 'pre',
    'FlexFlow Main Simulation Job': 'main',
    'FlexFlow Postprocessing Job': 'post',
}
_TYPE_STYLE = {'pre': 'cyan', 'main': 'green', 'post': 'magenta', 'other': 'dim'}


def execute_list(args):
    """Execute run list <what>."""
    if getattr(args, 'help', False) or not getattr(args, 'what', None):
        show_list_help()
        return
    if args.what == 'log':
        list_logs(args)


# ---------------------------------------------------------------------------
# Reading the files
# ---------------------------------------------------------------------------

def job_type(head: str):
    """(type, job name) from the start of a slurm file."""
    match = _JOB_NAME.search(head)
    name = match.group(1) if match else ''
    for prefix in JOB_TYPES:
        if name.startswith(prefix):
            return prefix, name
    for banner, kind in _BANNERS.items():
        if banner in head:
            return kind, name
    return 'other', name


def read_log(path: Path) -> dict:
    """What run list log shows of one slurm file."""
    match = re.match(r'slurm-(\d+)', path.name)
    try:
        with open(path, 'r', errors='replace') as f:
            head = f.read(HEAD_BYTES)
        stat = path.stat()
        mtime, size = stat.st_mtime, stat.st_size
    except OSError:
        head, mtime, size = '', 0.0, 0
    kind, name = job_type(head)
    return {'path': path, 'jobid': int(match.group(1)) if match else None,
            'type': kind, 'name': name, 'mtime': mtime, 'size': size}


def find_logs(case_dir: Path) -> list:
    return [read_log(p) for p in case_dir.glob('slurm-*') if p.is_file()]


def sort_logs(logs: list, key: str = 'time', reverse: bool = False) -> list:
    """Sort by time (modified), type (pre, main, post, other; then time) or jobid."""
    by_jobid = lambda log: (log['jobid'] is None, log['jobid'] or 0)
    if key == 'jobid':
        keyfn = by_jobid
    elif key == 'type':
        order = {kind: i for i, kind in enumerate(JOB_TYPES + ('other',))}
        keyfn = lambda log: (order[log['type']], log['mtime'], by_jobid(log))
    else:
        keyfn = lambda log: (log['mtime'], by_jobid(log))
    return sorted(logs, key=keyfn, reverse=reverse)


# ---------------------------------------------------------------------------
# run list log
# ---------------------------------------------------------------------------

def _case_dir(args):
    case = getattr(args, 'case', None)
    case_dir = Path(case) if case else Path.cwd()
    if not case_dir.is_dir():
        print(f"Error: Case directory not found: {case_dir}")
        return None
    return case_dir.resolve()


def _fmt_size(n: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f"{n} B" if unit == 'B' else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def list_logs(args):
    case_dir = _case_dir(args)
    if case_dir is None:
        return

    logs = find_logs(case_dir)
    kinds = getattr(args, 'type', None)
    if kinds:
        logs = [log for log in logs if log['type'] in kinds]

    console = Console()
    if not logs:
        which = f" of type {', '.join(kinds)}" if kinds else ''
        console.print(f"[yellow]No slurm-* files{which} in {escape(str(case_dir))}[/yellow]")
        return

    logs = sort_logs(logs, getattr(args, 'sort', None) or 'time',
                     getattr(args, 'reverse', False))

    table = Table(title=f"SLURM logs  ({escape(case_dir.name)})", box=None,
                  header_style='bold underline', padding=(0, 1), pad_edge=False)
    table.add_column('Job ID', style='cyan', justify='right', no_wrap=True)
    table.add_column('Type', no_wrap=True)
    table.add_column('Job name', no_wrap=True)
    table.add_column('Modified', no_wrap=True)
    table.add_column('Size', justify='right', no_wrap=True)
    table.add_column('File', style='dim', no_wrap=True)
    for log in logs:
        style = _TYPE_STYLE[log['type']]
        modified = (datetime.fromtimestamp(log['mtime']).strftime('%Y-%m-%d %H:%M')
                    if log['mtime'] else '?')
        table.add_row(str(log['jobid']) if log['jobid'] is not None else '?',
                      f"[{style}]{log['type']}[/{style}]",
                      escape(log['name']) or '[dim]—[/dim]',
                      modified, _fmt_size(log['size']), escape(log['path'].name))
    console.print(table)

    from shellkit.runtime import current_runtime
    rt = current_runtime()
    if rt is not None and rt.capturing:
        return      # a pipe gets the rows only: `| grep pre` should not match the summary
    counts = [f"{sum(log['type'] == kind for log in logs)} {kind}"
              for kind in JOB_TYPES + ('other',)
              if any(log['type'] == kind for log in logs)]
    console.print(f"  [dim]{len(logs)} file(s): {', '.join(counts)}[/dim]")


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

def show_list_help():
    from src.utils.colors import Colors
    print(f"""
{Colors.BOLD}{Colors.CYAN}run list{Colors.RESET} - List a case's job files

{Colors.BOLD}USAGE:{Colors.RESET}
    run list log [case_directory] [--sort time|type|jobid] [-r] [--type pre|main|post|other]

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Lists the slurm-* output files in the case directory (or the current
    directory, without a case or `use case`), with the job type of each:
    pre, main or post, read from the job name or banner in the file.
    Files from other scripts are listed as 'other'.

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--sort KEY{Colors.RESET}     time (default; by modification time),
                   type (pre, main, post, other; then time), or jobid
    {Colors.YELLOW}-r, --reverse{Colors.RESET}  Reverse the order (newest first with --sort time)
    {Colors.YELLOW}--type TYPE{Colors.RESET}    Only this job type; repeat for more
    {Colors.YELLOW}-h, --help{Colors.RESET}     Show this help

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    run list log Case001
    run list log --sort type
    run list log --type main -r
    run list log | grep post
""")
