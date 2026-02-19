"""Execute run post command - Submit postprocessing job."""

import os
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from ..shared_helpers import apply_partition_header


def execute_post(args):
    """Execute run post command to submit postprocessing job."""

    # Handle help flag
    if hasattr(args, 'help') and args.help:
        show_post_help()
        return

    # Get case directory
    case_dir = get_case_directory(args)
    if not case_dir:
        return

    console = Console()

    # Handle --cleanup-only flag
    if hasattr(args, 'cleanup_only') and args.cleanup_only:
        perform_cleanup(case_dir, args, console)
        return

    # Handle --cleanup flag (cleanup then submit)
    if hasattr(args, 'cleanup') and args.cleanup:
        perform_cleanup(case_dir, args, console)
        console.print()

    # Find postprocessing script
    script_path = find_postprocessing_script(case_dir)
    if not script_path:
        console.print()
        console.print("[red]Error: No postprocessing script found[/red]")
        console.print()
        console.print("[dim]Looking for one of:[/dim]")
        console.print("  [dim]• postFlex.sh[/dim]")
        console.print("  [dim]• PostSubmit.sh[/dim]")
        console.print("  [dim]• post.sh[/dim]")
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
    submit_postprocessing_job(script_path, case_dir, args, console)


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
        print("\nUsage: run post <case_directory>")
        print("   or: use case:<directory>, then run post")
        return None

    if not case_dir.exists():
        print(f"Error: Case directory not found: {case_dir}")
        return None

    if not case_dir.is_dir():
        print(f"Error: Not a directory: {case_dir}")
        return None

    return case_dir.resolve()


def find_postprocessing_script(case_dir):
    """Find postprocessing script in case directory."""
    script_names = ['postFlex.sh', 'PostSubmit.sh', 'post.sh']

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
    console.print("[bold cyan]Dry Run - Postprocessing Job[/bold cyan]")
    console.print()

    # Create info table
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("Case Directory", str(case_dir))
    table.add_row("Script", script_path.name)
    table.add_row("Working Directory", str(case_dir))

    # Check if partition header will be applied
    partition_override = getattr(args, 'partition', None)
    if partition_override:
        headers_dir = Path(__file__).parent.parent.parent / 'templates' / 'scripts' / 'headers'
        header_file = headers_dir / f'{partition_override}.header'
        if header_file.exists():
            table.add_row("Partition Header", f"[bold yellow]{partition_override}.header will be applied[/bold yellow]")
        else:
            table.add_row("Partition Header", f"[bold red]{partition_override}.header not found[/bold red]")

    start_tsid   = getattr(args, 'start',   None)
    upto_tsid    = getattr(args, 'upto',    None)
    freq_arg     = getattr(args, 'freq',    None)
    convert_only = getattr(args, 'convert', False)

    start_tsid = _validate_start(start_tsid, freq_arg, case_dir, console)
    upto_tsid  = _validate_upto(upto_tsid, freq_arg, case_dir, console)
    if upto_tsid is None and getattr(args, 'upto', None) is not None:
        return  # corrected to invalid (below freq); abort

    if start_tsid:
        table.add_row("Process from TSID", str(start_tsid))
    if upto_tsid:
        table.add_row("Process up to TSID", str(upto_tsid))
    if freq_arg:
        table.add_row("Frequency override", str(freq_arg))
    if convert_only:
        table.add_row("Mode", "convert-only (simPlt2Bin only)")

    # Check for cleanup option
    if hasattr(args, 'cleanup') and args.cleanup:
        table.add_row("Cleanup", "Yes (before postprocessing)")

    # Check for dependency option
    if hasattr(args, 'dependency') and args.dependency:
        table.add_row("Job Dependency", args.dependency)

    # Parse SBATCH directives from script
    sbatch_info = parse_sbatch_directives(script_path)
    if sbatch_info:
        for key, value in sbatch_info.items():
            table.add_row(key, value)

    console.print(table)
    console.print()
    console.print("[dim]Command that would be executed:[/dim]")
    console.print(f"[dim]  cd {case_dir}[/dim]")

    cmd_parts = ["sbatch"]
    if hasattr(args, 'dependency') and args.dependency:
        cmd_parts.append(f"--dependency=afterok:{args.dependency}")
    export_parts = []
    if start_tsid is not None:
        export_parts.append(f'START_TIME={start_tsid}')
    if upto_tsid is not None:
        export_parts.append(f'END_TIME={upto_tsid}')
    if freq_arg is not None:
        export_parts.append(f'FREQ={freq_arg}')
    if convert_only:
        export_parts.append('CONVERT_ONLY=1')
    if export_parts:
        cmd_parts.append(f'--export=ALL,{",".join(export_parts)}')
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


