"""Shared helper functions for run subcommands."""

from pathlib import Path
from typing import Optional, Callable
from rich.console import Console
from rich.table import Table
from rich import box


def get_case_name_and_base_dir():
    """Get current case name and base directory from interactive context."""
    from src.cli.interactive import InteractiveShell
    
    case_name = None
    base_dir = Path.cwd()
    
    if hasattr(InteractiveShell, '_instance') and InteractiveShell._instance:
        shell = InteractiveShell._instance
        case_name = shell._current_case
        base_dir = shell._current_dir
    
    return case_name, base_dir


def is_wildcard_case(case_name: Optional[str]) -> bool:
    """Check if case name is '*' (wildcard for all cases)."""
    return case_name == "*"


def load_cases_from_directory(base_dir: Path):
    """Load cases from .cases file in base directory."""
    from .. import case_iteration
    return case_iteration.load_cases_from_directory(base_dir)


def execute_on_all_cases(case_name: str, base_dir: Path, action: Callable, action_name: str):
    """
    Execute an action on all cases from .cases file.
    
    Args:
        case_name: Should be "*" (wildcard marker)
        base_dir: Base directory containing .cases file
        action: Callable that takes (case_path: Path, case_name: str) and executes action
        action_name: Display name of action (e.g., "Main simulation", "Pre-processing")
    """
    cases = load_cases_from_directory(base_dir)
    if not cases:
        print(f"Error: No cases found in .cases file")
        return
    
    console = Console()
    console.print(f"\n[cyan]{'─' * 70}[/cyan]")
    console.print(f"[green]Executing {action_name} on {len(cases)} cases[/green]")
    console.print(f"[cyan]{'─' * 70}[/cyan]\n")

    for case_idx, case_entry in enumerate(cases, 1):
        case_path = Path(case_entry['path'])
        case_display_name = case_entry['name']

        console.print(f"[cyan]{'─' * 70}[/cyan]")
        console.print(f"[green]Case {case_idx}/{len(cases)}:[/green] [cyan]{case_display_name}[/cyan]")
        console.print(f"[dim]Path: {case_path}[/dim]")
        console.print(f"[cyan]{'─' * 70}[/cyan]\n")

        if not case_path.exists():
            console.print(f"[red]Error:[/red] Case directory not found: {case_path}\n")
            continue

        try:
            action(case_path, case_display_name)
        except Exception as e:
            console.print(f"[red]Error executing {action_name}:[/red] {e}\n")

    console.print(f"[cyan]{'─' * 70}[/cyan]")
    console.print(f"[green]✓ Completed {action_name} on {len(cases)} cases[/green]")
    console.print(f"[cyan]{'─' * 70}[/cyan]\n")


def apply_partition_header(script_path: Path, partition: str, script_type: str, console) -> bool:
    """
    Replace the #SBATCH header block in *script_path* with the contents of
    src/templates/scripts/headers/<partition>.header.

    Args:
        script_path: Path to the job script file
        partition: Partition name (e.g. 'shared', 'medium')
        script_type: Script type ('pre', 'main', 'post') for {SCRIPT_TYPE} substitution
        console: Rich console for warnings

    Returns:
        True if a header file was found and applied, False otherwise.
    """
    # Locate the header file relative to this source file
    headers_dir = Path(__file__).parent.parent.parent / 'templates' / 'scripts' / 'headers'
    header_file = headers_dir / f'{partition}.header'

    if not header_file.exists():
        return False

    # Read header template and substitute {CASE_NAME} and {SCRIPT_TYPE}
    case_name = script_path.parent.name
    header_text = header_file.read_text()
    header_text = header_text.replace('{CASE_NAME}', case_name)
    header_text = header_text.replace('{SCRIPT_TYPE}', script_type)

    # Read the script and replace its #SBATCH block
    script_text = script_path.read_text()
    lines = script_text.splitlines(keepends=True)

    # Find the span of #SBATCH lines (may start after #!/bin/bash)
    sbatch_start = None
    sbatch_end = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('#SBATCH'):
            if sbatch_start is None:
                sbatch_start = i
            sbatch_end = i

    if sbatch_start is None:
        console.print(f"[yellow]Warning: no #SBATCH lines found in {script_path.name} — header not applied[/yellow]")
        return False

    new_lines = (
        lines[:sbatch_start]
        + [header_text if header_text.endswith('\n') else header_text + '\n']
        + lines[sbatch_end + 1:]
    )
    script_path.write_text(''.join(new_lines))
    return True


# ---------------------------------------------------------------------------
# Job name consistency (#SBATCH -J / --job-name)
#
# FlexFlow convention (see templates/scripts/*.sh) is <script_type><case_name>,
# e.g. pre<case>, main<case>, post<case>.
# ---------------------------------------------------------------------------

