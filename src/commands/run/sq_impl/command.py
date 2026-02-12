"""Execute run sq command - Show SLURM job queue status."""

import os
import re
import subprocess
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.live import Live


def execute_sq(args):
    """Execute run sq command to show SLURM job queue."""

    if hasattr(args, 'help') and args.help:
        show_sq_help()
        return

    if not check_slurm_available():
        print("Error: SLURM commands not available")
        print("Make sure you're on an HPC cluster with SLURM installed")
        return

    # Job detail mode: run sq <job_id>
    job_id = getattr(args, 'job_id', None)
    if job_id:
        show_job_detail(job_id)
        return

    if hasattr(args, 'watch') and args.watch:
        watch_queue(args)
    else:
        show_queue(args)


# ---------------------------------------------------------------------------
# SLURM availability
# ---------------------------------------------------------------------------

def check_slurm_available():
    """Check if SLURM commands are available."""
    try:
        result = subprocess.run(['which', 'squeue'], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Queue data fetch + parse
# ---------------------------------------------------------------------------

# squeue format fields (pipe-delimited to allow spaces in Reason)
_SQUEUE_FMT = '%i|%j|%T|%M|%D|%P|%C|%m|%V|%R'
_SQUEUE_COLS = ['jobid', 'name', 'state', 'time', 'nodes',
                'partition', 'cpus', 'memory', 'submit', 'reason']


def get_queue_data(show_all=False):
    """Run squeue and return raw stdout."""
    cmd = ['squeue', '--format', _SQUEUE_FMT, '--noheader']
    if not show_all:
        username = os.environ.get('USER', '')
        if username:
            cmd.extend(['-u', username])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return ''
    except Exception:
        return ''


def parse_queue_output(output: str) -> list:
    """Parse pipe-delimited squeue output into a list of dicts."""
    jobs = []
    for line in output.strip().splitlines():
        parts = line.split('|', len(_SQUEUE_COLS) - 1)
        if len(parts) == len(_SQUEUE_COLS):
            job = {k: v.strip() for k, v in zip(_SQUEUE_COLS, parts)}
            job['memory'] = _fmt_memory(job['memory'])
            job['submit'] = _fmt_submit_time(job['submit'])
            jobs.append(job)
    return jobs


def _fmt_memory(raw: str) -> str:
    """Convert squeue memory value (MB integer or suffix string) to readable form."""
    if not raw or raw in ('N/A', '0', '(null)'):
        return '—'
    # Already has suffix (e.g. '16G', '512M')
    if raw[-1].isalpha():
        return raw
    # Pure integer → MB
    try:
        mb = int(raw)
        if mb >= 1024:
            return f'{mb // 1024}G'
        return f'{mb}M'
    except ValueError:
        return raw


def _fmt_submit_time(raw: str) -> str:
    """Compact submit time: show HH:MM if today, else MM-DD HH:MM."""
    if not raw or raw in ('N/A', 'Unknown', '(null)'):
        return '—'
    # Format: 2024-01-15T10:00:00
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})', raw)
    if not m:
        return raw
    import datetime
    year, mon, day, hh, mm = (int(x) for x in m.groups())
    today = datetime.date.today()
    if (year, mon, day) == (today.year, today.month, today.day):
        return f'{hh:02d}:{mm:02d}'
    return f'{mon:02d}-{day:02d} {hh:02d}:{mm:02d}'


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------

def _state_markup(state: str) -> str:
    if state == 'RUNNING':
        return f'[bold green]{state}[/bold green]'
    if state == 'PENDING':
        return f'[bold yellow]{state}[/bold yellow]'
    if state in ('COMPLETED', 'COMPLETING'):
        return f'[bold blue]{state}[/bold blue]'
    if state in ('FAILED', 'CANCELLED', 'TIMEOUT'):
        return f'[bold red]{state}[/bold red]'
    return state


