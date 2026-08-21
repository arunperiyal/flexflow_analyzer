"""
Case domain command: what a case's domain is made of, kept in `domain.yml`.

A case names the same cylinder three ways -- `beamSolid( "beam_1" )` in the .def,
`riser.cyl.srf` on disk, zone `cyl` in the PLT -- and joins none of them up. This
command writes the join down once, so `field compute --zone`, `case out --map` and
anything else that needs a body can start from a name a person actually uses.

`--init` derives what it can from the .def and the case's PLT zones; `body` and
`field` edit the result; `--check` says which of it the case still agrees with.

Accepts the `*` wildcard case for the read-only paths and for `--init`, in which
case every case in the `.cases` registry is done in turn -- a case that cannot be
done is reported and stepped over rather than ending the batch.
"""

import os
import sys
from pathlib import Path

from rich import box
from rich.console import Console
from rich.table import Table

from ....core.domain import (AXES, BODY_TYPES, DomainConfig, DomainError,
                             FIELD_TYPES, FILENAME, derive_from_def, dump,
                             plt_zone_names)
from ....core.simflow_config import SimflowConfig
from ....utils.logger import Logger
from ...case_iteration import is_wildcard_case, load_cases_from_directory

TARGETS = ('body', 'field')

# What `--init` writes. A file carrying anything else is not wrong -- the format
# is open, and `--set` will put whatever you like in it -- but if it holds keys
# that --init used to derive and no longer does, it predates the current shape,
# and saying so beats leaving someone to wonder why a fresh --init looks different.
DERIVED_KEYS = {
    'field': {'name', 'type', 'geotag', 'plttag'},
    'body': {'name', 'type', 'geotag', 'plttag', 'geometry', 'outputs'},
}
# Keys earlier versions derived and this one does not: the .def holds them, and a
# second copy here could only drift.
RETIRED_KEYS = ('properties', 'source', 'solver')

# Flags that put something on a body or the field, as (flag, key-within-the-entry).
# Kept as a table because the same flags have to be recognised when adding, when
# setting, and when reporting that one was given with nothing to apply it to.
ATTRIBUTE_FLAGS = (
    ('type',     'type'),
    ('geotag',   'geotag'),
    ('plttag',   'plttag'),
    ('velocity', 'velocity'),
    ('radius',   'geometry.radius'),
    ('length',   'geometry.length'),
    ('origin',   'geometry.origin'),
    ('axis',     'geometry.axis'),
)
GEOMETRY_ONLY_FLAGS = ('radius', 'length', 'origin', 'axis')
# The free stream belongs to the continuum, not to anything sitting in it.
FIELD_ONLY_FLAGS = ('velocity',)


class DomainCommandError(Exception):
    """This case could not be handled. `skip` marks the harmless kind: nothing to do."""

    def __init__(self, message, skip=False):
        super().__init__(message)
        self.skip = skip


# ---------------------------------------------------------------------------
# Resolving what to act on
# ---------------------------------------------------------------------------

def _current_context_case():
    """The case set with `use case:<name>` in the interactive shell, if any."""
    try:
        from src.cli.interactive import InteractiveShell
        shell = getattr(InteractiveShell, '_instance', None)
        return shell._current_case if shell else None
    except Exception:
        return None


def resolve_target_and_case(args):
    """Split `case domain [body|field] [CASE]` into (target, case).

    The target and the case share one positional slot each, and argparse cannot
    tell them apart on its own: making `body`/`field` a sub-parser would reject
    `case domain BR0SG0U1P0 --init`, because a case name is not one of the
    choices. So the first word is read as the target only when it *is* `body` or
    `field`, and otherwise falls through to being the case.

    The case resolves as everywhere else in the CLI: the argument, then the
    interactive case context, then the current directory.
    """
    target = getattr(args, 'target', None)
    case = getattr(args, 'case', None)
    if target is not None and target not in TARGETS:
        if case is not None:
            raise DomainCommandError(
                f"Unknown target '{target}'. Say "
                + " or ".join(f"`case domain {t}`" for t in TARGETS)
                + ", or give just a case directory for a summary of it.")
        target, case = None, target
    if case is None:
        case = _current_context_case() or os.getcwd()
    return target, case


