"""Execute run pre command - Submit preprocessing job."""

import os
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from ..shared_helpers import (
    apply_partition_header,
    execute_on_all_cases,
    get_case_name_and_base_dir,
    check_jobname_consistency,
    show_jobname_info,
)


def execute_pre(args):
    """Execute run pre command to submit preprocessing job."""

    # Handle help flag
    if hasattr(args, 'help') and args.help:
        show_pre_help()
        return

    # Get case info
    case_name, base_dir = _get_case_info(args)
    if case_name is None:
        return

    # If wildcard, execute on all cases
    if case_name == "*":
        execute_on_all_cases(
            case_name, 
            base_dir,
            lambda case_dir, display_name: _execute_pre_on_case(case_dir, args),
            "Pre-processing"
        )
        return

    # Single case execution
    case_dir = Path(case_name)
    if not case_dir.exists():
        print(f"Error: Case directory not found: {case_dir}")
        return
    
    _execute_pre_on_case(case_dir.resolve(), args)


def _execute_pre_on_case(case_dir: Path, args):
    """Execute pre-processing on a single case."""
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


def _get_case_info(args):
    """Get case name and base directory."""
    # Try from args first
    if hasattr(args, 'case') and args.case:
        return args.case, Path.cwd()
    
    # Fall back to context
    case_name, base_dir = get_case_name_and_base_dir()
    
    if not case_name:
        print("Error: Case directory not specified")
        print("\nUsage: run pre <case_directory>")
        print("   or: use case:<directory>, then run pre")
        return None, None
    
    return case_name, base_dir



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

    convert_only = getattr(args, 'convert', False)
    if convert_only:
        table.add_row("Mode", "convert-only (simGmshCnvt only, skipping gmsh)")

    # Check if partition header will be applied
    partition_override = getattr(args, 'partition', None)
    if partition_override:
        headers_dir = Path(__file__).parent.parent.parent / 'templates' / 'scripts' / 'headers'
        header_file = headers_dir / f'{partition_override}.header'
        if header_file.exists():
            table.add_row("Partition Header", f"[bold yellow]{partition_override}.header will be applied[/bold yellow]")
        else:
            table.add_row("Partition Header", f"[bold red]{partition_override}.header not found[/bold red]")

    gmsh_override = getattr(args, 'gmsh', None)
    if gmsh_override:
        table.add_row("gmsh Override", f"[bold yellow]{gmsh_override}[/bold yellow] (via --export GMSH)")

    account_override = getattr(args, 'account', None)
    if account_override:
        table.add_row("Account", f"[bold yellow]{account_override}[/bold yellow]")

    qos_override = getattr(args, 'qos', None)
    if qos_override:
        table.add_row("QOS", f"[bold yellow]{qos_override}[/bold yellow]")

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
    if account_override:
        cmd_parts.append(f'--account={account_override}')
    if qos_override:
        cmd_parts.append(f'--qos={qos_override}')
    export_parts = []
    if gmsh_override:
        export_parts.append(f'GMSH={gmsh_override}')
    if convert_only:
        export_parts.append('CONVERT_ONLY=1')
    if export_parts:
        cmd_parts.append(f'--export=ALL,{",".join(export_parts)}')
    cmd_parts.append(script_path.name)
    console.print(f"[dim]  {' '.join(cmd_parts)}[/dim]")
    console.print()

    if convert_only and not _script_supports_convert(script_path):
        console.print(
            f"[yellow]Warning: {script_path.name} does not support --convert "
            f"(no CONVERT_ONLY guard).[/yellow]"
        )
        console.print(
            "[dim]Submitting (without --dry-run) will offer to retrofit the script.[/dim]"
        )
        console.print()

    # Show job-name check (informational only in dry-run)
    show_jobname_info(script_path, case_dir, 'pre', console)


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
                        value = value.split('#')[0].strip()
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

    # Apply partition header if requested
    partition_override = getattr(args, 'partition', None)
    if partition_override:
        if not apply_partition_header(script_path, partition_override, 'pre', console):
            console.print(f"[yellow]Warning: Partition header '{partition_override}.header' not found — proceeding with existing script[/yellow]")
            console.print()

    # If --convert is requested but the script predates the CONVERT_ONLY guard,
    # offer to retrofit it in place (otherwise gmsh meshing would still run).
    if getattr(args, 'convert', False) and not _script_supports_convert(script_path):
        console.print(
            f"[yellow]⚠  {script_path.name} does not support --convert "
            f"(no CONVERT_ONLY guard).[/yellow]"
        )
        console.print()
        console.print("  1. Retrofit the script and submit (convert-only)")
        console.print("  2. Submit anyway (gmsh meshing will run)")
        console.print("  3. Abort")
        console.print()
        console.print('Choice [1/2/3]: ', end='')
        try:
            answer = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print()
            console.print('[yellow]Aborted[/yellow]')
            return
        if answer in {'1', 'r'}:
            if not _retrofit_convert_guard(script_path, console):
                console.print('[yellow]Aborting — retrofit failed[/yellow]')
                return
        elif answer in {'2', 's'}:
            console.print('[dim]Submitting without convert support — gmsh will run.[/dim]')
            console.print()
        else:
            console.print('[yellow]Aborted[/yellow]')
            return

    # Ensure the SBATCH job name matches the expected name before submitting
    if not check_jobname_consistency(script_path, case_dir, 'pre', console):
        return

    console.print()
    console.print("[bold cyan]Submitting Preprocessing Job[/bold cyan]")
    console.print()

    gmsh_override = getattr(args, 'gmsh', None)
    convert_only = getattr(args, 'convert', False)

    # Display job info
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("Case", case_dir.name)
    table.add_row("Script", script_path.name)
    if convert_only:
        table.add_row("Mode", "convert-only (simGmshCnvt only, skipping gmsh)")

    # Parse SBATCH info
    sbatch_info = parse_sbatch_directives(script_path)
    if sbatch_info.get('Job Name'):
        table.add_row("Job Name", sbatch_info['Job Name'])
    if sbatch_info.get('Partition'):
        table.add_row("Partition", sbatch_info['Partition'])
    if gmsh_override:
        table.add_row("gmsh Override", f"[bold yellow]{gmsh_override}[/bold yellow] (via --export GMSH)")

    account_override = getattr(args, 'account', None)
    if account_override:
        table.add_row("Account", f"[bold yellow]{account_override}[/bold yellow]")

    qos_override = getattr(args, 'qos', None)
    if qos_override:
        table.add_row("QOS", f"[bold yellow]{qos_override}[/bold yellow]")

    console.print(table)
    console.print()

    try:
        # Build sbatch command
        cmd = ['sbatch']
        if account_override:
            cmd.append(f'--account={account_override}')
        if qos_override:
            cmd.append(f'--qos={qos_override}')

        # Combine all env overrides into a single --export (only the last
        # --export is honored by sbatch, so they must not be split).
        export_parts = []
        if gmsh_override:
            export_parts.append(f'GMSH={gmsh_override}')
        if convert_only:
            export_parts.append('CONVERT_ONLY=1')
        if export_parts:
            cmd.append(f'--export=ALL,{",".join(export_parts)}')

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