def perform_cleanup(case_dir, args, console):
    """Perform cleanup of files that have binary PLT."""
    console.print()
    console.print("[bold cyan]Cleanup - Remove files with existing binary PLT[/bold cyan]")
    console.print()

    # Find binary directory
    binary_dir = case_dir / 'binary'

    if not binary_dir.exists() or not binary_dir.is_dir():
        console.print("[yellow]Warning: binary/ directory not found[/yellow]")
        console.print("[dim]No binary PLT files to check[/dim]")
        console.print()
        return

    # Get list of binary PLT files
    try:
        binary_files = list(binary_dir.glob('*.plt'))

        if not binary_files:
            console.print("[yellow]No binary PLT files found in binary/[/yellow]")
            console.print("[dim]Nothing to clean up[/dim]")
            console.print()
            return

        # Extract timestep IDs from binary PLT files
        # Files are typically named like: riser.100.plt, riser.200.plt, etc.
        timesteps_with_binary = set()
        for binary_file in binary_files:
            # Parse timestep from filename
            name = binary_file.stem  # e.g., riser.100
            parts = name.split('.')
            if len(parts) >= 2:
                try:
                    tsid = int(parts[-1])
                    timesteps_with_binary.add(tsid)
                except ValueError:
                    pass

        if not timesteps_with_binary:
            console.print("[yellow]Could not identify timesteps from binary PLT files[/yellow]")
            console.print()
            return

        console.print(f"Found {len(timesteps_with_binary)} timesteps with binary PLT files")
        console.print()

        # Count files to be deleted
        files_to_delete = []

        # Check SIMFLOW_DATA directory
        simflow_data_dir = case_dir / 'SIMFLOW_DATA'
        if simflow_data_dir.exists():
            for tsid in timesteps_with_binary:
                # Look for .out, .rst, .plt files
                for ext in ['.out', '.rst', '.plt']:
                    # Try different naming patterns
                    for pattern in [f'riser.{tsid}{ext}', f'riser{tsid}{ext}']:
                        file_path = simflow_data_dir / pattern
                        if file_path.exists():
                            files_to_delete.append(file_path)

        if not files_to_delete:
            console.print("[green]No files to clean up[/green]")
            console.print()
            return

        # Display files to be deleted
        console.print(f"[bold]Files to delete:[/bold] {len(files_to_delete)}")
        console.print()

        # Group by extension
        by_ext = {}
        for f in files_to_delete:
            ext = f.suffix
            by_ext.setdefault(ext, []).append(f)

        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Extension", style="cyan")
        table.add_column("Count", justify="right")

        for ext in sorted(by_ext.keys()):
            table.add_row(ext, str(len(by_ext[ext])))

        console.print(table)
        console.print()

        # Delete files
        deleted_count = 0
        failed_count = 0

        for file_path in files_to_delete:
            try:
                file_path.unlink()
                deleted_count += 1
            except Exception as e:
                failed_count += 1
                console.print(f"[red]Failed to delete {file_path.name}: {e}[/red]")

        if deleted_count > 0:
            console.print(f"[green]✓ Deleted {deleted_count} file(s)[/green]")

        if failed_count > 0:
            console.print(f"[yellow]⚠ Failed to delete {failed_count} file(s)[/yellow]")

        console.print()

    except Exception as e:
        console.print(f"[red]Error during cleanup: {e}[/red]")
        console.print()