def _problem(case_dir):
    try:
        return SimflowConfig.find(case_dir).problem
    except Exception:
        return None


def _load(case_dir, must_exist=True):
    """The case's DomainConfig. Raises DomainCommandError with what to do next."""
    case_dir = Path(case_dir)
    if not case_dir.is_dir():
        raise DomainCommandError(f"Case directory not found: {case_dir}")
    try:
        domain = DomainConfig.find(case_dir)
    except DomainError as exc:
        raise DomainCommandError(str(exc))
    if must_exist and not domain.exists:
        raise DomainCommandError(
            f"No {FILENAME} in {case_dir.name}. Write one from the case's own .def "
            f"with `case domain {case_dir.name} --init`.", skip=True)
    return domain


# ---------------------------------------------------------------------------
# Reading values off the command line
# ---------------------------------------------------------------------------

def _scalar(text):
    """A command-line value as the YAML scalar it looks like.

    `0.5` becomes a float, `[0, 0, 0]` a list, `null` a None, `+x` and `FIELD`
    stay strings. Reading it as YAML rather than as text means what `--set` puts
    in the file is what a person writing that line by hand would have put there.
    """
    import yaml
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return text


def _vector3(text, what):
    """`0,0,1` or `"[0, 0, 1]"` as three numbers -- both forms people write."""
    value = _scalar(text) if text.strip().startswith('[') else [
        _scalar(part) for part in text.split(',')]
    if (not isinstance(value, list) or len(value) != 3
            or not all(isinstance(c, (int, float)) and not isinstance(c, bool)
                       for c in value)):
        raise DomainCommandError(f"{what} wants three numbers, e.g. 0,0,1 "
                                 f"(got '{text}')")
    return value


def _assignments(args, kind):
    """Every `key -> value` the flags ask for, in the order they were written.

    Both the shorthand flags (`--radius 1`) and the general `--set k=v` land here,
    so adding and editing put values in exactly the same places.
    """
    pairs = []
    types = FIELD_TYPES if kind == 'field' else BODY_TYPES
    for flag, key in ATTRIBUTE_FLAGS:
        raw = getattr(args, flag, None)
        if raw is None:
            continue
        if kind == 'field' and flag in GEOMETRY_ONLY_FLAGS:
            raise DomainCommandError(
                f"--{flag} describes a body's shape; the field has none. Use "
                f"`case domain body --set {key}=...` for a body.")
        if kind != 'field' and flag in FIELD_ONLY_FLAGS:
            raise DomainCommandError(
                f"--{flag} describes the flow the bodies sit in, which belongs to "
                f"the field. Use `case domain field --{flag} ...`.")
        if flag == 'type' and raw not in types:
            raise DomainCommandError(f"Unknown --type '{raw}' for a {kind}. Choose one "
                                     f"of: {', '.join(types)}")
        if flag == 'axis' and raw not in AXES and not raw.strip().startswith('['):
            raise DomainCommandError(f"Unknown --axis '{raw}'. Choose one of "
                                     f"{', '.join(AXES)}, or give a vector like "
                                     f"'[1, 0, 0]'")
        if flag in ('origin', 'velocity'):
            pairs.append((key, _vector3(raw, f"--{flag}")))
        elif flag == 'axis':
            pairs.append((key, _scalar(raw) if raw.strip().startswith('[') else raw))
        elif flag in ('radius', 'length'):
            value = _scalar(raw)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise DomainCommandError(f"--{flag} wants a number (got '{raw}')")
            pairs.append((key, value))
        else:
            pairs.append((key, raw))

    for item in getattr(args, 'set', None) or []:
        if '=' not in item:
            raise DomainCommandError(f"--set wants key=value (got '{item}'). Dotted "
                                     "keys reach inside, e.g. geometry.radius=0.5")
        key, _, raw = item.partition('=')
        key = key.strip()
        if not key:
            raise DomainCommandError(f"--set has no key before the '=' in '{item}'")
        value = _scalar(raw)
        if key == 'type' and value not in types:
            raise DomainCommandError(f"Unknown type '{value}' for a {kind}. Choose one "
                                     f"of: {', '.join(types)}")
        pairs.append((key, value))
    return pairs


