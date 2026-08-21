"""
DomainConfig -- what a case's domain is made of, as `domain.yml`.

A case already says all of this, but it says it three times over in three
vocabularies that nothing joins up:

  - the **.def** names a `beamSolid( "beam_1" )` and an `elementGroup( "interior" )`,
  - the **geometry files** name the same things `riser.cyl.srf` and `riser.fluid.cnn`,
  - the **PLT** names them again as zones `cyl` and `FIELD`.

So `field compute --zone cyl`, `case out --map cyl_nodes` and a `beamSolid` whose
bending stiffness you want are three different names for one cylinder, and only
the person at the keyboard knows that. `domain.yml` writes the join down once:

    field:
      name: water
      type: fluid
      geotag: fluid          # riser.fluid.cnn
      plttag: FIELD          # zone in the .plt
      velocity: [0, 0, 1]    # the free stream, declared -- see below

    bodies:
      - name: cyl
        type: beam
        geotag: cyl          # riser.cyl.nbc, riser.cyl.srf
        plttag: cyl
        outputs:
          - block: riser_probe            # outputTimeHistory( "riser_probe" )
            nodes: riser.cyl_nodes.nbc    # what orders its othd records

`geotag` is the token in the middle of a geometry file name, `plttag` is the zone
name in a PLT. Given both, a body named once resolves to its mesh files and its
PLT zone without anyone re-deriving the convention.

`outputs` adds the fourth place a body is named: the outputTimeHistory block that
writes its displacements. Those records are positional -- row k is the k-th node
of the file the block names -- so the node file is the one thing that turns a row
back into a point on the body.

It says *where a thing is*, not what it is made of. A beam's stiffnesses and the
fluid's density are not here: the .def has them, the solver reads them from there,
and a second copy in a file nobody feeds back would only drift.

What *is* here is what the case does not state anywhere -- a body's radius, and
the field's free-stream velocity. Neither is a copy. The mesh has the shape but no
number saying which diameter a coefficient is normalised by; and the .def's
nearest thing to a free stream, `initField( velocity )`, is the initial condition,
which for a case started from rest or ramped up at the inlet says nothing about
the flow the body ends up in. Both are declared, and both start out null.

Most of it can be *derived* -- `derive_from_def` reads the .def and any PLT
present and fills in what it can find. What it cannot know it leaves blank rather
than guessing: a beam's radius is in the mesh, not in the .def, and a wrong radius
propagates silently into every Cd that is normalised by it.

Usage
-----
    from src.core.domain import DomainConfig

    dom = DomainConfig.find(case_dir)
    dom.exists                      # bool
    dom.field                       # dict | None
    dom.bodies                      # list[dict], in file order
    dom.body('cyl')                 # resolved by name, geotag or plttag
    dom.plt_zone('cyl')             # -> 'cyl'      (the zone to ask a PLT for)
    dom.outputs('cyl')              # -> [{'block': ..., 'nodes': ...}]
    dom.geometry_files('cyl', 'riser')   # -> the riser.cyl.* files that exist

    dom.add_body(name='cyl', type='beam')
    dom.set_body('cyl', 'geometry.radius', 0.5)
    dom.save()
"""

import math
import re
from pathlib import Path
from typing import Optional, Union

FILENAME = 'domain.yml'
SCHEMA_VERSION = 1

# What a body *is*, which decides what may be asked of it. `beam` deforms and has
# stiffness; `rigid` moves as a whole; `fixed` does not move at all. The list is
# closed so that a typo is caught at the point it is written rather than becoming
# a body type of one that nothing else recognises.
BODY_TYPES = ('beam', 'rigid', 'fixed')
FIELD_TYPES = ('fluid',)

# The axis of a body, written the way it reads: a signed axis when it is
# axis-aligned, otherwise a three-vector.
AXES = ('+x', '-x', '+y', '-y', '+z', '-z')

# Geometry file extensions, by what they hold. A geotag names a set of these.
GEOMETRY_SUFFIXES = ('.crd', '.cnn', '.nbc', '.srf', '.ebc')



