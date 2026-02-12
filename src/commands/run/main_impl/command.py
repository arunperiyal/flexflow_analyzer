"""Execute run main command - Submit main simulation job."""

import os
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box


def execute_main(args):
    """Execute run main command to submit main simulation job."""

    # Handle help flag
    if hasattr(args, 'help') and args.help:
        show_main_help()
        return

    # Get case directory
    case_dir = get_case_directory(args)
    if not case_dir:
        return

    console = Console()

    # Find main simulation script
    script_path = find_main_script(case_dir)
    if not script_path:
        console.print()
        console.print("[red]Error: No main simulation script found[/red]")
        console.print()
        console.print("[dim]Looking for one of:[/dim]")
        console.print("  [dim]• mainFlex.sh[/dim]")
        console.print("  [dim]• submit.sh[/dim]")
        console.print("  [dim]• main.sh[/dim]")
        console.print()
        return

    # Check if script is executable
    if not os.access(script_path, os.X_OK):
        console.print()
        console.print(f"[yellow]Warning: Script is not executable: {script_path.name}[/yellow]")
        console.print(f"[dim]Run: chmod +x {script_path.name}[/dim]")
        console.print()
        return

    # Handle --show flag
    if hasattr(args, 'show') and args.show:
        show_script_content(script_path, console)
        return

    # Handle --dry-run flag
    if hasattr(args, 'dry_run') and args.dry_run:
        show_dry_run(script_path, case_dir, args, console)
        return

    # Submit the job
    submit_main_job(script_path, case_dir, args, console)


def get_case_directory(args):
    """Get and validate case directory from args or context."""
    from src.cli.interactive import InteractiveShell

    case_dir = None

    # Try to get from args
    if hasattr(args, 'case') and args.case:
        case_dir = Path(args.case)
    # Try to get from context (if in interactive mode)
    elif hasattr(InteractiveShell, '_instance') and InteractiveShell._instance:
        shell = InteractiveShell._instance
        if shell._current_case:
            case_dir = Path(shell._current_case)

    if not case_dir:
        print("Error: Case directory not specified")
        print("\nUsage: run main <case_directory>")
        print("   or: use case:<directory>, then run main")
        return None

    if not case_dir.exists():
        print(f"Error: Case directory not found: {case_dir}")
        return None

    if not case_dir.is_dir():
        print(f"Error: Not a directory: {case_dir}")
        return None

    return case_dir.resolve()


def find_main_script(case_dir):
    """Find main simulation script in case directory."""
    script_names = ['mainFlex.sh', 'submit.sh', 'main.sh']

    for script_name in script_names:
        script_path = case_dir / script_name
        if script_path.exists():
            return script_path

    return None


def show_script_content(script_path, console):
    """Display script content."""
    console.print()
    console.print(Panel(
        f"[bold cyan]Script:[/bold cyan] {script_path.name}",
        box=box.ROUNDED
    ))
    console.print()

    try:
        with open(script_path) as f:
            content = f.read()

        # Display script content with line numbers
        from rich.syntax import Syntax
        syntax = Syntax(content, "bash", theme="monokai", line_numbers=True)
        console.print(syntax)
        console.print()
    except Exception as e:
        console.print(f"[red]Error reading script: {e}[/red]")
        console.print()


def show_dry_run(script_path, case_dir, args, console):
    """Show what would be submitted without actually submitting."""
    console.print()
    console.print("[bold cyan]Dry Run - Main Simulation Job[/bold cyan]")
    console.print()

    # Create info table
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("Case Directory", str(case_dir))
    table.add_row("Script", script_path.name)
    table.add_row("Working Directory", str(case_dir))

    # Check for restart option
    if hasattr(args, 'restart') and args.restart:
        table.add_row("Restart from TSID", str(args.restart))

    # Check for dependency option
    if hasattr(args, 'dependency') and args.dependency:
        table.add_row("Job Dependency", args.dependency)

    # Check for partition override
    if hasattr(args, 'partition') and args.partition:
        table.add_row("Partition Override", f"[bold yellow]{args.partition}[/bold yellow] (via sbatch CLI)")

    # Parse SBATCH directives from script
    sbatch_info = parse_sbatch_directives(script_path)
    if sbatch_info:
        for key, value in sbatch_info.items():
            # Mark partition as overridden if --partition was specified
            if key == 'Partition' and hasattr(args, 'partition') and args.partition:
                table.add_row(f'{key} (script)', f'[dim]{value}[/dim]')
            else:
                table.add_row(key, value)

    console.print(table)
    console.print()
    console.print("[dim]Command that would be executed:[/dim]")
    console.print(f"[dim]  cd {case_dir}[/dim]")

    cmd_parts = ["sbatch"]
    if hasattr(args, 'dependency') and args.dependency:
        cmd_parts.append(f"--dependency=afterok:{args.dependency}")
    if hasattr(args, 'partition') and args.partition:
        cmd_parts.append(f"--partition={args.partition}")
    cmd_parts.append(script_path.name)

    console.print(f"[dim]  {' '.join(cmd_parts)}[/dim]")
    console.print()