# ---------------------------------------------------------------------------
# Describing an entry
# ---------------------------------------------------------------------------

def _number(value):
    """A number the way it should be read at a glance, or the value as written."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value) if value is not None else None
    if isinstance(value, int):
        return str(value)
    if value == 0 or 1e-3 <= abs(value) < 1e5:
        return f"{value:g}"
    return f"{value:.4g}"


def _shape_summary(entry):
    """A body's geometry on one line: 'r=0.5 L=12 +x @ (0, 0, 0)'."""
    geometry = entry.get('geometry') or {}
    if not geometry:
        return None
    parts = []
    if geometry.get('radius') is not None:
        parts.append(f"r={_number(geometry['radius'])}")
    if geometry.get('length') is not None:
        parts.append(f"L={_number(geometry['length'])}")
    if geometry.get('axis') is not None:
        axis = geometry['axis']
        parts.append(axis if isinstance(axis, str)
                     else "(" + ", ".join(_number(c) for c in axis) + ")")
    origin = geometry.get('origin')
    if isinstance(origin, list) and len(origin) == 3:
        parts.append("@ (" + ", ".join(_number(c) for c in origin) + ")")
    missing = [k for k in ('radius', 'length') if geometry.get(k) is None]
    if missing:
        parts.append(f"[yellow]{'/'.join(missing)} unset[/yellow]")
    return " ".join(parts) if parts else None


def _flow_summary(entry):
    """The field's free stream: '[0, 0, 1] |U| = 1', or that it is not declared."""
    velocity = entry.get('velocity')
    if velocity is None:
        return "[yellow]velocity unset[/yellow]"
    if not isinstance(velocity, list) or len(velocity) != 3:
        return f"[yellow]{velocity!r}[/yellow]"
    speed = sum(float(c) ** 2 for c in velocity) ** 0.5
    return ("[" + ", ".join(_number(c) for c in velocity) + "]"
            + f" [dim]|U| = {_number(speed)}[/dim]")


def _properties_summary(entry, limit=3):
    """The first few properties, flattened: 'density=1000, viscosity=1'."""
    properties = entry.get('properties') or {}
    shown = []
    for key, value in properties.items():
        if isinstance(value, dict):
            inner = ", ".join(f"{k}={_number(v)}" for k, v in value.items())
            shown.append(f"{key}={{{inner}}}" if inner else key)
        else:
            shown.append(f"{key}={_number(value)}")
    if not shown:
        return None
    if len(shown) > limit:
        return ", ".join(shown[:limit]) + f" [dim](+{len(shown) - limit})[/dim]"
    return ", ".join(shown)


def _output_summary(entry, case_dir):
    """A body's output blocks: 'riser_probe -> riser.cyl_nodes.nbc'.

    The node file is named alongside the block because it is the half that
    matters when reading an othd back: the records are positional, ordered by it.
    A file that is not there is marked, since the map cannot be built without it.
    """
    shown = []
    for output in entry.get('outputs') or []:
        if not isinstance(output, dict):
            continue
        block = output.get('block') or '[yellow]<unnamed>[/yellow]'
        nodes = output.get('nodes')
        if not nodes:
            shown.append(block)
        elif case_dir is not None and not (Path(case_dir) / nodes).exists():
            shown.append(f"{block} -> [yellow]{nodes}[/yellow]")
        else:
            shown.append(f"{block} -> {nodes}")
    return "\n".join(shown) if shown else None


def _cells(kind, entry, domain, case_dir, problem):
    """One entry as table cells: Kind, Name, Type, Geotag, Plttag, Shape, Output."""
    def tag(value, count=None):
        if not value:
            return "[dim]--[/dim]"
        if count is None:
            return str(value)
        return f"{value} [dim]({count})[/dim]" if count else f"[yellow]{value}[/yellow]"

    name = entry.get('name') or "[yellow]<unnamed>[/yellow]"
    files = domain.geometry_files(entry.get('name') or entry.get('geotag') or '',
                                  problem, case_dir) if entry.get('geotag') else []
    # A body is described by its shape, the field by the flow it carries: one
    # column, because no entry has both and two would leave half of each empty.
    describes = (_flow_summary(entry) if kind == 'field'
                 else _shape_summary(entry) or _properties_summary(entry))
    return (kind, name, entry.get('type') or "[dim]--[/dim]",
            tag(entry.get('geotag'), len(files)), tag(entry.get('plttag')),
            describes or "[dim]--[/dim]",
            _output_summary(entry, case_dir) or "[dim]--[/dim]")


