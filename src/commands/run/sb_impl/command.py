"""Execute run sb command - Submit a SLURM job script."""

import os
import re
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich import box


def execute_sb(args):
    """Execute run sb command to submit a job script via sbatch."""

    if hasattr(args, 'help') and args.help:
        show_sb_help()
        return

    if not check_slurm_available():
        print("Error: SLURM commands not available")
        print("Make sure you're on an HPC cluster with SLURM installed")
        return

    script = getattr(args, 'script', None)
    if not script:
        print("Error: No script specified")
        print("Usage: run sb <script> [sbatch_args...]")
        return

    extra = getattr(args, 'extra', []) or []
    submit_job(script, extra)


# ---------------------------------------------------------------------------
# SLURM availability
# ---------------------------------------------------------------------------

def check_slurm_available():
    """Check if SLURM commands are available."""
    try:
        result = subprocess.run(['which', 'sbatch'], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Job submission
# ---------------------------------------------------------------------------

def submit_job(script: str, extra_args: list):
    """Run sbatch and display the result."""
    console = Console()

    # Resolve script path
    script_path = os.path.expanduser(script)
    if not os.path.isabs(script_path):
        script_path = os.path.join(os.getcwd(), script_path)

    if not os.path.exists(script_path):
        console.print(f'[red]Error: Script not found: {script}[/red]')
        return

    if not os.access(script_path, os.R_OK):
        console.print(f'[red]Error: Script not readable: {script}[/red]')
        return

    cmd = ['sbatch'] + extra_args + [script_path]
    console.print()
    console.print(f'[dim]Submitting: {" ".join(cmd)}[/dim]')

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as e:
        console.print(f'[red]Error running sbatch: {e}[/red]')
        return

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if result.returncode == 0:
        # Parse job ID from "Submitted batch job 1234567"
        job_id = _parse_job_id(stdout)
        lines = [
            f'[bold green]Job submitted successfully[/bold green]',
            '',
            f'[bold]Script[/bold]   {script}',
        ]
        if job_id:
            lines.append(f'[bold]Job ID[/bold]   [bold yellow]{job_id}[/bold yellow]')
        if stdout:
            lines.append(f'[bold]Output[/bold]   {stdout}')

        console.print(Panel(
            '\n'.join(lines),
            title='[bold cyan]sbatch[/bold cyan]',
            border_style='green',
            box=box.ROUNDED,
        ))

        if job_id:
            console.print(f'[dim]Tip: run sq to check queue   |   run sq {job_id} for details[/dim]')
    else:
        lines = [
            f'[bold red]Job submission failed[/bold red]',
            '',
            f'[bold]Script[/bold]      {script}',
            f'[bold]Exit code[/bold]   {result.returncode}',
        ]
        if stderr:
            lines.append('')
            lines.append(f'[bold]Error:[/bold]')
            for line in stderr.splitlines():
                lines.append(f'  {line}')
        if stdout:
            lines.append('')
            lines.append(f'[bold]Output:[/bold]')
            for line in stdout.splitlines():
                lines.append(f'  {line}')

        console.print(Panel(
            '\n'.join(lines),
            title='[bold red]sbatch failed[/bold red]',
            border_style='red',
            box=box.ROUNDED,
        ))

    console.print()


def _parse_job_id(stdout: str) -> str:
    """Extract job ID from sbatch output ('Submitted batch job 1234567')."""
    m = re.search(r'(\d+)', stdout)
    return m.group(1) if m else ''


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

def show_sb_help():
    from src.utils.colors import Colors
    print(f"""
{Colors.BOLD}{Colors.CYAN}run sb — Submit SLURM Job Script{Colors.RESET}

{Colors.BOLD}USAGE:{Colors.RESET}
    run sb <script> [sbatch_options...]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}<script>{Colors.RESET}    Path to the SLURM batch script (.sh file)

{Colors.BOLD}OPTIONS:{Colors.RESET}
    Any additional arguments are passed directly to sbatch.
    {Colors.YELLOW}-h, --help{Colors.RESET}  Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    run sb postFlex.sh                  # Submit script in current directory
    run sb /path/to/case/runFlex.sh     # Submit with absolute path
    run sb postFlex.sh --dependency afterok:1258586
""")
