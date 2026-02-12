"""
DefConfig — canonical parser for FlexFlow .def files.

All code that needs to read a .def file should use this class instead of
implementing its own parsing logic.

Usage
-----
    from src.core.def_config import DefConfig

    cfg = DefConfig.find(case_dir, problem_name)   # preferred factory
    # or:
    cfg = DefConfig(case_dir / 'riser.def')

    # Typed convenience properties
    cfg.max_time_steps          # int  | None
    cfg.initial_time_increment  # float | None
    cfg.order                   # str  | None
    cfg.high_frequency_damping  # float | None

    # define{} block variables
    cfg.variables               # dict[str, str]  e.g. {'DIA': '1.0', 'SPAN': '12*DIA'}

    # Path info
    cfg.path                    # Path to .def file
    cfg.exists                  # bool
"""

import re
from pathlib import Path
from typing import Optional, Union


class DefConfig:
    """
    Parses and provides typed access to a FlexFlow .def file.

    Parsing rules
    -------------
    - ``timeSteppingControl{ ... }`` block is parsed for simulation parameters.
    - ``define{ variable = NAME  value = VAL }`` blocks are collected into
      ``variables``.
    - Comments (lines starting with ``#`` or ``//``) are ignored.
    """

    def __init__(self, def_path: Union[str, Path]):
        self._path = Path(def_path)
        self._tsc: dict = {}        # timeSteppingControl values
        self._variables: dict = {}  # define{} block variables
        if self._path.exists():
            self._parse()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse(self) -> None:
        try:
            content = self._path.read_text()
        except OSError:
            return

        self._parse_time_stepping_control(content)
        self._parse_define_blocks(content)

    def _parse_time_stepping_control(self, content: str) -> None:
        match = re.search(r'timeSteppingControl\s*\{([^}]*)\}', content, re.DOTALL)
        if not match:
            return
        block = match.group(1)

        patterns = {
            'initialTimeIncrement':      (r'initialTimeIncrement\s*=\s*([\d.eE+-]+)',      float),
            'maxTimeSteps':              (r'maxTimeSteps\s*=\s*(\d+)',                      int),
            'order':                     (r'order\s*=\s*(\w+)',                             str),
            'highFrequencyDampingFactor':(r'highFrequencyDampingFactor\s*=\s*([\d.eE+-]+)', float),
        }

        for key, (pattern, cast) in patterns.items():
            m = re.search(pattern, block)
            if m:
                try:
                    self._tsc[key] = cast(m.group(1))
                except (ValueError, TypeError):
                    pass

    def _parse_define_blocks(self, content: str) -> None:
        """Parse all define{ variable = NAME  value = VAL } blocks."""
        in_block = False
        current_var: Optional[str] = None

        for line in content.splitlines():
            stripped = line.strip()

            if stripped.startswith('define{'):
                in_block = True
                current_var = None
                continue

            if in_block and stripped == '}':
                in_block = False
                current_var = None
                continue

            if in_block:
                if stripped.startswith('variable') and '=' in stripped:
                    current_var = stripped.split('=', 1)[1].strip()
                elif stripped.startswith('value') and '=' in stripped and current_var:
                    val = stripped.split('=', 1)[1].strip()
                    self._variables[current_var] = val
                    current_var = None

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
    def max_time_steps(self) -> Optional[int]:
        """maxTimeSteps from timeSteppingControl{}."""
        return self._tsc.get('maxTimeSteps')

    @property
    def initial_time_increment(self) -> Optional[float]:
        """initialTimeIncrement from timeSteppingControl{}."""
        return self._tsc.get('initialTimeIncrement')

    @property
    def order(self) -> Optional[str]:
        """Time stepping order (e.g. 'second')."""
        return self._tsc.get('order')

    @property
    def high_frequency_damping(self) -> Optional[float]:
        """highFrequencyDampingFactor from timeSteppingControl{}."""
        return self._tsc.get('highFrequencyDampingFactor')

    @property
    def variables(self) -> dict:
        """Dict of name → value from all define{} blocks."""
        return dict(self._variables)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def find(case_dir: Union[str, Path],
             problem_name: Optional[str] = None) -> 'DefConfig':
        """
        Load a .def file from a case directory.

        Parameters
        ----------
        case_dir:
            Path to the case directory.
        problem_name:
            If given, tries ``<case_dir>/<problem_name>.def`` first.
            Falls back to the first ``*.def`` file found in the directory.

        Returns
        -------
        DefConfig
            Parsed config (may be empty if no .def file is found).
        """
        case_dir = Path(case_dir)

        if problem_name:
            specific = case_dir / f'{problem_name}.def'
            if specific.exists():
                return DefConfig(specific)

        # Fall back to any .def file
        candidates = sorted(case_dir.glob('*.def'))
        if candidates:
            return DefConfig(candidates[0])

        # Return an empty (non-existent) config so callers don't need None checks
        return DefConfig(case_dir / f'{problem_name or "unknown"}.def')

    def __repr__(self) -> str:
        return f"DefConfig({self._path}, max_time_steps={self.max_time_steps}, dt={self.initial_time_increment})"
