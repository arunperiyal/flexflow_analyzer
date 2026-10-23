"""Execute run post command - Submit postprocessing job."""

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


def execute_post(args):
    """Execute run post command to submit postprocessing job."""

    # Handle help flag
    if hasattr(args, 'help') and args.help:
        show_post_help()
        return

    if not _take_post_mode(args):
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
            lambda case_dir, display_name: _execute_post_on_case(case_dir, args),
            "Post-processing"
        )
        return

    # Single case execution
    case_dir = Path(case_name)
    if not case_dir.exists():
        print(f"Error: Case directory not found: {case_dir}")
        return
    
    _execute_post_on_case(case_dir.resolve(), args)


POST_MODES = ('full', 'convert')
_POST_USAGE = "Usage: run post {full|convert} [case_directory] [options]"


def _take_post_mode(args) -> bool:
    """
    Read the mode word: run post full [case] / run post convert [case].

    Sets args.convert and moves the case that follows the mode word into
    args.case. A mode is needed to submit; --cleanup-only and --show work
    without one. Returns False (after printing why) on bad input.
    """
    words = list(getattr(args, 'words', None) or [])
    mode = getattr(args, 'case', None)
    if mode in POST_MODES:
        args.case = words.pop(0) if words else None
    else:
        mode = None
    args.post_mode = mode
    args.convert = mode == 'convert'

    if words:
        print(f"Error: unexpected argument '{words[0]}'")
        print(_POST_USAGE)
        return False
    if mode is None and not (getattr(args, 'cleanup_only', False) or getattr(args, 'show', False)):
        print("Error: run post needs a mode: full (simPlt + simPlt2Bin) or convert (simPlt2Bin only)")
        print(_POST_USAGE)
        return False
    return True


def _execute_post_on_case(case_dir: Path, args):
    """Execute post-processing on a single case."""
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


def _get_case_info(args):
    """Get case name and base directory."""
    # Try from args first
    if hasattr(args, 'case') and args.case:
        return args.case, Path.cwd()
    
    # Fall back to context
    case_name, base_dir = get_case_name_and_base_dir()
    
    if not case_name:
        print("Error: Case directory not specified")
        print("\nUsage: run post {full|convert} <case_directory>")
        print("   or: use case:<directory>, then run post full")
        return None, None
    
    return case_name, base_dir


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

    job = _job_exports(args, case_dir, script_path, console, check_remote=False)
    if job is None:
        return
    export_parts, rows = job
    for row in rows:
        table.add_row(*row)

    # Check for cleanup option
    if hasattr(args, 'cleanup') and args.cleanup:
        table.add_row("Cleanup", "Yes (before postprocessing)")

    # Check for dependency option
    if hasattr(args, 'dependency') and args.dependency:
        table.add_row("Job Dependency", args.dependency)

    # Check for account override
    account_override = getattr(args, 'account', None)
    if account_override:
        table.add_row("Account", f"[bold yellow]{account_override}[/bold yellow]")

    # Check for QOS override
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

    cmd_parts = ["sbatch"]
    if hasattr(args, 'dependency') and args.dependency:
        cmd_parts.append(f"--dependency=afterok:{args.dependency}")
    account_override = getattr(args, 'account', None)
    if account_override:
        cmd_parts.append(f"--account={account_override}")
    qos_override = getattr(args, 'qos', None)
    if qos_override:
        cmd_parts.append(f"--qos={qos_override}")
    if export_parts:
        cmd_parts.append(f'--export=ALL,{",".join(export_parts)}')
    cmd_parts.append(script_path.name)

    console.print(f"[dim]  {' '.join(cmd_parts)}[/dim]")
    console.print()

    # Show job-name check (informational only in dry-run)
    show_jobname_info(script_path, case_dir, 'post', console)


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
    """Validate --t1 against output frequency and return a corrected value.

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
        f"[yellow]Warning:[/yellow] --t1 {start_tsid} is not a multiple of "
        f"outFreq={freq}. No .out file exists at that step."
    )
    console.print(
        f"[yellow]         Using nearest valid timestep: {corrected}[/yellow]"
    )
    return corrected


def _validate_upto(upto_tsid, freq_arg, case_dir, console):
    """Validate --t2 against output frequency and return a corrected value.

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
        f"[yellow]Warning:[/yellow] --t2 {upto_tsid} is not a multiple of "
        f"outFreq={freq}. No .out file exists at that step."
    )
    if corrected > 0:
        console.print(
            f"[yellow]         Using nearest valid timestep: {corrected}[/yellow]"
        )
        return corrected
    else:
        console.print("[red]Error:[/red] --t2 is smaller than the output frequency. Nothing to process.")
        return None


