"""services/mapfile.py — parse `othd.<block>.map` and `oisd.<name>.map`: the
`#` header, then CSV rows.

The header formats are written by `case out --map`
(src/commands/case/out_impl/command.py:_map_header / _surface_map_header);
this is their reader. The two are different shapes -- an othd map is one
row->node(->coordinate) table, an oisd map is a surface's mesh as two tables
(nodes, elements) -- so they get separate classes and parsers rather than one
overloaded with fields the other never uses.
"""

import re
from pathlib import Path
from typing import Optional


class MapFile:
    def __init__(self, path, block, probe, closed, oth_id, provenance_kind,
                provenance_file, provenance_count, has_node_col, rows):
        self.path = Path(path)
        self.block = block
        self.probe = probe
        self.closed = closed
        self.oth_id = oth_id
        self.provenance_kind = provenance_kind      # 'nodes' or 'coordinates'
        self.provenance_file = provenance_file
        self.provenance_count = provenance_count
        self.has_node_col = has_node_col
        self.rows = rows                            # [{row, node?, x, y, z}, ...]


def _parse_provenance(line: str):
    """'# nodes: riser.cyl_nodes.nbc (49)' -> ('nodes', 'riser.cyl_nodes.nbc', 49)."""
    kind, rest = line[2:].split(':', 1)
    rest = rest.strip()
    if rest.endswith(')') and '(' in rest:
        source, count = rest.rsplit('(', 1)
        try:
            count = int(count.rstrip(')').replace(',', ''))
        except ValueError:
            count = None
        return kind.strip(), source.strip(), count
    return kind.strip(), rest, None


def parse_map(path) -> MapFile:
    """Read one `othd.*.map`: its `#` header and its row,[node,]x,y,z table."""
    path = Path(path)
    lines = path.read_text().splitlines()

    block = probe = closed = oth_id = None
    provenance_kind = provenance_file = provenance_count = None

    i = 0
    while i < len(lines) and lines[i].startswith('#'):
        line = lines[i]
        if line.startswith('# outputTimeHistory:'):
            rest = line[len('# outputTimeHistory:'):].strip()
            if rest.startswith('"'):
                end = rest.find('"', 1)
                if end != -1:
                    block = rest[1:end]
        elif line.startswith('# othId:'):
            try:
                oth_id = int(line.split(':', 1)[1].strip())
            except ValueError:
                oth_id = None
        elif line.startswith('# probe:'):
            probe = line.split(':', 1)[1].strip()
        elif line.startswith('# closed:'):
            closed = line.split(':', 1)[1].strip() == 'yes'
        elif line.startswith('# nodes:') or line.startswith('# coordinates:'):
            provenance_kind, provenance_file, provenance_count = _parse_provenance(line)
        i += 1

    if i >= len(lines):
        raise ValueError(f"{path}: no CSV header found after the '#' block")
    header = [c.strip() for c in lines[i].split(',')]
    has_node_col = 'node' in header
    i += 1

    rows = []
    for line in lines[i:]:
        if not line.strip():
            continue
        fields = dict(zip(header, line.split(',')))
        row = {'row': int(fields['row']), 'x': float(fields['x']),
               'y': float(fields['y']), 'z': float(fields['z'])}
        if has_node_col:
            row['node'] = int(fields['node'])
        rows.append(row)

    return MapFile(path, block, probe, closed, oth_id, provenance_kind,
                   provenance_file, provenance_count, has_node_col, rows)


def list_maps(case_dir) -> list:
    """Every `othd.*.map` in a case directory, sorted by file name."""
    return sorted(Path(case_dir).glob('othd.*.map'))


class SurfaceMapFile:
    """An outputSurface's map: the surface it names, and the mesh (nodes,
    elements) it is built from -- not a row->data lookup like MapFile, since
    an oisd record has no per-row data to index; see _surface_map_header's
    own docstring in out_impl/command.py."""

    def __init__(self, path, block, element_group, shape, osg_id,
                srf_file, srf_count, nbc_file, nbc_count, nodes, elements):
        self.path = Path(path)
        self.block = block
        self.element_group = element_group
        self.shape = shape
        self.osg_id = osg_id
        self.srf_file = srf_file
        self.srf_count = srf_count
        self.nbc_file = nbc_file
        self.nbc_count = nbc_count
        self.nodes = nodes          # [{row, node, x, y, z}, ...]
        self.elements = elements    # [{row, parent, id, nodes: [...]}, ...]


