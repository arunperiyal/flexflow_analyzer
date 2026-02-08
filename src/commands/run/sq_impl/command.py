"""Execute run sq command - Show SLURM job queue status."""

import os
import subprocess
import time
from rich.console import Console
from rich.table import Table
from rich import box
from rich.live import Live


def execute_sq(args):
    """Execute run sq command to show SLURM job queue."""

    # Handle help flag
    if hasattr(args, 'help') and args.help:
        show_sq_help()
        return

    # Check if squeue is available
    if not check_slurm_available():
        print("Error: SLURM commands not available")
        print("Make sure you're on an HPC cluster with SLURM installed")
        return

    # Watch mode - refresh every 10 seconds
    if hasattr(args, 'watch') and args.watch:
        watch_queue(args)
    else:
        # Single display
        show_queue(args)


def check_slurm_available():
    """Check if SLURM commands are available."""
    try:
        result = subprocess.run(
            ['which', 'squeue'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def get_queue_data(show_all=False):
    """Get SLURM queue data."""
    try:
        # Build squeue command
        cmd = ['squeue']

        # Filter by user unless --all is specified
        if not show_all:
            username = os.environ.get('USER', '')
            if username:
                cmd.extend(['-u', username])

        # Format: JobID, Name, State, Time, Nodes, Reason
        cmd.extend(['-o', '%.10i %.15j %.10T %.10M %.6D %R'])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error running squeue: {e}"
    except Exception as e:
        return f"Error: {e}"


def parse_queue_output(output):
    """Parse squeue output into structured data."""
    lines = output.strip().split('\n')

    if not lines:
        return []

    # Skip header line
    if len(lines) <= 1:
        return []

    jobs = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 5:
            jobs.append({
                'jobid': parts[0],
                'name': parts[1],
                'state': parts[2],
                'time': parts[3],
                'nodes': parts[4],
                'reason': ' '.join(parts[5:]) if len(parts) > 5 else ''
            })

    return jobs


def create_queue_table(jobs):
    """Create a rich Table from job data."""
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title="SLURM Job Queue",
        title_style="bold magenta"
    )

    table.add_column("Job ID", style="yellow", justify="right")
    table.add_column("Name", style="green")
    table.add_column("State", style="cyan")
    table.add_column("Time", style="blue", justify="right")
    table.add_column("Nodes", style="magenta", justify="right")
    table.add_column("Reason", style="dim")

    if not jobs:
        table.add_row("—", "No jobs in queue", "—", "—", "—", "—")
        return table

    for job in jobs:
        # Color code state
        state = job['state']
        if state == 'RUNNING':
            state_style = "[bold green]" + state + "[/bold green]"
        elif state == 'PENDING':
            state_style = "[bold yellow]" + state + "[/bold yellow]"
        elif state in ['COMPLETED', 'COMPLETING']:
            state_style = "[bold blue]" + state + "[/bold blue]"
        elif state in ['FAILED', 'CANCELLED', 'TIMEOUT']:
            state_style = "[bold red]" + state + "[/bold red]"
        else:
            state_style = state

        table.add_row(
            job['jobid'],
            job['name'],
            state_style,
            job['time'],
            job['nodes'],
            job['reason']
        )

    return table


def show_queue(args):
    """Show queue once."""
    console = Console()

    show_all = hasattr(args, 'all') and args.all

    # Get and parse queue data
    output = get_queue_data(show_all)
    jobs = parse_queue_output(output)

    # Create and display table
    table = create_queue_table(jobs)

    console.print()
    console.print(table)
    console.print()

    # Show summary
    if jobs:
        running = sum(1 for j in jobs if j['state'] == 'RUNNING')
        pending = sum(1 for j in jobs if j['state'] == 'PENDING')
        console.print(f"[dim]Total: {len(jobs)} jobs  |  Running: {running}  |  Pending: {pending}[/dim]")
    else:
        console.print("[dim]No jobs in queue[/dim]")
    console.print()


def watch_queue(args):
    """Watch queue with auto-refresh."""
    console = Console()
    show_all = hasattr(args, 'all') and args.all

    console.print()
    console.print("[bold cyan]Watch Mode[/bold cyan] - Press Ctrl+C to exit")
    console.print()

    try:
        with Live(console=console, refresh_per_second=0.1) as live:
            while True:
                # Get and parse queue data
                output = get_queue_data(show_all)
                jobs = parse_queue_output(output)

                # Create table
                table = create_queue_table(jobs)

                # Update display
                live.update(table)

                # Wait 10 seconds
                time.sleep(10)

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Watch mode stopped[/yellow]")
        console.print()


def show_sq_help():
    """Show help for run sq command."""
    from src.utils.colors import Colors

    print(f"""
{Colors.BOLD}{Colors.CYAN}Run SQ - Show SLURM Job Queue{Colors.RESET}

Display SLURM job queue status in a formatted table.

{Colors.BOLD}USAGE:{Colors.RESET}
    run sq [options]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--all{Colors.RESET}      Show all users' jobs (not just yours)
    {Colors.YELLOW}--watch{Colors.RESET}    Watch mode - refresh every 10 seconds
    {Colors.YELLOW}-h, --help{Colors.RESET} Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Show your jobs
    run sq

    # Show all jobs
    run sq --all

    # Watch mode (auto-refresh)
    run sq --watch

    # Watch all jobs
    run sq --all --watch

{Colors.BOLD}JOB STATES:{Colors.RESET}
    {Colors.GREEN}RUNNING{Colors.RESET}    Job is currently executing
    {Colors.YELLOW}PENDING{Colors.RESET}    Job is waiting in queue
    {Colors.BLUE}COMPLETED{Colors.RESET}  Job finished successfully
    {Colors.RED}FAILED{Colors.RESET}     Job failed
    {Colors.RED}CANCELLED{Colors.RESET}  Job was cancelled
    {Colors.RED}TIMEOUT{Colors.RESET}    Job exceeded time limit

{Colors.BOLD}TIPS:{Colors.RESET}
    • Use watch mode to monitor long-running jobs
    • Press Ctrl+C to exit watch mode
    • Combine with other run commands:
        run main Case001    # Submit job
        run sq --watch      # Monitor progress
""")
