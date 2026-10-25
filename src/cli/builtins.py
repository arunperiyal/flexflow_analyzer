"""
FlexFlow's own shell builtins -- `web`, `quota`, `missing` -- the basic file and
system commands shellkit does not have (`find`, `mkdir`, `mv`, `touch`,
`top`), so the shell need not be left for them, and the colours `ls`/`tree`
give FlexFlow files.
"""

import fnmatch
import math
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

from rich.markup import escape

from shellkit import Builtin
from shellkit.builtins.files import _expand, _shown_path, _split_flags, _styled

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
        Builtin('find', _find, help='Find files and directories by name',
                usage='find [-f|-d|-c] [pattern] [path]',
                details="  [cyan]-f[/cyan]  Files only\n"
                        "  [cyan]-d[/cyan]  Directories only\n"
                        "  [cyan]-c[/cyan]  Case directories only\n"
                        "[dim]A pattern with * ? [ is a glob on the name, anything else a\n"
                        "substring; both ignore case. Hidden directories are skipped.\n"
                        "  find riser*.othd     # every riser othd below here\n"
                        "  find -d RUN_         # run directories\n"
                        "  find -c CS4          # cases with CS4 in the name[/dim]",
                complete='path', category='Files'),
        Builtin('missing', _missing, help='Missing files in a numbered series',
                usage='missing [dir] <pattern> [--t1 N] [--t2 N] [--freq N] [--empty] [--extra] [-q]',
                details="  [cyan]--t1 N[/cyan]    First number (default: the lowest found)\n"
                        "  [cyan]--t2 N[/cyan]    Last number (default: the highest found)\n"
                        "  [cyan]--freq N[/cyan]  Step between numbers (default: inferred from the files)\n"
                        "  [cyan]--empty[/cyan]   Also report 0-byte files\n"
                        "  [cyan]--extra[/cyan]   Also report files between the expected steps\n"
                        "  [cyan]-q[/cyan]        Only the summary line\n"
                        "[dim]{} in the pattern stands for the number; zero padding follows the\n"
                        "files found; a directory may come first or be part of the pattern.\n"
                        "Expects t1, t1+freq, ... up to t2. Exits 1 if any is\n"
                        "missing (or empty, with --empty). In a pipe it prints just the names.\n"
                        "  missing 'slice_xVor_{}.png' --t1 3000 --t2 5000 --freq 50\n"
                        "  missing binary riser.{}.plt --empty\n"
                        "  missing 'img_{}.png' | wc -l[/dim]",
                complete='path', category='Files'),
        Builtin('mkdir', _mkdir, help='Make directories', usage='mkdir [-p] <dir> [dirs...]',
                details="  [cyan]-p[/cyan]  Make parents as needed; no error if it exists",
                complete='path', category='Files'),
        Builtin('mv', _mv, help='Move or rename files', usage='mv [-f] <source> [sources...] <dest>',
                details="  [cyan]-f[/cyan]  Replace an existing target without asking",
                complete='path', category='Files'),
        Builtin('touch', _touch, help='Create a file, or update its time',
                usage='touch <file> [files...]', complete='path', category='Files'),
        Builtin('top', _top, help='Running processes (the system top)',
                usage='top [top options]',
                details="[dim]Options go to top as they are: `top -u $USER`. Quit with q.\n"
                        "In a pipe it prints one snapshot: `top | grep flexflow`.[/dim]",
                category='Shell', own_help=True),
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
# quota
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


# ---------------------------------------------------------------------------
# find / mkdir / mv / touch / top
# ---------------------------------------------------------------------------

def _find(rt, argv):
    """Paths below a directory whose name matches the pattern."""
    flags, rest, bad = _split_flags(argv, 'fdc')
    if bad:
        rt.error(f"find: unknown option {bad}")
        return 2
    if len(rest) > 2:
        rt.error("usage: find [-f|-d|-c] [pattern] [path]")
        return 2
    pattern = rest[0] if rest else '*'
    root = rt.resolve_path(rest[1]) if len(rest) > 1 else rt.cwd
    if not root.is_dir():
        rt.error(f"find: not a directory: {escape(str(root))}")
        return 1

    if any(c in pattern for c in '*?['):
        glob = pattern.lower()
        matches = lambda name: fnmatch.fnmatchcase(name.lower(), glob)
    else:
        needle = pattern.lower()
        matches = lambda name: needle in name.lower()

    found = []
    for top, dirs, files in os.walk(root, onerror=lambda e: None):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        top = Path(top)
        if 'f' not in flags:
            found.extend(top / d for d in dirs if matches(d))
        if not flags & {'d', 'c'}:
            found.extend(top / f for f in sorted(files) if matches(f))
    if 'c' in flags:
        found = [p for p in found if is_case_directory(p)]

    if not found:
        rt.warn(f"find: nothing matches '{pattern}'")
        return 1
    for path in found:
        shown = _shown_path(rt, path)
        if rt.capturing:
            rt.out(shown + ('/' if path.is_dir() else ''))
        else:
            parent = escape(str(Path(shown).parent))
            rt.console.print(('' if parent == '.' else f"[dim]{parent}/[/dim]") + _styled(rt, path),
                             highlight=False)
    if not rt.capturing:
        rt.console.print(f"[dim]{len(found)} found[/dim]")
    return 0