def _script_supports_convert(script_path):
    """True if the script honors CONVERT_ONLY (i.e. has the convert-only guard)."""
    try:
        return 'CONVERT_ONLY' in script_path.read_text()
    except Exception:
        return False


def _retrofit_convert_guard(script_path, console) -> bool:
    """
    Add CONVERT_ONLY support to an existing pre script, in place.

    Defines ``CONVERT_ONLY`` after the SBATCH header and wraps the gmsh
    invocation so it is skipped in convert-only mode. The script's own
    "mesh file" checks (if present) then guard against a missing mesh.

    Returns True on success.
    """
    import re

    try:
        lines = script_path.read_text().splitlines(keepends=True)
    except Exception as e:
        console.print(f"[red]Error reading {script_path.name}: {e}[/red]")
        return False

    if any('CONVERT_ONLY' in ln for ln in lines):
        return True  # already supported

    # Locate the gmsh execution line — e.g. `$GMSH -3 ...` (not the
    # `command -v $GMSH` validation, whose line starts with `if`).
    gmsh_re = re.compile(r'^\s*"?\$\{?GMSH\}?"?\s')
    gmsh_idx = next((i for i, ln in enumerate(lines) if gmsh_re.match(ln)), None)

    if gmsh_idx is None:
        console.print(
            f"[red]Could not find a gmsh command line in {script_path.name} to guard.[/red]"
        )
        return False

    # Wrap the gmsh command in a CONVERT_ONLY guard, preserving indentation.
    line = lines[gmsh_idx]
    indent = line[:len(line) - len(line.lstrip())]
    gmsh_cmd = line.strip()
    lines[gmsh_idx] = (
        f'{indent}if [ "$CONVERT_ONLY" = "1" ]; then\n'
        f'{indent}    echo "Skipping gmsh meshing (convert-only mode)"\n'
        f'{indent}else\n'
        f'{indent}    {gmsh_cmd}\n'
        f'{indent}fi\n'
    )

    # Insert the CONVERT_ONLY definition after the SBATCH header (or shebang).
    insert_idx = 0
    for i, ln in enumerate(lines):
        if ln.strip().startswith('#SBATCH'):
            insert_idx = i + 1
    if insert_idx == 0 and lines and lines[0].startswith('#!'):
        insert_idx = 1
    lines.insert(insert_idx,
                 '\n# CONVERT_ONLY: skip gmsh meshing and run only simGmshCnvt '
                 "(added by 'run pre --convert')\n"
                 'CONVERT_ONLY=${CONVERT_ONLY:-0}\n')

    try:
        script_path.write_text(''.join(lines))
        console.print(f"[green]✓ Retrofitted {script_path.name} with CONVERT_ONLY support[/green]")
        console.print()
        return True
    except Exception as e:
        console.print(f"[red]Error writing {script_path.name}: {e}[/red]")
        return False


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
    {Colors.YELLOW}--gmsh PATH{Colors.RESET}      Override gmsh executable (sbatch --export=GMSH=PATH, script unchanged)
    {Colors.YELLOW}--convert{Colors.RESET}        Skip gmsh meshing; run only simGmshCnvt (mesh must already exist).
                     Offers to retrofit older scripts that lack CONVERT_ONLY support.
    {Colors.YELLOW}--partition NAME{Colors.RESET} Apply partition header to script
    {Colors.YELLOW}--dry-run{Colors.RESET}        Show what would be submitted without actually submitting
    {Colors.YELLOW}--show{Colors.RESET}           Display the script content
    {Colors.YELLOW}-h, --help{Colors.RESET}       Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Submit preprocessing for specific case
    run pre Case001

    # Submit from context
    use case:Case001
    run pre

    # Override gmsh path at submit time (does not modify preFlex.sh)
    run pre Case001 --gmsh /usr/local/bin/gmsh

    # Skip meshing and only run the mesh conversion (mesh already exists)
    run pre Case001 --convert

    # Apply partition header before submission
    run pre Case001 --partition shared

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