def _whole_step(value, flag, console):
    """--t1/--t2 as an int timestep; they parse as floats so a `use t1:` context fits."""
    if value is None:
        return None
    if value != int(value) or value < 0:
        console.print(f"[red]Error:[/red] {flag} must be a whole, non-negative timestep, not {value}")
        raise ValueError(flag)
    return int(value)


def _job_exports(args, case_dir, script_path, console, check_remote):
    """
    The variables postFlex.sh reads (passed with sbatch --export), and the
    rows describing them for the summary table.

    Returns (exports, rows), or None (after saying why) when the job should
    not be submitted. With check_remote, a remote is also checked to accept
    key-based ssh before anything is submitted.
    """
    freq_arg = getattr(args, 'freq', None)
    convert_only = getattr(args, 'convert', False)
    try:
        t1 = _whole_step(getattr(args, 't1', None), '--t1', console)
        t2 = _whole_step(getattr(args, 't2', None), '--t2', console)
    except ValueError:
        return None

    t1 = _validate_start(t1, freq_arg, case_dir, console)
    t2_given = t2 is not None
    t2 = _validate_upto(t2, freq_arg, case_dir, console)
    if t2 is None and t2_given:
        return None  # corrected to invalid (below freq); abort

    exports, rows = [], []
    if t1 is not None:
        exports.append(f'START_TIME={t1}')
        if t1:
            rows.append(("Process from TSID", str(t1)))
    if t2 is not None:
        exports.append(f'END_TIME={t2}')
        rows.append(("Process up to TSID", str(t2)))
    if freq_arg is not None:
        exports.append(f'FREQ={freq_arg}')
        rows.append(("Frequency override", str(freq_arg)))
    if convert_only:
        exports.append('CONVERT_ONLY=1')
        rows.append(("Mode", "convert-only (simPlt2Bin only)"))

    remote = _remote_exports(args, case_dir, script_path, console, check_remote)
    if remote is None:
        return None
    if remote:
        remote_exports, remote_row = remote
        exports.extend(remote_exports)
        rows.append(remote_row)
    return exports, rows


def _remote_exports(args, case_dir, script_path, console, check):
    """
    REMOTE_TARGET/REMOTE_PORT/REMOTE_DIR for `--remote NAME` (or the `remote`
    context), or [] when nothing is to be sent. None means: do not submit.

    The remote case path is built as `case upload` builds it -- the remote's
    path, then the case name -- so the files land where `case upload binary`
    would put them. No password is passed: the job sends with ssh keys only.

    When ~/.ssh/config defines a Host with the remote's name, that alias is
    the target, so its User, IdentityFile and Port apply -- the remote config's
    user and ip are only the fallback. `ssh cloud` working while
    `ssh sshd@10.24.3.58` is refused is exactly the case this covers.
    """
    name = None if getattr(args, 'no_remote', False) else getattr(args, 'remote', None)
    if not name:
        return []

    from src.utils.remote_config import RemoteConfig
    from src.commands.case.download_impl.command import CaseUploadCommand

    remote = RemoteConfig().get_remote(name)
    if remote is None:
        console.print(f"[red]Error:[/red] remote '{name}' not found (`remote list` shows them)")
        return None

    try:
        script_text = script_path.read_text()
    except OSError:
        script_text = ''
    if 'REMOTE_TARGET' not in script_text:
        console.print(f"[red]Error:[/red] {script_path.name} predates sending to a remote, "
                      f"so --remote would do nothing.")
        console.print("[dim]  Regenerate it from the template (this replaces local edits):[/dim]")
        console.print(f"[dim]  template script post {case_dir} --force[/dim]")
        return None

    upload = CaseUploadCommand()
    base = upload.get_remote_base_path(remote, None)
    remote_dir = upload.construct_remote_case_path(base, str(case_dir)) + '/binary'

    alias = _ssh_alias(name)
    if alias:
        target, port = name, None
        via = f"ssh config: {alias.get('user', '?')}@{alias.get('hostname', '?')}"
    else:
        target, port = f"{remote.get('user')}@{remote.get('ip')}", remote.get('port') or 22
        via = target

    # sbatch --export splits on commas; the job quotes paths in single quotes
    bad = [v for v in (target, remote_dir) if ',' in v or "'" in v or ' ' in v]
    if bad:
        console.print(f"[red]Error:[/red] cannot pass {bad[0]!r} to the job "
                      f"(commas, quotes and spaces are not supported)")
        return None

    if check and not _ssh_key_login_works(target, port, console):
        return None

    exports = [f'REMOTE_TARGET={target}', f'REMOTE_DIR={remote_dir}']
    if port is not None:
        exports.insert(1, f'REMOTE_PORT={port}')
    return exports, ("Send binary PLT to", f"{name}  ({via}, {remote_dir})")


