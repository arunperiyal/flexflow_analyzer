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
        self._file_refs: list = []  # filenames referenced via File( "..." )
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
        self._parse_file_references(content)

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

    def _parse_file_references(self, content: str) -> None:
        """
        Collect filenames referenced via ``File( "name" )``.

        Whitespace inside the parentheses varies between cases, and the same
        file may be referenced many times; duplicates are removed while the
        order of first appearance is preserved. Lines commented out with
        ``#`` or ``//`` are ignored.
        """
        pattern = re.compile(r'File\s*\(\s*"([^"]+)"\s*\)')
        seen = set()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('//'):
                continue
            for match in pattern.finditer(line):
                name = match.group(1).strip()
                if name and name not in seen:
                    seen.add(name)
                    self._file_refs.append(name)

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

    @property
    def file_references(self) -> list:
        """Unique filenames referenced via File( "..." ), in first-seen order."""
        return list(self._file_refs)

    # ------------------------------------------------------------------
    # Write support
    # ------------------------------------------------------------------

    def set_variable(self, name: str, value: Union[str, float, int]) -> bool:
        """
        Update the value of a define{} block variable in the .def file.

        Rewrites the ``value = ...`` line of the ``define{}`` block whose
        ``variable = NAME`` matches ``name``, preserving the original
        indentation and ``value`` keyword alignment.

        Parameters
        ----------
        name:
            The variable name to update (case-sensitive, as in the file).
        value:
            The new value to write.

        Returns
        -------
        bool
            True if the variable was found and updated, False otherwise.
        """
        if not self._path.exists():
            raise FileNotFoundError(f".def file not found: {self._path}")

        lines = self._path.read_text().splitlines(keepends=True)

        in_block = False
        is_target = False
        found = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            if stripped.startswith('define{'):
                in_block = True
                is_target = False
                continue

            if in_block and stripped == '}':
                in_block = False
                is_target = False
                continue

            if in_block:
                if stripped.startswith('variable') and '=' in stripped:
                    var = stripped.split('=', 1)[1].strip()
                    is_target = (var == name)
                elif stripped.startswith('value') and '=' in stripped and is_target:
                    # Preserve everything up to and including the '=' so the
                    # original indentation and keyword alignment are kept.
                    key_part = line.split('=', 1)[0]
                    newline = '\n' if line.endswith('\n') else ''
                    lines[i] = f"{key_part}= {value}{newline}"
                    found = True
                    is_target = False

        if not found:
            return False

        self._path.write_text(''.join(lines))
        self._variables[name] = str(value)
        return True

    def update_output_frequency(self, frequency: int) -> None:
        """
        Update outFreq values in outputSimulation and outputRestart blocks.

        Parameters
        ----------
        frequency:
            The new output frequency value to set.
        """
        if not self._path.exists():
            raise FileNotFoundError(f".def file not found: {self._path}")

        with open(self._path, 'r') as f:
            lines = f.readlines()

        new_lines = []
        in_output_block = False
        block_name = None

        for line in lines:
            stripped = line.strip()

            # Detect outputSimulation or outputRestart block start
            if re.match(r'outputSimulation\s*\{', stripped) or re.match(r'outputRestart\s*\{', stripped):
                in_output_block = True
                block_name = 'outputSimulation' if 'outputSimulation' in stripped else 'outputRestart'
                new_lines.append(line)
                continue

            # Detect block end
            if in_output_block and stripped == '}':
                in_output_block = False
                block_name = None
                new_lines.append(line)
                continue

            # Inside output block, look for outFreq parameter
            if in_output_block and re.match(r'outFreq\s*=', stripped):
                # Update the outFreq value
                indent = len(line) - len(line.lstrip())
                new_lines.append(' ' * indent + f"outFreq               = {frequency}\n")
                continue

            new_lines.append(line)

        # Write back
        with open(self._path, 'w') as f:
            f.writelines(new_lines)

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