class DomainError(Exception):
    """domain.yml could not be read, or an edit to it does not make sense."""


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def tag_from_file(filename: str, problem: Optional[str] = None) -> Optional[str]:
    """'riser.cyl.srf' -> 'cyl': the geotag in the middle of a geometry file name.

    The problem name is stripped when it is known and leads the name, since that
    prefix is the case's, not the body's. Returns None for a name with no middle
    part to take -- 'riser.crd' names the mesh itself, not a tagged subset of it.
    """
    if not filename:
        return None
    stem = Path(filename).name
    suffix = Path(stem).suffix
    if suffix:
        stem = stem[: -len(suffix)]
    if problem and stem.startswith(problem + '.'):
        stem = stem[len(problem) + 1:]
    elif '.' in stem:
        stem = stem.split('.', 1)[1]
    else:
        return None
    return stem or None


def _as_number(value):
    """`value` as a number when it reads as one, else None. Bools are not numbers.

    A whole-number literal stays an int, so `nElems = 48` is written back as 48
    rather than 48.0 -- a count that reads as a measurement invites the question
    of what the fraction meant.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    try:
        return int(text)
    except (TypeError, ValueError):
        pass
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _axis_name(vector):
    """A unit direction as '+x' / '-z' when it is axis-aligned, else a list.

    Written back as a signed axis wherever possible because that is how a person
    describes a cylinder, and how they will want to read it.
    """
    length = math.sqrt(sum(c * c for c in vector))
    if length == 0:
        return None
    unit = [c / length for c in vector]
    for i, axis in enumerate('xyz'):
        others = [abs(unit[j]) for j in range(3) if j != i]
        if abs(abs(unit[i]) - 1.0) < 1e-9 and max(others) < 1e-9:
            return f"{'+' if unit[i] > 0 else '-'}{axis}"
    return [round(c, 12) for c in unit]


def _vector(raw, evaluate=None):
    """A `{a, b, c}` .def value as three floats, or None if it is not three numbers.

    `evaluate` resolves a component written as a define{} variable; without it,
    only literal numbers are read.
    """
    from .parsers.def_parser import as_list
    items = as_list(raw)
    if not items or len(items) != 3:
        return None
    out = []
    for item in items:
        value = _as_number(item)
        if value is None and evaluate is not None:
            value = evaluate(item)
        if value is None:
            return None
        out.append(value)
    return out


# ---------------------------------------------------------------------------
# Writing it out
# ---------------------------------------------------------------------------

class _Dumper(__import__('yaml').SafeDumper):
    """PyYAML's SafeDumper, laid out the way a person writes this file by hand.

    Two departures from the default, both about reading it back:

      - a list of plain scalars goes on one line, so an origin is
        ``[0, 0, 0]`` rather than three bullets that have to be reassembled by eye;
      - sequences are indented under their key, which is how every other YAML in
        this repo is written.
    """

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def dump(data) -> str:
    """`data` as the YAML this file is written in -- same layout, no header."""
    import yaml
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, default_flow_style=False,
                     allow_unicode=True, width=88)


def _represent_list(dumper, data):
    scalar = all(item is None or isinstance(item, (str, int, float, bool))
                 for item in data)
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data,
                                     flow_style=scalar and len(data) <= 8)


_Dumper.add_representer(list, _represent_list)


# ---------------------------------------------------------------------------
# The config
# ---------------------------------------------------------------------------

class DomainConfig:
    """Reads, edits and writes a case's `domain.yml`.

    An instance is always usable: a case with no domain.yml loads as an empty
    one, so callers ask `exists` rather than handling None.
    """

    def __init__(self, path: Union[str, Path], data: Optional[dict] = None):
        self._path = Path(path)
        self._data = data if data is not None else {}
        if data is None and self._path.exists():
            self._data = self._load(self._path)
        self._normalise()

    # -- construction ---------------------------------------------------

    @staticmethod
    def _load(path: Path) -> dict:
        import yaml
        try:
            with open(path) as fh:
                loaded = yaml.safe_load(fh)
        except OSError as exc:
            raise DomainError(f"Could not read {path}: {exc}")
        except yaml.YAMLError as exc:
            raise DomainError(f"{path.name} is not valid YAML: {exc}")
        if loaded is None:
            return {}
        if not isinstance(loaded, dict):
            raise DomainError(f"{path.name} should hold a mapping with 'field' and "
                              f"'bodies' keys, not a {type(loaded).__name__}")
        return loaded

    @classmethod
    def find(cls, case_dir: Union[str, Path]) -> 'DomainConfig':
        """Load `<case_dir>/domain.yml`, present or not."""
        return cls(Path(case_dir) / FILENAME)

    def _normalise(self) -> None:
        """Accept the shapes a hand-written file may arrive in.

        `bodies` written as a mapping of name to body, or as a list of
        single-key mappings, both become a list of bodies each carrying its own
        `name` -- one shape for the rest of the code to work with, and the shape
        that is written back.
        """
        bodies = self._data.get('bodies')
        if isinstance(bodies, dict):
            self._data['bodies'] = [dict(body or {}, name=(body or {}).get('name', key))
                                    for key, body in bodies.items()]
        elif isinstance(bodies, list):
            flat = []
            for entry in bodies:
                if not isinstance(entry, dict):
                    raise DomainError(
                        f"{self._path.name}: every entry under 'bodies' should be a "
                        f"mapping, found a {type(entry).__name__}")
                if 'name' not in entry and len(entry) == 1:
                    # `- cyl: {...}`, the label carrying the name
                    key, inner = next(iter(entry.items()))
                    if isinstance(inner, dict):
                        entry = dict(inner, name=inner.get('name', key))
                flat.append(entry)
            self._data['bodies'] = flat
        elif bodies is not None:
            raise DomainError(f"{self._path.name}: 'bodies' should be a list, not a "
                              f"{type(bodies).__name__}")

        field = self._data.get('field')
        if field is not None and not isinstance(field, dict):
            raise DomainError(f"{self._path.name}: 'field' should be a mapping, not a "
                              f"{type(field).__name__}")

    # -- reading --------------------------------------------------------

    @property
    def path(self) -> Path:
        return self._path

    @property
    def exists(self) -> bool:
        return self._path.exists()

    @property
    def data(self) -> dict:
        return self._data

    @property
    def field(self) -> Optional[dict]:
        """The continuum the bodies sit in, or None if none is declared."""
        return self._data.get('field')

    @property
    def bodies(self) -> list:
        """Declared bodies, in file order."""
        return list(self._data.get('bodies') or [])

    def body(self, token: str) -> Optional[dict]:
        """The body `token` names -- by name, then geotag, then plttag.

        Three vocabularies name the same body, and which one a caller has depends
        on where it came from: a PLT zone from `field compute --zone`, a geotag
        from a node file, a name from a person. All three resolve here so that
        none of them has to know about the others.
        """
        if not token:
            return None
        for key in ('name', 'geotag', 'plttag'):
            for body in self.bodies:
                if str(body.get(key) or '').lower() == token.lower():
                    return body
        return None

    def entry(self, token: str) -> Optional[dict]:
        """The body or the field that `token` names, whichever matches."""
        found = self.body(token)
        if found is not None:
            return found
        field = self.field
        if field and token:
            for key in ('name', 'geotag', 'plttag'):
                if str(field.get(key) or '').lower() == token.lower():
                    return field
        return None

    def plt_zone(self, token: str) -> Optional[str]:
        """The PLT zone name for whatever `token` names, or None if undeclared."""
        entry = self.entry(token)
        return entry.get('plttag') if entry else None

    def geotag(self, token: str) -> Optional[str]:
        """The geometry-file tag for whatever `token` names, or None."""
        entry = self.entry(token)
        return entry.get('geotag') if entry else None

    @property
    def velocity(self) -> Optional[list]:
        """The free-stream velocity the field declares, or None if it has not.

        Direction and magnitude in one declaration, so the two cannot disagree:
        a coefficient needs the direction to resolve drag from lift and the
        magnitude for its dynamic pressure, and both come from this.
        """
        return (self.field or {}).get('velocity')

    def outputs(self, token: str) -> list:
        """The outputTimeHistory blocks declared for whatever `token` names.

        Each is `{'block': ..., 'nodes': ...}`. The node file is what orders the
        othd records, so this is the link from a body to its displacement history
        -- what `case out --map` builds a map from, and what a reader needs to
        turn row k back into a point on the body.
        """
        entry = self.entry(token)
        return list((entry or {}).get('outputs') or [])

    def geometry_files(self, token: str, problem: Optional[str] = None,
                       case_dir: Optional[Union[str, Path]] = None) -> list:
        """The `<problem>.<geotag>*` geometry files that exist for `token`.

        Matches on the tag as a whole dotted component *or* as a prefix of one, so
        a cylinder tagged `cyl` picks up `riser.cyl.srf` and also `riser.cyl_BL.nbc`
        and `riser.cyl_nodes.nbc` -- the boundary layer and probe sets belong to
        the same body, and a caller asking what a body is made of wants them.
        """
        tag = self.geotag(token)
        if not tag:
            return []
        base = Path(case_dir) if case_dir is not None else self._path.parent
        prefix = f"{problem}." if problem else ""
        found = []
        for suffix in GEOMETRY_SUFFIXES:
            found += sorted(base.glob(f"{prefix}{tag}{suffix}"))
            found += sorted(base.glob(f"{prefix}{tag}[._-]*{suffix}"))
        return sorted(set(found))

    # -- editing --------------------------------------------------------

    def add_body(self, name: str, **attributes) -> dict:
        """Add a body and return it. Raises DomainError if the name is taken.

        Attributes may be given flat (`geotag='cyl'`) or dotted
        (`**{'geometry.radius': 0.5}`); both land where they belong.
        """
        if not name:
            raise DomainError("A body needs a name")
        if any(str(b.get('name') or '').lower() == name.lower() for b in self.bodies):
            raise DomainError(f"A body named '{name}' is already declared in "
                              f"{self._path.name}")
        body = {'name': name}
        self._data.setdefault('bodies', []).append(body)
        for key, value in attributes.items():
            if value is not None:
                self._set(body, key.replace('__', '.'), value)
        return body

    def remove_body(self, token: str) -> dict:
        """Remove the body `token` names and return it."""
        body = self.body(token)
        if body is None:
            raise DomainError(f"No body '{token}' in {self._path.name}. "
                              f"Declared: {', '.join(self.body_names()) or 'none'}")
        self._data['bodies'] = [b for b in self.bodies if b is not body]
        return body

    def set_body(self, token: str, key: str, value) -> dict:
        """Set `key` (dotted paths allowed) on the body `token` names."""
        body = self.body(token)
        if body is None:
            raise DomainError(f"No body '{token}' in {self._path.name}. "
                              f"Declared: {', '.join(self.body_names()) or 'none'}")
        self._set(body, key, value)
        return body

    def set_field(self, key: str, value) -> dict:
        """Set `key` (dotted paths allowed) on the field, creating it if needed."""
        field = self._data.setdefault('field', {})
        self._set(field, key, value)
        return field

    def body_names(self) -> list:
        return [str(b.get('name') or '?') for b in self.bodies]

    @staticmethod
    def _set(target: dict, key: str, value) -> None:
        """Assign a dotted `key` inside `target`, making mappings on the way down."""
        parts = [p for p in str(key).split('.') if p]
        if not parts:
            raise DomainError("An empty key cannot be set")
        for part in parts[:-1]:
            nested = target.get(part)
            if nested is None:
                nested = {}
                target[part] = nested
            elif not isinstance(nested, dict):
                raise DomainError(f"'{part}' holds a value, so '{key}' cannot be set "
                                  f"underneath it")
            target = nested
        # A None is stored, not dropped: `radius: null` is the file saying the
        # radius is not known, which is a different thing from not mentioning it.
        target[parts[-1]] = value

    # -- validation -----------------------------------------------------

    def problems(self, case_dir: Optional[Union[str, Path]] = None,
                 problem: Optional[str] = None,
                 plt_zones: Optional[list] = None) -> list:
        """What is wrong or unresolved, as a list of (severity, message).

        Severity is 'error' for something that makes the file self-contradictory
        and 'warning' for something merely unverifiable -- a geotag with no files
        yet, a plttag that no PLT could be found to check. The caller decides what
        an exit code should be.
        """
        found = []
        names, geotags, plttags = {}, {}, {}
        entries = [('field', self.field)] if self.field else []
        entries += [('body', b) for b in self.bodies]

        if not entries:
            found.append(('error', f"{self._path.name} declares no field and no bodies"))

        for kind, entry in entries:
            label = entry.get('name') or f"<unnamed {kind}>"
            if not entry.get('name'):
                found.append(('error', f"a {kind} has no name"))
            kind_types = FIELD_TYPES if kind == 'field' else BODY_TYPES
            declared = entry.get('type')
            if not declared:
                found.append(('warning', f"{label}: no type; expected one of "
                                         f"{', '.join(kind_types)}"))
            elif declared not in kind_types:
                found.append(('error', f"{label}: type '{declared}' is not one of "
                                       f"{', '.join(kind_types)}"))
            for key, seen in (('name', names), ('geotag', geotags), ('plttag', plttags)):
                value = entry.get(key)
                if not value:
                    continue
                lowered = str(value).lower()
                if lowered in seen:
                    found.append(('error', f"{label}: {key} '{value}' is also used by "
                                           f"{seen[lowered]}; each must name one thing"))
                else:
                    seen[lowered] = label

            if entry.get('geotag') and case_dir is not None:
                files = self.geometry_files(entry['name'] or entry['geotag'],
                                            problem, case_dir)
                if not files:
                    found.append(('warning',
                                  f"{label}: geotag '{entry['geotag']}' matches no "
                                  f"geometry file in {Path(case_dir).name}"))
            elif not entry.get('geotag'):
                found.append(('warning', f"{label}: no geotag, so its mesh files "
                                         "cannot be found from here"))

            if plt_zones is not None:
                zone = entry.get('plttag')
                if not zone:
                    found.append(('warning', f"{label}: no plttag, so its PLT zone "
                                             "cannot be found from here"))
                elif zone.lower() not in {z.lower() for z in plt_zones}:
                    found.append(('error', f"{label}: plttag '{zone}' is not a zone in "
                                           f"the case's PLT ({', '.join(plt_zones)})"))

            for output in entry.get('outputs') or []:
                if not isinstance(output, dict) or not output.get('block'):
                    found.append(('error', f"{label}: an entry under 'outputs' names "
                                           "no outputTimeHistory block"))
                    continue
                nodes = output.get('nodes')
                if not nodes:
                    found.append(('warning',
                                  f"{label}: output '{output['block']}' names no node "
                                  "file, so nothing orders its othd records"))
                elif case_dir is not None and not (Path(case_dir) / nodes).exists():
                    found.append(('warning',
                                  f"{label}: output '{output['block']}' reads {nodes}, "
                                  f"which is not in {Path(case_dir).name}"))

            if kind == 'field':
                velocity = entry.get('velocity')
                if velocity is None:
                    found.append(('warning', f"{label}: no velocity, so there is no "
                                             "free stream to normalise a coefficient "
                                             "against"))
                elif (not isinstance(velocity, list) or len(velocity) != 3
                        or not all(isinstance(c, (int, float))
                                   and not isinstance(c, bool) for c in velocity)):
                    found.append(('error', f"{label}: velocity {velocity!r} is not "
                                           "three numbers"))
                elif not any(velocity):
                    found.append(('error', f"{label}: velocity is zero, which gives "
                                           "no flow direction and no reference speed"))

            axis = (entry.get('geometry') or {}).get('axis')
            if isinstance(axis, str) and axis not in AXES:
                found.append(('error', f"{label}: axis '{axis}' is not one of "
                                       f"{', '.join(AXES)} or a three-vector"))
        return found

    # -- writing --------------------------------------------------------

    def _ordered(self) -> dict:
        """The data with its keys in reading order: what a thing *is* before its numbers."""
        head = ('name', 'type', 'geotag', 'plttag', 'velocity')
        # `properties` and `source` are not derived any more, but a hand-written
        # file may still carry them, and they belong at the end where they were.
        tail = ('geometry', 'outputs', 'properties', 'source')

        def order(entry):
            if not isinstance(entry, dict):
                return entry
            out = {k: entry[k] for k in head if k in entry}
            out.update({k: v for k, v in entry.items() if k not in head and k not in tail})
            out.update({k: entry[k] for k in tail if k in entry})
            return out

        out = {'version': self._data.get('version', SCHEMA_VERSION)}
        if self.field is not None:
            out['field'] = order(self.field)
        out['bodies'] = [order(b) for b in self.bodies]
        for key, value in self._data.items():
            if key not in ('version', 'field', 'bodies'):
                out[key] = value
        return out

    def save(self, path: Optional[Union[str, Path]] = None) -> Path:
        """Write domain.yml, header and all. Returns the path written.

        The file is *regenerated*, not patched: the header below is rewritten
        each time, and so any comment added by hand inside the body is lost on the
        next `--add` or `--set`. The header is written to carry what those
        comments would have said.
        """
        import yaml
        target = Path(path) if path is not None else self._path
        body = yaml.dump(self._ordered(), Dumper=_Dumper, sort_keys=False,
                         default_flow_style=False, allow_unicode=True, width=88)
        target.write_text(HEADER + body)
        self._path = target
        return target

    def __repr__(self) -> str:
        return (f"DomainConfig({self._path}, field="
                f"{(self.field or {}).get('name')!r}, bodies={self.body_names()})")


HEADER = """\
# domain.yml -- what this case's domain is made of.
#
# The same body is named four different ways by a FlexFlow case, and nothing in
# the case joins them up. This file does:
#
#   name     what you call it
#   type     what it is: a body is beam | rigid | fixed, the field is fluid
#   geotag   the token in its geometry file names -- geotag 'cyl' is riser.cyl.srf,
#            riser.cyl.nbc, riser.cyl_BL.nbc
#   plttag   its zone name inside a .plt -- what `field compute --zone` wants
#   outputs  the outputTimeHistory block written along the body, and the node file
#            that orders its records: row k of the othd is that file's k-th node
#   velocity the field's free stream, as a vector -- its direction is what drag is
#            measured along, its magnitude the U in 0.5*rho*U^2
#
# It says where a thing is, not what it is made of. Shape is here because nothing
# else records it; a beam's stiffnesses and the fluid's density are not, because
# the .def has them and the solver reads them from there. Two copies of a number
# is one copy too many.
#
# Edit it by hand, or with `case domain body --add / --set` and
# `case domain field --set`. Those rewrite the file, so comments added inside it
# below this header do not survive an edit.
#
# Written by `case domain --init`, which fills in what the .def and the case's
# PLT files say. Anything they do not say -- a beam's radius lives in the mesh,
# not the .def -- is left blank on purpose rather than guessed at.