def _entries(domain, kind=None):
    """(kind, entry) pairs for the field and bodies, filtered by `kind`."""
    out = []
    if kind in (None, 'field') and domain.field is not None:
        out.append(('field', domain.field))
    if kind in (None, 'body'):
        out += [('body', body) for body in domain.bodies]
    return out


def _table(title, with_case=False):
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow",
                  title=title, title_justify="left", title_style="bold cyan")
    if with_case:
        table.add_column("Case")
    for column in ("Kind", "Name", "Type", "Geotag", "Plttag", "Shape / flow",
                   "Output"):
        table.add_column(column)
    return table


def _legend(console):
    console.print("[dim]Geotag counts the geometry files it matches; yellow means none "
                  "were found. Output is the outputTimeHistory block written along "
                  "the body, and the node file that orders its records. `case domain "
                  "--check` says what the case disagrees with.[/dim]")


# ---------------------------------------------------------------------------
# The read-only views
# ---------------------------------------------------------------------------

def _show_summary(console, case_dir, kind=None):
    """The domain of one case as a table."""
    case_dir = Path(case_dir)
    domain = _load(case_dir)
    problem = _problem(case_dir)
    rows = _entries(domain, kind)
    what = {'body': 'Bodies', 'field': 'Field', None: 'Domain'}[kind]
    if not rows:
        missing = {'body': 'body', 'field': 'field', None: 'field or body'}[kind]
        fix = ("`case domain field --add --name water --type fluid`" if kind == 'field'
               else "`case domain body --add --name cyl --type beam`")
        raise DomainCommandError(f"{FILENAME} in {case_dir.name} declares no {missing}; "
                                 f"add one with {fix}", skip=True)

    table = _table(f"{what} of {case_dir.name}")
    for entry_kind, entry in rows:
        table.add_row(*_cells(entry_kind, entry, domain, case_dir, problem))
    console.print()
    console.print(table)
    console.print(f"[dim]{domain.path}[/dim]")
    _legend(console)
    console.print()


def _show_entry(console, case_dir, token, kind):
    """One body or the field, in full, as the YAML it is stored as."""
    case_dir = Path(case_dir)
    domain = _load(case_dir)
    if kind == 'body' and token is True:
        raise DomainCommandError(
            "Which body? `case domain body --show <name>`. Declared: "
            f"{', '.join(_load(case_dir).body_names()) or 'none'}")
    entry = domain.body(token) if kind == 'body' else domain.field
    if entry is None:
        if kind == 'body':
            raise DomainCommandError(
                f"No body '{token}' in {case_dir.name}/{FILENAME}. Declared: "
                f"{', '.join(domain.body_names()) or 'none'}")
        raise DomainCommandError(f"No field declared in {case_dir.name}/{FILENAME}")
    console.print()
    console.print(f"[bold cyan]{kind}[/bold cyan] "
                  f"[bold]{entry.get('name') or '<unnamed>'}[/bold] "
                  f"[dim]in {case_dir.name}/{FILENAME}[/dim]")
    console.print()
    for line in dump(entry).rstrip().splitlines():
        console.print("  " + line)
    problem = _problem(case_dir)
    files = domain.geometry_files(entry.get('name') or entry.get('geotag') or '',
                                  problem, case_dir)
    console.print()
    if files:
        console.print(f"  [bold]geometry files[/bold] ({len(files)}):")
        for path in files:
            console.print(f"    {path.name}")
    elif entry.get('geotag'):
        console.print(f"  [yellow]no geometry file matches geotag "
                      f"'{entry['geotag']}'[/yellow]")
    console.print()


