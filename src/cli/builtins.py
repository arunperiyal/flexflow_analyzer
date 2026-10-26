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
                usage='missing [dir] [pattern] [--t1 N] [--t2 N] [--freq N] [--empty] [--extra] [-q]\n'
                      '       missing [case] [pattern] --dir NAME[,NAME...] [same flags]',
                details="  [cyan]dir[/cyan]       Where the files are (default: here)\n"
                        "  [cyan]pattern[/cyan]   File name with {} for the number; leave it out to\n"
                        "            check every numbered series in dir\n"
                        "  [cyan]--t1 N[/cyan]    First number (default: the lowest found)\n"
                        "  [cyan]--t2 N[/cyan]    Last number (default: the highest found)\n"
                        "  [cyan]--freq N[/cyan]  Step between numbers (default: inferred from the files)\n"
                        "  [cyan]--empty[/cyan]   Also report 0-byte files\n"
                        "  [cyan]--extra[/cyan]   Also report files between the expected steps\n"
                        "  [cyan]-q[/cyan]        Only the summary line\n"
                        "  [cyan]--dir A,B[/cyan] Directories of the case to check, each with the\n"
                        "            directories one level in it (field render's camera views).\n"
                        "            The first word is then the case, by default `use case:`\n"
                        "[dim]Expects t1, t1+freq, ... up to t2; zero padding follows the files.\n"
                        "With no pattern, names that differ only in a number form a series\n"
                        "(riser.{}_0.out, riser.{}_1.out, ... one per subgrid), and each is\n"
                        "checked with the same flags. The directory can also be part of the\n"
                        "pattern (post/slice_{}.png). Exits 1 if anything is missing (or\n"
                        "empty, with --empty). In a pipe it prints just the names.\n"
                        "  missing post                       # every series in post/\n"
                        "  missing post 'slice_xVor_{}.png'   # just this one\n"
                        "  missing binary riser.{}.plt --empty\n"
                        "  missing post --t1 3000 --t2 5000 --freq 50\n"
                        "  missing post | wc -l\n"
                        "  use case:CS4SG3U6P0\n"
                        "  missing --dir slice_xVor,slice_zVor_yplane   # each view of both\n"
                        "  missing CS4SG3U1P0 --dir slice_xVor --freq 50[/dim]",
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


_MISSING_USAGE = ("usage: missing [dir] [pattern] [--t1 N] [--t2 N] [--freq N] [--empty] [--extra] [-q]\n"
                  "       missing [case] [pattern] --dir NAME[,NAME...] [same flags]")


def _missing_args(argv):
    """(words, {t1, t2, freq}, flags, dirs) or an error message. dirs is the
    --dir list, or None without it."""
    numbers, flags, rest, dirs = {}, set(), [], None
    args = iter(argv)
    for arg in args:
        name, eq, value = arg.partition('=')
        if name == '--dir':
            if not eq:
                value = next(args, None)
                if value is None:
                    return "--dir needs a value: NAME[,NAME...]"
            dirs = (dirs or []) + [d.strip().strip('/') for d in value.split(',') if d.strip()]
            if not dirs:
                return "--dir needs a value: NAME[,NAME...]"
        elif name in ('--t1', '--t2', '--freq'):
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
    if len(rest) > 2:
        return _MISSING_USAGE
    if numbers.get('freq', 1) < 1:
        return "--freq must be 1 or more"
    if 't1' in numbers and 't2' in numbers and numbers['t1'] > numbers['t2']:
        return f"--t1 {numbers['t1']} is after --t2 {numbers['t2']}"
    return rest, numbers, flags, dirs


def _missing_series(folder):
    """The numbered series in folder, as (prefix, suffix) around the number.
    Names are grouped by their text between digit runs; the run that takes
    the most values is the number, so riser.{}_0.out and riser.{}_1.out are
    two series, one per subgrid. A series needs two numbers or more."""
    shapes = {}
    for entry in os.scandir(folder):
        if entry.name.startswith('.') or not entry.is_file():
            continue
        parts = re.split(r'(\d+)', entry.name)
        if len(parts) > 1:
            shapes.setdefault(tuple(parts[0::2]), []).append(tuple(parts[1::2]))
    series = set()
    for text, runs in shapes.items():
        distinct = [len({r[i] for r in runs}) for i in range(len(runs[0]))]
        vary = max(range(len(distinct)), key=lambda i: (distinct[i], i))
        groups = {}
        for r in runs:
            groups.setdefault(r[:vary] + r[vary + 1:], set()).add(r[vary])
        for fixed, values in groups.items():
            if len(values) < 2:
                continue
            digits = list(fixed[:vary]) + ['{}'] + list(fixed[vary:])
            name = ''.join(t + d for t, d in zip(text, digits + ['']))
            prefix, suffix = name.split('{}')
            series.add((prefix, suffix))
    return sorted(series, key=lambda ps: [int(c) if c.isdigit() else c.lower()
                                          for c in re.split(r'(\d+)', ps[0] + '{}' + ps[1])])


