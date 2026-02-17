"""case report — compact table of all cases listed in .cases."""

import re
import os
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import box


def execute_report(args):
    """Print a compact status table for all cases in .cases."""
    console = Console()

    if hasattr(args, 'help') and args.help:
        _show_help(console)
        return

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

    console.print()

    tbl = Table(
        title=f"Case Report  ({search_dir})",
        box=box.ROUNDED,
        show_header=True,
        header_style='bold',
    )
    tbl.add_column('Case',              style='cyan',   no_wrap=True)
    tbl.add_column('Last (archive)',    justify='right')
    tbl.add_column('Last (binary PLT)', justify='right')
    tbl.add_column('Rundir size',       justify='right')

    for entry in entries:
        case_path = Path(entry['path'])
        name      = entry['name']

        if not case_path.is_dir():
            tbl.add_row(name, '[red]missing[/red]', '—', '—')
            continue

        # --- simflow.config (need problem name and run dir) ---
        cfg          = _parse_config(case_path / 'simflow.config')
        problem      = cfg.get('problem', '').strip().strip('"').strip("'") or None
        raw_dir      = cfg.get('dir', '').strip().strip('"').strip("'")
        run_dir_path = None
        if raw_dir:
            rd = Path(raw_dir)
            run_dir_path = rd if rd.is_absolute() else (case_path / rd).resolve()

        # --- Column 1: last timestep from othd_files/ archive ---
        archive_last = _last_othd_timestep(case_path)
        archive_str  = str(archive_last) if archive_last is not None else '[dim]—[/dim]'

        # --- Column 2: last PLT from binary/ (by modification time) ---
        binary_last = _last_binary_plt_timestep(case_path, problem)
        binary_str  = str(binary_last) if binary_last is not None else '[dim]—[/dim]'

        # --- Column 3: rundir size ---
        size_str = '[dim]—[/dim]'
        if run_dir_path and run_dir_path.is_dir():
            size_bytes = _dir_size(run_dir_path)
            size_str   = _fmt_size(size_bytes)

        tbl.add_row(name, archive_str, binary_str, size_str)

    console.print(tbl)
    console.print()


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _last_othd_timestep(case_path: Path):
    """Return the highest end-timestep across all .othd files in othd_files/."""
    othd_dir = case_path / 'othd_files'
    if not othd_dir.is_dir():
        return None

    files = sorted(othd_dir.glob('*.othd'))
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

    # Pick the file with the latest modification time
    newest = max(plt_files, key=lambda f: f.stat().st_mtime)

    # Extract timestep from filename
    ts = _extract_plt_step(newest.name, problem)
    return ts


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


def _dir_size(directory: Path) -> int:
    """Return total size in bytes of all files directly inside *directory* (non-recursive)."""
    total = 0
    try:
        with os.scandir(directory) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False):
                    try:
                        total += entry.stat().st_size
                    except OSError:
                        pass
    except OSError:
        pass
    return total


def _fmt_size(n: int) -> str:
    """Human-readable file size."""
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != 'B' else f"{n} B"
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
    console.print("    case report [--dir PATH]")
    console.print()
    console.print("[bold]OPTIONS:[/bold]")
    console.print("    --dir PATH    Directory containing .cases file (default: current directory)")
    console.print("    -h, --help    Show this help message")
    console.print()
    console.print("[bold]COLUMNS:[/bold]")
    console.print("    Case              Case directory name")
    console.print("    Last (archive)    Highest timestep across all .othd files in othd_files/")
    console.print("    Last (binary PLT) Timestep of the most recently modified PLT in binary/")
    console.print("    Rundir size       Total size of files in the active run directory")
    console.print()
    console.print("[bold]EXAMPLES:[/bold]")
    console.print("    case report")
    console.print("    case report --dir /scratch/me/project")
    console.print()
