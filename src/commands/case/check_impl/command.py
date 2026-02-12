"""
Case check command implementation

Checks OTHD/OISD file time step ranges in the run directory and/or
archive directories, and validates simflow.config consistency.
"""

import re
import sys
from pathlib import Path
from typing import Optional, List, Tuple

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from ....utils.logger import Logger
from ....utils.colors import Colors


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def execute_case_check(args):
    """Execute the case check command."""
    from .help_messages import print_check_help

    if hasattr(args, 'help') and args.help:
        print_check_help()
        return

    if hasattr(args, 'examples') and args.examples:
        print_check_help()
        return

    do_run     = getattr(args, 'run',     False)
    do_archive = getattr(args, 'archive', False)
    do_config  = getattr(args, 'config',  False)
    do_all     = getattr(args, 'all',     False)

    if do_all:
        do_run = do_archive = do_config = True

    if not (do_run or do_archive or do_config):
        print_check_help()
        return

    # Resolve case directory
    case_dir = _get_case_dir(args)
    if case_dir is None:
        return

    logger  = Logger(verbose=getattr(args, 'verbose', False))
    console = Console()

    console.print()
    console.print(Panel(
        f"[bold cyan]Case Check:[/bold cyan] {case_dir.name}\n"
        f"[dim]Path: {case_dir}[/dim]",
        border_style="cyan",
        box=box.ROUNDED,
    ))
    console.print()

    # Parse config once — used by all checks
    cfg = _parse_config(case_dir)

    any_error = False

    if do_config:
        ok = _check_config(cfg, case_dir, console)
        any_error = any_error or not ok

    if do_run:
        ok = _check_run(cfg, case_dir, console)
        any_error = any_error or not ok

    if do_archive:
        _check_archive(cfg, case_dir, console)

    console.print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_case_dir(args) -> Optional[Path]:
    """Resolve case directory from args or interactive context."""
    from src.cli.interactive import InteractiveShell

    if hasattr(args, 'case') and args.case:
        p = Path(args.case)
    elif (hasattr(InteractiveShell, '_instance') and
          InteractiveShell._instance and
          InteractiveShell._instance._current_case):
        p = Path(InteractiveShell._instance._current_case)
    else:
        print("Error: No case directory specified.")
        print("Usage:  case check <dir> --run")
        print("   or:  use case <dir>  then  case check --run")
        return None

    if not p.exists() or not p.is_dir():
        print(f"Error: Case directory not found: {p}")
        return None

    return p.resolve()


