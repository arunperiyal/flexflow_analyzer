"""
FlexFlow's own shell builtins -- the ones that are not generic file handling:
`web`, `quota`, `du` and `find` -- and the colours `ls`/`tree` give FlexFlow
files.
"""

import os
import subprocess
import threading
from pathlib import Path

from rich import box
from rich.markup import escape
from rich.table import Table

from shellkit import Builtin

CASE_INDICATORS = ('input', 'output', 'binary', 'simflow.config', 'case.config')
CASE_GLOBS = ('*.othd', '*.oisd')


def is_case_directory(path: Path) -> bool:
    """True if a directory looks like a FlexFlow case."""
    if not path.is_dir():
        return False
    try:
        if any((path / name).exists() for name in CASE_INDICATORS):
            return True
        return any(next(path.glob(pattern), None) for pattern in CASE_GLOBS)
    except OSError:
        return False


def file_style(path: Path):
    """Colour for a name in `ls` / `tree`: cases green, data magenta, scripts yellow."""
    if path.is_dir():
        return 'bold green' if is_case_directory(path) else None
    if path.suffix in ('.othd', '.oisd', '.plt'):
        return 'magenta'
    if path.suffix == '.sh' or path.name.startswith('slurm-'):
        return 'yellow'
    return None


def builtins():
    return [
        Builtin('web', _web, help='Start/stop the web UI in this shell',
                usage='web start [--root PATH] [--port N] | web stop',
                complete=lambda rt, args, cur: [] if args else
                [('start', 'Start the web UI'), ('stop', 'Stop it')],
                category='FlexFlow', own_help=True),
        Builtin('quota', _quota, help='Disk quota for /home and /scratch', category='FlexFlow'),
        Builtin('du', _du, help='Disk usage of directory entries', usage='du [path]',
                complete='path', category='FlexFlow'),
        Builtin('find', _find, help='Find case directories', usage='find [pattern]',
                details="  [dim]find           # every case below here\n"
                        "  find CS4        # cases with CS4 in the name[/dim]",
                category='FlexFlow'),
    ]


# ---------------------------------------------------------------------------
# web
# ---------------------------------------------------------------------------

class _WebServer:
    """The werkzeug server `web start` runs on a background thread."""
    server = None
    thread = None
    url = None


def _web(rt, argv):
    if not argv or argv[0] in ('--help', '-h', 'help'):
        rt.console.print("[yellow]Usage:[/yellow] web start [--root PATH] [--port N]  |  web stop")
        rt.console.print("[dim]Starts the Flask web UI on a background thread inside this shell.[/dim]")
        return 0

    sub = argv[0].lower()
    if sub == 'start':
        return _web_start(rt, argv[1:])
    if sub == 'stop':
        return _web_stop(rt)
    rt.warn(f"Unknown web subcommand: {sub} (web start|stop)")
    return 2


def _web_start(rt, rest):
    if _WebServer.server is not None:
        rt.warn(f"Web UI already running at {_WebServer.url}")
        return 0

    root, port = str(rt.cwd), 8080
    i = 0
    while i < len(rest):
        if rest[i] == '--root' and i + 1 < len(rest):
            root, i = rest[i + 1], i + 2
        elif rest[i] == '--port' and i + 1 < len(rest):
            try:
                port = int(rest[i + 1])
            except ValueError:
                rt.error(f"Invalid --port: {escape(rest[i + 1])}")
                return 2
            i += 2
        else:
            rt.warn(f"Unknown option: {rest[i]}")
            return 2

    workspace_root = rt.resolve_path(root).resolve()
    if not workspace_root.is_dir():
        rt.error(f"Not a directory: {workspace_root}")
        return 1

    try:
        from werkzeug.serving import make_server
        from src.web.server import create_app
        server = make_server('127.0.0.1', port, create_app(workspace_root))
    except OSError as exc:
        rt.error(f"Could not start the web UI: {escape(str(exc))}")
        return 1

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _WebServer.server, _WebServer.thread = server, thread
    _WebServer.url = f"http://127.0.0.1:{port}"
    rt.console.print(f"[green]Web UI running at {_WebServer.url}[/green]  "
                     f"(workspace: [cyan]{escape(str(workspace_root))}[/cyan])")
    rt.console.print("[dim]No authentication -- reach it over `ssh -L` from elsewhere. "
                     "`web stop` shuts it down.[/dim]")
    return 0