def _validate_start(start_tsid, freq_arg, case_dir, console):
    """Validate --start against output frequency and return a corrected value.

    Rounds up to the nearest valid multiple so we don't skip available files.
    Returns the (possibly adjusted) start value, or None if start was None.
    """
    if start_tsid is None:
        return None

    freq = freq_arg
    if freq is None:
        try:
            from src.core.simflow_config import SimflowConfig
            cfg = SimflowConfig.find(case_dir)
            freq = cfg.out_freq
        except Exception:
            freq = None

    if freq is None or freq <= 0:
        return start_tsid

    if start_tsid % freq == 0:
        return start_tsid

    # Round up to nearest valid multiple
    corrected = ((start_tsid + freq - 1) // freq) * freq
    console.print(
        f"[yellow]Warning:[/yellow] --start {start_tsid} is not a multiple of "
        f"outFreq={freq}. No .out file exists at that step."
    )
    console.print(
        f"[yellow]         Using nearest valid timestep: {corrected}[/yellow]"
    )
    return corrected


def _validate_upto(upto_tsid, freq_arg, case_dir, console):
    """Validate --upto against output frequency and return a corrected value.

    Returns the (possibly adjusted) upto value, or None if upto was None.
    Prints a warning if the value was not a multiple of the frequency.
    """
    if upto_tsid is None:
        return None

    # Determine frequency: explicit --freq flag wins, then simflow.config
    freq = freq_arg
    if freq is None:
        try:
            from src.core.simflow_config import SimflowConfig
            cfg = SimflowConfig.find(case_dir)
            freq = cfg.out_freq
        except Exception:
            freq = None

    if freq is None or freq <= 0:
        # Can't validate without a known frequency
        return upto_tsid

    if upto_tsid % freq == 0:
        return upto_tsid

    # Round down to nearest valid multiple
    corrected = (upto_tsid // freq) * freq
    console.print(
        f"[yellow]Warning:[/yellow] --upto {upto_tsid} is not a multiple of "
        f"outFreq={freq}. No .out file exists at that step."
    )
    if corrected > 0:
        console.print(
            f"[yellow]         Using nearest valid timestep: {corrected}[/yellow]"
        )
        return corrected
    else:
        console.print("[red]Error:[/red] --upto is smaller than the output frequency. Nothing to process.")
        return None


def submit_postprocessing_job(script_path, case_dir, args, console):
    """Submit postprocessing job to SLURM."""

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
        if not apply_partition_header(script_path, partition_override, 'post', console):
            console.print(f"[yellow]Warning: Partition header '{partition_override}.header' not found — proceeding with existing script[/yellow]")
            console.print()

    console.print()
    console.print("[bold cyan]Submitting Postprocessing Job[/bold cyan]")
    console.print()

    # Display job info
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("Case", case_dir.name)
    table.add_row("Script", script_path.name)

    start_tsid   = getattr(args, 'start',   None)
    upto_tsid    = getattr(args, 'upto',    None)
    freq_arg     = getattr(args, 'freq',    None)
    convert_only = getattr(args, 'convert', False)

    start_tsid = _validate_start(start_tsid, freq_arg, case_dir, console)
    upto_tsid  = _validate_upto(upto_tsid, freq_arg, case_dir, console)
    if upto_tsid is None and getattr(args, 'upto', None) is not None:
        return  # corrected to invalid (below freq); abort

    if start_tsid:
        table.add_row("Process from TSID", str(start_tsid))
    if upto_tsid:
        table.add_row("Process up to TSID", str(upto_tsid))
    if freq_arg:
        table.add_row("Frequency override", str(freq_arg))
    if convert_only:
        table.add_row("Mode", "convert-only (simPlt2Bin only)")

    if hasattr(args, 'dependency') and args.dependency:
        table.add_row("Dependency", f"Wait for job {args.dependency}")

    # Parse SBATCH info
    sbatch_info = parse_sbatch_directives(script_path)
    if sbatch_info.get('Job Name'):
        table.add_row("Job Name", sbatch_info['Job Name'])
    if sbatch_info.get('Partition'):
        table.add_row("Partition", sbatch_info['Partition'])

    console.print(table)
    console.print()

    try:
        # Build sbatch command
        cmd = ['sbatch']

        # Add dependency if specified
        if hasattr(args, 'dependency') and args.dependency:
            cmd.append(f'--dependency=afterok:{args.dependency}')

        # Pass overrides via --export so postFlex.sh picks them up
        export_parts = []
        if start_tsid is not None:
            export_parts.append(f'START_TIME={start_tsid}')
        if upto_tsid is not None:
            export_parts.append(f'END_TIME={upto_tsid}')
        if freq_arg is not None:
            export_parts.append(f'FREQ={freq_arg}')
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
            console.print(f"[dim]  run sq --watch      # Live queue monitoring[/dim]")
            console.print(f"[dim]  squeue -j {job_id}   # Check specific job[/dim]")
            console.print(f"[dim]  scancel {job_id}     # Cancel job[/dim]")
            console.print()
            console.print("[dim]After completion:[/dim]")
            console.print(f"[dim]  Check binary/ directory for PLT files[/dim]")
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


def show_post_help():
    """Show help for run post command."""
    from src.utils.colors import Colors

    print(f"""
{Colors.BOLD}{Colors.CYAN}Run Post - Submit Postprocessing Job{Colors.RESET}

Submit the postprocessing job script to SLURM queue.
This typically runs simPlt (PLT generation) and simPlt2Bin (binary conversion).

{Colors.BOLD}USAGE:{Colors.RESET}
    run post [case_directory] [options]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--start TSID{Colors.RESET}         Process from this timestep (rounds up to nearest outFreq multiple)
    {Colors.YELLOW}--upto TSID{Colors.RESET}          Process up to this timestep (rounds down to nearest outFreq multiple)
    {Colors.YELLOW}--freq N{Colors.RESET}             Override output frequency from simflow.config
    {Colors.YELLOW}--convert{Colors.RESET}            Run simPlt2Bin only (skip simPlt; .plt files must already exist)
    {Colors.YELLOW}--partition NAME{Colors.RESET}     Apply partition header to script
    {Colors.YELLOW}--cleanup{Colors.RESET}            Clean up files with binary PLT before submitting
    {Colors.YELLOW}--cleanup-only{Colors.RESET}       Only perform cleanup, don't submit job
    {Colors.YELLOW}--dependency JOB_ID{Colors.RESET}  Wait for another job to complete first
    {Colors.YELLOW}--dry-run{Colors.RESET}            Show what would be submitted
    {Colors.YELLOW}--show{Colors.RESET}               Display the script content
    {Colors.YELLOW}-h, --help{Colors.RESET}           Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Submit postprocessing
    run post Case001

    # Submit from context
    use case:Case001
    run post

    # Cleanup first, then submit
    run post Case001 --cleanup

    # Only cleanup, don't submit
    run post Case001 --cleanup-only

    # Process up to timestep 5000
    run post Case001 --upto 5000

    # Chain after main simulation
    run post Case001 --dependency 12345

    # Apply partition header before submission
    run post Case001 --partition shared

{Colors.BOLD}SCRIPT PRIORITY:{Colors.RESET}
    The command looks for scripts in this order:
    1. postFlex.sh
    2. PostSubmit.sh
    3. post.sh

{Colors.BOLD}CLEANUP WORKFLOW:{Colors.RESET}
    When using --cleanup:
    1. Scans binary/ directory for existing binary PLT files
    2. Identifies timesteps that already have binary PLT
    3. Deletes .out, .rst, .plt files for those timesteps from SIMFLOW_DATA/
    4. Submits postprocessing job (which processes remaining files)

    This saves disk space by removing large files that are no longer needed
    after binary PLT conversion.

{Colors.BOLD}TYPICAL POSTPROCESSING STEPS:{Colors.RESET}
    The postFlex.sh script typically:
    1. Runs simPlt to generate PLT files from simulation output
    2. Runs simPlt2Bin to convert PLT to binary format

    Note: Both steps can take significant time (hours for large simulations)

{Colors.BOLD}TYPICAL WORKFLOW:{Colors.RESET}
    # Option 1: Chain entire workflow
    run pre Case001              # Get job ID: 100
    run main --dependency 100    # Get job ID: 101
    run post --dependency 101

    # Option 2: Cleanup between runs
    run post Case001 --cleanup   # Clean old files, process new ones

    # Option 3: Just cleanup
    run post Case001 --cleanup-only

{Colors.BOLD}AFTER SUBMISSION:{Colors.RESET}
    {Colors.GREEN}Monitor job status:{Colors.RESET}
    • run sq              # Show all your jobs
    • run sq --watch      # Live queue monitoring
    • squeue -j <job_id>  # Check specific job

    {Colors.GREEN}Check results:{Colors.RESET}
    • Binary PLT files will be in binary/ directory
    • Use visualization tools to analyze results
""")
