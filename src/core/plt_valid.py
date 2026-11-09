"""
Is a binary PLT whole? Read from its header, without loading the data.

A FlexFlow binary PLT (Tecplot TDV112) states every zone's size in its
header and each zone's value formats in a short preamble before the zone's
data. Those give the exact length of a complete file: on every real file
checked (BR0SG0U1P0 169 MB, CT4SG3U* 436 MB) the file ends at that offset to
the byte. A post job killed at the walltime, a full disk or an interrupted
copy leaves a file that is shorter (or, from a broken writer, longer), and
that is what this catches -- reading a few hundred bytes per zone, not the
hundreds of MB of data.

    check = check_plt(path)
    check.ok, check.reason, check.size, check.expected

This says nothing about whether the PLT is the *right* one (made from the
current .out, after a restart). That needs the files it came from; see
plt_covers() for the rule `case organise output` uses.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

MAGIC = b"#!TDV112"


@dataclass(frozen=True)
class PltCheck:
    path: Path
    ok: bool
    reason: str                    # '' when ok
    size: int
    expected: Optional[int] = None  # bytes a complete file has, when the header could be read


def _flag(f) -> int:
    import struct
    return struct.unpack('<i', f.read(4))[0]


class CutShort(Exception):
    """The file ends before a zone's preamble: it is at least `at_least` bytes."""

    def __init__(self, at_least: int, zone: int):
        super().__init__(f"ends before the data of zone {zone} (needs at least {at_least:,} bytes)")
        self.at_least = at_least
        self.zone = zone


def expected_size(path) -> int:
    """Bytes a complete file with this header has.

    Raises CutShort when the file ends before a zone's preamble (so the full
    length cannot be known, only that it is longer); ValueError for a file
    that is not TDV112; or whatever the header reader raises on a header
    that is cut short or malformed.
    """
    from src.plt.fxplt import PltFile, NPE, FMT_SIZE
    size = os.path.getsize(path)
    plt = PltFile(path)
    try:
        f = plt._f
        f.seek(plt._data_start)
        nvar = len(plt.vars)
        for i, zone in enumerate(plt.zones):
            if f.tell() >= size:
                raise CutShort(f.tell() + 1, i + 1)
            # the preamble's min/max pairs are read with f.read(16), which
            # comes back short at the end of the file instead of failing; the
            # preamble's length is known, so check it was all there
            start = f.tell()
            fmts, present, shareconn, _, _ = plt._read_data_preamble(f, nvar)
            length = 4 + 4 * nvar + 4 + 4 + 4 + 16 * sum(present)
            # passive/shared lists add 4 * nvar each when flagged; read them back
            f.seek(start + 4 + 4 * nvar)
            if _flag(f) == 1:
                length += 4 * nvar
                f.seek(4 * nvar, 1)
            if _flag(f) == 1:
                length += 4 * nvar
            if start + length > size:
                raise CutShort(start + length, i + 1)
            f.seek(start + length)
            for v in range(nvar):
                if present[v]:
                    f.seek(zone["npts"] * FMT_SIZE[fmts[v]], 1)
            if shareconn == -1 and zone["ztype"] in NPE:
                f.seek(zone["nelem"] * NPE[zone["ztype"]] * 4, 1)
        return f.tell()
    finally:
        plt.close()


def check_plt(path) -> PltCheck:
    """Whether the binary PLT at path is whole: non-empty, TDV112, and exactly
    as long as its header says."""
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError as e:
        return PltCheck(path, False, f"cannot read: {e.strerror or e}", 0)
    if size == 0:
        return PltCheck(path, False, "empty", 0)
    try:
        with open(path, 'rb') as f:
            magic = f.read(len(MAGIC))
    except OSError as e:
        return PltCheck(path, False, f"cannot read: {e.strerror or e}", size)
    if magic != MAGIC:
        return PltCheck(path, False, "not a binary PLT (no #!TDV112 header)", size)
    try:
        expected = expected_size(path)
    except CutShort as e:
        return PltCheck(path, False, f"cut short: {size:,} bytes, {e}", size)
    except Exception:
        # the header or a zone preamble ends early (or is garbage): a file cut
        # short inside its first bytes
        return PltCheck(path, False, "header cut short or unreadable", size)
    if size < expected:
        return PltCheck(path, False, f"cut short: {size:,} of {expected:,} bytes", size, expected)
    if size > expected:
        return PltCheck(path, False, f"{size - expected:,} bytes past the end its header gives",
                        size, expected)
    return PltCheck(path, True, '', size, expected)


def plt_covers(plt_path, out_paths: Iterable) -> Optional[str]:
    """Why the PLT at plt_path can NOT stand in for these .out files, or None
    when it can: it is whole (check_plt), and it was written after every one
    of them.

    The second condition is what makes deleting the .out safe after a
    restart: the resumed run writes its steps' .out again, and a PLT older
    than them was made from the earlier run's output.
    """
    check = check_plt(plt_path)
    if not check.ok:
        return check.reason
    try:
        plt_time = os.stat(plt_path).st_mtime
        newest_out = max((os.stat(p).st_mtime for p in out_paths), default=None)
    except OSError as e:
        return f"cannot read: {e.strerror or e}"
    if newest_out is not None and plt_time < newest_out:
        return "older than its .out (made before they were written again, e.g. by a restart)"
    return None