_FILE_COUNT = re.compile(r'^(?P<file>.+?)\s*\((?P<count>[\d,]+)\s+\w+(?:\(s\))?\)')


def _parse_file_count(rest: str):
    """'riser.cyl.srf (6144 element(s))...' -> ('riser.cyl.srf', 6144).

    Matches up to the first ')', so trailing prose after the count (the
    '# nodes:' line's "-- derived from..." explanation) is simply not part
    of the match rather than something that has to be stripped first.
    """
    match = _FILE_COUNT.match(rest.strip())
    if not match:
        return rest.strip(), None
    try:
        count = int(match.group('count').replace(',', ''))
    except ValueError:
        count = None
    return match.group('file').strip(), count


def _parse_output_surface_line(line: str):
    """'# outputSurface: "cylinder_body"   elementGroup: interior   shape: fourNodeQuad'
    -> ('cylinder_body', 'interior', 'fourNodeQuad')."""
    rest = line[len('# outputSurface:'):].strip()
    name = None
    if rest.startswith('"'):
        end = rest.find('"', 1)
        if end != -1:
            name = rest[1:end]
    element_group = None
    match = re.search(r'elementGroup:\s*(\S+)', rest)
    if match:
        element_group = match.group(1)
    shape = None
    match = re.search(r'shape:\s*(\S+)', rest)
    if match:
        shape = match.group(1)
    return name, element_group, shape


def parse_surface_map(path) -> SurfaceMapFile:
    """Read one `oisd.*.map`: its `#` header, then its node table and its
    element table (in that order, separated by a blank line -- see
    _write_surface_map in out_impl/command.py)."""
    path = Path(path)
    lines = path.read_text().splitlines()

    block = element_group = shape = osg_id = None
    srf_file = srf_count = nbc_file = nbc_count = None

    i = 0
    while i < len(lines) and lines[i].startswith('#'):
        line = lines[i]
        if line.startswith('# outputSurface:'):
            block, element_group, shape = _parse_output_surface_line(line)
        elif line.startswith('# osgId:'):
            try:
                osg_id = int(line.split(':', 1)[1].strip())
            except ValueError:
                osg_id = None
        elif line.startswith('# surfaces:'):
            srf_file, srf_count = _parse_file_count(line[len('# surfaces:'):])
        elif line.startswith('# nodes:'):
            nbc_file, nbc_count = _parse_file_count(line[len('# nodes:'):])
        i += 1

    def skip_blank():
        nonlocal i
        while i < len(lines) and not lines[i].strip():
            i += 1

    skip_blank()
    if i >= len(lines):
        raise ValueError(f"{path}: no node table found after the '#' block")
    node_header = [c.strip() for c in lines[i].split(',')]
    i += 1
    nodes = []
    while i < len(lines) and lines[i].strip():
        fields = dict(zip(node_header, lines[i].split(',')))
        nodes.append({'row': int(fields['row']), 'node': int(fields['node']),
                      'x': float(fields['x']), 'y': float(fields['y']),
                      'z': float(fields['z'])})
        i += 1

    skip_blank()
    elements = []
    if i < len(lines):
        elem_header = [c.strip() for c in lines[i].split(',')]
        node_cols = [c for c in elem_header if c.startswith('node')]
        i += 1
        while i < len(lines) and lines[i].strip():
            fields = dict(zip(elem_header, lines[i].split(',')))
            elements.append({'row': int(fields['row']), 'parent': int(fields['parent']),
                             'id': int(fields['id']),
                             'nodes': [int(fields[c]) for c in node_cols]})
            i += 1

    return SurfaceMapFile(path, block, element_group, shape, osg_id,
                          srf_file, srf_count, nbc_file, nbc_count, nodes, elements)


def list_surface_maps(case_dir) -> list:
    """Every `oisd.*.map` in a case directory, sorted by file name."""
    return sorted(Path(case_dir).glob('oisd.*.map'))
