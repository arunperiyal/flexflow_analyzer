"""
`.restarts` in the case directory: where each run took over from the one
before, kept for the analysis after `case organise history --clean` has
cut the runs into one history and `--prune` has deleted the archived ones.

    # after  first  time          reached  replaced  part         previous     recorded
    4000     4001   2.0005e+02    5000     1000      riser2.othd  riser1.othd  2026-10-26 12:00

after     the run resumed after this step (restartTsId)
first     its first step, and `time` the simulation time there
reached   the step the run before had got to
replaced  steps the run before wrote past `after`: computed again, and the
          compiled file keeps the later run's
part, previous  the archive parts, as named when this was recorded

Plain columns, so `numpy.loadtxt(..., usecols=(0, 1, 2))` or awk read it. A
line is kept once written: after --prune the parts are gone, and with them
any way to find these restarts again.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional

FILENAME = '.restarts'
COLUMNS = ('after', 'first', 'time', 'reached', 'replaced', 'part', 'previous', 'recorded')

_HEADER = """\
# Restarts of {case}: where each run took over from the one before.
# Written by `case organise history --clean` (and kept through --prune, when
# the archived runs are gone). after: the run resumed after this step; first:
# its first step, at simulation time `time`; reached: the step the run before
# had got to;
# replaced: steps of that run past `after`, computed again (the compiled file
# keeps the later run's); part/previous: the archive parts when recorded.
"""


def path_for(case_dir) -> Path:
    return Path(case_dir) / FILENAME


def read(case_dir) -> List[Dict[str, str]]:
    """The recorded restarts, in step order ([] without the file)."""
    path = path_for(case_dir)
    if not path.is_file():
        return []
    return parse(path.read_text(errors='replace'))


def parse(text: str) -> List[Dict[str, str]]:
    """The rows of a .restarts file's text, in step order."""
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        cells = line.split(None, len(COLUMNS) - 1)
        if len(cells) < 2 or not cells[0].isdigit():
            continue
        rows.append(dict(zip(COLUMNS, cells + ['-'] * (len(COLUMNS) - len(cells)))))
    return sorted(rows, key=lambda r: int(r['after']))


def block_time(path: Path, start: int) -> Optional[float]:
    """The `time` of the block that starts at byte `start` of an OTHD/OISD file."""
    try:
        with open(path, 'rb') as f:
            f.seek(start)
            for _ in range(3):
                line = f.readline()
                if line.startswith(b'time '):
                    return float(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def record(case_dir, found: List[dict], when: Optional[float] = None) -> List[Dict[str, str]]:
    """Add the restarts a compile plan found to the file, keeping every line
    already there. `found` holds dicts with after/first/reached/replaced and
    part/previous/start (Paths and a byte offset, for the time). A restart
    already recorded keeps its line. Returns the rows now in the file."""
    rows = {int(r['after']): r for r in read(case_dir)}
    stamp = time.strftime('%Y-%m-%d %H:%M', time.localtime(when))
    for r in found:
        if r['after'] in rows:
            continue
        t = block_time(r['part'], r['start'])
        rows[r['after']] = {
            'after': str(r['after']), 'first': str(r['first']),
            'time': f"{t:.6e}" if t is not None else '-',
            'reached': str(r['reached']), 'replaced': str(r['replaced']),
            'part': Path(r['part']).name, 'previous': Path(r['previous']).name,
            'recorded': stamp,
        }
    ordered = [rows[k] for k in sorted(rows)]
    write(case_dir, ordered)
    return ordered


def write(case_dir, rows: List[Dict[str, str]]):
    path = path_for(case_dir)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(render(rows, Path(case_dir).resolve().name))
    tmp.replace(path)


def render(rows: List[Dict[str, str]], case: str) -> str:
    """The file's text for these rows."""
    table = [('# ' + COLUMNS[0],) + COLUMNS[1:]] + [tuple(r[c] for c in COLUMNS) for r in rows]
    widths = [max(len(row[i]) for row in table) for i in range(len(COLUMNS) - 1)]
    lines = ['  '.join(cell.ljust(w) for cell, w in zip(row[:-1], widths)) + '  ' + row[-1]
             for row in table]
    return _HEADER.format(case=case) + '\n'.join(lines) + '\n'


def merge(dest: str, source: str) -> List[Dict[str, str]]:
    """The rows of two copies (here and on a remote): every restart once, in
    step order. A restart in both keeps dest's line, as a line once written
    is kept."""
    rows = {int(r['after']): r for r in parse(source)}
    rows.update({int(r['after']): r for r in parse(dest)})
    return [rows[k] for k in sorted(rows)]
