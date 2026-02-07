# FlexFlow Case Directory Structure

## Overview

This document defines the standard FlexFlow case directory structure. All commands should follow this structure consistently.

## Directory Layout

```
CaseDirectory/
├── simflow.config          # Main configuration file
├── {problem}.def           # Problem definition file
├── binary/                 # Binary PLT files (converted from ASCII)
│   └── {problem}.{step}.plt
├── othd_files/             # Time history data files
│   ├── {problem}1.othd
│   ├── {problem}2.othd
│   └── ...
├── oisd_files/             # Surface data files
│   ├── {problem}1.oisd
│   ├── {problem}2.oisd
│   └── ...
└── {output_dir}/           # Output directory (specified in simflow.config)
    ├── {problem}.{step}_*.out    # Output files
    ├── {problem}.{step}_*.rst    # Restart files
    └── {problem}.{step}.plt      # ASCII PLT files (before conversion)
```

## Configuration File: simflow.config

### Required Fields

```
problem = "{problem_name}"    # Problem name used for all file naming
dir = "{output_directory}"    # Output directory path (relative or absolute)
outFreq = {frequency}         # Output frequency (time steps between outputs)
```

### Example

```
problem = "rigid"
dir = "./SIMFLOW_DATA"
outFreq = 50
```

## File Naming Conventions

### Output Files (in output directory)

- **Output files**: `{problem}.{timestep}_{rank}.out`
  - Example: `rigid.1000_1.out`, `rigid.1050_1.out`

- **Restart files**: `{problem}.{timestep}_{rank}.rst`
  - Example: `rigid.1000_1.rst`, `rigid.1050_1.rst`

- **ASCII PLT files**: `{problem}.{timestep}.plt`
  - Example: `rigid.1000.plt`, `rigid.1050.plt`

### Binary Directory

- **Binary PLT files**: `{problem}.{timestep}.plt`
  - Example: `rigid.1000.plt`, `rigid.1050.plt`
  - These are converted from ASCII PLT files in output directory

### OTHD/OISD Files

- **OTHD files**: `{problem}{number}.othd`
  - Example: `rigid1.othd`, `rigid2.othd`
  - Sequential numbering, sorted by starting time step

- **OISD files**: `{problem}{number}.oisd`
  - Example: `rigid1.oisd`, `rigid2.oisd`
  - Sequential numbering, sorted by starting time step

## Path Resolution Rules

### Output Directory (`dir` field)

1. **Relative path**: Resolved relative to case directory
   ```
   dir = "./SIMFLOW_DATA"
   → {case_directory}/SIMFLOW_DATA
   ```

2. **Absolute path**: Used as-is
   ```
   dir = "/scratch/user/project/output"
   → /scratch/user/project/output
   ```

### Problem Name

- Read from `simflow.config` file: `problem` field
- Can be overridden by context using `use problem {name}`

## How Commands Should Access Case Structure

### Reading Configuration

```python
from core.case import FlexFlowCase

case = FlexFlowCase(case_directory)

# Get problem name
problem = case.problem_name  # from simflow.config

# Get output directory
output_dir = case.config['dir']  # from simflow.config

# Get frequency
freq = int(case.config['outFreq'])  # from simflow.config
```

### Resolving Output Directory Path

```python
import os
from pathlib import Path

def get_output_directory(case: FlexFlowCase, case_path: Path) -> Optional[Path]:
    """Get output directory from case config."""
    if 'dir' not in case.config:
        return None

    output_dir_str = case.config['dir']

    if not os.path.isabs(output_dir_str):
        output_dir_path = case_path / output_dir_str
    else:
        output_dir_path = Path(output_dir_str)

    return output_dir_path
```

### Finding Output Files

```python
output_dir = get_output_directory(case, case_path)
problem = case.problem_name

# Find all .out files
out_files = list(output_dir.glob(f'{problem}.*_*.out'))

# Find all .rst files
rst_files = list(output_dir.glob(f'{problem}.*_*.rst'))

# Find all ASCII PLT files
plt_files = list(output_dir.glob(f'{problem}.*.plt'))
```