def create_queue_table(jobs: list) -> Table:
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style='bold cyan',
        title='SLURM Job Queue',
        title_style='bold magenta',
    )
    table.add_column('Job ID',    style='yellow',  justify='right', min_width=10)
    table.add_column('Name',      style='green',   min_width=12)
    table.add_column('State',     justify='center')
    table.add_column('Time',      style='blue',    justify='right')
    table.add_column('Nodes',     style='magenta', justify='right')
    table.add_column('Partition', style='cyan')
    table.add_column('CPUs',      style='white',   justify='right')
    table.add_column('Memory',    style='white',   justify='right')
    table.add_column('Submitted', style='dim')
    table.add_column('Reason',    style='dim')

    if not jobs:
        table.add_row('—', 'No jobs in queue', '—', '—', '—', '—', '—', '—', '—', '—')
        return table

    for job in jobs:
        table.add_row(
            job['jobid'],
            job['name'],
            _state_markup(job['state']),
            job['time'],
            job['nodes'],
            job['partition'],
            job['cpus'],
            job['memory'],
            job['submit'],
            job['reason'],
        )
    return table


# ---------------------------------------------------------------------------
# Queue display
# ---------------------------------------------------------------------------

def show_queue(args):
    console = Console()
    show_all = getattr(args, 'all', False)

    output = get_queue_data(show_all)
    jobs = parse_queue_output(output)

    console.print()
    console.print(create_queue_table(jobs))
    console.print()

    if jobs:
        running = sum(1 for j in jobs if j['state'] == 'RUNNING')
        pending = sum(1 for j in jobs if j['state'] == 'PENDING')
        console.print(f'[dim]Total: {len(jobs)} jobs  |  Running: {running}  |  Pending: {pending}[/dim]')
    else:
        console.print('[dim]No jobs in queue[/dim]')
    console.print()


def watch_queue(args):
    console = Console()
    show_all = getattr(args, 'all', False)

    console.print()
    console.print('[bold cyan]Watch Mode[/bold cyan] - Press Ctrl+C to exit')
    console.print()

    try:
        with Live(console=console, refresh_per_second=0.1) as live:
            while True:
                jobs = parse_queue_output(get_queue_data(show_all))
                live.update(create_queue_table(jobs))
                time.sleep(10)
    except KeyboardInterrupt:
        console.print()
        console.print('[yellow]Watch mode stopped[/yellow]')
        console.print()


# ---------------------------------------------------------------------------
# Job detail view  (run sq <job_id>)
# ---------------------------------------------------------------------------

def show_job_detail(job_id: str):
    """Show detailed info for a single job using scontrol + sstat."""
    console = Console()
    console.print()

    # --- scontrol show job ---
    try:
        result = subprocess.run(
            ['scontrol', 'show', 'job', job_id],
            capture_output=True, text=True
        )
        ctrl_text = result.stdout.strip()
    except Exception as e:
        console.print(f'[red]Error running scontrol: {e}[/red]')
        return

    if not ctrl_text or 'Invalid job id' in ctrl_text:
        console.print(f'[red]Job {job_id} not found[/red]')
        return

    # Parse key=value pairs from scontrol output
    ctrl = {}
    for token in re.split(r'\s+', ctrl_text):
        if '=' in token:
            k, _, v = token.partition('=')
            ctrl[k.strip()] = v.strip()

    state = ctrl.get('JobState', '—')

    # Build detail panel
    lines = [
        f'[bold]Job ID[/bold]       {ctrl.get("JobId", job_id)}',
        f'[bold]Name[/bold]         {ctrl.get("JobName", "—")}',
        f'[bold]State[/bold]        {_state_markup(state)}',
        f'[bold]Partition[/bold]    {ctrl.get("Partition", "—")}',
        f'[bold]Account[/bold]      {ctrl.get("Account", "—")}',
        f'[bold]User[/bold]         {ctrl.get("UserId", "—")}',
        '',
        f'[bold]Nodes[/bold]        {ctrl.get("NumNodes", "—")}  ({ctrl.get("NodeList", "—")})',
        f'[bold]CPUs[/bold]         {ctrl.get("NumCPUs", "—")}  (tasks: {ctrl.get("NumTasks", "—")})',
        f'[bold]Memory[/bold]       {_fmt_scontrol_mem(ctrl.get("MinMemoryNode") or ctrl.get("TRES", ""))}',
        '',
        f'[bold]Time limit[/bold]   {ctrl.get("TimeLimit", "—")}',
        f'[bold]Submitted[/bold]    {ctrl.get("SubmitTime", "—")}',
        f'[bold]Started[/bold]      {ctrl.get("StartTime", "—")}',
        f'[bold]End (est.)[/bold]   {ctrl.get("EndTime", "—")}',
        '',
        f'[bold]Work dir[/bold]     {ctrl.get("WorkDir", "—")}',
        f'[bold]Script[/bold]       {ctrl.get("Command", "—")}',
        f'[bold]StdOut[/bold]       {ctrl.get("StdOut", "—")}',
        f'[bold]StdErr[/bold]       {ctrl.get("StdErr", "—")}',
    ]

    console.print(Panel(
        '\n'.join(lines),
        title=f'[bold cyan]Job Detail: {job_id}[/bold cyan]',
        border_style='cyan',
        box=box.ROUNDED,
    ))

    # --- sstat live usage (running jobs only) ---
    if state == 'RUNNING':
        console.print()
        console.print('[bold]Live usage (sstat)[/bold]')
        try:
            stat_result = subprocess.run(
                ['sstat', '--format=JobID,CPUTime,MaxRSS,MaxVMSize,NTasks',
                 '-j', job_id, '--noheader', '-a'],
                capture_output=True, text=True
            )
            stat_out = stat_result.stdout.strip()
            if stat_out:
                stat_tbl = Table(box=box.SIMPLE, show_header=True, header_style='bold')
                stat_tbl.add_column('Step',    style='cyan')
                stat_tbl.add_column('CPU Time', justify='right')
                stat_tbl.add_column('Max RSS',  justify='right', style='green')
                stat_tbl.add_column('Max VMem', justify='right', style='dim')
                stat_tbl.add_column('Tasks',    justify='right')
                for sline in stat_out.splitlines():
                    sparts = sline.split()
                    if len(sparts) >= 5:
                        stat_tbl.add_row(sparts[0], sparts[1],
                                         _fmt_kb(sparts[2]), _fmt_kb(sparts[3]), sparts[4])
                console.print(stat_tbl)
            else:
                console.print('  [dim]No sstat data yet (job may not have started steps)[/dim]')
        except Exception as e:
            console.print(f'  [dim]sstat unavailable: {e}[/dim]')

    console.print()


