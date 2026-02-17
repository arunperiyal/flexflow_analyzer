"""case report — compact table of all cases listed in .cases."""

import re
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
    tbl.add_column('Case',           style='cyan',   no_wrap=True)
    tbl.add_column('restartFlag',    justify='center')
    tbl.add_column('restartTsId',    justify='right')
    tbl.add_column('.out files',     justify='right')
    tbl.add_column('Last timestep',  justify='right')

    for entry in entries:
        case_path = Path(entry['path'])
        name      = entry['name']

        if not case_path.is_dir():
            tbl.add_row(name, '[red]missing[/red]', '—', '—', '—')
            continue

        # --- simflow.config ---
        restart_flag_str = '[dim]—[/dim]'
        restart_tsid_str = '[dim]—[/dim]'
        run_dir_path     = None
        problem          = None

        cfg_path = case_path / 'simflow.config'
        if cfg_path.exists():
            cfg = _parse_config(cfg_path)

            rf = cfg.get('restartFlag', '')
            if rf:
                active = rf.strip() not in ('', '0')
                restart_flag_str = '[green]1[/green]' if active else '[dim]0[/dim]'
            else:
                restart_flag_str = '[dim]—[/dim]'

            rt = cfg.get('restartTsId', '')
            restart_tsid_str = rt if rt else '[dim]—[/dim]'

            problem = cfg.get('problem', '').strip().strip('"').strip("'") or None

            raw_dir = cfg.get('dir', '').strip().strip('"').strip("'")
            if raw_dir:
                rd = Path(raw_dir)
                run_dir_path = rd if rd.is_absolute() else (case_path / rd).resolve()

        # --- scan rundir for .out files ---
        out_count_str  = '[dim]—[/dim]'
        last_ts_str    = '[dim]—[/dim]'

        if run_dir_path and run_dir_path.is_dir() and problem:
            pattern   = f'{problem}.*_*.out'
            out_files = list(run_dir_path.glob(pattern))
            if out_files:
                out_count_str = str(len(out_files))
                steps = []
                for f in out_files:
                    s = _extract_step(f.name, problem)
                    if s is not None:
                        steps.append(s)
                if steps:
                    last_ts_str = str(max(steps))

        tbl.add_row(
            name,
            restart_flag_str,
            restart_tsid_str,
            out_count_str,
            last_ts_str,
        )

    console.print(tbl)
    console.print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_config(cfg_path: Path) -> dict:
    """Minimal parser: returns active (uncommented) key=value pairs."""
    data = {}
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


def _extract_step(filename: str, problem: str) -> 'int | None':
    """Extract integer timestep from e.g. riser.1050_0.out → 1050."""
    stem = filename
    for ext in ('.out', '.rst', '.plt'):
        if stem.endswith(ext):
            stem = stem[:-len(ext)]
            break
    prefix = problem + '.'
    if stem.startswith(prefix):
        rest = stem[len(prefix):]
        m = re.match(r'^(\d+)', rest)
        if m:
            return int(m.group(1))
    return None


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
    console.print("    Case           Case directory name")
    console.print("    restartFlag    Current value of restartFlag in simflow.config")
    console.print("    restartTsId    Current value of restartTsId in simflow.config")
    console.print("    .out files     Number of .out files in the run directory")
    console.print("    Last timestep  Highest timestep seen in the run directory")
    console.print()
    console.print("[bold]EXAMPLES:[/bold]")
    console.print("    case report")
    console.print("    case report --dir /scratch/me/project")
    console.print()