def parse_sbatch_directives(script_path):
    """Parse SBATCH directives from script."""
    directives = {}

    try:
        with open(script_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('#SBATCH'):
                    # Parse directive
                    parts = line[7:].strip().split(maxsplit=1)
                    if len(parts) == 2:
                        flag, value = parts
                        flag = flag.lstrip('-')

                        # Map common flags to readable names
                        flag_names = {
                            'J': 'Job Name',
                            'p': 'Partition',
                            'n': 'Tasks',
                            'N': 'Nodes',
                            't': 'Time Limit',
                            'cpus-per-task': 'CPUs per Task',
                            'ntasks-per-node': 'Tasks per Node',
                            'mem': 'Memory',
                            'o': 'Output File',
                            'e': 'Error File',
                        }

                        readable_name = flag_names.get(flag, flag)
                        directives[readable_name] = value
    except Exception:
        pass

    return directives


def handle_restart(case_dir, restart_tsid, console):
    """Handle restart from specific timestep - to be implemented once restart mechanism is confirmed."""
    console.print(f"[yellow]Note: Restart from TSID {restart_tsid} - passing to simulation script[/yellow]")
    console.print()
    return True


def submit_main_job(script_path, case_dir, args, console):
    """Submit main simulation job to SLURM."""

    # Check if SLURM is available
    if not check_slurm_available():
        console.print()
        console.print("[red]Error: SLURM commands not available[/red]")
        console.print("[dim]Cannot submit job without SLURM[/dim]")
        console.print()
        return

    # Handle restart if specified
    if hasattr(args, 'restart') and args.restart:
        console.print()
        console.print(f"[bold cyan]Preparing restart from TSID {args.restart}[/bold cyan]")
        console.print()
        if not handle_restart(case_dir, args.restart, console):
            console.print("[yellow]Continue with submission anyway? (Ctrl+C to cancel)[/yellow]")
            console.print()

    console.print()
    console.print("[bold cyan]Submitting Main Simulation Job[/bold cyan]")
    console.print()

    # Display job info
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("Case", case_dir.name)
    table.add_row("Script", script_path.name)

    if hasattr(args, 'restart') and args.restart:
        table.add_row("Mode", f"Restart from TSID {args.restart}")
    else:
        table.add_row("Mode", "New simulation")

    if hasattr(args, 'dependency') and args.dependency:
        table.add_row("Dependency", f"Wait for job {args.dependency}")

    # Parse SBATCH info
    sbatch_info = parse_sbatch_directives(script_path)
    if sbatch_info.get('Job Name'):
        table.add_row("Job Name", sbatch_info['Job Name'])

    partition_override = getattr(args, 'partition', None)
    if partition_override:
        script_partition = sbatch_info.get('Partition', '—')
        table.add_row("Partition", f"[bold yellow]{partition_override}[/bold yellow] [dim](script: {script_partition})[/dim]")
    elif sbatch_info.get('Partition'):
        table.add_row("Partition", sbatch_info['Partition'])

    if sbatch_info.get('Tasks'):
        table.add_row("Tasks", sbatch_info['Tasks'])

    console.print(table)
    console.print()

    try:
        # Build sbatch command
        cmd = ['sbatch']

        # Add dependency if specified
        if hasattr(args, 'dependency') and args.dependency:
            cmd.append(f'--dependency=afterok:{args.dependency}')

        # Add partition override if specified
        if partition_override:
            cmd.append(f'--partition={partition_override}')

        cmd.append(script_path.name)

        # Submit job using sbatch
        result = subprocess.run(
            cmd,
            cwd=case_dir,
            capture_output=True,
            text=True,
            check=True
        )

        # Parse job ID from output
        # SLURM typically outputs: "Submitted batch job 12345"
        output = result.stdout.strip()
        job_id = None
        if 'Submitted batch job' in output:
            job_id = output.split()[-1]

        if job_id:
            console.print(f"[green]✓ Job submitted successfully[/green]")
            console.print()
            console.print(f"[bold]Job ID:[/bold] {job_id}")
            console.print()
            console.print("[dim]Monitor with:[/dim]")
            console.print(f"[dim]  run sq              # Show queue[/dim]")
            console.print(f"[dim]  run sq --watch      # Live queue monitoring[/dim]")
            console.print(f"[dim]  squeue -j {job_id}   # Check specific job[/dim]")
            console.print(f"[dim]  scancel {job_id}     # Cancel job[/dim]")
            console.print()
            console.print("[dim]After completion:[/dim]")
            console.print(f"[dim]  run post            # Submit postprocessing[/dim]")
        else:
            console.print("[green]✓ Job submitted[/green]")
            console.print(f"[dim]{output}[/dim]")

        console.print()

    except subprocess.CalledProcessError as e:
        console.print("[red]✗ Job submission failed[/red]")
        console.print()
        if e.stderr:
            console.print("[red]Error:[/red]")
            console.print(e.stderr)
        console.print()
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        console.print()


def check_slurm_available():
    """Check if SLURM commands are available."""
    try:
        subprocess.run(['which', 'sbatch'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def show_main_help():
    """Show help for run main command."""
    from src.utils.colors import Colors

    print(f"""
{Colors.BOLD}{Colors.CYAN}Run Main - Submit Main Simulation Job{Colors.RESET}

Submit the main simulation job script to SLURM queue.
This runs the primary FlexFlow simulation (mpiSimflow).

{Colors.BOLD}USAGE:{Colors.RESET}
    run main [case_directory] [options]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--restart TSID{Colors.RESET}        Restart from specific timestep ID
    {Colors.YELLOW}--dependency JOB_ID{Colors.RESET}   Wait for another job to complete first
    {Colors.YELLOW}--partition NAME{Colors.RESET}       Override partition at submit time (sbatch CLI, script unchanged)
    {Colors.YELLOW}--dry-run{Colors.RESET}             Show what would be submitted
    {Colors.YELLOW}--show{Colors.RESET}                Display the script content
    {Colors.YELLOW}-h, --help{Colors.RESET}            Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Submit main simulation
    run main Case001

    # Submit from context
    use case:Case001
    run main

    # Restart from timestep 5000
    run main Case001 --restart 5000

    # Chain after preprocessing
    run main Case001 --dependency 12345

    # Override partition at submit time (does not modify mainFlex.sh)
    run main Case001 --partition shared

    # Preview what will be submitted
    run main Case001 --dry-run

{Colors.BOLD}SCRIPT PRIORITY:{Colors.RESET}
    The command looks for scripts in this order:
    1. mainFlex.sh
    2. submit.sh
    3. main.sh

{Colors.BOLD}JOB DEPENDENCIES:{Colors.RESET}
    Use --dependency to chain jobs:
    • Job will wait in queue until dependency completes
    • Uses SLURM's --dependency=afterok:JOB_ID
    • Useful for preprocessing → main → postprocessing chains

{Colors.BOLD}TYPICAL WORKFLOW:{Colors.RESET}
    # Option 1: Manual chain
    run pre Case001             # Get job ID (e.g., 12345)
    run main Case001 --dependency 12345

    # Option 2: Restart simulation
    run main Case001            # Initial run
    # ... simulation runs, stops at TSID 5000
    run main Case001 --restart 5000

{Colors.BOLD}AFTER SUBMISSION:{Colors.RESET}
    {Colors.GREEN}Monitor job status:{Colors.RESET}
    • run sq              # Show all your jobs
    • run sq --watch      # Live queue monitoring
    • squeue -j <job_id>  # Check specific job

    {Colors.GREEN}Next steps:{Colors.RESET}
    • Wait for simulation to complete
    • Check output files (*.out, *.rst, *.othd, *.oisd)
    • Submit postprocessing: run post
""")
