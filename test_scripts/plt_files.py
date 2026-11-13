"""Small but genuine FlexFlow-style binary PLTs (Tecplot TDV112) for tests.

write_plt(path) writes one hex zone with x, y, z, p as float32 and its
connectivity -- the layout src/plt/fxplt.py reads -- so src/core/plt_valid.py
sees a whole file. cut=N writes only the first N bytes, as a post job killed
mid-write would.
"""

import struct
from pathlib import Path

VARS = ('x', 'y', 'z', 'p')


def _i32(v):
    return struct.pack('<i', v)


def _f32(v):
    return struct.pack('<f', v)


def _f64(v):
    return struct.pack('<d', v)


def _tstr(s):
    return b''.join(_i32(ord(c)) for c in s) + _i32(0)


def plt_bytes(npts=8, nelem=1, title='riser') -> bytes:
    nvar = len(VARS)
    out = [b'#!TDV112', _i32(1), _i32(0), _tstr(title), _i32(nvar)]
    out += [_tstr(v) for v in VARS]
    # zone header: name, parent, strand, time, color, ztype 5 (brick, 8 nodes)
    out += [_f32(299.0), _tstr('fluid'), _i32(-1), _i32(0), _f64(0.0), _i32(-1), _i32(5),
            _i32(0),            # var location not specified
            _i32(0),            # raw face neighbours
            _i32(0),            # no user face neighbour connections
            _i32(npts), _i32(nelem), _i32(0), _i32(0), _i32(0),
            _i32(0)]            # no aux data
    out.append(_f32(357.0))     # end of header
    # data: marker, formats (1 = float), not passive, not shared, own connectivity
    out += [_f32(299.0)] + [_i32(1)] * nvar + [_i32(0), _i32(0), _i32(-1)]
    out += [_f64(0.0) + _f64(1.0)] * nvar                       # min/max per variable
    out += [_f32(float(i)) for _ in range(nvar) for i in range(npts)]
    out += [_i32(i % npts) for i in range(nelem * 8)]
    return b''.join(out)


def write_plt(path, cut=None, **kw) -> Path:
    path = Path(path)
    data = plt_bytes(**kw)
    path.write_bytes(data if cut is None else data[:cut])
    return path


def write_ascii_plt(path, nodes=8, elements=1, title='riser') -> Path:
    """An ASCII Tecplot PLT in point packing: `nodes` lines, then `elements`."""
    path = Path(path)
    lines = [f'TITLE = "{title}"', 'VARIABLES = "X" "Y" "Z" "U"',
             f'ZONE T="fluid", N={nodes}, E={elements}, F=FEPOINT, ET=BRICK']
    lines += [f'{i}.0 {i}.5 0.0 1.0E-03' for i in range(nodes)]
    lines += [' '.join(str(1 + (e + k) % nodes) for k in range(8)) for e in range(elements)]
    path.write_text('\n'.join(lines) + '\n')
    return path