def _fmt_scontrol_mem(raw: str) -> str:
    """Extract memory from scontrol MinMemoryNode or TRES string."""
    if not raw:
        return '—'
    # TRES format: cpu=16,mem=64G,node=4
    m = re.search(r'mem=([\d.]+[KMGT]?)', raw)
    if m:
        return m.group(1)
    return raw


def _fmt_kb(raw: str) -> str:
    """Format a KB value (as string) to human-readable."""
    if not raw or raw == '0':
        return '—'
    try:
        kb = int(raw.rstrip('K'))
        if kb >= 1024 * 1024:
            return f'{kb / 1024 / 1024:.1f} GB'
        if kb >= 1024:
            return f'{kb / 1024:.0f} MB'
        return f'{kb} KB'
    except ValueError:
        return raw


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

def show_sq_help():
    from src.utils.colors import Colors
    print(f"""
{Colors.BOLD}{Colors.CYAN}run sq — SLURM Job Queue{Colors.RESET}

{Colors.BOLD}USAGE:{Colors.RESET}
    run sq [<job_id>] [--all] [--watch]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}<job_id>{Colors.RESET}    Show detailed info for a single job (scontrol + sstat)

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--all{Colors.RESET}       Show all users' jobs (default: yours only)
    {Colors.YELLOW}--watch{Colors.RESET}     Refresh every 10 seconds (Ctrl+C to stop)
    {Colors.YELLOW}-h, --help{Colors.RESET}  Show this help message

{Colors.BOLD}COLUMNS (queue view):{Colors.RESET}
    Job ID · Name · State · Time · Nodes · Partition · CPUs · Memory · Submitted · Reason

{Colors.BOLD}JOB STATES:{Colors.RESET}
    {Colors.GREEN}RUNNING{Colors.RESET}    Currently executing
    {Colors.YELLOW}PENDING{Colors.RESET}    Waiting in queue
    {Colors.BLUE}COMPLETED{Colors.RESET}  Finished successfully
    {Colors.RED}FAILED / CANCELLED / TIMEOUT{Colors.RESET}

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    run sq                  # Your jobs
    run sq --all            # All users
    run sq --watch          # Auto-refresh
    run sq 1258586          # Detail for job 1258586
""")