"""


# ---------------------------------------------------------------------------
# Derivation from the case's own files
# ---------------------------------------------------------------------------

def _newest_plt(case_dir: Union[str, Path]) -> Optional[Path]:
    """The highest-numbered `binary/*.plt`, or None.

    Deliberately not `commands.field.locate.find_plt`, near-identical though it
    is: core is what commands are built on, and reaching back up the other way to
    borrow fifteen lines would make every future import of this module drag a
    command package in with it.
    """
    binary = Path(case_dir) / 'binary'
    if not binary.is_dir():
        return None
    files = list(binary.glob('*.plt'))
    if not files:
        return None

    def step(path):
        match = re.search(r'\.(\d+)\.plt$', path.name)
        return int(match.group(1)) if match else -1

    return max(files, key=step)


def _read_zones(case_dir: Union[str, Path]) -> list:
    """Zone dicts from the case's newest PLT, or [] if there is none to read.

    Only the header is read; a PLT is hundreds of megabytes and the zone list is
    in its first few kilobytes. A PLT that cannot be read is not a reason to
    refuse to write domain.yml -- the tags it would have confirmed are left for
    --check to raise -- so failure here is empty, not an exception.
    """
    path = _newest_plt(case_dir)
    if path is None:
        return []
    try:
        from ..plt.fxplt import PltFile
        return PltFile(str(path)).zones
    except Exception:
        return []


def plt_zone_names(case_dir: Union[str, Path]) -> list:
    """Zone names from the case's newest PLT, or [] if there is none to read."""
    return [zone['name'] for zone in _read_zones(case_dir)]


