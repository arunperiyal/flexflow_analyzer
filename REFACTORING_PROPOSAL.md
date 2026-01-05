# FlexFlow Manager - Refactoring Proposal

## Current Issues

1. **Inconsistent Command Handler Pattern**: Mix of direct execution and subcommand patterns
2. **Duplicate Code**: `tecplot_python.py` at root vs `module/tecplot_handler.py`
3. **Large Parser File**: 313 lines with all command definitions in one place
4. **Main.py Complexity**: 125 lines of repetitive if-elif chains
5. **Help Message Coupling**: Help is tightly coupled to command implementation
6. **Missing Command**: `tecplot` not exported in `module/commands/__init__.py`

## Proposed Structure

### 1. Command Registry Pattern

Replace the large if-elif chain with a registry-based approach:

```
module/
├── cli/
│   ├── __init__.py
│   ├── parser.py           # Main parser only
│   ├── registry.py         # NEW: Command registry
│   └── help_messages.py    # Main help only
├── commands/
│   ├── __init__.py         # Auto-discover commands
│   ├── base.py             # NEW: Base command class
│   ├── info/               # Renamed from info_cmd
│   │   ├── __init__.py
│   │   ├── command.py
│   │   ├── parser.py       # NEW: Command-specific parser
│   │   └── help.py         # Renamed from help_messages.py
│   ├── plot/
│   ├── compare/
│   ├── tecplot/
│   │   ├── __init__.py
│   │   ├── command.py
│   │   ├── parser.py
│   │   ├── help.py
│   │   ├── info.py         # Subcommand
│   │   ├── extract.py      # Subcommand
│   │   ├── converter.py
│   │   └── hdf5_reader.py
│   └── ...
├── core/                   # Keep as is
├── utils/                  # Keep as is
└── installer/              # Keep as is
```

### 2. Base Command Class

Each command inherits from a base class:

```python
# module/commands/base.py
from abc import ABC, abstractmethod

class BaseCommand(ABC):
    """Base class for all commands"""
    
    @property
    @abstractmethod
    def name(self):
        """Command name"""
        pass
    
    @property
    @abstractmethod
    def description(self):
        """Short description for help"""
        pass
    
    @property
    def category(self):
        """Command category for grouped help"""
        return "General"
    
    @abstractmethod
    def setup_parser(self, subparsers):
        """Add this command's parser to subparsers"""
        pass
    
    @abstractmethod
    def execute(self, args):
        """Execute the command"""
        pass
    
    def show_help(self):
        """Show detailed help (optional override)"""
        pass
    
    def show_examples(self):
        """Show examples (optional override)"""
        pass
```

### 3. Command Implementation Example

```python
# module/commands/info/command.py
from ..base import BaseCommand

class InfoCommand(BaseCommand):
    name = "info"
    description = "Display case information"
    category = "Analysis"
    
    def setup_parser(self, subparsers):
        parser = subparsers.add_parser(
            self.name, 
            add_help=False,
            help=self.description
        )
        parser.add_argument('case', nargs='?', help='Case directory path')
        parser.add_argument('-v', '--verbose', action='store_true')
        parser.add_argument('-h', '--help', action='store_true')
        parser.add_argument('--examples', action='store_true')
        return parser
    
    def execute(self, args):
        if hasattr(args, 'help') and args.help:
            self.show_help()
        elif hasattr(args, 'examples') and args.examples:
            self.show_examples()
        else:
            # Actual execution logic
            from .core import execute_info
            execute_info(args)
    
    def show_help(self):
        from .help import print_info_help
        print_info_help()
    
    def show_examples(self):
        from .help import print_info_examples
        print_info_examples()
```

### 4. Command Registry

```python
# module/cli/registry.py
class CommandRegistry:
    """Registry for all commands"""
    
    def __init__(self):
        self._commands = {}
    
    def register(self, command_class):
        """Register a command"""
        cmd = command_class()
        self._commands[cmd.name] = cmd
        return cmd
    
    def get(self, name):
        """Get command by name"""
        return self._commands.get(name)
    
    def all(self):
        """Get all commands"""
        return self._commands.values()
    
    def by_category(self):
        """Get commands grouped by category"""
        categories = {}
        for cmd in self._commands.values():
            cat = cmd.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(cmd)
        return categories

# Global registry
registry = CommandRegistry()
```

### 5. Auto-Discovery

```python
# module/commands/__init__.py
from ..cli.registry import registry

# Import and register all commands
from .info.command import InfoCommand
from .new.command import NewCommand
from .preview.command import PreviewCommand
from .statistics.command import StatisticsCommand
from .plot.command import PlotCommand
from .compare.command import CompareCommand
from .tecplot.command import TecplotCommand
from .template.command import TemplateCommand
from .docs.command import DocsCommand

# Register commands
registry.register(InfoCommand)
registry.register(NewCommand)
registry.register(PreviewCommand)
registry.register(StatisticsCommand)
registry.register(PlotCommand)
registry.register(CompareCommand)
registry.register(TecplotCommand)
registry.register(TemplateCommand)
registry.register(DocsCommand)

__all__ = ['registry']
```

### 6. Simplified Main.py