def _missing(rt, argv):
    """The numbers of a series like slice_{}.png that have no file; given just
    a directory, every numbered series in it."""
    parsed = _missing_args(argv)
    if isinstance(parsed, str):
        rt.error(f"missing: {parsed}" if not parsed.startswith('usage') else parsed)
        return 2
    rest, numbers, flags, dirs = parsed
    if dirs is not None:
        return _missing_in_case(rt, rest, numbers, flags, dirs)
    # A directory may come before the pattern: `missing post slice_{}.png` is
    # post/slice_{}.png; `missing post` alone is every series in post/.
    if not rest:
        rest = ['.']
    if len(rest) == 2:
        rest = [rest[0].rstrip('/') + '/' + rest[1] if rest[0].rstrip('/') else '/' + rest[1]]
    pattern = rest[0]
    if '{}' not in pattern and rt.resolve_path(pattern).is_dir():
        typed_dir = pattern.rstrip('/') or '/'
        typed_dir = '' if typed_dir == '.' else typed_dir
        folder = rt.resolve_path(pattern)
        series = _missing_series(folder)
        if not series:
            rt.warn(f"missing: no numbered series in {escape(pattern)}")
            return 1
        status = 0
        for i, (prefix, suffix) in enumerate(series):
            if i and not rt.capturing and 'q' not in flags:
                rt.console.print()
            status = max(status, _missing_check(rt, folder, typed_dir, prefix, suffix,
                                                numbers, flags, labelled=True))
        return status

    typed_dir, _, name = pattern.rpartition('/')
    if name.count('{}') != 1 or '{}' in typed_dir:
        rt.error("missing: the file name needs one {} where the number goes "
                 "(or give just a directory)")
        return 2
    folder = rt.resolve_path(typed_dir) if typed_dir else rt.cwd
    if not folder.is_dir():
        rt.error(f"missing: not a directory: {escape(str(folder))}")
        return 1
    prefix, suffix = name.split('{}')
    return _missing_check(rt, folder, typed_dir, prefix, suffix, numbers, flags)


def _missing_in_case(rt, rest, numbers, flags, dirs):
    """`missing [case] [pattern] --dir A,B`: the series under each of the
    case's directories A, B -- in it and in each subdirectory one level down,
    which is where `field render` files each camera view. The case is the
    `use case:` context when not given, else the current directory."""
    pattern = rest.pop() if rest and '{}' in rest[-1] else None
    if len(rest) > 1:
        rt.error(_MISSING_USAGE)
        return 2
    if pattern is not None and (pattern.count('{}') != 1 or '/' in pattern):
        rt.error("missing: with --dir the pattern is a file name with one {} (no /)")
        return 2
    case = rest[0] if rest else rt.get('case')
    if case == '*':
        rt.error("missing: --dir checks one case, and `use case:` is '*'; give the case")
        return 2
    case_dir = rt.resolve_path(case) if case else rt.cwd
    if not case_dir.is_dir():
        rt.error(f"missing: not a directory: {escape(str(case_dir))}")
        return 1

    def shown(folder):
        try:
            rel = os.path.relpath(folder, rt.cwd)
        except ValueError:
            rel = str(folder)
        rel = str(folder) if rel.startswith('..') else rel
        return '' if rel == '.' else rel

    status, printed = 0, False
    for name in dirs:
        base = case_dir / name
        if not base.is_dir():
            rt.warn(f"missing: no {escape(name)}/ in {escape(str(case_dir))}")
            status = max(status, 1)
            continue
        folders = [base] + sorted((Path(e.path) for e in os.scandir(base)
                                   if e.is_dir() and not e.name.startswith('.')),
                                  key=lambda p: p.name)
        checked = 0
        for folder in folders:
            if pattern is None:
                series = _missing_series(folder)
            else:
                prefix, suffix = pattern.split('{}')
                hit = re.compile(re.escape(prefix) + r'\d+' + re.escape(suffix) + '$')
                series = ([(prefix, suffix)] if any(hit.match(e.name) for e in os.scandir(folder))
                          else [])
            for prefix, suffix in series:
                if printed and not rt.capturing and 'q' not in flags:
                    rt.console.print()
                printed = True
                checked += 1
                status = max(status, _missing_check(rt, folder, shown(folder), prefix, suffix,
                                                    numbers, flags, labelled=True))
        if not checked:
            what = f"'{pattern}'" if pattern else "numbered series"
            rt.warn(f"missing: no {escape(what)} in {escape(name)}/ or the directories in it")
            status = max(status, 1)
    return status


def _missing_check(rt, folder, typed_dir, prefix, suffix, numbers, flags, labelled=False):
    """Report one series; labelled puts its pattern on the summary line."""
    pattern = (f"{typed_dir}/" if typed_dir else '') + f"{prefix}{{}}{suffix}"
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
        rt.error(f"missing: {pattern}: --t1 {t1} is after the last file, {t2}" if labelled
                 else f"missing: --t1 {t1} is after the last file, {t2}")
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
    kinds = bool(flags & {'empty', 'extra'})
    if 'q' not in flags:
        for kind, n, colour in rows:
            if rt.capturing:
                rt.out(f"{kind:<8} {shown(n)}" if kinds else shown(n))
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
        if labelled:
            text = f"{pattern}  " + text
        if rt.capturing:
            rt.out(("✗ " if bad else "✓ ") + text)
        else:
            if rows and 'q' not in flags:
                rt.console.print()
            rt.console.print(f"{mark} {escape(text)}", highlight=False)
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
