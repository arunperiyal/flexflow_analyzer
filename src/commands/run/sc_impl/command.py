"""Execute run sc command - Cancel SLURM jobs by ID or name."""

import re
import subprocess
from rich.console import Console
from rich.table import Table
from rich import box


def execute_sc(args):
    """Execute run sc command to cancel SLURM jobs."""

    if hasattr(args, 'help') and args.help:
        show_sc_help()
        return

    if not check_slurm_available():
        print("Error: SLURM commands not available")
        print("Make sure you're on an HPC cluster with SLURM installed")
        return

    target = getattr(args, 'target', None)
    if not target:
        print("Error: No job ID or name specified")
        print("Usage: run sc <job_id|job_name>")
        return

    cancel_job(target)


# ---------------------------------------------------------------------------
# SLURM availability
# ---------------------------------------------------------------------------

def check_slurm_available():
    """Check if SLURM commands are available."""
    try:
        result = subprocess.run(['which', 'scancel'], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Queue lookup
# ---------------------------------------------------------------------------

def _get_jobs_by_name(name: str) -> list:
    """Return list of (job_id, job_name, state) matching the given job name."""
    import os
    try:
        cmd = ['squeue', '--format', '%i|%j|%T', '--noheader']
        username = os.environ.get('USER', '')
        if username:
            cmd.extend(['-u', username])
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return []
        matches = []
        for line in result.stdout.strip().splitlines():
            parts = line.split('|', 2)
            if len(parts) == 3:
                jid, jname, jstate = parts[0].strip(), parts[1].strip(), parts[2].strip()
                if jname == name:
                    matches.append((jid, jname, jstate))
        return matches
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

def cancel_job(target: str):
    """Cancel a job by numeric ID or by name."""
    console = Console()
    console.print()

    is_numeric = re.fullmatch(r'\d+', target) is not None

    if is_numeric:
        _cancel_by_id(console, target)
    else:
        _cancel_by_name(console, target)

    console.print()


def _cancel_by_id(console: Console, job_id: str):
    """Cancel a single job by numeric job ID."""
    console.print(f'Cancelling job [yellow]{job_id}[/yellow]...')
    try:
        result = subprocess.run(['scancel', job_id], capture_output=True, text=True)
    except Exception as e:
        console.print(f'[red]Error running scancel: {e}[/red]')
        return

    if result.returncode == 0:
        console.print(f'[bold green]✓ Job {job_id} cancelled[/bold green]')
    else:
        err = (result.stderr or result.stdout).strip()
        console.print(f'[red]Failed to cancel job {job_id}[/red]')
        if err:
            console.print(f'[dim]{err}[/dim]')


def _cancel_by_name(console: Console, name: str):
    """Look up jobs by name, confirm, then cancel each."""
    console.print(f'Looking up jobs named [yellow]{name}[/yellow]...')
    matches = _get_jobs_by_name(name)

    if not matches:
        console.print(f'[yellow]No running/pending jobs found with name: {name}[/yellow]')
        return

    # Show matching jobs
    tbl = Table(box=box.SIMPLE, show_header=True, header_style='bold cyan')
    tbl.add_column('Job ID',  style='yellow', justify='right')
    tbl.add_column('Name',    style='green')
    tbl.add_column('State',   justify='center')
    for jid, jname, jstate in matches:
        tbl.add_row(jid, jname, _state_markup(jstate))
    console.print(tbl)

    # Confirm
    ids_str = ', '.join(jid for jid, _, _ in matches)
    console.print(f'Cancel {len(matches)} job(s): {ids_str}? [y/N] ', end='')
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print()
        console.print('[yellow]Cancelled[/yellow]')
        return

    if answer != 'y':
        console.print('[yellow]Aborted[/yellow]')
        return

    # Cancel each
    failed = []
    for jid, jname, _ in matches:
        try:
            result = subprocess.run(['scancel', jid], capture_output=True, text=True)
            if result.returncode == 0:
                console.print(f'[green]✓[/green] Cancelled job {jid} ({jname})')
            else:
                err = (result.stderr or result.stdout).strip()
                console.print(f'[red]✗[/red] Failed to cancel job {jid}: {err}')
                failed.append(jid)
        except Exception as e:
            console.print(f'[red]✗[/red] Error cancelling job {jid}: {e}')
            failed.append(jid)

    console.print()
    if not failed:
        console.print(f'[bold green]All {len(matches)} job(s) cancelled[/bold green]')
    else:
        console.print(f'[yellow]{len(matches) - len(failed)} cancelled, {len(failed)} failed[/yellow]')


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


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

def show_sc_help():
    from src.utils.colors import Colors
    print(f"""
{Colors.BOLD}{Colors.CYAN}run sc — Cancel SLURM Jobs{Colors.RESET}

{Colors.BOLD}USAGE:{Colors.RESET}
    run sc <job_id|job_name>

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}<job_id>{Colors.RESET}     Numeric SLURM job ID — cancelled immediately
    {Colors.YELLOW}<job_name>{Colors.RESET}   Job name string — looks up matching jobs, asks confirmation

{Colors.BOLD}BEHAVIOUR:{Colors.RESET}
    • If the argument is a number, scancel is called directly
    • If the argument is a name, matching jobs are listed and confirmation is requested
    • Only your own jobs are searched when cancelling by name

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}-h, --help{Colors.RESET}  Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    run sc 1258586              # Cancel job by ID
    run sc postCase005          # Find and cancel all jobs named 'postCase005'
""")