def _list_all(console, logger, kind=None):
    """Every registered case's domain in one table.

    One table rather than one per case: the question `*` asks is which cases have
    a domain declared yet, and that is answered by scanning a column.
    """
    cases = _registry(logger)
    table = _table(None, with_case=True)
    listed, skipped, failed, entries = [], [], [], 0
    for name, path in cases:
        try:
            domain = _load(path)
            rows = _entries(domain, kind)
        except DomainCommandError as exc:
            (skipped if exc.skip else failed).append((name, str(exc)))
            continue
        if not rows:
            skipped.append((name, f"{FILENAME} declares no {kind or 'field or body'}"))
            continue
        listed.append(name)
        entries += len(rows)
        problem = _problem(path)
        for i, (entry_kind, entry) in enumerate(rows):
            # The case name only on its first row: repeating it down a group makes
            # the column hard to scan, which is the one thing it is for.
            table.add_row(f"[bold]{name}[/bold]" if i == 0 else "",
                          *_cells(entry_kind, entry, domain, path, problem))

    console.print()
    if listed:
        what = {'body': 'Bodies', 'field': 'Field', None: 'Domain'}[kind]
        table.title = (f"{what} in {len(listed)} of {len(cases)} case(s)"
                       if len(listed) != len(cases)
                       else f"{what} across {len(cases)} case(s)")
        console.print(table)
    console.print(f"[bold]{len(listed)} case(s)[/bold], {entries} entr"
                  f"{'y' if entries == 1 else 'ies'}"
                  + (f"; {len(skipped)} skipped" if skipped else "")
                  + (f"; [yellow]{len(failed)} failed[/yellow]" if failed else ""))
    for who, why in skipped + failed:
        console.print(f"  [dim]{who}: {why}[/dim]")
    if listed:
        _legend(console)
    console.print()
    if not listed:
        sys.exit(1)


def _registry(logger):
    """[(name, path)] from the .cases file in the current directory."""
    cases = load_cases_from_directory(Path.cwd())
    if not cases:
        logger.error(f"No cases found. Is there a .cases file in {Path.cwd()}? "
                     "Build one with `case add`.")
        sys.exit(1)
    out = []
    for entry in cases:
        path = entry.get('path')
        if path:
            out.append((entry.get('name', Path(path).name), path))
        else:
            logger.warning(f"{entry.get('name', '?')}: no path in .cases; skipped")
    return out


# ---------------------------------------------------------------------------
# --init and --check
# ---------------------------------------------------------------------------

def init_case(case_dir, force=False):
    """Write domain.yml for one case from its .def. Returns (path, notes)."""
    case_dir = Path(case_dir)
    if not case_dir.is_dir():
        raise DomainCommandError(f"Case directory not found: {case_dir}")
    target = case_dir / FILENAME
    if target.exists() and not force:
        message = (f"{target} already exists. Edit it with `case domain body --set`, "
                   "or pass --force to derive it again from the .def -- which "
                   "discards anything the .def cannot say, the radius among it.")
        retired = _retired_keys(target)
        if retired:
            message += (f" It still carries {', '.join(retired)}, which --init no "
                        "longer writes: those live in the .def now. --force rewrites "
                        "it in the current shape.")
        raise DomainCommandError(message, skip=True)
    try:
        domain, notes = derive_from_def(case_dir)
    except DomainError as exc:
        raise DomainCommandError(str(exc), skip=True)
    return domain.save(), notes


def _retired_keys(path):
    """Keys in an existing domain.yml that --init used to write and no longer does.

    Read straight off the file rather than through DomainConfig, so a file too odd
    to load cannot turn a helpful aside into a second error.
    """
    try:
        import yaml
        data = yaml.safe_load(path.read_text())
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    entries = [data.get('field')] + list(data.get('bodies') or [])
    found = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for key in RETIRED_KEYS:
            if key in entry and key not in found:
                found.append(key)
    return found


def _init(console, logger, case_dir, force):
    path, notes = init_case(case_dir, force)
    console.print(f"[green]+[/green] Wrote {path}")
    for note in notes:
        console.print(f"  [yellow]note[/yellow] {note}")
    console.print()
    _show_summary(console, case_dir)


