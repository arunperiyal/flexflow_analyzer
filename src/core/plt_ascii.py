"""
Whether an ASCII Tecplot PLT (what simPlt writes from the .out files) is
whole: not empty, and each zone holds as many data lines as its header says.

    ZONE T="fluid", N=1200, E=1000, F=FEPOINT, ET=BRICK
    <1200 lines, one per node>
    <1000 lines, one per element>

    check = check_ascii_plt(path)     # .ok, .reason

A post job killed at the walltime leaves the file cut short: fewer lines than
N + E, or a last line that stops in the middle. That is what this catches.

What cannot be counted is not called whole: a zone in BLOCK packing (values
are not one node per line) or a header without its counts gives ok=False with
the reason, so nothing is ever deleted on the strength of a file this module
did not understand.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_HEADER_WORDS = ('TITLE', 'VARIABLES', 'ZONE', 'TEXT', 'GEOMETRY', 'DATASETAUXDATA',
                 'VARAUXDATA', 'CUSTOMLABELS', 'FILETYPE')
_NUMBER = re.compile(rb'^[+-]?(\d|\.\d)')


@dataclass(frozen=True)
class AsciiCheck:
    path: Path
    ok: bool
    reason: str = ''
    size: int = 0
    zones: int = 0


def _count(header: str, *names) -> Optional[int]:
    for name in names:
        m = re.search(rf'(?<![A-Z]){name}\s*=\s*(\d+)', header)
        if m:
            return int(m.group(1))
    return None


def _expected_lines(header: str):
    """(lines, None) a zone with this header holds, or (None, why it cannot be told)."""
    packing = re.search(r'(?<![A-Z])(?:DATAPACKING|F)\s*=\s*([A-Z]+)', header)
    packing = packing.group(1) if packing else 'POINT'
    if packing in ('BLOCK', 'FEBLOCK'):
        return None, f"{packing} packing: its lines cannot be counted against the header"
    nodes = _count(header, 'NODES', 'N')
    if nodes is not None:
        elements = _count(header, 'ELEMENTS', 'E')
        if elements is None:
            return None, "the zone header gives no element count (E=)"
        if 'CONNECTIVITYSHAREZONE' in header:
            elements = 0
        return nodes + elements, None
    i = _count(header, 'I')
    if i is None:
        return None, "the zone header gives no node count (N= or I=)"
    return i * (_count(header, 'J') or 1) * (_count(header, 'K') or 1), None


def check_ascii_plt(path) -> AsciiCheck:
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError as e:
        return AsciiCheck(path, False, f"cannot read: {e.strerror or e}")
    if size == 0:
        return AsciiCheck(path, False, "empty", 0)
    zones: List[list] = []          # [header text, data lines]
    in_header = True
    last = b''
    try:
        with open(path, 'rb') as f:
            if f.read(8).startswith(b'#!TDV'):
                return AsciiCheck(path, False, "a binary PLT, not an ASCII one", size)
            f.seek(0)
            for raw in f:
                line = raw.strip()
                if not line or line.startswith(b'#'):
                    continue
                last = raw
                if _NUMBER.match(line):
                    if not zones:
                        return AsciiCheck(path, False, "data before any ZONE header", size)
                    zones[-1][1] += 1
                    in_header = False
                    continue
                text = line.decode('latin-1').upper()
                if text.startswith('ZONE'):
                    zones.append([text, 0])
                    in_header = True
                elif zones and in_header and not text.startswith(_HEADER_WORDS):
                    zones[-1][0] += ' ' + text          # the ZONE record goes on
                elif zones and not in_header and not text.startswith(_HEADER_WORDS):
                    return AsciiCheck(path, False, "a line that is neither numbers nor a header "
                                                   "in the data (cut short or damaged)", size,
                                      len(zones))
    except OSError as e:
        return AsciiCheck(path, False, f"cannot read: {e.strerror or e}", size)
    if not zones:
        return AsciiCheck(path, False, "no ZONE in it (cut short in its header, or not a PLT)",
                          size)
    for n, (header, lines) in enumerate(zones, 1):
        expected, why = _expected_lines(header)
        if expected is None:
            return AsciiCheck(path, False, f"zone {n}: {why}", size, len(zones))
        if lines != expected:
            how = "cut short" if lines < expected else "more than its header gives"
            return AsciiCheck(path, False, f"{how}: zone {n} has {lines:,} of {expected:,} "
                                           f"data lines", size, len(zones))
    if not last.endswith(b'\n'):
        return AsciiCheck(path, False, "cut short: the last line is not ended", size, len(zones))
    return AsciiCheck(path, True, '', size, len(zones))