### Extracting Time Step from Filename

```python
import re

def extract_step_from_output(filename: str, problem: str) -> Optional[int]:
    """Extract time step from .out or .rst filename."""
    # Pattern: {problem}.{step}_*.out or {problem}.{step}_*.rst
    pattern = rf'{re.escape(problem)}\.(\d+)_.*\.(?:out|rst)'
    match = re.match(pattern, filename)
    if match:
        return int(match.group(1))
    return None

def extract_step_from_plt(filename: str, problem: str) -> Optional[int]:
    """Extract time step from PLT filename."""
    # Pattern: {problem}.{step}.plt
    pattern = rf'{re.escape(problem)}\.(\d+)\.plt'
    match = re.match(pattern, filename)
    if match:
        return int(match.group(1))
    return None
```

## Context Management (use command)

Users can override configuration values using the `use` command in interactive mode:

```bash
use case Case005              # Set case context
use problem rigid             # Override problem name
use rundir SIMFLOW_DATA       # Override output directory
```

When context is set, commands should prioritize context values over config file values.

## Common Patterns

### Pattern 1: Auto-detect Frequency

```python
def get_frequency(case: FlexFlowCase, output_dir: Path, problem: str) -> Optional[int]:
    """Get frequency from config or auto-detect."""
    # Try config first
    if 'outFreq' in case.config:
        try:
            return int(case.config['outFreq'])
        except ValueError:
            pass

    # Auto-detect from output files
    out_files = list(output_dir.glob(f'{problem}.*_*.out'))
    steps = []
    for file in out_files:
        step = extract_step_from_output(file.name, problem)
        if step:
            steps.append(step)

    if len(steps) < 2:
        return None

    steps.sort()
    min_gap = min(steps[i+1] - steps[i] for i in range(len(steps) - 1))
    return min_gap
```

### Pattern 2: Get Expected Time Steps

```python
def get_expected_timesteps(output_dir: Path, problem: str, freq: int) -> Set[int]:
    """Get all expected time steps based on existing output files."""
    out_files = list(output_dir.glob(f'{problem}.*_*.out'))

    steps = set()
    for file in out_files:
        step = extract_step_from_output(file.name, problem)
        if step:
            steps.add(step)

    if not steps:
        return set()

    # Generate expected steps at frequency intervals
    min_step = min(steps)
    max_step = max(steps)

    expected = set()
    step = min_step
    while step <= max_step:
        expected.add(step)
        step += freq

    return expected
```

### Pattern 3: Check Data File Coverage

```python
from core.readers.othd_reader import OTHDReader

def check_othd_coverage(case_path: Path, expected_steps: Set[int]) -> Tuple[bool, float]:
    """Check if OTHD files cover all expected time steps."""
    othd_dir = case_path / 'othd_files'

    if not othd_dir.exists():
        return False, 0.0

    othd_files = list(othd_dir.glob('*.othd'))

    covered_steps = set()
    for othd_file in othd_files:
        try:
            reader = OTHDReader(str(othd_file))
            covered_steps.update(reader.tsIds)
        except Exception:
            continue

    coverage = (len(covered_steps & expected_steps) / len(expected_steps)) * 100
    is_complete = expected_steps.issubset(covered_steps)

    return is_complete, coverage
```

## Important Notes

1. **Never hardcode directory names** like `RUN_*` or `SIMFLOW_DATA`
   - Always read from `simflow.config['dir']`

2. **Never hardcode problem names** like `rigid` or `riser`
   - Always use `case.problem_name`

3. **Handle both relative and absolute paths** for output directory
   - Use the path resolution pattern shown above

4. **Respect user context** from `use` commands
   - Check for context overrides before using config values

5. **Time step extraction must match exact patterns**
   - `.out`/`.rst`: `{problem}.{step}_*.{ext}`
   - `.plt`: `{problem}.{step}.plt`

## Reference Implementation

See these files for correct implementation examples:
- `src/commands/case/organise_impl/organizer.py` - Output directory handling
- `src/commands/case/status_impl/command.py` - Case structure usage
- `src/core/case.py` - FlexFlowCase class