def _web_stop(rt):
    if _WebServer.server is None:
        rt.warn("Web UI is not running.")
        return 0
    _WebServer.server.shutdown()
    _WebServer.thread.join(timeout=5)
    _WebServer.server = _WebServer.thread = _WebServer.url = None
    rt.console.print("[green]Web UI stopped.[/green]")
    return 0


# ---------------------------------------------------------------------------
# quota / du / find
# ---------------------------------------------------------------------------

def _quota(rt, argv):
    """lfs quota for /home and /scratch."""
    user = os.environ.get('USER', '')
    if not user:
        rt.error("$USER not set")
        return 1
    for fs in ('/home', '/scratch'):
        rt.console.print(f"[bold cyan]{fs}[/bold cyan]")
        try:
            result = subprocess.run(['lfs', 'quota', '-u', user, fs, '-h'],
                                    capture_output=True, text=True)
        except FileNotFoundError:
            rt.warn("lfs not found — not on a Lustre filesystem")
            return 1
        output = (result.stdout or '') + (result.stderr or '')
        rt.out(output.rstrip() if output.strip() else '(no output)')
        rt.console.print()
    return 0


def _du(rt, argv):
    """Size of each entry in a directory, largest first."""
    target = rt.resolve_path(argv[0]) if argv else rt.cwd
    if not target.is_dir():
        rt.error(f"Not a directory: {escape(str(target))}")
        return 1

    entries = []
    try:
        with os.scandir(target) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        size = sum(f.stat().st_size for f in Path(entry.path).rglob('*')
                                   if f.is_file())
                        entries.append((size, entry.name + '/'))
                    else:
                        entries.append((entry.stat(follow_symlinks=False).st_size, entry.name))
                except OSError:
                    entries.append((0, entry.name))
    except OSError as e:
        rt.error(f"Error reading directory: {escape(str(e))}")
        return 1

    if not entries:
        rt.console.print("[dim]Empty directory.[/dim]")
        return 0

    def fmt(n):
        for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
            if n < 1024:
                return f"{n:.1f} {unit}" if unit != 'B' else f"{n} B"
            n /= 1024
        return f"{n:.1f} PB"

    table = Table(title=f"Disk Usage  ({target})", box=box.ROUNDED, header_style='bold')
    table.add_column('Size', justify='right', style='green', no_wrap=True)
    table.add_column('Name', style='cyan')
    for size, label in sorted(entries, reverse=True):
        table.add_row(fmt(size), escape(label))
    rt.console.print(table)
    return 0


def _find(rt, argv):
    """Case directories below the cwd whose name contains the pattern."""
    pattern = argv[0] if argv else '*'
    rt.console.print(f"[dim]Searching for cases matching '{escape(pattern)}'...[/dim]")
    found = [p for p in rt.cwd.rglob('*')
             if is_case_directory(p) and (pattern == '*' or pattern.lower() in p.name.lower())]
    if not found:
        rt.warn(f"No cases found matching '{pattern}'")
        return 1

    if rt.capturing:
        for case in found:
            rt.out(str(case.relative_to(rt.cwd)))
        return 0
    table = Table(title=f"Cases Found ({len(found)})", box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("Case Name", style="green")
    table.add_column("Path", style="cyan")
    for i, case in enumerate(found, 1):
        table.add_row(str(i), escape(case.name), escape(str(case.relative_to(rt.cwd))))
    rt.console.print(table)
    return 0
