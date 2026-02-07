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
        f"[bold cyan]Case Status Check[/bold cyan]\n"
        f"[white]Case:[/white] {case_path.name}\n"
        f"[white]Problem:[/white] {case.problem_name}",
        border_style="cyan",
        box=box.DOUBLE
    ))

    # Determine time step range and frequency
    freq = get_frequency(case, case_path)
    if not freq:
        console.print()
        console.print("[yellow]⚠[/yellow]  Could not determine frequency from config or output files")
        console.print("[dim]   Status check requires frequency information[/dim]")
        console.print()
        return

    # Get expected time steps for output files (at frequency intervals)
    output_time_steps = get_expected_time_steps(case, case_path, freq)
    if not output_time_steps:
        console.print()
        console.print("[yellow]⚠[/yellow]  Could not determine time step range")
        console.print()
        return

    # Get expected time steps for OTHD/OISD files (all time steps)
    all_time_steps = get_all_time_steps(case, case_path)
    if not all_time_steps:
        console.print()
        console.print("[yellow]⚠[/yellow]  Could not determine full time step range")
        console.print()
        return

    # Check each file type
    # PLT files should match frequency intervals (output steps)
    plt_status, plt_coverage = check_plt_files(case_path, case.problem_name, output_time_steps)
    # OTHD/OISD files should have all time steps
    othd_status, othd_coverage = check_othd_files(case_path, all_time_steps)
    oisd_status, oisd_coverage = check_oisd_files(case_path, all_time_steps)

    # Check output directory progress
    output_dir_path = get_output_directory(case, case_path)
    out_progress, rst_progress, plt_out_progress, othd_out_progress, oisd_out_progress = check_output_directory_progress(
        output_dir_path, case.problem_name, output_time_steps, all_time_steps
    )

    # Display simulation info
    console.print()
    console.print("[bold cyan]Simulation Configuration[/bold cyan]")
    console.print(f"  Output Frequency:  [yellow]{freq}[/yellow] steps")
    console.print(f"  Output Steps:      [yellow]{min(output_time_steps)}[/yellow] → [yellow]{max(output_time_steps)}[/yellow]  ([dim]{len(output_time_steps)} steps[/dim])")
    console.print(f"  Total Steps:       [yellow]{min(all_time_steps)}[/yellow] → [yellow]{max(all_time_steps)}[/yellow]  ([dim]{len(all_time_steps)} steps[/dim])")

    # Display data file status
    console.print()
    console.print("[bold cyan]Data Files (Final Storage)[/bold cyan]")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Type", style="white", width=25)
    table.add_column("Location", style="dim", width=20)
    table.add_column("Status", justify="center", width=12)
    table.add_column("Coverage", justify="right", style="yellow", width=10)

    # PLT files
    status_icon = "[green]✓[/green]" if plt_status else "[red]✗[/red]"
    status_text = "[green]Complete[/green]" if plt_status else "[red]Incomplete[/red]"
    table.add_row("  Binary PLT files", "binary/", status_icon + " " + status_text, f"{plt_coverage:.1f}%")

    # OTHD files
    status_icon = "[green]✓[/green]" if othd_status else "[red]✗[/red]"
    status_text = "[green]Complete[/green]" if othd_status else "[red]Incomplete[/red]"
    table.add_row("  OTHD files", "othd_files/", status_icon + " " + status_text, f"{othd_coverage:.1f}%")

    # OISD files
    status_icon = "[green]✓[/green]" if oisd_status else "[red]✗[/red]"
    status_text = "[green]Complete[/green]" if oisd_status else "[red]Incomplete[/red]"
    table.add_row("  OISD files", "oisd_files/", status_icon + " " + status_text, f"{oisd_coverage:.1f}%")

    console.print(table)

    # Display output directory progress
    if output_dir_path and output_dir_path.exists():
        console.print()
        console.print("[bold cyan]Output Directory (Work in Progress)[/bold cyan]")
        console.print(f"  [dim]Location: {output_dir_path.relative_to(case_path) if output_dir_path.is_relative_to(case_path) else output_dir_path}[/dim]")
        console.print()

        progress_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        progress_table.add_column("Type", style="white", width=25)
        progress_table.add_column("Progress", justify="right", style="yellow", width=10)
        progress_table.add_column("Bar", width=30)

        # Helper function to create progress bar
        def make_bar(percentage: float) -> str:
            filled = int(percentage / 5)  # 20 blocks = 100%
            empty = 20 - filled
            if percentage == 100.0:
                return f"[green]{'█' * filled}[/green]"
            elif percentage >= 75.0:
                return f"[yellow]{'█' * filled}[/yellow][dim]{'░' * empty}[/dim]"
            elif percentage >= 50.0:
                return f"[yellow]{'█' * filled}[/yellow][dim]{'░' * empty}[/dim]"
            else:
                return f"[red]{'█' * filled}[/red][dim]{'░' * empty}[/dim]"

        progress_table.add_row("  OUT files", f"{out_progress:.1f}%", make_bar(out_progress))
        progress_table.add_row("  RST files", f"{rst_progress:.1f}%", make_bar(rst_progress))
        progress_table.add_row("  PLT files (ASCII)", f"{plt_out_progress:.1f}%", make_bar(plt_out_progress))
        progress_table.add_row("  OTHD files", f"{othd_out_progress:.1f}%", make_bar(othd_out_progress))
        progress_table.add_row("  OISD files", f"{oisd_out_progress:.1f}%", make_bar(oisd_out_progress))

        console.print(progress_table)

    # Overall status
    console.print()
    overall_complete = plt_status and othd_status and oisd_status

    if overall_complete:
        console.print(Panel(
            "[bold green]✓ COMPLETE[/bold green]\n"
            "[white]All data files are present for all expected time steps[/white]",
            border_style="green",
            box=box.HEAVY
        ))
    else:
        console.print(Panel(
            "[bold red]✗ INCOMPLETE[/bold red]\n"
            "[white]Some data files are missing or incomplete[/white]",
            border_style="red",
            box=box.HEAVY
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

    Returns the set of time steps that actually exist (multiples of frequency).
    This represents what we expect for complete output.
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
            # Only include steps that are multiples of frequency (but not step 0)
            if step > 0 and step % freq == 0:
                steps.add(step)

    return steps


def get_all_time_steps(case: FlexFlowCase, case_path: Path) -> Set[int]:
    """
    Get all time steps (for OTHD/OISD files).

    OTHD/OISD files contain all time steps from the simulation,
    not just ones at frequency intervals.

    Returns a set from 1 to maxTimeSteps.
    """
    # Try to get maxTimeSteps from .def file
    max_steps = get_max_timesteps_from_def(case_path, case.problem_name)

    if max_steps:
        return set(range(1, max_steps + 1))

    # Fallback: get from existing OTHD/OISD files
    return get_timesteps_from_data_files(case_path)


def get_max_timesteps_from_def(case_path: Path, problem: str) -> Optional[int]:
    """Get maxTimeSteps from .def file."""
    import re

    def_file = case_path / f'{problem}.def'
    if not def_file.exists():
        return None

    try:
        with open(def_file, 'r') as f:
            content = f.read()
            # Look for maxTimeSteps = value
            match = re.search(r'maxTimeSteps\s*=\s*(\d+)', content)
            if match:
                return int(match.group(1))
    except Exception:
        pass

    return None


def get_timesteps_from_data_files(case_path: Path) -> Set[int]:
    """Get time steps from existing OTHD files."""
    othd_dir = case_path / 'othd_files'

    if not othd_dir.exists():
        return set()

    othd_files = list(othd_dir.glob('*.othd'))
    if not othd_files:
        return set()

    all_steps = set()

    for othd_file in othd_files:
        try:
            reader = OTHDReader(str(othd_file))
            all_steps.update(reader.tsIds)
        except Exception:
            continue

    return all_steps


def check_output_directory_progress(
    output_dir: Optional[Path],
    problem: str,
    output_steps: Set[int],
    all_steps: Set[int]
) -> Tuple[float, float, float, float, float]:
    """
    Check progress of files in output directory.

    Returns:
        Tuple of (out_progress, rst_progress, plt_progress, othd_progress, oisd_progress)
    """
    if not output_dir or not output_dir.exists():
        return 0.0, 0.0, 0.0, 0.0, 0.0

    # Check .out files (should match output_steps)
    out_files = list(output_dir.glob(f'{problem}.*_*.out'))
    out_steps = set()
    for file in out_files:
        step = extract_step_from_filename(file.name, problem)
        if step:
            out_steps.add(step)

    out_progress = (len(out_steps & output_steps) / len(output_steps) * 100) if output_steps else 0.0

    # Check .rst files (should match output_steps)
    rst_files = list(output_dir.glob(f'{problem}.*_*.rst'))
    rst_steps = set()
    for file in rst_files:
        step = extract_step_from_filename(file.name, problem)
        if step:
            rst_steps.add(step)

    rst_progress = (len(rst_steps & output_steps) / len(output_steps) * 100) if output_steps else 0.0

    # Check ASCII PLT files (should match output_steps)
    plt_files = list(output_dir.glob(f'{problem}.*.plt'))
    plt_steps = set()
    for file in plt_files:
        step = extract_plt_step(file.name, problem)
        if step:
            plt_steps.add(step)

    plt_progress = (len(plt_steps & output_steps) / len(output_steps) * 100) if output_steps else 0.0

    # Check OTHD files in output directory (should have all_steps)
    othd_files = list(output_dir.glob('*.othd'))
    othd_steps = set()
    for othd_file in othd_files:
        try:
            reader = OTHDReader(str(othd_file))
            othd_steps.update(reader.tsIds)
        except Exception:
            continue

    othd_progress = (len(othd_steps & all_steps) / len(all_steps) * 100) if all_steps else 0.0

    # Check OISD files in output directory (should have all_steps)
    oisd_files = list(output_dir.glob('*.oisd'))
    oisd_steps = set()
    for oisd_file in oisd_files:
        try:
            reader = OISDReader(str(oisd_file))
            oisd_steps.update(reader.tsIds)
        except Exception:
            continue

    oisd_progress = (len(oisd_steps & all_steps) / len(all_steps) * 100) if all_steps else 0.0

    return out_progress, rst_progress, plt_progress, othd_progress, oisd_progress


def extract_plt_step(filename: str, problem: str) -> Optional[int]:
    """Extract time step from PLT filename."""
    import re
    # Pattern: {problem}.{step}.plt
    pattern = rf'{re.escape(problem)}\.(\d+)\.plt'
    match = re.match(pattern, filename)
    if match:
        return int(match.group(1))
    return None


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
