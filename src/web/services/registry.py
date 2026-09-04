"""The .cases registry, read and written non-interactively.

Wraps the same scan_for_cases() / write_cases_file() / load_cases_file()
that `case add` uses, so `.cases` written from the browser is
byte-for-byte what the CLI would have written.
"""

from pathlib import Path
from typing import Optional

from src.commands.case.add_impl.command import (load_cases_file, scan_for_cases,
                                                 write_cases_file)


def case_path(root: Path, name: str) -> Optional[Path]:
    """The registered directory for `name`, or None if it is not registered."""
    for entry in load_cases_file(root):
        if entry['name'] == name:
            return Path(entry['path'])
    return None


def list_cases(root: Path) -> list:
    """Cases currently registered under *root*, each flagged with whether its path still exists."""
    entries = load_cases_file(root)
    return [
        {'name': e['name'], 'path': e['path'], 'exists': Path(e['path']).is_dir()}
        for e in entries
    ]


def scan(scan_dir: Path) -> list:
    """Candidate case directories under *scan_dir*. Writes nothing."""
    return [{'name': p.name, 'path': str(p)} for p in scan_for_cases(scan_dir)]


def add_cases(root: Path, scan_dir: Path, exclude: set) -> list:
    """Scan *scan_dir*, drop names in *exclude*, and write root/.cases."""
    found = scan_for_cases(scan_dir)
    selected = [p for p in found if p.name not in exclude]
    write_cases_file(root, selected)
    return list_cases(root)


def delete_case(root: Path, name: str) -> list:
    """Remove *name* from root/.cases. Never touches the case directory itself."""
    entries = load_cases_file(root)
    remaining = [Path(e['path']) for e in entries if e['name'] != name]
    write_cases_file(root, remaining)
    return list_cases(root)