def parse_script_jobname(script_path):
    """Parse #SBATCH -J / --job-name from a job script (returns str or None)."""
    import re
    try:
        with open(script_path) as f:
            for line in f:
                line = line.strip()
                if not line.startswith('#SBATCH'):
                    continue
                body = line[7:].strip()
                m = re.match(r'(?:-J|--job-name)[=\s]+(\S+)', body)
                if m:
                    return m.group(1).split('#')[0]
    except Exception:
        pass
    return None


def set_script_jobname(script_path: Path, job_name: str, console) -> bool:
    """
    Update #SBATCH -J/--job-name in the script.

    If no job-name directive exists, add one after the SBATCH header block.
    """
    import re

    try:
        lines = script_path.read_text().splitlines(keepends=True)
    except Exception as e:
        console.print(f"[red]Error reading {script_path.name}: {e}[/red]")
        return False

    jobname_pattern = re.compile(r'(^\s*#SBATCH\s+(?:-J|--job-name)(?:=|\s+))\S+')
    updated = False

    for i, line in enumerate(lines):
        if jobname_pattern.search(line):
            lines[i] = jobname_pattern.sub(lambda m: m.group(1) + job_name, line, count=1)
            updated = True

    if not updated:
        insert_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith('#SBATCH'):
                insert_idx = i + 1
        new_line = f"#SBATCH --job-name={job_name}\n"
        if insert_idx is not None:
            lines.insert(insert_idx, new_line)
        elif lines and lines[0].startswith('#!'):
            lines.insert(1, new_line)
        else:
            lines.insert(0, new_line)

    try:
        script_path.write_text(''.join(lines))
        console.print(f"[dim]Updated {script_path.name}: --job-name={job_name}[/dim]")
        console.print()
        return True
    except Exception as e:
        console.print(f"[red]Error updating {script_path.name}: {e}[/red]")
        return False


def check_jobname_consistency(script_path, case_dir, script_type: str, console) -> bool:
    """
    Compare the SBATCH job name in the script with the expected name.

    The expected name is ``<script_type><case_name>`` (e.g. ``main<case>``),
    matching templates/scripts/*.sh. On mismatch (or a missing job name)
    offers to set the job to the expected name, submit anyway, or abort.

    Returns True to proceed with submission, False to abort.
    """
    case_name = case_dir.name
    expected = f'{script_type}{case_name}'
    job_name = parse_script_jobname(script_path)

    # Matches — nothing to do.
    if job_name is not None and job_name == expected:
        return True

    console.print()
    if job_name is None:
        console.print(
            f"[bold yellow]⚠  No #SBATCH job name found in {script_path.name}[/bold yellow]"
        )
        console.print(f"[dim]Expected job name: {expected}[/dim]")
        console.print()
        console.print(f"  1. Set job name to '{expected}' and submit")
        console.print("  2. Submit anyway (no job name)")
        console.print("  3. Abort")
    else:
        console.print("[bold yellow]⚠  Job name does not match the expected name[/bold yellow]")
        tbl = Table(box=box.SIMPLE, show_header=False)
        tbl.add_column("Field", style="cyan")
        tbl.add_column("Value")
        tbl.add_row("Expected job name", expected)
        tbl.add_row("Current job name",  job_name)
        console.print(tbl)
        console.print()
        console.print(f"  1. Rename job to '{expected}' and submit")
        console.print("  2. Submit anyway (keep current job name)")
        console.print("  3. Abort")

    console.print()
    console.print('Choice [1/2/3]: ', end='')

    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print()
        console.print('[yellow]Aborted[/yellow]')
        return False

    if answer in {'1', 'r', 'f'}:
        if set_script_jobname(script_path, expected, console):
            return True
        console.print("[yellow]Aborting — fix the script manually and re-run[/yellow]")
        return False

    if answer in {'2', 's'}:
        return True

    console.print('[yellow]Aborted[/yellow]')
    console.print()
    return False


def show_jobname_info(script_path, case_dir, script_type: str, console):
    """Print an expected vs current job-name comparison (no prompt). Used by dry-run."""
    expected = f'{script_type}{case_dir.name}'
    job_name = parse_script_jobname(script_path)

    tbl = Table(box=box.SIMPLE, show_header=True, header_style='bold')
    tbl.add_column('Parameter', style='cyan')
    tbl.add_column('Expected',  justify='right', style='yellow')
    tbl.add_column('Job name',  justify='right', style='blue')
    tbl.add_column('Match?',    justify='center')

    job_name_str = job_name if job_name is not None else '[dim](not set)[/dim]'
    match_icon = '[green]✓[/green]' if job_name == expected else '[red]✗[/red]'
    tbl.add_row('job name', expected, job_name_str, match_icon)

    console.print('[bold]Job name check:[/bold]')
    console.print(tbl)
    console.print()