def _plt_split(case_dir: Union[str, Path]):
    """(volume zone names, surface zone names) from the case's newest PLT.

    The split is what makes a tag guessable at all: the fluid field is the volume
    zone, a body is one of the surfaces, and pairing them the other way round is
    never right.
    """
    from ..plt.fxplt import VOLUME_ZTYPES
    zones = _read_zones(case_dir)
    volume = [z['name'] for z in zones if z['ztype'] in VOLUME_ZTYPES]
    surface = [z['name'] for z in zones if z['ztype'] not in VOLUME_ZTYPES]
    return volume, surface


def _pick_zone(tag: Optional[str], candidates: list) -> Optional[str]:
    """The zone `tag` most likely names: an exact match, a near one, or the only one."""
    if not candidates:
        return None
    if tag:
        for zone in candidates:
            if zone.lower() == tag.lower():
                return zone
        for zone in candidates:
            if tag.lower() in zone.lower() or zone.lower() in tag.lower():
                return zone
    return candidates[0] if len(candidates) == 1 else None


def _derive_field(blocks, problem, volume_zones, notes):
    """The continuum the bodies sit in: what it is called, and its two tags.

    Its geotag comes from the element group's connectivity file --
    `riser.fluid.cnn` makes it `fluid` -- and its plttag from the PLT's volume
    zone. Its density and viscosity are *not* copied here: they are two lines of
    the .def that the solver reads from there, and a second copy in a file nobody
    feeds back would only drift.
    """
    from .parsers.def_parser import as_file

    groups = [b for b in blocks if b['kind'] == 'elementGroup']
    if not groups:
        notes.append("no elementGroup in the .def, so the field is left undeclared")
        return None
    if len(groups) > 1:
        notes.append(f"{len(groups)} elementGroup blocks; taking the first "
                     f"('{groups[0]['name']}') as the field")
    group = groups[0]

    geotag = tag_from_file(as_file(group['values'].get('elements')), problem)
    if geotag is None:
        notes.append(f"elementGroup(\"{group['name']}\") names no element file, so "
                     "the field's geotag is left blank")
    # The free stream is left for a person to declare. The .def's nearest thing to
    # it is initField( velocity ), and that is the *initial condition*: a case
    # started from rest, or ramped up at the inlet, has one that says nothing about
    # the flow the body eventually sees. Reading it would be right often enough to
    # be trusted and wrong quietly enough to matter.
    notes.append("the field's velocity is left blank: the .def's initField is an "
                 "initial condition, not the free stream. Declare it with "
                 "`case domain field --velocity X,Y,Z`")
    return {
        'name': group['name'] or geotag or 'field',
        'type': 'fluid',
        'geotag': geotag,
        'plttag': _pick_zone(geotag, volume_zones),
        'velocity': None,
    }