def _init_all(console, logger, force):
    cases = _registry(logger)
    console.print(f"\n[bold cyan]Deriving {FILENAME} for {len(cases)} case(s)"
                  f"[/bold cyan]\n")
    done, skipped, failed = [], [], []
    for name, path in cases:
        try:
            written, notes = init_case(path, force)
        except DomainCommandError as exc:
            (skipped if exc.skip else failed).append((name, str(exc)))
            mark = "[dim]-[/dim]" if exc.skip else "[yellow]![/yellow]"
            console.print(f"  {mark} [bold]{name}[/bold]: {exc}")
            continue
        done.append(name)
        console.print(f"  [green]+[/green] [bold]{name}[/bold]: {written.name}"
                      + (f" [dim]({len(notes)} note(s))[/dim]" if notes else ""))
        for note in notes:
            console.print(f"      [dim]{note}[/dim]")
    console.print()
    console.print(f"[bold]{len(done)} case(s) written[/bold]"
                  + (f"; {len(skipped)} skipped" if skipped else "")
                  + (f"; [yellow]{len(failed)} failed[/yellow]" if failed else ""))
    console.print()
    if failed and not done:
        sys.exit(1)


def check_case(case_dir):
    """What the case disagrees with its domain.yml about, as [(severity, message)]."""
    case_dir = Path(case_dir)
    domain = _load(case_dir)
    zones = plt_zone_names(case_dir)
    found = domain.problems(case_dir=case_dir, problem=_problem(case_dir),
                            plt_zones=zones or None)
    if not zones:
        found.append(('warning', "no readable PLT in binary/, so no plttag could be "
                                 "checked against a real zone"))
    return found


def _check(console, case_dir):
    case_dir = Path(case_dir)
    found = check_case(case_dir)
    errors = [m for severity, m in found if severity == 'error']
    warnings = [m for severity, m in found if severity == 'warning']

    console.print()
    console.print(f"[bold cyan]Checking {case_dir.name}/{FILENAME}[/bold cyan]")
    console.print()
    for message in errors:
        console.print(f"  [red]x[/red] {message}")
    for message in warnings:
        console.print(f"  [yellow]![/yellow] {message}")
    if not found:
        console.print("  [green]+[/green] every name, tag and type checks out against "
                      "the case's own files")
    console.print()
    console.print(f"[bold]{len(errors)} error(s), {len(warnings)} warning(s)[/bold]")
    console.print()
    if errors:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Editing
# ---------------------------------------------------------------------------

def _edit_body(console, case_dir, args):
    domain = _load(case_dir, must_exist=not args.add)
    name = getattr(args, 'name', None)

    if args.remove:
        removed = domain.remove_body(args.remove)
        domain.save()
        console.print(f"[green]+[/green] Removed body [bold]{removed.get('name')}"
                      f"[/bold] from {domain.path}")
        return

    pairs = _assignments(args, 'body')

    if args.add:
        if not name:
            raise DomainCommandError("--add needs a name: `case domain body --add "
                                     "--name cyl --type beam`")
        attributes = dict(pairs)
        # A body is usually tagged with its own name -- the cylinder called cyl is
        # riser.cyl.srf and zone cyl -- so defaulting saves saying it three times.
        # It is said out loud rather than done quietly, because a case that names
        # them differently would otherwise get two wrong tags without a word.
        defaulted = [key for key in ('geotag', 'plttag') if key not in attributes]
        for key in defaulted:
            attributes[key] = name
        if 'type' not in attributes:
            raise DomainCommandError("--add needs a type: one of "
                                     f"{', '.join(BODY_TYPES)}")
        domain.add_body(name, **attributes)
        domain.save()
        console.print(f"[green]+[/green] Added body [bold]{name}[/bold] to {domain.path}")
        if defaulted:
            console.print(f"  [dim]{' and '.join(defaulted)} default to the name; "
                          f"`case domain body --name {name} --set geotag=<tag>` if the "
                          "case names it otherwise[/dim]")
        _report_check(console, case_dir)
        return

    if not pairs:
        raise DomainCommandError(
            "Nothing to change. Pass --list to see the bodies, --show NAME for one of "
            "them, --add to declare a new one, or --set key=value to edit one.")
    if not name:
        raise DomainCommandError(
            "Which body? Name it with --name, e.g. "
            f"`case domain body --name {domain.body_names()[0] if domain.bodies else 'cyl'}"
            f" --set {pairs[0][0]}={pairs[0][1]}`")

    for key, value in pairs:
        domain.set_body(name, key, value)
    domain.save()
    console.print(f"[green]+[/green] Body [bold]{name}[/bold] in {domain.path}")
    for key, value in pairs:
        console.print(f"    {key} = {value!r}")
    _report_check(console, case_dir)


