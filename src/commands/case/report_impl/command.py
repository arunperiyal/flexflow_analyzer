"""case report — compact table of all cases listed in .cases."""

import os
import re
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import box


def _get_context_rundir() -> 'str | None':
    """Return the rundir set via 'use rundir' in the interactive shell, or None."""
    try:
        from src.cli.interactive import InteractiveShell
        if hasattr(InteractiveShell, '_instance') and InteractiveShell._instance:
            return InteractiveShell._instance._current_rundir
    except Exception:
        pass
    return None


def execute_report(args):
    """Print a compact status table for all cases in .cases."""
    console = Console()

    if hasattr(args, 'help') and args.help:
        _show_help(console)
        return

    show_run  = bool(getattr(args, 'run',  False))
    show_size = bool(getattr(args, 'size', False))

    # Locate .cases file
    search_dir = Path(getattr(args, 'dir', None) or '.').resolve()
    from ..add_impl.command import load_cases_file
    entries = load_cases_file(search_dir)

    if not entries:
        cases_path = search_dir / '.cases'
        console.print()
        console.print(f"[yellow]No .cases file found at {cases_path}[/yellow]")
        console.print("[dim]Run `case add` first to build the registry.[/dim]")
        console.print()
        return

    # Resolve context rundir once (used as fallback when simflow.config has no dir)
    context_rundir = _get_context_rundir() if show_run else None

    console.print()

    tbl = Table(
        title=f"Case Report  ({search_dir})",
        box=box.ROUNDED,
        show_header=True,
        header_style='bold',
    )
    tbl.add_column('Case',              style='cyan', no_wrap=True)
    tbl.add_column('Last (archive)',    justify='right')
    tbl.add_column('Last (binary PLT)', justify='right')
    if show_run:
        tbl.add_column('Last (rundir)', justify='right')
    if show_size:
        tbl.add_column('Disk Usage',    justify='right', style='green')

    for entry in entries:
        case_path = Path(entry['path'])
        name      = entry['name']

        if not case_path.is_dir():
            row = [name, '[red]missing[/red]', '[dim]—[/dim]']
            if show_run:
                row.append('[dim]—[/dim]')
            if show_size:
                row.append('[dim]—[/dim]')
            tbl.add_row(*row)
            continue

        # --- simflow.config (need problem name + dir key) ---
        cfg     = _parse_config(case_path / 'simflow.config')
        problem = cfg.get('problem', '').strip().strip('"').strip("'") or None

        # --- Column 1: last timestep from othd_files/ archive ---
        archive_last = _last_othd_timestep(case_path)
        archive_str  = str(archive_last) if archive_last is not None else '[dim]—[/dim]'

        # --- Column 2: last PLT from binary/ ---
        binary_last = _last_binary_plt_timestep(case_path, problem)
        binary_str  = str(binary_last) if binary_last is not None else '[dim]—[/dim]'

        row = [name, archive_str, binary_str]

        # --- Column 3 (optional): last timestep from rundir ---
        if show_run:
            rundir = _resolve_rundir(case_path, cfg, context_rundir)
            if rundir:
                run_last = _last_othd_timestep_in_dir(rundir)
                run_str  = str(run_last) if run_last is not None else '[dim]—[/dim]'
            else:
                run_str = '[dim]no rundir[/dim]'
            row.append(run_str)

        # --- Column 4 (optional): disk usage ---
        if show_size:
            row.append(_fmt_size(_dir_size(case_path)))

        tbl.add_row(*row)

    console.print(tbl)
    console.print()


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _resolve_rundir(case_path: Path, cfg: dict, context_rundir: 'str | None') -> 'Path | None':
    """
    Determine the run directory for a case.

    Priority: context rundir (absolute) > simflow.config 'dir' key (resolved
    relative to case_path) > None.
    """
    if context_rundir:
        p = Path(context_rundir)
        return p if p.is_dir() else None

    dir_val = cfg.get('dir', '').strip().strip('"').strip("'")
    if dir_val:
        p = Path(dir_val) if Path(dir_val).is_absolute() else case_path / dir_val
        return p if p.is_dir() else None

    return None


