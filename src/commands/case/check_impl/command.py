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
from rich.markup import escape

from ....utils.logger import Logger
from ....utils.colors import Colors
from ....utils.file_utils import natural_sort_key
from ....core.simflow_config import SimflowConfig
from ...case_iteration import is_wildcard_case, load_cases_from_directory


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

    subcommand = getattr(args, 'check_subcommand', None)
    if not subcommand:
        print_check_help()
        return

    if subcommand == 'data':
        # the old `case status`: data file completeness
        from .data import execute_check_data
        execute_check_data(args)
        return

    do_run     = subcommand in ('run', 'all')
    do_archive = subcommand in ('archive', 'all')
    do_config  = subcommand in ('config', 'all')
    do_plt     = subcommand in ('plt', 'all')
    do_def     = subcommand in ('def', 'all')
    do_out     = subcommand in ('out', 'all')

    # --freq overrides outFreq from simflow.config. The config says what the run
    # was asked to write; the files say what it wrote, and after a restart at a
    # different frequency those are not the same claim.
    freq = getattr(args, 'freq', None)
    # --t1/--t2 restrict the `plt` check to a timestep window (only meaningful
    # on the `plt` subcommand — `all` runs plt unwindowed).
    t1 = getattr(args, 't1', None)
    t2 = getattr(args, 't2', None)

    # Get case name from args or interactive context
    case_name = _get_case_name(args)
    if case_name is None:
        return

    # Check if wildcard - if so, iterate over all cases
    if is_wildcard_case(case_name):
        _execute_check_on_all_cases(args, do_run, do_archive, do_config, do_plt, do_def, do_out, freq, t1, t2)
        return

    # Single case execution
    case_dir = _resolve_case_dir(case_name)
    if case_dir is None:
        return

    _execute_check_on_case(case_dir, do_run, do_archive, do_config, do_plt, do_def, do_out, freq, t1, t2)


def _get_case_name(args) -> Optional[str]:
    """Get case name from args or interactive context."""
    from src.cli.context import current_case

    if hasattr(args, 'case') and args.case:
        return args.case
    elif current_case():
        return current_case()
    else:
        print("Error: No case directory specified.")
        print("Usage:  case check run <dir>")
        print("   or:  use case <dir>  then  case check run")
        return None


def _execute_check_on_all_cases(args, do_run, do_archive, do_config, do_plt, do_def, do_out,
                                freq=None, t1=None, t2=None):
    """Execute check on all cases from .cases file."""
    from src.cli.context import current_dir

    base_dir = current_dir()
    
    # Load cases
    cases = load_cases_from_directory(base_dir)
    if not cases:
        print(f"Error: No cases found in .cases file or file does not exist")
        return

    console = Console()
    console.print(f"\n[cyan]{'─' * 60}[/cyan]")
    console.print(f"[green]Processing {len(cases)} cases[/green]")
    console.print(f"[cyan]{'─' * 60}[/cyan]\n")

    for case_idx, case_entry in enumerate(cases, 1):
        case_path = Path(case_entry['path'])
        case_name = case_entry['name']

        console.print(f"[cyan]{'─' * 60}[/cyan]")
        console.print(f"[green]Case {case_idx}/{len(cases)}:[/green] [cyan]{case_name}[/cyan]")
        console.print(f"[dim]Path: {case_path}[/dim]")
        console.print(f"[cyan]{'─' * 60}[/cyan]\n")

        if not case_path.exists():
            console.print(f"[red]Error:[/red] Case directory not found: {case_path}\n")
            continue

        _execute_check_on_case(case_path, do_run, do_archive, do_config, do_plt, do_def, do_out, freq, t1, t2)

    console.print(f"[cyan]{'─' * 60}[/cyan]")
    console.print(f"[green]✓ Processed {len(cases)} cases[/green]")
    console.print(f"[cyan]{'─' * 60}[/cyan]\n")


def _execute_check_on_case(case_dir: Path, do_run, do_archive, do_config, do_plt, do_def, do_out,
                           freq=None, t1=None, t2=None):
    """Execute check on a single case."""
    logger  = Logger(verbose=False)
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

    if do_def:
        ok = _check_def(cfg, case_dir, console)
        any_error = any_error or not ok

    if do_run:
        ok = _check_run(cfg, case_dir, console)
        any_error = any_error or not ok

    if do_archive:
        _check_archive(cfg, case_dir, console)

    if do_plt:
        _check_plt(cfg, case_dir, console, freq, t1, t2)

    if do_out:
        # `case check all --freq` is the PLT frequency; only `case check out
        # --freq` is the frequency of the .out/.rst files.
        _check_out(cfg, case_dir, console, t1, t2, freq=None if do_plt else freq)

    console.print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_case_dir(case_name: str) -> Optional[Path]:
    """Resolve a single case directory from case name."""
    p = Path(case_name)

    if not p.exists() or not p.is_dir():
        print(f"Error: Case directory not found: {p}")
        return None

    return p.resolve()