_MISSING_USAGE = "usage: missing [dir] <pattern> [--t1 N] [--t2 N] [--freq N] [--empty] [--extra] [-q]"


def _missing_args(argv):
    """(pattern, {t1, t2, freq}, flags) or an error message. A directory may
    come before the pattern: `missing post slice_{}.png` is post/slice_{}.png."""
    numbers, flags, rest = {}, set(), []
    args = iter(argv)
    for arg in args:
        name, eq, value = arg.partition('=')
        if name in ('--t1', '--t2', '--freq'):
            if not eq:
                value = next(args, None)
                if value is None:
                    return f"{name} needs a value"
            try:
                numbers[name[2:]] = int(value)
            except ValueError:
                return f"{name} needs a whole number, not '{value}'"
        elif arg in ('--empty', '--extra', '-q'):
            flags.add(arg.lstrip('-'))
        elif arg.startswith('-') and len(arg) > 1:
            return f"unknown option {arg}"
        else:
            rest.append(arg)
    if len(rest) == 2:
        rest = [rest[0].rstrip('/') + '/' + rest[1] if rest[0].rstrip('/') else '/' + rest[1]]
    if len(rest) != 1:
        return _MISSING_USAGE
    if numbers.get('freq', 1) < 1:
        return "--freq must be 1 or more"
    if 't1' in numbers and 't2' in numbers and numbers['t1'] > numbers['t2']:
        return f"--t1 {numbers['t1']} is after --t2 {numbers['t2']}"
    return rest[0], numbers, flags


def _missing(rt, argv):
    """The numbers of a series like slice_{}.png that have no file."""
    parsed = _missing_args(argv)
    if isinstance(parsed, str):
        rt.error(f"missing: {parsed}" if not parsed.startswith('usage') else parsed)
        return 2
    pattern, numbers, flags = parsed
    typed_dir, _, name = pattern.rpartition('/')
    if name.count('{}') != 1 or '{}' in typed_dir:
        rt.error("missing: the file name needs one {} where the number goes")
        return 2
    folder = rt.resolve_path(typed_dir) if typed_dir else rt.cwd
    if not folder.is_dir():
        rt.error(f"missing: not a directory: {escape(str(folder))}")
        return 1

    prefix, suffix = name.split('{}')
    number = re.compile(re.escape(prefix) + r'(\d+)' + re.escape(suffix) + '$')
    found, pad = {}, 0
    for entry in os.scandir(folder):
        match = number.match(entry.name)
        if match:
            digits = match.group(1)
            found[int(digits)] = Path(entry.path)
            if len(digits) > 1 and digits.startswith('0'):
                pad = len(digits)

    t1 = numbers.get('t1', min(found, default=None))
    t2 = numbers.get('t2', max(found, default=None))
    if t1 is None or t2 is None:
        rt.warn(f"missing: no file matches '{pattern}' (give --t1 and --t2 to list them all)")
        return 1
    if t1 > t2:
        rt.error(f"missing: --t1 {t1} is after the last file, {t2}")
        return 2
    freq = numbers.get('freq')
    guessed = freq is None
    if guessed:
        freq = math.gcd(*(n - t1 for n in found if t1 <= n <= t2)) or 1
    if (t2 - t1) // freq > 5_000_000:
        rt.error(f"missing: {t1}..{t2} every {freq} is too many steps; give --freq")
        return 2

    expected = range(t1, t2 + 1, freq)
    missing = [n for n in expected if n not in found]
    empty = [n for n in expected if n in found and 'empty' in flags
             and found[n].stat().st_size == 0]
    extra = sorted(n for n in found if 'extra' in flags and t1 <= n <= t2 and (n - t1) % freq)

    shown = lambda n: (f"{typed_dir}/" if typed_dir else '') + f"{prefix}{n:0{pad}d}{suffix}"
    rows = ([('missing', n, 'red') for n in missing] + [('empty', n, 'yellow') for n in empty]
            + [('extra', n, 'cyan') for n in extra])
    rows.sort(key=lambda row: row[1])
    labelled = bool(flags & {'empty', 'extra'})
    if 'q' not in flags:
        for kind, n, colour in rows:
            if rt.capturing:
                rt.out(f"{kind:<8} {shown(n)}" if labelled else shown(n))
            else:
                rt.console.print(f"  [{colour}]{kind:<8}[/{colour}] {escape(shown(n))}",
                                 highlight=False)

    span = f"{t1}..{t2} every {freq}" + (" (inferred)" if guessed else "")
    if not rt.capturing or 'q' in flags:
        parts = [f"{len(missing)} of {len(expected)} missing" if missing
                 else f"all {len(expected)} present"]
        if 'empty' in flags:
            parts.append(f"{len(empty)} empty")
        if 'extra' in flags:
            parts.append(f"{len(extra)} extra")
        bad = missing or empty
        mark = "[red]✗[/red]" if bad else "[green]✓[/green]"
        text = ", ".join(parts) + f" · {span}"
        if rt.capturing:
            rt.out(("✗ " if bad else "✓ ") + text)
        else:
            if rows and 'q' not in flags:
                rt.console.print()
            rt.console.print(f"{mark} {text}", highlight=False)
    return 1 if missing or empty else 0