def _same_body(tag, geotag):
    """True if `tag` names a set belonging to the body tagged `geotag`.

    Exactly the tag, or the tag followed by a separator: `cyl` owns `cyl_nodes`
    and `cyl_BL`, but not `cylinder2`, which is a different body whose name
    happens to start the same way.
    """
    if not tag or not geotag:
        return False
    tag, geotag = str(tag).lower(), str(geotag).lower()
    if tag == geotag:
        return True
    return tag.startswith(geotag) and tag[len(geotag):len(geotag) + 1] in '._-'


def _body_outputs(geotag, history, problem):
    """The outputTimeHistory blocks whose node file belongs to this body.

    A nodal block writes its records *positionally*: row k of every output block
    is the k-th node of the file the block names, and the othd carries no id and
    no coordinate of its own. So `riser.cyl_nodes.nbc` is what turns a row back
    into a point on the cylinder, and which block reads it is the one link
    between a body and its displacement history. Recording it here saves every
    reader re-deriving it from the .def.
    """
    found = []
    for block in history:
        nodes = block.get('nodes')
        if not nodes or (block.get('type') or '').lower() != 'nodal':
            continue
        if _same_body(tag_from_file(nodes, problem), geotag):
            found.append({'block': block['name'], 'nodes': nodes})
    return found