def _parse_config(case_dir: Path) -> dict:
    """Parse simflow.config into a plain dict.  Returns {} on error."""
    config_file = case_dir / 'simflow.config'
    cfg: dict = {}
    if not config_file.exists():
        return cfg
    try:
        with open(config_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, _, val = line.partition('=')
                    # Strip inline comments and quotes
                    val = re.split(r'\s*#', val, maxsplit=1)[0].strip().strip('"').strip("'")
                    cfg[key.strip()] = val
    except Exception:
        pass
    return cfg


def _read_data_file_range(file_path: Path) -> Optional[Tuple[int, int]]:
    """Return (min_tsId, max_tsId) for an OTHD or OISD file, or None on error."""
    try:
        if file_path.suffix == '.othd':
            from ....core.readers.othd_reader import OTHDReader
            reader = OTHDReader(str(file_path))
        else:
            from ....core.readers.oisd_reader import OISDReader
            reader = OISDReader(str(file_path))
        if not reader.tsIds:
            return None
        return (min(reader.tsIds), max(reader.tsIds))
    except Exception:
        return None


def _fmt_tsid(tsid: int) -> str:
    return f"{tsid:,}"


# ---------------------------------------------------------------------------
# --config check
# ---------------------------------------------------------------------------

def _check_config(cfg: dict, case_dir: Path, console: Console) -> bool:
    """Validate simflow.config for consistency. Returns True if no errors."""
    console.print("[bold]Config check[/bold]")

    config_file = case_dir / 'simflow.config'
    if not config_file.exists():
        console.print("  [red]✗[/red] simflow.config not found")
        console.print()
        return False

    rows: List[Tuple[str, str, str, str]] = []   # (icon, key, value, note)
    ok = True

    def row(icon, key, value, note='', color='green'):
        rows.append((icon, key, value, note, color))

    # problem
    problem = cfg.get('problem', '')
    if problem:
        geo  = list(case_dir.glob(f'{problem}.geo'))
        defn = list(case_dir.glob(f'{problem}.def'))
        geo_ok  = bool(geo)
        defn_ok = bool(defn)
        if geo_ok and defn_ok:
            row('✓', 'problem', problem, '.geo and .def found')
        else:
            missing = []
            if not geo_ok:  missing.append(f'{problem}.geo')
            if not defn_ok: missing.append(f'{problem}.def')
            row('✗', 'problem', problem, 'Missing: ' + ', '.join(missing), 'red')
            ok = False
    else:
        row('✗', 'problem', '(not set)', '', 'red')
        ok = False

    # dir (run directory)
    run_dir_str = cfg.get('dir', '')
    if run_dir_str:
        run_dir = (case_dir / run_dir_str).resolve() if not Path(run_dir_str).is_absolute() \
                  else Path(run_dir_str)
        exists = run_dir.exists()
        row('✓' if exists else '⚠',
            'dir', run_dir_str,
            'exists' if exists else 'directory not yet created',
            'green' if exists else 'yellow')
    else:
        row('⚠', 'dir', '(not set)', 'run directory unspecified', 'yellow')

    # outFreq
    freq = cfg.get('outFreq', '')
    if freq:
        row('✓', 'outFreq', freq, '')
    else:
        row('⚠', 'outFreq', '(not set)', '', 'yellow')

    # np
    np_val = cfg.get('np', '')
    if np_val:
        row('✓', 'np', np_val, '')
    else:
        row('⚠', 'np', '(not set)', '', 'yellow')

    # restartTsId (informational)
    restart = cfg.get('restartTsId', '')
    if restart:
        row('ℹ', 'restartTsId', restart, 'restart mode', 'cyan')
    else:
        row('—', 'restartTsId', '(not set)', 'fresh run (0)', 'dim')

    # Print table
    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    tbl.add_column("", width=2)
    tbl.add_column("Key",   style="cyan")
    tbl.add_column("Value", style="white")
    tbl.add_column("Note",  style="dim")

    color_map = {'green': 'green', 'red': 'red', 'yellow': 'yellow',
                 'cyan': 'cyan', 'dim': 'dim'}
    for icon, key, value, note, color in rows:
        c = color_map.get(color, 'white')
        tbl.add_row(f"[{c}]{icon}[/{c}]", key, value, note)

    console.print(tbl)
    console.print()
    return ok


# ---------------------------------------------------------------------------
# --run check
# ---------------------------------------------------------------------------

def _check_run(cfg: dict, case_dir: Path, console: Console) -> bool:
    """Check OTHD/OISD in the run directory. Returns True if no errors."""
    console.print("[bold]Run directory check[/bold]")

    problem = cfg.get('problem', '')
    run_dir_str = cfg.get('dir', '')
    restart_tsid_str = cfg.get('restartTsId', '').strip()

    if not run_dir_str:
        console.print("  [yellow]⚠[/yellow]  'dir' not set in simflow.config")
        console.print()
        return False

    run_dir = (case_dir / run_dir_str).resolve() if not Path(run_dir_str).is_absolute() \
              else Path(run_dir_str)

    if not run_dir.exists():
        console.print(f"  [yellow]⚠[/yellow]  Run directory does not exist: {run_dir_str}")
        console.print()
        return False

    if not problem:
        console.print("  [yellow]⚠[/yellow]  'problem' not set in simflow.config")
        console.print()
        return False

    # Parse restartTsId
    restart_tsid: Optional[int] = None
    if restart_tsid_str:
        try:
            restart_tsid = int(restart_tsid_str)
        except ValueError:
            pass

    found_any = False
    ok = True

    # Check both .othd and .oisd
    for ext in ('othd', 'oisd'):
        candidates = list(run_dir.glob(f'*.{ext}'))
        if not candidates:
            console.print(f"  [dim]—[/dim]  No .{ext} file found in {run_dir_str}")
            continue

        for file_path in sorted(candidates):
            found_any = True
            rng = _read_data_file_range(file_path)
            if rng is None:
                console.print(f"  [red]✗[/red]  {file_path.name}  [dim](could not read)[/dim]")
                ok = False
                continue

            start_ts, end_ts = rng
            size_mb = file_path.stat().st_size / 1_048_576

            # Restart consistency check (only for .othd)
            restart_note = ''
            restart_ok = True
            if ext == 'othd' and restart_tsid is not None:
                if start_ts == restart_tsid:
                    restart_note = f'[green]restartTsId={restart_tsid} ✓[/green]'
                else:
                    restart_note = (
                        f'[red]restartTsId mismatch: config={restart_tsid}, '
                        f'file starts at {start_ts}[/red]'
                    )
                    restart_ok = False
                    ok = False
            elif ext == 'othd' and restart_tsid is None:
                if start_ts == 0:
                    restart_note = '[dim]fresh run (start=0)[/dim]'
                else:
                    restart_note = (
                        f'[yellow]⚠ starts at {start_ts} but restartTsId not set in config[/yellow]'
                    )

            icon  = '[green]✓[/green]' if restart_ok else '[red]✗[/red]'
            label = f'{file_path.name}'
            range_str = f'[cyan]{_fmt_tsid(start_ts)}[/cyan] → [cyan]{_fmt_tsid(end_ts)}[/cyan]'
            steps = end_ts - start_ts
            meta  = f'{_fmt_tsid(steps)} steps  {size_mb:.1f} MB'

            console.print(f"  {icon}  {label}")
            console.print(f"       Range : {range_str}  ({meta})")
            if restart_note:
                console.print(f"       Restart: {restart_note}")
            console.print()

    if not found_any:
        console.print(f"  [dim]No .othd or .oisd files found in {run_dir_str}[/dim]")
        console.print()

    return ok


# ---------------------------------------------------------------------------
# --archive check
# ---------------------------------------------------------------------------

def _check_archive(cfg: dict, case_dir: Path, console: Console):
    """Show time step ranges for all archived OTHD/OISD files."""
    console.print("[bold]Archive check[/bold]")

    found_any = False

    for subdir_name, ext in (('othd_files', 'othd'), ('oisd_files', 'oisd')):
        subdir = case_dir / subdir_name
        if not subdir.exists():
            console.print(f"  [dim]—[/dim]  {subdir_name}/ not found")
            continue

        files = sorted(subdir.glob(f'*.{ext}'))
        if not files:
            console.print(f"  [dim]—[/dim]  No .{ext} files in {subdir_name}/")
            continue

        found_any = True

        tbl = Table(
            title=f"{subdir_name}/",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold yellow",
        )
        tbl.add_column("File",    style="cyan")
        tbl.add_column("Start",   justify="right", style="white")
        tbl.add_column("End",     justify="right", style="white")
        tbl.add_column("Steps",   justify="right", style="dim")
        tbl.add_column("Size",    justify="right", style="dim")

        for fp in files:
            rng = _read_data_file_range(fp)
            size_mb = fp.stat().st_size / 1_048_576
            if rng is None:
                tbl.add_row(fp.name, '[red]error[/red]', '', '', f'{size_mb:.1f} MB')
            else:
                start_ts, end_ts = rng
                tbl.add_row(
                    fp.name,
                    _fmt_tsid(start_ts),
                    _fmt_tsid(end_ts),
                    _fmt_tsid(end_ts - start_ts),
                    f'{size_mb:.1f} MB',
                )

        console.print(tbl)
        console.print()

    if not found_any:
        console.print("  [dim]No archived files found (othd_files/ and oisd_files/ are empty or missing)[/dim]")
        console.print()
