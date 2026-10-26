"""
The case's own notes: `.casestatus.md` in the case directory.

A small header the tools read, then free markdown the user writes:

    ---
    state: running
    tags: [CS4, sweep-A]
    ---
    # CS4SG3U6P0

    What the case is for ...

    ## Log
    - 2026-10-20 14:02  main job 81234 started: resumed from 4000
    - 2026-10-12 11:40  created

Only what a person knows goes in it -- state, purpose, notes, the log. What
the files say (the last step, the PLTs, the job in the queue) is worked out
each time it is shown, so it cannot go stale.

The log is oldest first and the job scripts append to it too (the same
format, from bash), so a line is always added at the end of the Log section.
"""

import re
import time
from pathlib import Path
from typing import Optional, Tuple

FILENAME = '.casestatus.md'
STATES = ('new', 'meshing', 'running', 'stopped', 'done', 'failed', 'archived')
LOG_HEADING = '## Log'

_FRONT = re.compile(r'\A---[ \t]*\n(.*?)\n---[ \t]*\n', re.DOTALL)
_HEADING = re.compile(r'^#{1,2} ', re.MULTILINE)


def path_for(case_dir) -> Path:
    return Path(case_dir) / FILENAME


def stamp(when: Optional[float] = None) -> str:
    return time.strftime('%Y-%m-%d %H:%M', time.localtime(when))


def template(case_dir, when: Optional[float] = None) -> str:
    name = Path(case_dir).resolve().name
    return (f"---\nstate: new\ntags: []\n---\n"
            f"# {name}\n\n"
            f"<!-- What this case is for, what it is compared with, what to watch. -->\n\n"
            f"## Notes\n\n"
            f"{LOG_HEADING}\n"
            f"- {stamp(when)}  created\n")


def split(text: str) -> Tuple[dict, str]:
    """(header fields, the markdown after the header). No header: ({}, text)."""
    m = _FRONT.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(':')
        if sep and key.strip():
            value = value.split(' #', 1)[0].strip()
            if key.strip() == 'tags':
                value = [t.strip() for t in value.strip('[]').split(',') if t.strip()]
            meta[key.strip()] = value
    return meta, text[m.end():]


def read(case_dir) -> Optional[Tuple[dict, str]]:
    path = path_for(case_dir)
    if not path.is_file():
        return None
    return split(path.read_text(errors='replace'))


def ensure(case_dir) -> bool:
    """Write the template if there is no file yet. True when it was written."""
    path = path_for(case_dir)
    if path.exists():
        return False
    path.write_text(template(case_dir))
    return True


def _write(path: Path, text: str):
    # Through a temporary name, so a job script appending at the same moment
    # never sees half a file.
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text)
    tmp.replace(path)


def with_log_line(text: str, line: str) -> str:
    """text with `- line` added at the end of its Log section (made if absent)."""
    entry = f"- {line}\n"
    at = text.find(f"\n{LOG_HEADING}\n")
    if at < 0 and text.startswith(f"{LOG_HEADING}\n"):
        at = -1
    elif at < 0:
        return text.rstrip('\n') + f"\n\n{LOG_HEADING}\n{entry}"
    start = at + 1 + len(LOG_HEADING) + 1
    nxt = _HEADING.search(text, start)
    end = nxt.start() if nxt else len(text)
    section = text[start:end].rstrip('\n')
    rest = text[end:]
    return (text[:start] + (section + '\n' if section else '') + entry
            + ('\n' + rest if rest else ''))


def add_log(case_dir, message: str, when: Optional[float] = None) -> Path:
    """Append a timestamped line to the log, writing the file first if needed."""
    ensure(case_dir)
    path = path_for(case_dir)
    lines = [l.strip() for l in message.strip().splitlines() if l.strip()]
    text = path.read_text(errors='replace')
    for i, line in enumerate(lines):
        text = with_log_line(text, (f"{stamp(when)}  " if i == 0 else "    ") + line)
    _write(path, text)
    return path


def set_state(case_dir, state: str, when: Optional[float] = None) -> Optional[str]:
    """Set the header's state and log the change. Returns the old state."""
    if state not in STATES:
        raise ValueError(f"state must be one of {', '.join(STATES)}, not '{state}'")
    ensure(case_dir)
    path = path_for(case_dir)
    text = path.read_text(errors='replace')
    meta, body = split(text)
    old = meta.get('state')
    m = _FRONT.match(text)
    if m:
        head = m.group(1)
        if re.search(r'^state:', head, re.MULTILINE):
            head = re.sub(r'^state:.*$', f'state: {state}', head, count=1, flags=re.MULTILINE)
        else:
            head = f'state: {state}\n' + head
        text = f"---\n{head}\n---\n" + body
    else:
        text = f"---\nstate: {state}\n---\n" + text
    if old != state:
        text = with_log_line(text, f"{stamp(when)}  state: {old or '-'} -> {state}")
    _write(path, text)
    return old


def last_log_line(body: str) -> Optional[str]:
    at = body.find(f"{LOG_HEADING}\n")
    if at < 0:
        return None
    start = at + len(LOG_HEADING) + 1
    nxt = _HEADING.search(body, start)
    lines = [l[2:] for l in body[start:nxt.start() if nxt else len(body)].splitlines()
             if l.startswith('- ')]
    return lines[-1] if lines else None


# ---------------------------------------------------------------------------
# Two copies of the file (here and on a remote): merging them
# ---------------------------------------------------------------------------

_STAMP = re.compile(r'^- (\d{4}-\d\d-\d\d \d\d:\d\d)\b')


def _log_bounds(text: str):
    """(start, end) of the Log section's lines in text, or None."""
    at = text.find(f"\n{LOG_HEADING}\n")
    if at >= 0:
        start = at + 1 + len(LOG_HEADING) + 1
    elif text.startswith(f"{LOG_HEADING}\n"):
        start = len(LOG_HEADING) + 1
    else:
        return None
    nxt = _HEADING.search(text, start)
    return start, nxt.start() if nxt else len(text)


def log_entries(text: str):
    """The log as entries: an entry is a '- ' line and the lines under it."""
    bounds = _log_bounds(text)
    if not bounds:
        return []
    entries = []
    for line in text[bounds[0]:bounds[1]].rstrip('\n').splitlines():
        if line.startswith('- ') or not entries:
            entries.append([line])
        else:
            entries[-1].append(line)
    return ['\n'.join(e) for e in entries if ''.join(e).strip()]


def merge(newer: str, older: str) -> str:
    """One file from two copies: `newer`'s header and notes, and the log of
    both -- every entry once, in time order (an entry with no timestamp
    keeps its place after the one before it)."""
    ours = log_entries(newer)
    seen = set(ours)
    extra = [e for e in log_entries(older) if e not in seen]
    if not extra:
        return newer

    def keyed(entries, side):
        out, last = [], ''
        for i, e in enumerate(entries):
            m = _STAMP.match(e)
            last = m.group(1) if m else last
            out.append(((last, side, i), e))
        return out
    entries = [e for _, e in sorted(keyed(ours, 0) + keyed(extra, 1))]
    block = '\n'.join(entries) + '\n'
    bounds = _log_bounds(newer)
    if not bounds:
        return newer.rstrip('\n') + f"\n\n{LOG_HEADING}\n" + block
    rest = newer[bounds[1]:]
    return newer[:bounds[0]] + block + ('\n' + rest if rest else '')