def _derive_beam(block, blocks, evaluate, problem, surface_zones, history, notes):
    """One beamSolid as a body: what its surface is, and where its history goes.

    Only what defines the *surface* is kept -- the tags that name it, its shape,
    and the output blocks written along it. The beam's stiffnesses stay in the
    .def, which is the one place they are ever read from.
    """
    from .parsers.def_parser import as_file, as_list

    values = block['values']
    name = block['name'] or 'beam'

    # A beamSolid does not name a geometry file. It names its outputSurface
    # blocks, and *those* name the .srf the body's faces are in -- which is where
    # the geotag comes from. Without that link a beam has no tag at all.
    geotag = None
    for output in as_list(values.get('surfaceOutputs')) or []:
        surface = next((b for b in blocks if b['kind'] == 'outputSurface'
                        and b['name'] == output), None)
        if surface:
            geotag = tag_from_file(as_file(surface['values'].get('surfaces')), problem)
            if geotag:
                break
    if geotag is None:
        notes.append(f"beamSolid(\"{name}\"): no outputSurface names a surface file, "
                     "so its geotag is left blank")

    body = {
        'name': geotag or name,
        'type': 'beam',
        'geotag': geotag,
        'plttag': _pick_zone(geotag, surface_zones),
        'geometry': {},
    }

    start = _vector(values.get('pnt1'), evaluate)
    end = _vector(values.get('pnt2'), evaluate)
    if start and end:
        span = [b - a for a, b in zip(start, end)]
        body['geometry']['origin'] = start
        body['geometry']['length'] = round(math.sqrt(sum(c * c for c in span)), 12)
        axis = _axis_name(span)
        if axis is not None:
            body['geometry']['axis'] = axis
    # The radius is a property of the mesh around the beam, not of the beamSolid,
    # so the .def cannot supply it. Left null: a guessed radius would silently
    # scale every coefficient normalised by it.
    body['geometry']['radius'] = None

    outputs = _body_outputs(geotag, history, problem)
    if outputs:
        body['outputs'] = outputs
    elif geotag:
        notes.append(f"{body['name']}: no nodal outputTimeHistory reads a "
                     f"{problem + '.' if problem else ''}{geotag}* node file, so "
                     "nothing records this body's displacements")
    return body