```python
#!/usr/bin/env python3
"""FlexFlow CLI - Main entry point"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from module.cli.parser import parse_args
from module.cli.help_messages import print_main_help
from module.commands import registry
from module.installer import install, uninstall, update

def main():
    args = parse_args()
    
    # Handle global flags first
    if args.install:
        install()
        return
    elif args.uninstall:
        uninstall()
        return
    elif args.update:
        update()
        return
    elif args.completion:
        from module.cli.completion import generate_completion_script
        print(generate_completion_script(args.completion))
        return
    
    # Handle commands via registry
    if not args.command:
        print_main_help()
    else:
        command = registry.get(args.command)
        if command:
            command.execute(args)
        else:
            print(f"Unknown command: {args.command}")
            print_main_help()
            sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
```

### 7. Simplified Parser

```python
# module/cli/parser.py
import argparse
from module.commands import registry

def create_parser():
    """Create and configure the argument parser"""
    
    parser = argparse.ArgumentParser(
        description='FlexFlow - Analyze and visualize FlexFlow simulation data',
        add_help=False
    )
    
    # Global options
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--update', action='store_true')
    parser.add_argument('--completion', choices=['bash', 'zsh', 'fish'])
    parser.add_argument('--version', action='store_true')
    parser.add_argument('-h', '--help', action='store_true')
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Let each command register itself
    for command in registry.all():
        command.setup_parser(subparsers)
    
    return parser

def parse_args(args=None):
    """Parse command line arguments"""
    parser = create_parser()
    return parser.parse_args(args)
```

### 8. Categorized Help

```python
# module/cli/help_messages.py
from module.utils.colors import Colors
from module.commands import registry

def print_main_help():
    """Print main help message with categorized commands"""
    
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow - Analysis and Visualization Tool{Colors.RESET}

{Colors.BOLD}USAGE:{Colors.RESET}
    {Colors.GREEN}flexflow{Colors.RESET} {Colors.YELLOW}<command>{Colors.RESET} [options]
""")
    
    # Group commands by category
    categories = registry.by_category()
    
    for category in ["Analysis", "Visualization", "File Operations", "Utilities"]:
        if category in categories:
            print(f"{Colors.BOLD}{category.upper()} COMMANDS:{Colors.RESET}")
            for cmd in sorted(categories[category], key=lambda x: x.name):
                print(f"    {Colors.CYAN}{cmd.name:12}{Colors.RESET} {cmd.description}")
            print()
    
    print(f"""{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--install{Colors.RESET}           Install FlexFlow system-wide
    {Colors.YELLOW}--uninstall{Colors.RESET}         Remove FlexFlow from system
    {Colors.YELLOW}--update{Colors.RESET}            Update FlexFlow installation
    {Colors.YELLOW}--completion{Colors.RESET} <shell> Generate completion script
    {Colors.YELLOW}--help, -h{Colors.RESET}          Show this help message

For more help on a specific command:
    flexflow {Colors.YELLOW}<command>{Colors.RESET} --help
""")
```

## Migration Benefits

### Advantages
1. **Extensibility**: Add new commands by creating a new folder + class
2. **Maintainability**: Each command is self-contained
3. **Testability**: Easy to test commands in isolation
4. **Consistency**: All commands follow same pattern
5. **Discoverability**: Auto-registration reduces boilerplate
6. **Categorization**: Grouped help for better UX
7. **Less Code**: Eliminates repetitive if-elif chains

### Trade-offs
1. **Initial Effort**: Need to refactor all existing commands
2. **Learning Curve**: New pattern for contributors
3. **Abstraction**: Additional layer of indirection

## Migration Path

### Phase 1: Foundation (No Breaking Changes)
1. Create `base.py` and `registry.py`
2. Create new `main_v2.py` with registry pattern
3. Test alongside existing `main.py`

### Phase 2: Migrate Commands (One at a time)
1. Start with simplest command (e.g., `info`)
2. Refactor to new structure
3. Test thoroughly
4. Repeat for all commands

### Phase 3: Cleanup
1. Remove old `main.py`
2. Rename `main_v2.py` → `main.py`
3. Remove duplicate code (tecplot_python.py)
4. Update documentation

### Phase 4: Polish
1. Add command categories
2. Enhance help messages
3. Add plugin system for external commands (future)

## File Cleanup

### Files to Remove
- `tecplot_python.py` (merge into module/commands/tecplot/)

### Files to Rename
- `*_cmd/` → remove `_cmd` suffix for cleaner structure
- `help_messages.py` → `help.py` for consistency

## Additional Improvements

1. **Configuration Management**
   - Centralized config in `~/.flexflow/config.yaml`
   - Per-command default settings

2. **Plugin System** (Future)
   ```python
   # Allow users to add custom commands
   ~/.flexflow/plugins/
   ├── my_custom_command.py
   └── another_command.py
   ```

3. **Better Error Handling**
   - Custom exception hierarchy
   - Consistent error messages
   - Better validation feedback

4. **Logging System**
   - Structured logging
   - Debug mode with `-vv`
   - Log to file option

## Questions to Consider

1. Do you want to keep subcommands (like `tecplot info`, `tecplot extract`)?
2. Should commands be grouped by category in help?
3. Do you want a plugin system for extensibility?
4. Should we maintain backward compatibility during migration?

## Next Steps

If you approve this proposal, I can:
1. Implement Phase 1 (foundation without breaking changes)
2. Migrate one command as proof of concept
3. Create a migration script for batch refactoring
4. Update documentation and examples

Would you like me to proceed with implementation?