def _ssh_alias(name):
    """
    ssh's settings for `name` when ~/.ssh/config makes it an alias for another
    host, else None. `ssh -G` prints the configuration ssh would use without
    connecting; with no matching Host entry, its hostname is the name itself.
    """
    try:
        result = subprocess.run(['ssh', '-G', name], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    settings = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition(' ')
        settings.setdefault(key.lower(), value.strip())
    if settings.get('hostname', name).lower() == name.lower():
        return None
    return settings


def _ssh_key_login_works(target, port, console) -> bool:
    """
    Whether `target` accepts ssh without a password. BatchMode makes ssh fail
    instead of prompting, which is exactly what the job will meet. Checked
    from here, not the compute node -- a cluster that blocks outbound ssh from
    compute nodes is reported by the job, which then skips sending.
    """
    cmd = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10']
    if port is not None:
        cmd += ['-p', str(port)]
    cmd += [target, 'true']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        result = None
        reason = str(e)
    else:
        reason = (result.stderr or '').strip().splitlines()[-1:] or ['']
        reason = reason[0]
    if result is not None and result.returncode == 0:
        return True
    where = f"{target} (port {port})" if port is not None else target
    console.print(f"[red]Error:[/red] ssh to {where} without a password failed"
                  + (f": {reason}" if reason else ""))
    console.print("[dim]  Set up a key (ssh-copy-id), or give ~/.ssh/config a Host entry named "
                  "like the remote with the User and IdentityFile that work;[/dim]")
    console.print("[dim]  or drop --remote / use --no-remote.[/dim]")
    return False


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

    # Ensure the SBATCH job name matches the expected name before submitting
    if not check_jobname_consistency(script_path, case_dir, 'post', console):
        return

    console.print()
    console.print("[bold cyan]Submitting Postprocessing Job[/bold cyan]")
    console.print()

    # Display job info
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("Case", case_dir.name)
    table.add_row("Script", script_path.name)

    job = _job_exports(args, case_dir, script_path, console, check_remote=True)
    if job is None:
        return
    export_parts, rows = job
    for row in rows:
        table.add_row(*row)

    if hasattr(args, 'dependency') and args.dependency:
        table.add_row("Dependency", f"Wait for job {args.dependency}")

    account_override = getattr(args, 'account', None)
    if account_override:
        table.add_row("Account", f"[bold yellow]{account_override}[/bold yellow]")

    qos_override = getattr(args, 'qos', None)
    if qos_override:
        table.add_row("QOS", f"[bold yellow]{qos_override}[/bold yellow]")

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

        # Add account if specified
        if account_override:
            cmd.append(f'--account={account_override}')

        # Add QOS if specified
        if qos_override:
            cmd.append(f'--qos={qos_override}')

        # Pass overrides via --export so postFlex.sh picks them up
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
            console.print(f"[dim]  run sq watch       # Live queue monitoring[/dim]")
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
    run post full [case_directory] [options]
    run post convert [case_directory] [options]
    run post [case_directory] --cleanup-only | --show

{Colors.BOLD}SUBCOMMANDS:{Colors.RESET}
    {Colors.YELLOW}full{Colors.RESET}                 Run simPlt then simPlt2Bin
    {Colors.YELLOW}convert{Colors.RESET}              Run simPlt2Bin only (skip simPlt; .plt files must already exist)

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--t1 TSID{Colors.RESET}            Process from this timestep (rounds up to nearest outFreq multiple)
    {Colors.YELLOW}--t2 TSID{Colors.RESET}            Process up to this timestep (rounds down to nearest outFreq multiple)
                         Both also come from context: use t1:N t2:N (or use time:N)
    {Colors.YELLOW}--remote NAME{Colors.RESET}        Send each binary PLT to this remote as soon as it is written
                         (from context: use remote:NAME). Needs ssh key login.
    {Colors.YELLOW}--no-remote{Colors.RESET}          Do not send, even with a remote context set
    {Colors.YELLOW}--freq N{Colors.RESET}             Override output frequency from simflow.config
    {Colors.YELLOW}--partition NAME{Colors.RESET}     Apply partition header to script
    {Colors.YELLOW}--cleanup{Colors.RESET}            Clean up files with binary PLT before submitting
    {Colors.YELLOW}--cleanup-only{Colors.RESET}       Only perform cleanup, don't submit job
    {Colors.YELLOW}--dependency JOB_ID{Colors.RESET}  Wait for another job to complete first
    {Colors.YELLOW}--dry-run{Colors.RESET}            Show what would be submitted
    {Colors.YELLOW}--show{Colors.RESET}               Display the script content
    {Colors.YELLOW}-h, --help{Colors.RESET}           Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Submit postprocessing
    run post full Case001

    # Submit from context
    use case:Case001
    run post full

    # Cleanup first, then submit
    run post full Case001 --cleanup

    # Only cleanup, don't submit
    run post Case001 --cleanup-only

    # Convert existing .plt files to binary only
    run post convert Case001

    # Process up to timestep 5000
    run post full Case001 --t2 5000

    # Send each binary PLT to the remote 'ws' as soon as it is written
    run post full Case001 --remote ws

    # Same, from context
    use remote:ws
    run post full Case001

    # Chain after main simulation
    run post full Case001 --dependency 12345

    # Apply partition header before submission
    run post full Case001 --partition shared

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
    3. With --remote: sends each binary PLT as soon as it is finished

{Colors.BOLD}SENDING TO A REMOTE (--remote):{Colors.RESET}
    • Files go where `case upload binary` puts them: <remote path>/<case>/binary/
    • Only key-based ssh is used (no password); run post checks the login
      before submitting, and refuses if it would prompt
    • If ~/.ssh/config has a Host named like the remote (`ssh cloud`), that
      alias is used, with its User, IdentityFile and Port
    • A file is sent once simPlt2Bin has not changed it for 30 s; after
      simPlt2Bin ends, the rest is sent. rsync when both ends have it, else
      streamed over ssh into a temporary name, size-checked, then renamed
      (needs only a shell on the remote) -- never a half-written file
    • Only files this job writes, for steps in --t1/--t2, are sent
    • A failed transfer does not fail the job: it is listed in the job
      output and post_sent_<jobid>.log, with the case upload command to
      send it later
    • Needs a postFlex.sh from the current template:
      template script post <case> --force

    Note: Both steps can take significant time (hours for large simulations)

{Colors.BOLD}TYPICAL WORKFLOW:{Colors.RESET}
    # Option 1: Chain entire workflow
    run pre Case001              # Get job ID: 100
    run main --dependency 100    # Get job ID: 101
    run post full --dependency 101

    # Option 2: Cleanup between runs
    run post full Case001 --cleanup   # Clean old files, process new ones

    # Option 3: Just cleanup
    run post Case001 --cleanup-only

{Colors.BOLD}AFTER SUBMISSION:{Colors.RESET}
    {Colors.GREEN}Monitor job status:{Colors.RESET}
    • run sq              # Show all your jobs
    • run sq watch       # Live queue monitoring
    • squeue -j <job_id>  # Check specific job

    {Colors.GREEN}Check results:{Colors.RESET}
    • Binary PLT files will be in binary/ directory
    • Use visualization tools to analyze results
""")
