"""services/mapfile.py — parse `othd.<block>.map`: the `#` header, then CSV rows.

The header format is written by `case out --map`
(src/commands/case/out_impl/command.py:_map_header); this is its reader.
"""

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