def _read_data_file_range(file_path: Path) -> Optional[Tuple[int, int]]:
    """Return (min_tsId, max_tsId) for an OTHD or OISD file, or None on error."""
    try:
        if file_path.suffix == '.othd':
            from ....core.readers.othd_reader import OTHDReader
            reader = OTHDReader(str(file_path), range_only=True)
        else:
            from ....core.readers.oisd_reader import OISDReader
            reader = OISDReader(str(file_path), range_only=True)
        if not reader.tsIds:
            return None
        return (min(reader.tsIds), max(reader.tsIds))
    except Exception:
        return None


def _fmt_tsid(tsid: int) -> str:
    # Plain digits, no thousands separators: tsIds are names people grep for
    # (`case check out | grep 4000`) and pass back as --t1/--t2.
    return str(tsid)


def _step_in_bounds(step: float, t1: Optional[float], t2: Optional[float]) -> bool:
    """Whether a single timestep falls inside the [t1, t2] window (either bound optional)."""
    if t1 is not None and step < t1:
        return False
    if t2 is not None and step > t2:
        return False
    return True


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

        for file_path in sorted(candidates, key=natural_sort_key):
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
    """Show the time step range of every OTHD/OISD history file: archive/,
    cleaned/, the compiled file, and parts still in the old flat layout."""
    console.print("[bold]Archive check[/bold]")

    found_any = False

    for subdir_name, ext in (('othd_files', 'othd'), ('oisd_files', 'oisd')):
        subdir = case_dir / subdir_name
        if not subdir.exists():
            console.print(f"  [dim]—[/dim]  {subdir_name}/ not found")
            continue

        files = sorted((p for p in subdir.rglob(f'*.{ext}') if p.parent.name != 'compiled'),
                       key=lambda p: (len(p.relative_to(subdir).parts) == 1
                                      and not p.stem[-1:].isdigit(),
                                      natural_sort_key(str(p.relative_to(subdir)))))
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
                tbl.add_row(str(fp.relative_to(subdir)), '[red]error[/red]', '', '', f'{size_mb:.1f} MB')
            else:
                start_ts, end_ts = rng
                tbl.add_row(
                    str(fp.relative_to(subdir)),
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
# --def check
# ---------------------------------------------------------------------------

def _check_def(cfg, case_dir: Path, console: Console) -> bool:
    """Verify every File( "..." ) referenced in the .def file exists.

    Returns True if all referenced files are present (or there are none).
    """
    console.print("[bold]Def file check[/bold]")

    from ....core.def_config import DefConfig
    def_cfg = DefConfig.find(case_dir, cfg.problem)

    if not def_cfg.exists:
        console.print("  [red]✗[/red]  No .def file found in case directory")
        console.print()
        return False

    refs = def_cfg.file_references
    if not refs:
        console.print(f"  [dim]—[/dim]  No File( \"...\" ) references in {def_cfg.path.name}")
        console.print()
        return True

    base_dir = def_cfg.path.parent

    tbl = Table(
        title=f"File() references — {def_cfg.path.name}",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold yellow",
    )
    tbl.add_column("", width=2)
    tbl.add_column("File", style="cyan")
    tbl.add_column("Status", style="white")

    missing = []
    for name in refs:
        ref_path = Path(name)
        full = ref_path if ref_path.is_absolute() else (base_dir / ref_path)
        if full.exists():
            tbl.add_row("[green]✓[/green]", name, "[green]present[/green]")
        else:
            tbl.add_row("[red]✗[/red]", name, "[red]missing[/red]")
            missing.append(name)

    console.print(tbl)

    n_total = len(refs)
    n_present = n_total - len(missing)
    if missing:
        console.print(
            f"  [red]✗[/red]  {n_present}/{n_total} referenced files present  "
            f"([red]{len(missing)} missing[/red])"
        )
    else:
        console.print(
            f"  [green]✓[/green]  all {n_total} referenced files present"
        )
    console.print()
    return not missing


# ---------------------------------------------------------------------------
# --plt check
# ---------------------------------------------------------------------------

def _check_plt(cfg, case_dir: Path, console: Console, freq: Optional[int] = None,
               t1: Optional[float] = None, t2: Optional[float] = None):
    """Check PLT files in binary/ and the run directory against expected set.

    `freq` overrides outFreq from simflow.config. The config records what the
    run was asked to write; a restart at another frequency, or a config edited
    since, makes that a different claim from what is on disk -- and checking
    against the wrong one reports every file that was never meant to exist as
    missing.

    `t1`/`t2` restrict both the expected and found sets to a timestep window,
    so the check (and its missing/extra counts) only concern that window.

    A step counts as present in either place (organise moves them from the
    run directory to binary/). Expected steps after the last one found are
    not written yet -- the run stopped or is still going -- so they are shown
    apart from the gaps, which are the files really lost.

    After a restart from restartTsId R, the steps past R are computed again,
    and a PLT made from the earlier run's output is stale: the flow drifts
    apart between the two runs, so it does not join up with the frames
    around it. See _stale_plts for how such a file is told apart.
    """
    import re as _re
    from shellkit.builtins.files import format_size

    problem = cfg.problem
    if not problem:
        console.print("[bold]PLT file check[/bold]")
        console.print("  [yellow]⚠[/yellow]  'problem' not set in simflow.config — cannot determine PLT file names")
        console.print()
        return

    out_freq = freq or cfg.out_freq
    if not out_freq:
        console.print("[bold]PLT file check[/bold]")
        console.print("  [yellow]⚠[/yellow]  'outFreq' not set in simflow.config — cannot determine expected PLT files")
        console.print("  [dim]give --freq N to check against a frequency anyway[/dim]")
        console.print()
        return

    from ....core.def_config import DefConfig
    def_cfg = DefConfig.find(case_dir, problem)
    max_steps = def_cfg.max_time_steps
    if not max_steps:
        console.print("[bold]PLT file check[/bold]")
        console.print("  [yellow]⚠[/yellow]  'maxTimeSteps' not found in .def file — cannot determine expected PLT files")
        console.print()
        return

    windowed = t1 is not None or t2 is not None
    window = f" · steps {_fmt_bound(t1)}..{_fmt_bound(t2)}" if windowed else ''
    console.print(f"[bold]PLT file check[/bold]  [dim]{escape(problem)}.<step>.plt · every "
                  f"{out_freq} ({'--freq' if freq else 'outFreq'}) up to {_fmt_tsid(max_steps)} "
                  f"(maxTimeSteps){window}[/dim]")

    # Build expected tsId set: outFreq, 2*outFreq, ..., maxTimeSteps
    expected = {t for t in range(out_freq, max_steps + 1, out_freq) if _step_in_bounds(t, t1, t2)}

    locations = []
    binary_dir = case_dir / 'binary'
    if binary_dir.exists():
        locations.append(('binary/', binary_dir))
    run_dir = cfg.run_dir(case_dir)
    if run_dir and run_dir.exists() and run_dir != binary_dir:
        locations.append(((cfg.run_dir_str or 'run dir').rstrip('/') + '/', run_dir))
    if not locations:
        console.print("  [dim]Neither binary/ nor the run directory exists[/dim]")
        console.print()
        return

    pattern = _re.compile(rf'^{_re.escape(problem)}\.(\d+)\.plt$')
    found: dict = {}            # step -> sizes, one per location holding it
    stats: dict = {}            # label -> {step: os.stat_result}
    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow", pad_edge=False)
    tbl.add_column("where", style="bold")
    tbl.add_column("files", justify="right")
    tbl.add_column("steps")
    tbl.add_column("size", justify="right")
    for label, directory in locations:
        here = {}
        stats[label] = {}
        for f in directory.iterdir():
            m = pattern.match(f.name)
            if m and _step_in_bounds(int(m.group(1)), t1, t2):
                st = f.stat()
                stats[label][int(m.group(1))] = st
                here[int(m.group(1))] = st.st_size
        for step, size in here.items():
            found.setdefault(step, []).append(size)
        if here:
            tbl.add_row(label, str(len(here)),
                        f"[cyan]{_fmt_tsid(min(here))}[/cyan] → [cyan]{_fmt_tsid(max(here))}[/cyan]",
                        format_size(sum(here.values())))
        else:
            tbl.add_row(label, "[dim]0[/dim]", "[dim]—[/dim]", "[dim]—[/dim]")
    console.print(tbl)

    if not found:
        console.print(f"  [red]✗[/red] no {escape(problem)}.<step>.plt in "
                      f"{' or '.join(label for label, _ in locations)}; {len(expected)} expected")
        console.print()
        return

    last = max(found)
    upto = {t for t in expected if t <= last}
    missing = sorted(upto - set(found))
    later = sorted(t for t in expected if t > last)
    empty = sorted(t for t in expected if t in found and 0 in found[t])
    extra = sorted(set(found) - expected)
    both = sorted(t for t, sizes in found.items() if len(sizes) > 1)
    restart = cfg.restart_tsid if cfg.restart_flag else None
    stale, dated_from = ({}, None) if restart is None else \
        _stale_plts(stats, run_dir, problem, restart)

    bad = missing or empty or stale
    mark = "[red]✗[/red]" if bad else "[green]✓[/green]"
    parts = [f"[red]{len(missing)} missing[/red]" if missing else "none missing"]
    if empty:
        parts.append(f"[yellow]{len(empty)} empty[/yellow]")
    if stale:
        parts.append(f"[red]{sum(len(v) for v in stale.values())} from before the restart[/red]")
    console.print(f"  {mark} {len(upto) - len(missing)} of {len(upto)} present up to "
                  f"{_fmt_tsid(last)}, the last step found · " + ", ".join(parts))

    # label | steps, so a long list wraps under itself
    details = Table.grid(padding=(0, 2))
    details.add_column(no_wrap=True)
    details.add_column()
    if missing:
        details.add_row("    [red]missing[/red]", _fmt_steps(missing, out_freq))
    if empty:
        details.add_row("    [yellow]empty[/yellow]", _fmt_steps(empty, out_freq))
    for label, steps in stale.items():
        details.add_row("    [red]stale[/red]",
                        f"{_fmt_steps(steps, out_freq)}  [dim](in {label}; older than the "
                        f"resumed run's output, so made before the restart at {restart})[/dim]")
    if restart is not None and not stale:
        details.add_row("    [dim]restart[/dim]",
                        f"[dim]at {restart}: " +
                        (f"none older than the resumed run (dated by its output from "
                         f"{dated_from} on)" if dated_from is not None else
                         f"no .out/.rst past it in the run directory to date the files by")
                        + "[/dim]")
    if extra:
        details.add_row("    [dim]extra[/dim]",
                        f"[dim]{_fmt_steps(extra, None)}  (off the every-{out_freq} grid)[/dim]")
    if both:
        details.add_row("    [dim]in both[/dim]",
                        f"[dim]{_fmt_steps(both, out_freq)}  "
                        f"({' and '.join(label for label, _ in locations)})[/dim]")
    if later:
        details.add_row("    [dim]not yet[/dim]",
                        f"[dim]{_fmt_steps(later, out_freq)}  "
                        f"(the run is at {_fmt_tsid(last)} of {_fmt_tsid(max(expected))})[/dim]")
    if details.row_count:
        console.print(details)
    console.print()


def _stale_plts(stats: dict, run_dir: Optional[Path], problem: str, restart: int):
    """The PLT files past the restart step made from the earlier run's output.

    The resumed run computes its steps in order, so by the time it reached
    step t it had already written its .out/.rst for every step from restart+1
    to t. A PLT of step t older than the latest of those files was made
    before the resumed run got to t -- from the earlier run's output, which
    the restart computed again. Steps before the first .out/.rst left past
    the restart cannot be dated, and are not flagged.

    Returns ({label: [steps]}, the first step dated by, or None).
    """
    import bisect
    import re as _re
    if not run_dir or not run_dir.is_dir():
        return {}, None
    pattern = _re.compile(rf'^{_re.escape(problem)}\.(\d+)_\d+\.(out|rst)$')
    written: dict = {}          # step -> latest mtime of the resumed run's files
    for f in run_dir.iterdir():
        m = pattern.match(f.name)
        if m and int(m.group(1)) > restart:
            step, mtime = int(m.group(1)), f.stat().st_mtime
            written[step] = max(mtime, written.get(step, mtime))
    if not written:
        return {}, None
    steps = sorted(written)
    reached = []                # reached[i]: the run was past steps[i] no earlier than this
    for step in steps:
        reached.append(max(written[step], reached[-1]) if reached else written[step])

    stale = {}
    for label, files in stats.items():
        for t, st in sorted(files.items()):
            i = bisect.bisect_right(steps, t) - 1
            if t > restart and i >= 0 and st.st_mtime < reached[i]:
                stale.setdefault(label, []).append(t)
    return stale, steps[0]


def _fmt_bound(bound: Optional[float]) -> str:
    if bound is None:
        return ''
    return _fmt_tsid(int(bound)) if float(bound).is_integer() else str(bound)


def _fmt_steps(steps: List[int], freq: Optional[int], limit: int = 12) -> str:
    """Steps as runs: '300 · 650–750 (3) · 1200'. A run is consecutive steps
    `freq` apart; without freq every step stands alone. Past `limit` runs the
    middle is elided."""
    runs = []
    for t in steps:
        if runs and freq and t - runs[-1][-1] == freq:
            runs[-1].append(t)
        else:
            runs.append([t])
    text = [_fmt_tsid(r[0]) if len(r) == 1 else
            f"{_fmt_tsid(r[0])}–{_fmt_tsid(r[-1])} ({len(r)})" for r in runs]
    if len(text) > limit:
        text = text[:limit // 2] + [f"… {len(text) - limit} more …"] + text[-(limit // 2):]
    return " · ".join(text)


# ---------------------------------------------------------------------------
# --out check
# ---------------------------------------------------------------------------

def _check_out(cfg, case_dir: Path, console: Console,
               t1: Optional[float] = None, t2: Optional[float] = None,
               freq: Optional[int] = None):
    """List timesteps for which .out/.rst files are present in the run directory.

    With `freq`, the steps freq, 2*freq, ... are expected too: each one with
    neither file is listed as missing. They run up to t2, or to the last step
    found -- not maxTimeSteps, so a run still going does not show its future
    steps as missing.
    """
    console.print("[bold]Out/Rst file check[/bold]")

    problem = cfg.problem
    if not problem:
        console.print("  [yellow]⚠[/yellow]  'problem' not set in simflow.config — cannot determine .out/.rst file names")
        console.print()
        return

    run_dir = cfg.run_dir(case_dir)
    if not run_dir or not run_dir.exists():
        where = f": {cfg.run_dir_str}" if cfg.run_dir_str else " ('dir' not set in simflow.config)"
        console.print(f"  [yellow]⚠[/yellow]  Run directory does not exist{where}")
        console.print()
        return

    import re as _re
    # Pattern: {problem}.{tsId}_<rank>.out or {problem}.{tsId}_<rank>.rst
    pattern = _re.compile(rf'^{_re.escape(problem)}\.(\d+)_.*\.(out|rst)$')

    out_steps: dict = {}
    rst_steps: dict = {}
    for f in run_dir.iterdir():
        m = pattern.match(f.name)
        if not m:
            continue
        step = int(m.group(1))
        (out_steps if m.group(2) == 'out' else rst_steps)[step] = f

    if t1 is not None or t2 is not None:
        out_steps = {s: f for s, f in out_steps.items() if _step_in_bounds(s, t1, t2)}
        rst_steps = {s: f for s, f in rst_steps.items() if _step_in_bounds(s, t1, t2)}
        console.print(f"  [dim]Limiting to timesteps in [{t1}, {t2}][/dim]")

    all_steps = sorted(set(out_steps) | set(rst_steps))

    missing = set()
    if freq and (all_steps or t2 is not None):
        first = freq if t1 is None else max(freq, int(-(-t1 // freq)) * freq)
        last = int(t2) if t2 is not None else all_steps[-1]
        missing = set(range(first, last + 1, freq)) - set(all_steps)

    if not all_steps and not missing:
        console.print(f"  [dim]No {problem}.*_*.out or .rst files found in "
                       f"{cfg.run_dir_str or run_dir}[/dim]")
        console.print()
        return
    all_steps = sorted(set(all_steps) | missing)

    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
    tbl.add_column("tsId", justify="right", style="cyan")
    tbl.add_column(".out", justify="center")
    tbl.add_column(".rst", justify="center")
    if freq:
        tbl.add_column("", no_wrap=True)

    for step in all_steps:
        if step in missing:
            tbl.add_row(f"[red]{_fmt_tsid(step)}[/red]", '[red]✗[/red]', '[red]✗[/red]',
                        '[red]missing[/red]')
            continue
        out_icon = '[green]✓[/green]' if step in out_steps else '[dim]—[/dim]'
        rst_icon = '[green]✓[/green]' if step in rst_steps else '[dim]—[/dim]'
        tbl.add_row(_fmt_tsid(step), out_icon, rst_icon, *([''] if freq else []))

    console.print(tbl)
    present = [s for s in all_steps if s not in missing]
    span = (f"  ([cyan]{_fmt_tsid(present[0])}[/cyan] → [cyan]{_fmt_tsid(present[-1])}[/cyan])"
            if present else '')
    console.print(f"  {len(out_steps)} .out file(s), {len(rst_steps)} .rst file(s){span}")
    if freq:
        if missing:
            console.print(f"  [red]✗[/red] {len(missing)} step(s) missing at --freq {freq}")
        else:
            console.print(f"  [green]✓[/green] no step missing at --freq {freq}")
    console.print()