def _mkdir(rt, argv):
    flags, rest, bad = _split_flags(argv, 'p')
    if bad:
        rt.error(f"mkdir: unknown option {bad}")
        return 2
    if not rest:
        rt.error("usage: mkdir [-p] <dir> [dirs...]")
        return 2
    status = 0
    for name in rest:
        target = rt.resolve_path(name)
        try:
            target.mkdir(parents='p' in flags, exist_ok='p' in flags)
            rt.console.print(f"  [green]created[/green]  {escape(str(target))}")
        except FileExistsError:
            rt.error(f"mkdir: already exists: {escape(str(target))}")
            status = 1
        except FileNotFoundError:
            rt.error(f"mkdir: no parent directory (use -p): {escape(str(target))}")
            status = 1
        except OSError as e:
            rt.error(f"mkdir: {escape(str(e))}")
            status = 1
    return status


def _mv(rt, argv):
    argv = ['-f' if a == '--force' else a for a in argv]
    flags, rest, bad = _split_flags(argv, 'f')
    if bad:
        rt.error(f"mv: unknown option {bad}")
        return 2
    if len(rest) < 2:
        rt.error("usage: mv [-f] <source> [sources...] <dest>")
        return 2

    sources = _expand(rt, rest[:-1])
    dest = rt.resolve_path(rest[-1])
    if len(sources) > 1 and not dest.is_dir():
        rt.error("mv: destination must be an existing directory when moving several sources")
        return 1

    status = 0
    for src in sources:
        target = dest / src.name if dest.is_dir() else dest
        if not src.exists() and not src.is_symlink():
            rt.error(f"mv: not found: {escape(str(src))}")
            status = 1
            continue
        if target.exists():
            if target.is_dir():
                rt.error(f"mv: a directory is in the way: {escape(str(target))}")
                status = 1
                continue
            if src.is_dir():
                rt.error(f"mv: cannot replace a file with a directory: {escape(str(target))}")
                status = 1
                continue
            if 'f' not in flags and not rt.confirm(
                    f"  Replace [cyan]{escape(str(target))}[/cyan]?"):
                rt.console.print("  [dim]skipped[/dim]")
                continue
        try:
            shutil.move(str(src), str(target))
            rt.console.print(f"  [green]moved[/green]  {escape(str(src))}  →  {escape(str(target))}")
        except (OSError, shutil.Error) as e:
            rt.error(f"mv: {escape(str(e))}")
            status = 1
    return status


def _touch(rt, argv):
    if not argv:
        rt.error("usage: touch <file> [files...]")
        return 2
    status = 0
    for name in argv:
        target = rt.resolve_path(name)
        try:
            target.touch()
        except OSError as e:
            rt.error(f"touch: {escape(str(e))}")
            status = 1
    return status


def _top(rt, argv):
    """The system top: interactive at the prompt, one batch snapshot in a pipe."""
    if argv in (['-h'], ['--help']):
        rt.console.print("[yellow]Usage:[/yellow] top [top options]   "
                         "[dim](e.g. top -u $USER; q quits)[/dim]")
        return 0
    argv = [os.path.expandvars(a) for a in argv]     # `top -u $USER`
    try:
        if rt.capturing:
            result = subprocess.run(['top', '-b', '-n', '1', *argv], cwd=rt.cwd,
                                    capture_output=True, text=True)
            rt.out(result.stdout, end='')
            if result.returncode:
                rt.error(escape(result.stderr.strip() or f"top exited with {result.returncode}"))
            return result.returncode
        return subprocess.run(['top', *argv], cwd=rt.cwd).returncode
    except FileNotFoundError:
        rt.error("top not found")
        return 127
    except KeyboardInterrupt:
        return 130
