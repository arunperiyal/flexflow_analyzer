"""
Case status command implementation.

Checks the completeness of case data files.
"""

import os
from pathlib import Path
from typing import Optional, List, Set, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from ....core.case import FlexFlowCase
from ....core.readers.othd_reader import OTHDReader
from ....core.readers.oisd_reader import OISDReader


def execute_status(args):
    """Execute case status command."""
    console = Console()

    # Get case directory
    case_path = args.case if hasattr(args, 'case') and args.case else os.getcwd()
    case_path = Path(case_path).resolve()

    if not case_path.exists():
        console.print(f"[red]Error:[/red] Case directory not found: {case_path}")
        return

    # Load case
    try:
        case = FlexFlowCase(str(case_path))
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to load case: {e}")
        return

    # Display header
    console.print()
    console.print(Panel(
        f"[bold cyan]Case Status:[/bold cyan] {case_path.name}\n"
        f"[dim]Path: {case_path}[/dim]",
        border_style="cyan",
        box=box.ROUNDED
    ))
    console.print()

    # Determine time step range and frequency
    freq = get_frequency(case, case_path)
    if not freq:
        console.print("[yellow]Warning:[/yellow] Could not determine frequency from config or output files")
        console.print("[dim]Status check requires frequency information[/dim]")
        return

    time_steps = get_expected_time_steps(case, case_path, freq)
    if not time_steps:
        console.print("[yellow]Warning:[/yellow] Could not determine time step range")
        return

    console.print(f"[cyan]Frequency:[/cyan] {freq}")
    console.print(f"[cyan]Expected time steps:[/cyan] {min(time_steps)} to {max(time_steps)} ({len(time_steps)} steps)")
    console.print()

    # Check each file type
    plt_status, plt_coverage = check_plt_files(case_path, case.problem_name, time_steps)
    othd_status, othd_coverage = check_othd_files(case_path, time_steps)
    oisd_status, oisd_coverage = check_oisd_files(case_path, time_steps)

    # Display results table
    table = Table(title="Data File Status", box=box.ROUNDED, show_header=True)
    table.add_column("File Type", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Coverage", justify="right", style="yellow")

    # PLT files
    status_text = "[green]Complete[/green]" if plt_status else "[red]Incomplete[/red]"
    coverage_text = f"{plt_coverage:.1f}%"
    table.add_row("PLT files (binary/)", status_text, coverage_text)

    # OTHD files
    status_text = "[green]Complete[/green]" if othd_status else "[red]Incomplete[/red]"
    coverage_text = f"{othd_coverage:.1f}%"
    table.add_row("OTHD files (othd_files/)", status_text, coverage_text)

    # OISD files
    status_text = "[green]Complete[/green]" if oisd_status else "[red]Incomplete[/red]"
    coverage_text = f"{oisd_coverage:.1f}%"
    table.add_row("OISD files (oisd_files/)", status_text, coverage_text)

    console.print(table)
    console.print()

    # Overall status
    overall_complete = plt_status and othd_status and oisd_status

    if overall_complete:
        console.print(Panel(
            "[bold green]✓ Case is COMPLETE[/bold green]\n"
            "All data files are present for all time steps",
            border_style="green",
            box=box.ROUNDED
        ))
    else:
        console.print(Panel(
            "[bold red]✗ Case is INCOMPLETE[/bold red]\n"
            "Some data files are missing",
            border_style="red",
            box=box.ROUNDED
        ))
    console.print()


def get_output_directory(case: FlexFlowCase, case_path: Path) -> Optional[Path]:
    """Get output directory from case config."""
    if 'dir' not in case.config:
        return None

    output_dir_str = case.config['dir']

    if not os.path.isabs(output_dir_str):
        output_dir_path = case_path / output_dir_str
    else:
        output_dir_path = Path(output_dir_str)

    return output_dir_path


def get_frequency(case: FlexFlowCase, case_path: Path) -> Optional[int]:
    """Get output frequency from config or auto-detect."""
    # Try simflow.config
    if 'outFreq' in case.config:
        try:
            return int(case.config['outFreq'])
        except ValueError:
            pass

    # Auto-detect from output files
    return auto_detect_frequency(case_path, case.problem_name, case)


def auto_detect_frequency(case_path: Path, problem: str, case: FlexFlowCase) -> Optional[int]:
    """Auto-detect frequency from output file time steps."""
    # Get output directory from config
    output_dir_path = get_output_directory(case, case_path)
    if not output_dir_path or not output_dir_path.exists():
        return None

    out_pattern = f'{problem}.*_*.out'

    steps = []
    for file in output_dir_path.glob(out_pattern):
        step = extract_step_from_filename(file.name, problem)
        if step is not None:
            steps.append(step)

    if len(steps) < 2:
        return None

    steps.sort()

    # Find smallest gap
    min_gap = min(steps[i+1] - steps[i] for i in range(len(steps) - 1))
    return min_gap


def extract_step_from_filename(filename: str, problem: str) -> Optional[int]:
    """Extract time step from filename."""
    import re
    # Pattern: {problem}.{step}_*.out or {problem}.{step}_*.rst
    pattern = rf'{re.escape(problem)}\.(\d+)_.*\.(?:out|rst)'
    match = re.match(pattern, filename)
    if match:
        return int(match.group(1))
    return None


def get_expected_time_steps(case: FlexFlowCase, case_path: Path, freq: int) -> Set[int]:
    """
    Determine expected time steps from output files.

    Returns a set of time steps that should exist based on frequency.
    """
    # Get output directory from config
    output_dir_path = get_output_directory(case, case_path)
    if not output_dir_path or not output_dir_path.exists():
        return set()

    problem = case.problem_name
    out_pattern = f'{problem}.*_*.out'

    steps = set()
    for file in output_dir_path.glob(out_pattern):
        step = extract_step_from_filename(file.name, problem)
        if step is not None:
            steps.add(step)

    if not steps:
        return set()

    # Return all steps that are multiples of frequency
    min_step = min(steps)
    max_step = max(steps)

    expected_steps = set()
    step = min_step
    while step <= max_step:
        expected_steps.add(step)
        step += freq

    return expected_steps


def check_plt_files(case_path: Path, problem: str, expected_steps: Set[int]) -> Tuple[bool, float]:
    """
    Check PLT files in binary directory.

    Returns:
        Tuple of (is_complete, coverage_percentage)
    """
    binary_dir = case_path / 'binary'

    if not binary_dir.exists():
        return False, 0.0

    found_steps = set()

    # Find all PLT files: {problem}.{step}.plt
    for plt_file in binary_dir.glob(f'{problem}.*.plt'):
        import re
        pattern = rf'{re.escape(problem)}\.(\d+)\.plt'
        match = re.match(pattern, plt_file.name)
        if match:
            step = int(match.group(1))
            found_steps.add(step)

    if not expected_steps:
        return False, 0.0

    coverage = (len(found_steps & expected_steps) / len(expected_steps)) * 100
    is_complete = found_steps >= expected_steps

    return is_complete, coverage


def check_othd_files(case_path: Path, expected_steps: Set[int]) -> Tuple[bool, float]:
    """
    Check OTHD files coverage.

    Returns:
        Tuple of (is_complete, coverage_percentage)
    """
    othd_dir = case_path / 'othd_files'

    if not othd_dir.exists():
        return False, 0.0

    othd_files = list(othd_dir.glob('*.othd'))

    if not othd_files:
        return False, 0.0

    # Collect all time steps covered by OTHD files
    covered_steps = set()

    for othd_file in othd_files:
        try:
            reader = OTHDReader(str(othd_file))
            covered_steps.update(reader.tsIds)
        except Exception:
            # Skip files that can't be read
            continue

    if not expected_steps:
        return False, 0.0

    coverage = (len(covered_steps & expected_steps) / len(expected_steps)) * 100
    is_complete = expected_steps.issubset(covered_steps)

    return is_complete, coverage


def check_oisd_files(case_path: Path, expected_steps: Set[int]) -> Tuple[bool, float]:
    """
    Check OISD files coverage.

    Returns:
        Tuple of (is_complete, coverage_percentage)
    """
    oisd_dir = case_path / 'oisd_files'

    if not oisd_dir.exists():
        return False, 0.0

    oisd_files = list(oisd_dir.glob('*.oisd'))

    if not oisd_files:
        return False, 0.0

    # Collect all time steps covered by OISD files
    covered_steps = set()

    for oisd_file in oisd_files:
        try:
            reader = OISDReader(str(oisd_file))
            covered_steps.update(reader.tsIds)
        except Exception:
            # Skip files that can't be read
            continue

    if not expected_steps:
        return False, 0.0

    coverage = (len(covered_steps & expected_steps) / len(expected_steps)) * 100
    is_complete = expected_steps.issubset(covered_steps)

    return is_complete, coverage
