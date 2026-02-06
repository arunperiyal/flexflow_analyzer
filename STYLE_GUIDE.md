# FlexFlow Python Style Guide

This document defines the coding standards for FlexFlow Manager. All Python code should follow these conventions for consistency and maintainability.

## Table of Contents

- [Core Principles](#core-principles)
- [Code Layout](#code-layout)
- [Naming Conventions](#naming-conventions)
- [Documentation](#documentation)
- [Type Hints](#type-hints)
- [Module Structure](#module-structure)
- [Command Pattern](#command-pattern)
- [Error Handling](#error-handling)
- [Testing](#testing)
- [Examples](#examples)

## Core Principles

FlexFlow follows these established standards:

1. **PEP 8** - Python Enhancement Proposal 8 (official Python style guide)
2. **PEP 257** - Docstring conventions
3. **Google Python Style Guide** - For documentation and structure
4. **Clean Architecture** - Separation of concerns, dependency inversion

### Key Philosophy

- **Explicit is better than implicit**
- **Readability counts**
- **Simple is better than complex**
- **Maintainability over cleverness**

## Code Layout

### File Organization

Every Python file should follow this structure:

```python
#!/usr/bin/env python3  # Only for executable files
"""
Module docstring explaining purpose.

This module provides functionality for...
"""

# Standard library imports
import os
import sys
from typing import Optional, List

# Third-party imports
import numpy as np
from rich.console import Console

# Local imports
from src.core.case import Case
from src.utils.colors import Colors

# Module-level constants
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3

# Classes
class MyClass:
    """Class implementation."""
    pass

# Functions
def my_function():
    """Function implementation."""
    pass

# Entry point (only in main.py or scripts)
if __name__ == '__main__':
    main()
```

### Import Order

Imports should be grouped in this order, with a blank line between groups:

1. Standard library imports
2. Third-party library imports
3. Local application imports

Within each group, imports should be alphabetically sorted.

**Good:**
```python
import os
import sys
from typing import Optional

import numpy as np
from rich.console import Console

from src.core.case import Case
from src.utils.logger import Logger
```

**Bad:**
```python
from src.core.case import Case
import numpy as np
import os
from rich.console import Console
```

### Line Length

- Maximum line length: **88 characters** (Black formatter default)
- For long strings, use implicit line continuation:

```python
message = (
    "This is a very long message that needs to be split "
    "across multiple lines for better readability."
)
```

### Indentation

- Use **4 spaces** per indentation level
- Never use tabs
- Continuation lines should use hanging indent or vertical alignment

```python
# Hanging indent
result = some_function(
    arg1, arg2, arg3,
    arg4, arg5
)

# Vertical alignment
result = some_function(arg1, arg2, arg3,
                      arg4, arg5)
```

### Blank Lines

- **Two blank lines** between top-level functions and classes
- **One blank line** between methods in a class
- Use blank lines sparingly within functions to separate logical sections

## Naming Conventions

### General Rules

| Type | Convention | Example |
|------|-----------|---------|
| Module | `snake_case` | `data_utils.py` |
| Class | `PascalCase` | `CaseCommand` |
| Function | `snake_case` | `execute_command()` |
| Method | `snake_case` | `get_data()` |
| Variable | `snake_case` | `case_name` |
| Constant | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |
| Private | `_leading_underscore` | `_internal_method()` |
| Protected | `_leading_underscore` | `_helper_function()` |

### Specific Naming Guidelines

**Classes:**
```python
class CaseCommand:          # Good: descriptive noun
class DataProcessor:        # Good: clear purpose
class execute_case:         # Bad: not PascalCase
class Cmd:                  # Bad: unclear abbreviation
```

**Functions:**
```python
def execute_command(args):  # Good: verb + object
def get_case_data():        # Good: clear action
def ExecuteCommand():       # Bad: not snake_case
def process():              # Bad: too generic
```

**Variables:**
```python
case_name = "CS4SG1U1"      # Good: descriptive
max_nodes = 100             # Good: clear meaning
cn = "CS4SG1U1"             # Bad: unclear abbreviation
CaseName = "CS4SG1U1"       # Bad: not snake_case
```

**Constants:**
```python
DEFAULT_TIMEOUT = 30        # Good: all caps
MAX_RETRY_COUNT = 3         # Good: descriptive
default_timeout = 30        # Bad: not all caps
TIMEOUT = 30                # OK: but less descriptive
```

**Boolean Variables:**
Use prefixes like `is_`, `has_`, `can_`, `should_`:

```python
is_valid = True
has_data = False
can_execute = True
should_retry = False
```

## Documentation

### Module Docstrings

Every module should have a docstring at the top:

```python
"""
Brief one-line description.

More detailed explanation if needed. This can span multiple
lines and provide context about what the module does.
"""
```

### Class Docstrings

Use Google-style docstrings for classes:

```python
class CaseCommand(BaseCommand):
    """
    Command for managing simulation cases.

    This class handles case operations including showing case information,
    creating new cases, and running simulations.

    Attributes:
        name: Command name used in CLI
        description: Brief description for help text
        category: Command category for grouping
    """
```

### Function/Method Docstrings

Use Google-style format with Args, Returns, and Raises sections:

```python
def execute_command(case_path: str, verbose: bool = False) -> dict:
    """
    Execute command for the specified case.

    Loads case data, processes it, and returns results in a structured
    format. Supports verbose output for debugging.

    Args:
        case_path: Path to the case directory
        verbose: Enable detailed output if True

    Returns:
        Dictionary containing:
            - status: Execution status ('success' or 'error')
            - data: Processed case data
            - message: Status message

    Raises:
        FileNotFoundError: If case_path does not exist
        ValueError: If case_path is not a valid case directory

    Examples:
        >>> result = execute_command('CS4SG1U1', verbose=True)
        >>> print(result['status'])
        success
    """
```

### Inline Comments

- Use sparingly - code should be self-documenting
- Place comments on the line before the code
- Use complete sentences with proper punctuation

```python
# Good: Explains why, not what
# Use case-insensitive comparison for cross-platform compatibility
if case_name.lower() == target.lower():
    process_case()

# Bad: States the obvious
# Check if names are equal
if case_name.lower() == target.lower():
    process_case()
```

## Type Hints

Use type hints for function signatures and complex variables:

### Basic Type Hints

```python
from typing import List, Dict, Optional, Tuple, Union

def get_case_data(case_path: str) -> Dict[str, any]:
    """Get case data."""
    pass

def process_nodes(nodes: List[int], verbose: bool = False) -> None:
    """Process nodes."""
    pass

def find_case(name: str) -> Optional[Case]:
    """Find case by name, returns None if not found."""
    pass
```

### Complex Type Hints

```python
from typing import List, Dict, Optional, Callable

def process_data(
    data: List[Dict[str, float]],
    callback: Optional[Callable[[float], float]] = None
) -> Tuple[bool, str]:
    """Process data with optional callback."""
    pass
```

### When to Use Type Hints

**Always use for:**
- Public API functions
- Class methods (except simple getters/setters)
- Complex data structures

**Optional for:**
- Simple internal functions
- Obvious types (like `name: str` in many cases)
- When it reduces readability

## Module Structure

### Entry Point (main.py)

The main.py file should be minimal - just the entry point:

```python
#!/usr/bin/env python3
"""
FlexFlow - Main entry point.

This is the application entry point. All application logic
is in src/cli/app.py to keep this file minimal and clean.
"""

import sys

from src.cli.app import FlexFlowApp


def main() -> None:
    """Main entry point for FlexFlow application."""
    app = FlexFlowApp()
    sys.exit(app.run())


if __name__ == '__main__':
    main()
```

### Application Logic (src/cli/app.py)

Main application logic goes in a dedicated application class:

```python
"""
FlexFlow application class.

Contains the main application logic, command registration,
and execution flow.
"""

from typing import List, Optional

from src.cli.registry import CommandRegistry
from src.commands.case import CaseCommand


class FlexFlowApp:
    """
    Main FlexFlow application.

    Handles command registration, argument parsing, and
    command execution.
    """

    def __init__(self) -> None:
        """Initialize FlexFlow application."""
        self.registry = CommandRegistry()
        self._register_commands()

    def _register_commands(self) -> None:
        """Register all available commands."""
        commands = [
            CaseCommand(),
            DataCommand(),
            # ... other commands
        ]
        for cmd in commands:
            self.registry.register(cmd)

    def run(self, args: Optional[List[str]] = None) -> int:
        """
        Run the application.

        Args:
            args: Command-line arguments (default: sys.argv)

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        # Application logic here
        pass
```

### Command Modules

Each command should be a self-contained class:

```python
"""
Case command implementation.

Provides functionality for managing simulation cases including
showing information, creating new cases, and running simulations.
"""

from typing import Optional

from src.commands.base import BaseCommand


class CaseCommand(BaseCommand):
    """
    Case management command.

    Handles case operations: show, create, run.
    """

    # Class attributes (not properties)
    name = "case"
    description = "Manage simulation cases"
    category = "Core"

    def setup_parser(self, subparsers) -> None:
        """Set up argument parser for case command."""
        pass

    def execute(self, args) -> None:
        """Execute case command with given arguments."""
        pass


# NO module-level instantiation!
# Let the registry instantiate the class
```

### Utility Modules

Utility modules should contain related functions:

```python
"""
File utility functions.

Provides helper functions for file operations including
path validation, file reading, and directory management.
"""

import os
from pathlib import Path
from typing import Optional, List


def find_case_files(directory: Path, pattern: str = "*.othd") -> List[Path]:
    """
    Find case files matching pattern in directory.

    Args:
        directory: Directory to search
        pattern: Glob pattern for matching files

    Returns:
        List of matching file paths

    Raises:
        ValueError: If directory does not exist
    """
    if not directory.exists():
        raise ValueError(f"Directory not found: {directory}")

    return list(directory.glob(pattern))
```

## Command Pattern

### Base Command Structure

All commands inherit from BaseCommand:

```python
from abc import ABC, abstractmethod
from typing import Any


class BaseCommand(ABC):
    """
    Abstract base class for all commands.

    Defines the interface that all commands must implement.
    Uses the Command pattern for consistency and extensibility.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Command name for CLI."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description for help text."""
        pass

    @abstractmethod
    def setup_parser(self, subparsers: Any) -> None:
        """Configure argument parser."""
        pass

    @abstractmethod
    def execute(self, args: Any) -> None:
        """Execute command logic."""
        pass
```

### Command Implementation

```python
class DataCommand(BaseCommand):
    """Data analysis and inspection command."""

    # Class attributes (constants)
    name = "data"
    description = "Analyze and inspect simulation data"
    category = "Core"

    def setup_parser(self, subparsers) -> None:
        """Set up argument parser for data command."""
        parser = subparsers.add_parser(
            self.name,
            help=self.description
        )
        # Add arguments...
        return parser

    def execute(self, args) -> None:
        """Execute data command."""
        # Implementation...
        pass
```

## Error Handling

### Exception Hierarchy

Create custom exceptions for domain-specific errors:

```python
class FlexFlowError(Exception):
    """Base exception for FlexFlow errors."""
    pass


class CaseNotFoundError(FlexFlowError):
    """Raised when case directory is not found."""
    pass


class InvalidDataError(FlexFlowError):
    """Raised when data is invalid or corrupted."""
    pass
```

### Exception Handling

```python
def load_case(case_path: str) -> Case:
    """
    Load case from directory.

    Args:
        case_path: Path to case directory

    Returns:
        Loaded Case object

    Raises:
        CaseNotFoundError: If case directory not found
        InvalidDataError: If case data is invalid
    """
    if not os.path.exists(case_path):
        raise CaseNotFoundError(f"Case not found: {case_path}")

    try:
        case = Case.from_directory(case_path)
    except ValueError as e:
        raise InvalidDataError(f"Invalid case data: {e}")

    return case
```

### Error Messages

- Be specific and actionable
- Include relevant context
- Suggest solutions when possible

```python
# Good
raise ValueError(
    f"Invalid node number: {node}. "
    f"Valid range is 1-{max_nodes}. "
    "Use --list-nodes to see available nodes."
)

# Bad
raise ValueError("Invalid input")
```

## Testing

### Test Structure

```python
"""
Tests for case command.

Test cases for CaseCommand functionality including
show, create, and run operations.
"""

import pytest
from pathlib import Path

from src.commands.case import CaseCommand


class TestCaseCommand:
    """Test cases for CaseCommand."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.command = CaseCommand()
        self.test_case_path = Path("tests/fixtures/test_case")

    def test_command_name(self) -> None:
        """Test command has correct name."""
        assert self.command.name == "case"

    def test_execute_show_valid_case(self) -> None:
        """Test executing show with valid case."""
        # Test implementation...
        pass
```

### Test Naming

- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`
- Be descriptive: `test_execute_show_with_invalid_case`

## Examples

### Complete Module Example

```python
#!/usr/bin/env python3
"""
Data utilities for FlexFlow.

Provides helper functions for data manipulation, validation,
and transformation used throughout the application.
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np

from src.core.case import Case
from src.utils.logger import get_logger

# Module constants
DEFAULT_SAMPLE_RATE = 50
MAX_DATA_POINTS = 100000

# Module logger
logger = get_logger(__name__)


class DataProcessor:
    """
    Process and validate simulation data.

    Handles data loading, validation, and transformation for
    simulation analysis.

    Attributes:
        sample_rate: Data sampling rate in Hz
        max_points: Maximum number of data points to process
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        max_points: int = MAX_DATA_POINTS
    ) -> None:
        """
        Initialize data processor.

        Args:
            sample_rate: Sampling rate for data processing
            max_points: Maximum points to process
        """
        self.sample_rate = sample_rate
        self.max_points = max_points
        self._cache: Dict[str, Any] = {}

    def load_data(self, file_path: Path) -> np.ndarray:
        """
        Load data from file.

        Args:
            file_path: Path to data file

        Returns:
            Loaded data as numpy array

        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If file format is invalid
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")

        logger.info(f"Loading data from {file_path}")

        try:
            data = np.loadtxt(file_path)
        except Exception as e:
            raise ValueError(f"Failed to load data: {e}")

        return data

    def _validate_data(self, data: np.ndarray) -> bool:
        """
        Validate data integrity.

        Args:
            data: Data to validate

        Returns:
            True if data is valid
        """
        # Validation logic...
        return True


def calculate_statistics(data: np.ndarray) -> Dict[str, float]:
    """
    Calculate basic statistics for data.

    Args:
        data: Input data array

    Returns:
        Dictionary with statistics:
            - mean: Mean value
            - std: Standard deviation
            - min: Minimum value
            - max: Maximum value

    Examples:
        >>> data = np.array([1, 2, 3, 4, 5])
        >>> stats = calculate_statistics(data)
        >>> print(stats['mean'])
        3.0
    """
    return {
        'mean': np.mean(data),
        'std': np.std(data),
        'min': np.min(data),
        'max': np.max(data)
    }
```

## Tools and Automation

### Recommended Tools

1. **black** - Code formatter (88 char line length)
2. **flake8** - Linter for style checking
3. **mypy** - Static type checker
4. **isort** - Import sorter
5. **pylint** - Code quality checker

### Configuration Files

Create these in project root:

**setup.cfg:**
```ini
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude = .git,__pycache__,build,dist

[mypy]
python_version = 3.12
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
```

**pyproject.toml:**
```toml
[tool.black]
line-length = 88
target-version = ['py312']

[tool.isort]
profile = "black"
line_length = 88
```

## Summary

### Quick Checklist

Before committing code, verify:

- [ ] Follows PEP 8 style guidelines
- [ ] Has appropriate docstrings (module, class, function)
- [ ] Uses type hints for public functions
- [ ] Imports are organized correctly
- [ ] No module-level instantiation (except constants)
- [ ] Error messages are clear and actionable
- [ ] Variable names are descriptive
- [ ] Code is properly commented (when needed)
- [ ] Tests are included (for new features)
- [ ] Line length is ≤ 88 characters

### Key Principles

1. **Readability first** - Code is read more than written
2. **Consistency** - Follow established patterns
3. **Simplicity** - Simple solutions over complex ones
4. **Documentation** - Document why, not what
5. **Testing** - Test critical functionality

## References

- [PEP 8 - Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [PEP 257 - Docstring Conventions](https://peps.python.org/pep-0257/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
