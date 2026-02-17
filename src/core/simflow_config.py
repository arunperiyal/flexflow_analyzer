"""
SimflowConfig — canonical parser for simflow.config files.

All code that needs to read a simflow.config should use this class
instead of implementing its own parsing logic.

Usage
-----
    from src.core.simflow_config import SimflowConfig

    cfg = SimflowConfig(case_dir / 'simflow.config')

    # dict-style access
    problem = cfg['problem']           # KeyError if missing
    freq    = cfg.get('outFreq', 50)   # with default

    # convenience properties
    cfg.problem          # str | None
    cfg.run_dir          # Path | None   (resolved relative to case_dir)
    cfg.out_freq         # int  | None
    cfg.np               # int  | None
    cfg.nsg              # int  | None
    cfg.restart_flag     # bool
    cfg.restart_tsid     # int  | None
"""

import re
from pathlib import Path
from typing import Optional, Union


class SimflowConfig:
    """
    Parses and provides access to a simflow.config file.

    Parsing rules
    -------------
    - Lines starting with ``#`` are skipped (full-line comments).
    - Inline comments (`` # ...``) are stripped from values.
    - Surrounding quotes (single or double) are stripped from values.
    - Key and value are split on the first ``=`` only.
    - Empty lines are ignored.
    """

    def __init__(self, config_path: Union[str, Path]):
        self._path = Path(config_path)
        self._data: dict = {}
        self._parse()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' not in line:
                        continue
                    key, _, raw_val = line.partition('=')
                    key = key.strip()
                    # Strip inline comments, then quotes/whitespace
                    val = re.split(r'\s*#', raw_val, maxsplit=1)[0].strip().strip('"').strip("'")
                    if key:
                        self._data[key] = val
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Mapping interface
    # ------------------------------------------------------------------

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key: str):
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __iter__(self):
        return iter(self._data)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def as_dict(self) -> dict:
        """Return a plain copy of all parsed key-value pairs."""
        return dict(self._data)

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def path(self) -> Path:
        return self._path

    @property
    def exists(self) -> bool:
        return self._path.exists()

    @property
    def problem(self) -> Optional[str]:
        return self._data.get('problem') or None

    @property
    def run_dir_str(self) -> Optional[str]:
        """Raw 'dir' value as written in the config (e.g. './SIMFLOW_DATA')."""
        return self._data.get('dir') or None

    def run_dir(self, base: Optional[Union[str, Path]] = None) -> Optional[Path]:
        """
        Resolve the run directory path.

        Parameters
        ----------
        base:
            Base directory for resolving relative paths.
            Defaults to the directory containing simflow.config.
        """
        raw = self.run_dir_str
        if not raw:
            return None
        p = Path(raw)
        if p.is_absolute():
            return p
        root = Path(base) if base else self._path.parent
        return (root / p).resolve()

    @property
    def out_freq(self) -> Optional[int]:
        val = self._data.get('outFreq')
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    @property
    def np(self) -> Optional[int]:
        val = self._data.get('np')
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    @property
    def nsg(self) -> Optional[int]:
        val = self._data.get('nsg')
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    @property
    def restart_flag(self) -> bool:
        """True when restartFlag is set and non-zero."""
        val = self._data.get('restartFlag', '').strip()
        return bool(val) and val != '0'

    @property
    def restart_tsid(self) -> Optional[int]:
        val = self._data.get('restartTsId')
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Write support
    # ------------------------------------------------------------------

    def update_values(self, updates: dict) -> None:
        """
        Update one or more key values in the simflow.config file in-place,
        preserving all comments, blank lines, and the original formatting of
        unchanged lines.

        For each key in *updates*:
        - If the key exists in the file, its value is replaced on that line.
        - If the key does not exist, a new ``key = value`` line is appended.

        Parameters
        ----------
        updates:
            Mapping of {key: new_value}.  Values are converted to str.
        """
        if not updates:
            return

        if not self._path.exists():
            raise FileNotFoundError(f"simflow.config not found: {self._path}")

        with open(self._path, 'r') as f:
            lines = f.readlines()

        remaining = dict(updates)  # keys yet to be written
        new_lines = []

        for line in lines:
            stripped = line.rstrip('\n')
            # Check if this line defines one of the keys we want to update
            if '=' in stripped and not stripped.lstrip().startswith('#'):
                key_part, _, rest = stripped.partition('=')
                key = key_part.strip()
                if key in remaining:
                    new_val = remaining.pop(key)
                    # Preserve any inline comment that was after the value
                    comment = ''
                    m = re.search(r'(\s*#.*)$', rest)
                    if m:
                        comment = m.group(1)
                    # Preserve leading whitespace of the key
                    indent = len(key_part) - len(key_part.lstrip())
                    new_line = ' ' * indent + f'{key} = {new_val}{comment}\n'
                    new_lines.append(new_line)
                    # Keep in-memory data in sync
                    self._data[key] = str(new_val)
                    continue
            # Check for commented-out key=value lines (e.g. #restartTsId = 2100)
            # If the key is in updates, uncomment the line and set the new value
            elif '=' in stripped:
                cm = re.match(r'^(\s*)#\s*(\w+)\s*=', stripped)
                if cm:
                    key = cm.group(2)
                    if key in remaining:
                        new_val = remaining.pop(key)
                        indent = cm.group(1)
                        new_lines.append(f'{indent}{key} = {new_val}\n')
                        self._data[key] = str(new_val)
                        continue
            new_lines.append(line if line.endswith('\n') else line + '\n')

        # Append any keys that didn't exist yet
        for key, val in remaining.items():
            new_lines.append(f'{key} = {val}\n')
            self._data[key] = str(val)

        with open(self._path, 'w') as f:
            f.writelines(new_lines)

    def comment_out_keys(self, keys: list) -> None:
        """
        Comment out active key=value lines for the given keys, leaving any
        already-commented lines untouched.

        For example, ``restartFlag = 1`` becomes ``#restartFlag = 1``.
        """
        if not keys:
            return

        if not self._path.exists():
            raise FileNotFoundError(f"simflow.config not found: {self._path}")

        with open(self._path, 'r') as f:
            lines = f.readlines()

        keys_set = set(keys)
        new_lines = []

        for line in lines:
            stripped = line.rstrip('\n')
            if '=' in stripped and not stripped.lstrip().startswith('#'):
                key_part, _, _ = stripped.partition('=')
                key = key_part.strip()
                if key in keys_set:
                    # Preserve indentation, prepend #
                    indent = len(key_part) - len(key_part.lstrip())
                    new_lines.append(' ' * indent + '#' + stripped.lstrip() + '\n')
                    self._data.pop(key, None)
                    continue
            new_lines.append(line if line.endswith('\n') else line + '\n')

        with open(self._path, 'w') as f:
            f.writelines(new_lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def find(case_dir: Union[str, Path]) -> 'SimflowConfig':
        """
        Load simflow.config from a case directory.

        Parameters
        ----------
        case_dir:
            Path to the case directory.

        Returns
        -------
        SimflowConfig
            Parsed config (may be empty if file not found).
        """
        return SimflowConfig(Path(case_dir) / 'simflow.config')

    def __repr__(self) -> str:
        return f"SimflowConfig({self._path}, keys={list(self._data.keys())})"