def _last_othd_timestep_in_dir(directory: Path):
    """Return the highest timestep across all .othd files directly in directory."""
    files = sorted(directory.glob('*.othd'))
    if not files:
        return None

    max_ts = None
    for fp in files:
        try:
            from ....core.readers.othd_reader import OTHDReader
            reader = OTHDReader(str(fp))
            if reader.tsIds:
                ts = max(reader.tsIds)
                if max_ts is None or ts > max_ts:
                    max_ts = ts
        except Exception:
            continue

    return max_ts


def _last_othd_timestep(case_path: Path):
    """Return the highest end-timestep across all .othd files in othd_files/."""
    othd_dir = case_path / 'othd_files'
    if not othd_dir.is_dir():
        return None
    return _last_othd_timestep_in_dir(othd_dir)


def _last_binary_plt_timestep(case_path: Path, problem: str):
    """
    Return the timestep of the most recently modified PLT file in binary/.
    File names are expected to follow the pattern <problem>.<tsid>.plt.
    """
    binary_dir = case_path / 'binary'
    if not binary_dir.is_dir():
        return None

    pattern = f'{problem}.*.plt' if problem else '*.plt'
    plt_files = list(binary_dir.glob(pattern))
    if not plt_files:
        return None

    # Pick the file with the highest timestep number extracted from the filename
    best_ts = None
    for f in plt_files:
        ts = _extract_plt_step(f.name, problem)
        if ts is not None and (best_ts is None or ts > best_ts):
            best_ts = ts
    return best_ts


def _extract_plt_step(filename: str, problem: str) -> 'int | None':
    """Extract integer timestep from e.g. riser.1050.plt → 1050."""
    stem = filename
    if stem.endswith('.plt'):
        stem = stem[:-4]
    if problem:
        prefix = problem + '.'
        if stem.startswith(prefix):
            rest = stem[len(prefix):]
            m = re.match(r'^(\d+)', rest)
            if m:
                return int(m.group(1))
    else:
        m = re.search(r'\.(\d+)$', stem)
        if m:
            return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Disk usage helpers
# ---------------------------------------------------------------------------

def _dir_size(path: Path) -> int:
    """Return total byte size of all files under path."""
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _fmt_size(n: int) -> str:
    """Human-readable byte size (e.g. 1.4 GB)."""
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024:
            return f"{n} {unit}" if unit == 'B' else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ---------------------------------------------------------------------------
# Config parser
# ---------------------------------------------------------------------------

def _parse_config(cfg_path: Path) -> dict:
    """Minimal parser: returns active (uncommented) key=value pairs."""
    data = {}
    if not cfg_path.exists():
        return data
    try:
        with open(cfg_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, raw = line.partition('=')
                key = key.strip()
                val = re.split(r'\s*#', raw, maxsplit=1)[0].strip().strip('"').strip("'")
                if key:
                    data[key] = val
    except OSError:
        pass
    return data


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

def _show_help(console):
    console.print()
    console.print("[bold cyan]case report[/bold cyan] — Compact status table for all registered cases")
    console.print()
    console.print("[bold]USAGE:[/bold]")
    console.print("    case report [--dir PATH] [--run] [--size]")
    console.print()
    console.print("[bold]OPTIONS:[/bold]")
    console.print("    --dir PATH    Directory containing .cases file (default: current directory)")
    console.print("    --run         Add column with last timestep from each case's run directory")
    console.print("    --size        Add column with total disk usage of each case")
    console.print("    -h, --help    Show this help message")
    console.print()
    console.print("[bold]COLUMNS:[/bold]")
    console.print("    Case              Case directory name")
    console.print("    Last (archive)    Highest timestep across all .othd files in othd_files/")
    console.print("    Last (binary PLT) Timestep of the most recently modified PLT in binary/")
    console.print("    Last (rundir)     Highest timestep from .othd files in run directory (--run)")
    console.print("    Disk Usage        Total size of the case directory (--size)")
    console.print()
    console.print("[bold]EXAMPLES:[/bold]")
    console.print("    case report")
    console.print("    case report --dir /scratch/me/project")
    console.print()
