"""Execute run pre command - Submit preprocessing job."""

import os
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box


def execute_pre(args):
    """Execute run pre command to submit preprocessing job."""

    # Handle help flag
    if hasattr(args, 'help') and args.help:
        show_pre_help()
        return

    # Get case directory
    case_dir = get_case_directory(args)
    if not case_dir:
        return

    console = Console()

    # Find preprocessing script
    script_path = find_preprocessing_script(case_dir)
    if not script_path:
        console.print()
        console.print("[red]Error: No preprocessing script found[/red]")
        console.print()
        console.print("[dim]Looking for one of:[/dim]")
        console.print("  [dim]• preFlex.sh[/dim]")
        console.print("  [dim]• pre.sh[/dim]")
        console.print("  [dim]• preprocessing.sh[/dim]")
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
    submit_preprocessing_job(script_path, case_dir, args, console)


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
        print("\nUsage: run pre <case_directory>")
        print("   or: use case:<directory>, then run pre")
        return None

    if not case_dir.exists():
        print(f"Error: Case directory not found: {case_dir}")
        return None

    if not case_dir.is_dir():
        print(f"Error: Not a directory: {case_dir}")
        return None

    return case_dir.resolve()


def find_preprocessing_script(case_dir):
    """Find preprocessing script in case directory."""
    script_names = ['preFlex.sh', 'pre.sh', 'preprocessing.sh']

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
    console.print("[bold cyan]Dry Run - Preprocessing Job[/bold cyan]")
    console.print()

    # Create info table
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("Case Directory", str(case_dir))
    table.add_row("Script", script_path.name)
    table.add_row("Working Directory", str(case_dir))

    gmsh_override = getattr(args, 'gmsh', None)
    if gmsh_override:
        table.add_row("gmsh Override", f"[bold yellow]{gmsh_override}[/bold yellow] (via --export GMSH)")

    # Parse SBATCH directives from script
    sbatch_info = parse_sbatch_directives(script_path)
    if sbatch_info:
        for key, value in sbatch_info.items():
            table.add_row(key, value)

    console.print(table)
    console.print()
    console.print("[dim]Command that would be executed:[/dim]")
    console.print(f"[dim]  cd {case_dir}[/dim]")

    cmd_parts = ['sbatch']
    if gmsh_override:
        cmd_parts.append(f'--export=GMSH={gmsh_override}')
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
                            'mem': 'Memory',
                            'o': 'Output File',
                            'e': 'Error File',
                        }

                        readable_name = flag_names.get(flag, flag)
                        directives[readable_name] = value
    except Exception:
        pass

    return directives


def submit_preprocessing_job(script_path, case_dir, args, console):
    """Submit preprocessing job to SLURM."""

    # Check if SLURM is available
    if not check_slurm_available():
        console.print()
        console.print("[red]Error: SLURM commands not available[/red]")
        console.print("[dim]Cannot submit job without SLURM[/dim]")
        console.print()
        return

    console.print()
    console.print("[bold cyan]Submitting Preprocessing Job[/bold cyan]")
    console.print()

    gmsh_override = getattr(args, 'gmsh', None)

    # Display job info
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("Case", case_dir.name)
    table.add_row("Script", script_path.name)

    # Parse SBATCH info
    sbatch_info = parse_sbatch_directives(script_path)
    if sbatch_info.get('Job Name'):
        table.add_row("Job Name", sbatch_info['Job Name'])
    if sbatch_info.get('Partition'):
        table.add_row("Partition", sbatch_info['Partition'])
    if gmsh_override:
        table.add_row("gmsh Override", f"[bold yellow]{gmsh_override}[/bold yellow] (via --export GMSH)")

    console.print(table)
    console.print()

    try:
        # Build sbatch command
        cmd = ['sbatch']
        if gmsh_override:
            cmd.append(f'--export=GMSH={gmsh_override}')
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
            console.print(f"[dim]  squeue -j {job_id}   # Check specific job[/dim]")
            console.print(f"[dim]  scancel {job_id}     # Cancel job[/dim]")
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


def show_pre_help():
    """Show help for run pre command."""
    from src.utils.colors import Colors

    print(f"""
{Colors.BOLD}{Colors.CYAN}Run Pre - Submit Preprocessing Job{Colors.RESET}

Submit the preprocessing job script to SLURM queue.
This typically runs mesh generation (gmsh) and mesh conversion (simGmshCnvt).

{Colors.BOLD}USAGE:{Colors.RESET}
    run pre [case_directory] [options]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--gmsh PATH{Colors.RESET}   Override gmsh executable (sbatch --export=GMSH=PATH, script unchanged)
    {Colors.YELLOW}--dry-run{Colors.RESET}     Show what would be submitted without actually submitting
    {Colors.YELLOW}--show{Colors.RESET}        Display the script content
    {Colors.YELLOW}-h, --help{Colors.RESET}    Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Submit preprocessing for specific case
    run pre Case001

    # Submit from context
    use case:Case001
    run pre

    # Override gmsh path at submit time (does not modify preFlex.sh)
    run pre Case001 --gmsh /usr/local/bin/gmsh

    # Preview what will be submitted
    run pre Case001 --dry-run

    # View the script content
    run pre Case001 --show

{Colors.BOLD}SCRIPT PRIORITY:{Colors.RESET}
    The command looks for scripts in this order:
    1. preFlex.sh
    2. pre.sh
    3. preprocessing.sh

{Colors.BOLD}WORKFLOW:{Colors.RESET}
    1. Finds preprocessing script in case directory
    2. Validates script is executable
    3. Submits to SLURM using 'sbatch'
    4. Returns job ID for monitoring

{Colors.BOLD}TYPICAL PREPROCESSING STEPS:{Colors.RESET}
    • Mesh generation with gmsh
    • Mesh conversion with simGmshCnvt
    • Pre-simulation setup tasks

{Colors.BOLD}AFTER SUBMISSION:{Colors.RESET}
    {Colors.GREEN}Monitor job status:{Colors.RESET}
    • run sq              # Show all your jobs
    • run sq --watch      # Live queue monitoring
    • squeue -j <job_id>  # Check specific job

    {Colors.GREEN}Next steps:{Colors.RESET}
    • Wait for preprocessing to complete
    • Check output files (*.msh, domain files)
    • Submit main simulation: run main
""")