def _edit_field(console, case_dir, args):
    domain = _load(case_dir, must_exist=not args.add)
    pairs = _assignments(args, 'field')
    name = getattr(args, 'name', None)
    if name:
        pairs.insert(0, ('name', name))

    if args.add and domain.field is not None and not getattr(args, 'force', False):
        raise DomainCommandError(
            f"A field named '{domain.field.get('name')}' is already declared in "
            f"{domain.path.name}. A domain has one continuum, so edit it with "
            "`case domain field --set key=value`, or pass --force to replace it.")
    if args.add and getattr(args, 'force', False):
        domain.data['field'] = {}
    if args.add and not name:
        raise DomainCommandError("--add needs a name: `case domain field --add "
                                 "--name water --type fluid`")

    if not pairs:
        raise DomainCommandError(
            "Nothing to change. Pass --list to see the field, or --set key=value to "
            "edit it, e.g. `case domain field --set plttag=FIELD`.")

    for key, value in pairs:
        domain.set_field(key, value)
    domain.save()
    console.print(f"[green]+[/green] {'Added field' if args.add else 'Field'} "
                  f"[bold]{domain.field.get('name')}[/bold] in {domain.path}")
    for key, value in pairs:
        console.print(f"    {key} = {value!r}")
    _report_check(console, case_dir)


def _report_check(console, case_dir):
    """After an edit, say what the case now disagrees with -- errors only.

    Warnings are left out here: a freshly added body has nothing on disk yet, and
    saying so on every edit would train people to ignore the line that matters.
    """
    try:
        errors = [m for severity, m in check_case(case_dir) if severity == 'error']
    except (DomainCommandError, DomainError):
        return
    for message in errors:
        console.print(f"  [red]x[/red] {message}")
    if errors:
        console.print("  [dim]`case domain --check` for the full picture[/dim]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _is_edit(args):
    return bool(args.add or args.remove or getattr(args, 'set', None)
                or any(getattr(args, flag, None) is not None
                       for flag, _ in ATTRIBUTE_FLAGS)
                or (args.name and not args.show))


def execute_domain(args):
    from .help_messages import print_domain_help

    if getattr(args, 'help', False):
        print_domain_help()
        return

    console = Console()
    logger = Logger(verbose=getattr(args, 'verbose', False))
    try:
        target, case = resolve_target_and_case(args)
        wildcard = is_wildcard_case(case)

        if args.path:
            if wildcard:
                raise DomainCommandError("--path names one file, so it needs one case")
            print(Path(case).resolve() / FILENAME)
            return

        if args.init:
            if _is_edit(args):
                raise DomainCommandError("--init derives the whole file from the .def, "
                                         "so it cannot be combined with an edit. Run "
                                         "it first, then edit what it wrote.")
            _init_all(console, logger, args.force) if wildcard else \
                _init(console, logger, case, args.force)
            return

        if args.check:
            if wildcard:
                raise DomainCommandError("--check reports on one case at a time; give a "
                                         "case, or use `case domain * --list` for a "
                                         "survey")
            _check(console, case)
            return

        if target is None:
            if _is_edit(args):
                raise DomainCommandError(
                    f"Say what to edit: `case domain body ...` or "
                    f"`case domain field ...`")
            _list_all(console, logger) if wildcard else _show_summary(console, case)
            return

        if wildcard:
            if _is_edit(args) or args.show:
                raise DomainCommandError(
                    "The * case is for reading. Editing every case's domain at once "
                    "would write the same body into all of them; name a case instead.")
            _list_all(console, logger, target)
            return

        if args.show:
            # `--show` alone with `--name cyl` reads as naturally as `--show cyl`.
            token = args.show if isinstance(args.show, str) else (args.name or True)
            _show_entry(console, case, token, target)
            return
        if args.list or not _is_edit(args):
            _show_summary(console, case, target)
            return
        _edit_body(console, case, args) if target == 'body' else \
            _edit_field(console, case, args)

    except (DomainCommandError, DomainError) as exc:
        logger.error(str(exc))
        sys.exit(1)
