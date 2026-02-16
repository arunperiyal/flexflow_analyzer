"""
Case check command implementation

Checks OTHD/OISD file time step ranges in the run directory and/or
archive directories, and validates simflow.config consistency.
"""

import sys
from pathlib import Path
from typing import Optional, List, Tuple

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from ....utils.logger import Logger
from ....utils.colors import Colors
from ....core.simflow_config import SimflowConfig


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
    do_plt     = getattr(args, 'plt',     False)
    do_all     = getattr(args, 'all',     False)

    if do_all:
        do_run = do_archive = do_config = do_plt = True

    if not (do_run or do_archive or do_config or do_plt):
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
    cfg = SimflowConfig.find(case_dir)

    any_error = False

    if do_config:
        ok = _check_config(cfg, case_dir, console)
        any_error = any_error or not ok

    if do_run:
        ok = _check_run(cfg, case_dir, console)
        any_error = any_error or not ok

    if do_archive:
        _check_archive(cfg, case_dir, console)

    if do_plt:
        _check_plt(cfg, case_dir, console)

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
    problem = cfg.problem
    if problem:
        geo_ok  = bool(list(case_dir.glob(f'{problem}.geo')))
        defn_ok = bool(list(case_dir.glob(f'{problem}.def')))
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
    run_dir = cfg.run_dir(case_dir)
    if run_dir:
        row('✓' if run_dir.exists() else '⚠',
            'dir', cfg.run_dir_str or '',
            'exists' if run_dir.exists() else 'directory not yet created',
            'green' if run_dir.exists() else 'yellow')
    else:
        row('⚠', 'dir', '(not set)', 'run directory unspecified', 'yellow')

    # outFreq
    freq = cfg.out_freq
    row('✓' if freq else '⚠', 'outFreq', str(freq) if freq else '(not set)', '',
        'green' if freq else 'yellow')

    # np
    np_val = cfg.np
    row('✓' if np_val else '⚠', 'np', str(np_val) if np_val else '(not set)', '',
        'green' if np_val else 'yellow')

    # restartFlag + restartTsId (informational)
    if cfg.restart_flag:
        row('ℹ', 'restartFlag', cfg.get('restartFlag', ''), 'restart mode active', 'cyan')
        if cfg.restart_tsid is not None:
            row('ℹ', 'restartTsId', str(cfg.restart_tsid), 'restart from this tsId', 'cyan')
        else:
            row('⚠', 'restartTsId', '(not set)', 'restartFlag active but no tsId', 'yellow')
    else:
        row('—', 'restartFlag', '(not set)', 'fresh run', 'dim')

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
    restart_tsid_str  = cfg.get('restartTsId',  '').strip()
    restart_flag_str  = cfg.get('restartFlag',  '').strip()

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

    # restartFlag must be active (uncommented, non-zero) to trigger restart checks.
    is_restart = bool(restart_flag_str) and restart_flag_str != '0'

    restart_tsid: Optional[int] = None
    if is_restart and restart_tsid_str:
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

            # Restart consistency check — only for .othd and only when restartFlag is active
            restart_note = ''
            restart_ok = True
            if ext == 'othd' and is_restart:
                if restart_tsid is not None:
                    if start_ts == restart_tsid + 1:
                        restart_note = f'[green]restartTsId={restart_tsid} ✓[/green]'
                    else:
                        restart_note = (
                            f'[red]restartTsId mismatch: config={restart_tsid}, '
                            f'file starts at {start_ts} (expected {restart_tsid + 1})[/red]'
                        )
                        restart_ok = False
                        ok = False
                else:
                    restart_note = '[yellow]⚠ restartFlag=1 but restartTsId not set in config[/yellow]'

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


# ---------------------------------------------------------------------------
# --plt check
# ---------------------------------------------------------------------------

def _check_plt(cfg, case_dir: Path, console: Console):
    """Check PLT files in binary/ and the run directory against expected set."""
    console.print("[bold]PLT file check[/bold]")

    problem = cfg.problem
    if not problem:
        console.print("  [yellow]⚠[/yellow]  'problem' not set in simflow.config — cannot determine PLT file names")
        console.print()
        return

    out_freq = cfg.out_freq
    if not out_freq:
        console.print("  [yellow]⚠[/yellow]  'outFreq' not set in simflow.config — cannot determine expected PLT files")
        console.print()
        return

    from ....core.def_config import DefConfig
    def_cfg = DefConfig.find(case_dir, problem)
    max_steps = def_cfg.max_time_steps
    if not max_steps:
        console.print("  [yellow]⚠[/yellow]  'maxTimeSteps' not found in .def file — cannot determine expected PLT files")
        console.print()
        return

    # Build expected tsId set: outFreq, 2*outFreq, ..., maxTimeSteps
    expected = set(range(out_freq, max_steps + 1, out_freq))
    total_expected = len(expected)

    # Directories to check: binary/ and run dir
    locations = []

    binary_dir = case_dir / 'binary'
    if binary_dir.exists():
        locations.append(('binary/', binary_dir))

    run_dir = cfg.run_dir(case_dir)
    if run_dir and run_dir.exists() and run_dir != binary_dir:
        locations.append((cfg.run_dir_str or 'run dir', run_dir))

    if not locations:
        console.print("  [dim]Neither binary/ nor the run directory exists[/dim]")
        console.print()
        return

    for label, directory in locations:
        console.print(f"  [bold]{label}[/bold]")

        # Find PLT files matching <problem>.<tsId>.plt
        import re as _re
        pattern = _re.compile(rf'^{_re.escape(problem)}\.(\d+)\.plt$')
        found: dict = {}
        for f in directory.iterdir():
            m = pattern.match(f.name)
            if m:
                found[int(m.group(1))] = f

        if not found:
            console.print(f"    [dim]No {problem}.*.plt files found[/dim]")
            console.print()
            continue

        present   = set(found.keys())
        missing   = sorted(expected - present)
        extra     = sorted(present - expected)
        n_found   = len(present & expected)
        total_size = sum(f.stat().st_size for f in found.values()) / 1_048_576

        # Summary line
        if not missing:
            console.print(
                f"    [green]✓[/green]  {n_found}/{total_expected} expected files present  "
                f"({total_size:.1f} MB total)"
            )
        else:
            console.print(
                f"    [red]✗[/red]  {n_found}/{total_expected} expected files present  "
                f"([red]{len(missing)} missing[/red],  {total_size:.1f} MB total)"
            )

        # tsId range of found files
        console.print(
            f"    Range : [cyan]{_fmt_tsid(min(present))}[/cyan]"
            f" → [cyan]{_fmt_tsid(max(present))}[/cyan]"
            f"  (outFreq={out_freq},  maxTimeSteps={_fmt_tsid(max_steps)})"
        )

        # Missing tsIds
        if missing:
            console.print(f"    [red]Missing tsIds:[/red]")
            # Print in rows of 10 for readability
            chunk = 10
            for i in range(0, len(missing), chunk):
                row = ', '.join(_fmt_tsid(t) for t in missing[i:i + chunk])
                console.print(f"      {row}")

        # Extra (not in expected set)
        if extra:
            console.print(
                f"    [dim]Extra (not in expected set): "
                + ', '.join(_fmt_tsid(t) for t in extra[:20])
                + (f"  … ({len(extra)} total)" if len(extra) > 20 else '')
                + "[/dim]"
            )

        console.print()