def derive_from_def(case_dir: Union[str, Path], problem: Optional[str] = None):
    """Build a DomainConfig for `case_dir` from its .def and its PLT zones.

    Returns (config, notes) -- notes being the things it could not work out,
    said plainly, so `--init` can print them rather than leaving silent holes.

    Raises DomainError when there is no .def to read: everything here comes from
    it, and an empty domain.yml would be worse than none.
    """
    from .parsers.def_parser import (find_def_file, parse_blocks,
                                     parse_output_time_history)
    from .def_config import DefConfig
    from .simflow_config import SimflowConfig

    case_dir = Path(case_dir)
    if problem is None:
        try:
            problem = SimflowConfig.find(case_dir).problem
        except Exception:
            problem = None

    def_file = find_def_file(str(case_dir), problem)
    if not def_file:
        raise DomainError(f"No .def file in {case_dir}; there is nothing to derive a "
                          "domain from")

    notes = []
    blocks = parse_blocks(def_file)
    history = parse_output_time_history(def_file)
    evaluate = DefConfig(def_file).evaluate
    volume_zones, surface_zones = _plt_split(case_dir)
    if not volume_zones and not surface_zones:
        notes.append("no readable PLT in binary/, so plttag is left blank; set it "
                     "with `case domain body --set plttag=<zone>` once one exists")

    data = {'version': SCHEMA_VERSION}
    field = _derive_field(blocks, problem, volume_zones, notes)
    if field:
        data['field'] = field

    bodies = []
    for block in blocks:
        if block['kind'] == 'beamSolid':
            bodies.append(_derive_beam(block, blocks, evaluate, problem,
                                       surface_zones, history, notes))
    if not bodies:
        notes.append("no beamSolid in the .def, so no body was derived; add one with "
                     "`case domain body --add --name <name> --type <type>`")
    data['bodies'] = bodies

    claimed = {b['plttag'] for b in bodies if b.get('plttag')}
    spare = [z for z in surface_zones if z not in claimed]
    if spare:
        notes.append(f"PLT surface zone(s) not claimed by any body: {', '.join(spare)}"
                     " -- add a body for each, or set its plttag")

    return DomainConfig(case_dir / FILENAME, data), notes
