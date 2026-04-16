"""Shared helper functions for run subcommands."""

from pathlib import Path
from typing import Optional, Callable
from rich.console import Console


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
    from ...case_iteration import load_cases_from_directory as load_cases
    return load_cases(base_dir)


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
