"""Writing a folder's .cases.yml in tests (src/core/cases_file.py)."""

from pathlib import Path

from src.core import cases_file


def write_registry(folder, entries, remotes=None, auto=None) -> Path:
    """.cases.yml in folder listing these cases ({'name', 'path'} dicts)."""
    return cases_file.write(cases_file.CasesFile(
        cases_file.path_for(folder),
        cases=[{'name': str(e.get('name') or Path(e['path']).name), 'path': str(e['path'])}
               for e in entries],
        remotes=dict(remotes or {}), auto=dict(auto or {})))
