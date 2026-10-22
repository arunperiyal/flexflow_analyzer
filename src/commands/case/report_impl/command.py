"""case report — compact table of all cases listed in .cases."""

import json
import os
import re
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import box


def _get_context_rundir() -> 'str | None':
    """Return the rundir set via 'use rundir' in the interactive shell, or None."""
    from src.cli.context import current_rundir
    return current_rundir()


_CACHE_FILE = '.case_report'
_CACHE_VERSION = 1

# The .cases directories whose report was computed afresh in this process. The
# shell runs commands in-process, so this lasts the session: its first
# `case report` recomputes and rewrites .case_report, later ones read it.
_refreshed = set()


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

    fresh = bool(getattr(args, 'update', False)) or search_dir not in _refreshed
    old_cache = _load_cache(search_dir)
    cache = {}                                  # only the cases still in .cases
    now = time.time()
    oldest = None                               # when the oldest value shown was computed

    def cached(case_cache, key, compute, match=None):
        """case_cache[key] if it is there (and was computed for `match`), else compute it.
        A fresh report computes every column it shows; the others stay as they were."""
        nonlocal oldest
        hit = case_cache.get(key)
        if (not fresh and isinstance(hit, dict) and hit.get('for') == match
                and 'value' in hit and isinstance(hit.get('at'), (int, float))):
            oldest = min(oldest or hit['at'], hit['at'])
            return hit['value']
        value = compute()
        case_cache[key] = {'value': value, 'at': now, 'for': match}
        return value

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

    dash = '[dim]—[/dim]'
    for entry in entries:
        case_path = Path(entry['path'])
        name      = entry['name']

        if not case_path.is_dir():
            row = [name, '[red]missing[/red]', dash]
            if show_run:
                row.append(dash)
            if show_size:
                row.append(dash)
            tbl.add_row(*row)
            continue

        case_cache = old_cache.get(str(case_path))
        case_cache = cache[str(case_path)] = case_cache if isinstance(case_cache, dict) else {}

        # --- simflow.config (need problem name + dir key) ---
        cfg     = _parse_config(case_path / 'simflow.config')
        problem = cfg.get('problem', '').strip().strip('"').strip("'") or None

        # --- Column 1: last timestep from othd_files/ archive ---
        archive_last = cached(case_cache, 'archive', lambda: _last_othd_timestep(case_path))
        # --- Column 2: last PLT from binary/ ---
        binary_last = cached(case_cache, 'binary',
                             lambda: _last_binary_plt_timestep(case_path, problem), match=problem)
        row = [name, _fmt_step(archive_last), _fmt_step(binary_last)]

        # --- Column 3 (optional): last timestep from rundir ---
        if show_run:
            rundir = _resolve_rundir(case_path, cfg, context_rundir)
            if rundir:
                row.append(_fmt_step(cached(case_cache, 'run',
                                            lambda: _last_othd_timestep_in_dir(rundir),
                                            match=str(rundir))))
            else:
                row.append('[dim]no rundir[/dim]')

        # --- Column 4 (optional): disk usage ---
        if show_size:
            row.append(_fmt_size(cached(case_cache, 'size', lambda: _dir_size(case_path))))

        tbl.add_row(*row)

    console.print(tbl)
    if oldest is not None:
        console.print(f"[dim]From {_CACHE_FILE}, computed {_fmt_age(now - oldest)} ago — "
                      f"`case report --update` to recompute[/dim]")
    if _save_cache(search_dir, cache):
        _refreshed.add(search_dir)
    else:
        console.print(f"[dim]Could not write {search_dir / _CACHE_FILE}[/dim]")
    console.print()


def _fmt_step(step) -> str:
    return str(step) if step is not None else '[dim]—[/dim]'


def _fmt_age(seconds: float) -> str:
    """5 s, 12 min, 3 h, 2 d."""
    for unit, size in (('d', 86400), ('h', 3600), ('min', 60)):
        if seconds >= size:
            return f"{int(seconds // size)} {unit}"
    return f"{int(seconds)} s"


def _load_cache(search_dir: Path) -> dict:
    """The cases part of .case_report, or {} if it is missing, unreadable or old."""
    try:
        data = json.loads((search_dir / _CACHE_FILE).read_text())
        if data.get('version') == _CACHE_VERSION and isinstance(data.get('cases'), dict):
            return data['cases']
    except (OSError, ValueError, AttributeError):
        pass
    return {}


def _save_cache(search_dir: Path, cases: dict) -> bool:
    """Write .case_report (via a temporary file, so a reader never sees half of it)."""
    path = search_dir / _CACHE_FILE
    tmp = path.with_name(path.name + '.tmp')
    try:
        tmp.write_text(json.dumps({'version': _CACHE_VERSION, 'cases': cases}, indent=1))
        os.replace(tmp, path)
        return True
    except OSError:
        return False


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


_TSID = re.compile(rb'^[ \t]*tsId[ \t]+(\d+)', re.M)


def _last_tsid(path: Path):
    """The last tsId written to an .othd file, read from its end.

    A run writes its steps in order, so the last block is where it got to;
    reading the tail (growing it until a whole tsId line is in it) costs the
    same for a 10 MB file as for a 10 GB one. After a restart inside one file
    this is where the restarted run stopped -- the step the file really holds.
    """
    with open(path, 'rb') as f:
        size = f.seek(0, os.SEEK_END)
        window = 1 << 20
        while True:
            start = max(0, size - window)
            f.seek(start)
            hits = _TSID.findall(f.read(size - start))
            # a hit at the very start of the window may be a cut-off line
            if hits and (start == 0 or len(hits) > 1):
                return int(hits[-1])
            if start == 0:
                return None
            window *= 4


def _last_othd_timestep_in_dir(directory: Path):
    """Return the last timestep reached across the .othd files directly in directory."""
    max_ts = None
    for fp in sorted(directory.glob('*.othd')):
        try:
            ts = _last_tsid(fp)
        except OSError:
            continue
        if ts is not None and (max_ts is None or ts > max_ts):
            max_ts = ts
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
    console.print("    case report [--dir PATH] [--run] [--size] [--update]")
    console.print()
    console.print("[bold]OPTIONS:[/bold]")
    console.print("    --dir PATH    Directory containing .cases file (default: current directory)")
    console.print("    --run         Add column with last timestep from each case's run directory")
    console.print("    --size        Add column with total disk usage of each case")
    console.print("    --update      Recompute everything, not reading .case_report")
    console.print("    -h, --help    Show this help message")
    console.print()
    console.print("[bold]COLUMNS:[/bold]")
    console.print("    Case              Case directory name")
    console.print("    Last (archive)    Last timestep reached by the .othd files in othd_files/")
    console.print("    Last (binary PLT) Highest PLT timestep in binary/")
    console.print("    Last (rundir)     Last timestep reached by the .othd files in the run directory (--run)")
    console.print("    Disk Usage        Total size of the case directory (--size)")
    console.print()
    console.print("[bold]CACHE:[/bold]")
    console.print("    The report is saved in .case_report beside .cases. The first `case report`")
    console.print("    in a shell session recomputes it; later ones read it (a column not in it yet")
    console.print("    is computed then) and say how old it is. Outside the shell every run is a")
    console.print("    first one. --update recomputes any time.")
    console.print()
    console.print("[bold]EXAMPLES:[/bold]")
    console.print("    case report")
    console.print("    case report --dir /scratch/me/project")
    console.print("    case report --size --update")
    console.print()
