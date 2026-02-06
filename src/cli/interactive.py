"""
Interactive shell for FlexFlow.

Provides an interactive REPL (Read-Eval-Print Loop) interface with
command history, tab completion, and syntax highlighting.
"""

import os
import sys
import shlex
from pathlib import Path
from typing import Optional, List, Dict, Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion, WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.tree import Tree
from rich import box

from src.cli.registry import registry
from src.utils.colors import Colors


class FlexFlowCompleter(Completer):
    """
    Custom completer for FlexFlow commands.

    Provides intelligent tab completion for commands, subcommands,
    options, file paths, and context commands.
    """

    def __init__(self, shell=None):
        """
        Initialize the completer with command registry.

        Args:
            shell: InteractiveShell instance for context-aware completion
        """
        self.shell = shell
        self.commands = {}
        self._build_command_tree()

    def _build_command_tree(self) -> None:
        """Build command tree from registry for completion."""
        for cmd in registry.all():
            self.commands[cmd.name] = {
                'description': cmd.description,
                'subcommands': self._get_subcommands(cmd),
                'flags': self._get_flags(cmd)
            }

    def _get_subcommands(self, command) -> List[str]:
        """
        Get subcommands for a command.

        Args:
            command: Command instance

        Returns:
            List of subcommand names
        """
        subcommands_map = {
            'case': ['show', 'create', 'run'],
            'data': ['show', 'stats'],
            'field': ['info', 'extract'],
            'template': ['plot', 'case'],
            'check': [],
            'plot': [],
            'compare': [],
            'docs': [],
        }
        return subcommands_map.get(command.name, [])

    def _get_flags(self, command) -> Dict[str, str]:
        """
        Get common flags for commands.

        Args:
            command: Command instance

        Returns:
            Dictionary of flag -> description
        """
        common_flags = {
            '--help': 'Show help message',
            '-h': 'Show help message',
            '--verbose': 'Enable verbose output',
            '-v': 'Enable verbose output',
            '--examples': 'Show usage examples',
        }

        # Command-specific flags
        command_flags = {
            'case': {
                **common_flags,
            },
            'data': {
                **common_flags,
                '--node': 'Node ID',
                '--component': 'Component (x, y, z)',
            },
            'field': {
                **common_flags,
            },
            'plot': {
                **common_flags,
                '--node': 'Node ID to plot',
                '--component': 'Component to plot',
                '--output': 'Output file',
            },
        }

        return command_flags.get(command.name, common_flags)

    def _get_file_completions(self, word: str, directory: Path) -> List[tuple]:
        """
        Get file/directory completions.

        Args:
            word: Current word being completed
            directory: Directory to search in

        Returns:
            List of (name, is_dir) tuples
        """
        try:
            if not directory.exists():
                return []

            completions = []
            for item in directory.iterdir():
                if item.name.startswith(word):
                    completions.append((item.name, item.is_dir()))

            return sorted(completions, key=lambda x: (not x[1], x[0]))
        except (PermissionError, OSError):
            return []

    def get_completions(self, document, complete_event):
        """
        Generate completions based on current input.

        Args:
            document: Current document from prompt_toolkit
            complete_event: Completion event

        Yields:
            Completion objects for matching commands
        """
        text = document.text_before_cursor
        words = text.split()

        # Complete command names (first word)
        if len(words) == 0 or (len(words) == 1 and not text.endswith(' ')):
            word = words[0] if words else ''

            # FlexFlow commands
            for cmd_name in self.commands.keys():
                if cmd_name.startswith(word):
                    yield Completion(
                        cmd_name,
                        start_position=-len(word),
                        display_meta=self.commands[cmd_name]['description']
                    )

            # Shell commands
            shell_commands = [
                ('exit', 'Exit FlexFlow'),
                ('quit', 'Exit FlexFlow'),
                ('help', 'Show help message'),
                ('?', 'Show help message'),
                ('clear', 'Clear screen'),
                ('history', 'Show command history'),
                ('pwd', 'Show current directory and contexts'),
                ('ls', 'List files'),
                ('ll', 'List files (long format)'),
                ('la', 'List all files'),
                ('cd', 'Change directory'),
                ('cat', 'View file contents'),
                ('find', 'Find case directories'),
                ('tree', 'Show directory tree'),
                ('use', 'Set context'),
                ('unuse', 'Clear context'),
            ]

            for shell_cmd, desc in shell_commands:
                if shell_cmd.startswith(word):
                    yield Completion(
                        shell_cmd,
                        start_position=-len(word),
                        display_meta=desc
                    )

        # Complete subcommands and flags
        elif len(words) >= 1:
            cmd_name = words[0]

            # Handle context commands (use/unuse)
            if cmd_name == 'use':
                self._complete_use_command(words, text)
                return
            elif cmd_name == 'unuse':
                self._complete_unuse_command(words, text)
                return

            # Handle file browsing commands
            if cmd_name in ['cd', 'cat', 'ls', 'll', 'la']:
                yield from self._complete_path(words, text)
                return

            # Handle FlexFlow commands
            if cmd_name in self.commands:
                # Complete subcommands
                if len(words) == 1 or (len(words) == 2 and not text.endswith(' ')):
                    word = words[1] if len(words) == 2 else ''

                    # Subcommands
                    subcommands = self.commands[cmd_name]['subcommands']
                    for subcmd in subcommands:
                        if subcmd.startswith(word):
                            yield Completion(
                                subcmd,
                                start_position=-len(word),
                                display_meta='Subcommand'
                            )

                    # Flags
                    if word.startswith('-'):
                        flags = self.commands[cmd_name]['flags']
                        for flag, desc in flags.items():
                            if flag.startswith(word):
                                yield Completion(
                                    flag,
                                    start_position=-len(word),
                                    display_meta=desc
                                )

                # Complete flags after subcommand
                elif len(words) >= 2:
                    word = words[-1] if not text.endswith(' ') else ''

                    if word.startswith('-') or text.endswith(' '):
                        flags = self.commands[cmd_name]['flags']
                        for flag, desc in flags.items():
                            if flag.startswith(word):
                                yield Completion(
                                    flag,
                                    start_position=-len(word),
                                    display_meta=desc
                                )

    def _complete_use_command(self, words: List[str], text: str):
        """Complete use command with subcommands."""
        if len(words) == 1 or (len(words) == 2 and not text.endswith(' ')):
            word = words[1] if len(words) == 2 else ''
            subcommands = [
                ('case', 'Set case context'),
                ('problem', 'Set problem name'),
                ('rundir', 'Set run directory'),
                ('dir', 'Set output directory'),
                ('--help', 'Show help'),
                ('-h', 'Show help'),
            ]

            for subcmd, desc in subcommands:
                if subcmd.startswith(word):
                    yield Completion(
                        subcmd,
                        start_position=-len(word),
                        display_meta=desc
                    )

    def _complete_unuse_command(self, words: List[str], text: str):
        """Complete unuse command with subcommands."""
        if len(words) == 1 or (len(words) == 2 and not text.endswith(' ')):
            word = words[1] if len(words) == 2 else ''
            subcommands = [
                ('case', 'Clear case context'),
                ('problem', 'Clear problem context'),
                ('rundir', 'Clear rundir context'),
                ('dir', 'Clear output dir context'),
                ('all', 'Clear all contexts'),
                ('--help', 'Show help'),
                ('-h', 'Show help'),
            ]

            for subcmd, desc in subcommands:
                if subcmd.startswith(word):
                    yield Completion(
                        subcmd,
                        start_position=-len(word),
                        display_meta=desc
                    )

    def _complete_path(self, words: List[str], text: str):
        """Complete file paths for cd, cat, ls commands."""
        if self.shell is None:
            return

        # Get the path being completed
        if len(words) == 1 or text.endswith(' '):
            word = ''
            base_dir = self.shell._current_dir
        else:
            word = words[-1]
            if '/' in word:
                # Completing within a subdirectory
                parts = word.rsplit('/', 1)
                base_dir = self.shell._current_dir / parts[0]
                word = parts[1]
            else:
                base_dir = self.shell._current_dir

        # Get completions
        completions = self._get_file_completions(word, base_dir)
        for name, is_dir in completions:
            suffix = '/' if is_dir else ''
            yield Completion(
                name + suffix,
                start_position=-len(word),
                display_meta='dir' if is_dir else 'file'
            )


class InteractiveShell:
    """
    Interactive shell for FlexFlow.

    Provides a REPL interface with command history, tab completion,
    and persistent session state.

    Attributes:
        console: Rich console for formatted output
        session: Prompt toolkit session
        history_file: Path to command history file
        running: Flag indicating if shell is running
        app: FlexFlowApp instance for command execution
    """

    def __init__(self, app=None):
        """
        Initialize the interactive shell.

        Args:
            app: FlexFlowApp instance (optional, will create if not provided)
        """
        self.console = Console()
        self.running = True
        self.history_file = self._get_history_file()
        self.session = self._create_session()

        # Context tracking
        self._current_case: Optional[str] = None  # Full path to case
        self._current_case_name: Optional[str] = None  # Just the case name for display
        self._current_problem: Optional[str] = None  # Problem name/ID
        self._current_rundir: Optional[str] = None  # Run directory
        self._current_output_dir: Optional[str] = None  # Output directory (dir from simflow.config)
        self._current_dir: Path = Path.cwd()  # Track current working directory

        # Store app instance for command execution
        if app is None:
            from src.cli.app import FlexFlowApp
            self.app = FlexFlowApp()
        else:
            self.app = app

    def _get_history_file(self) -> Path:
        """
        Get path to history file.

        Returns:
            Path to command history file
        """
        history_dir = Path.home() / '.flexflow'
        history_dir.mkdir(exist_ok=True)
        return history_dir / 'history'

    def _create_session(self) -> PromptSession:
        """
        Create prompt_toolkit session with history and completion.

        Returns:
            Configured PromptSession instance
        """
        # Custom style for prompt with color-coded contexts
        style = Style.from_dict({
            'prompt': '#00aa00 bold',
            'path': '#888888',
            'box': '#666666',           # Box drawing characters
            'case': '#00aaff bold',     # Cyan for case
            'problem': '#ffaa00',       # Yellow/orange for problem
            'rundir': '#ff00ff',        # Magenta for rundir
            'outputdir': '#00ff00',     # Green for output dir
            'sep': '#444444',           # Separator
        })

        return PromptSession(
            history=FileHistory(str(self.history_file)),
            completer=FlexFlowCompleter(shell=self),
            style=style,
            enable_history_search=True,
            complete_while_typing=True,
        )

    def _get_prompt_message(self) -> HTML:
        """
        Generate prompt message with context (multi-line format).

        Returns:
            Formatted prompt message
        """
        # Show abbreviated path
        try:
            home = Path.home()
            if self._current_dir == home:
                dir_display = "~"
            elif self._current_dir.is_relative_to(home):
                dir_display = "~/" + str(self._current_dir.relative_to(home))
            else:
                dir_display = str(self._current_dir)
        except (ValueError, RuntimeError):
            dir_display = str(self._current_dir)

        # Don't limit path length for multi-line prompt

        # Build context string with color coding
        contexts = []
        if self._current_case_name:
            contexts.append(f'<case>c:{self._current_case_name}</case>')
        if self._current_problem:
            contexts.append(f'<problem>p:{self._current_problem}</problem>')
        if self._current_rundir:
            rundir_name = Path(self._current_rundir).name
            contexts.append(f'<rundir>r:{rundir_name}</rundir>')
        if self._current_output_dir:
            output_dir_name = Path(self._current_output_dir).name
            contexts.append(f'<outputdir>d:{output_dir_name}</outputdir>')

        # Multi-line prompt format
        if contexts:
            context_str = " <sep>|</sep> ".join(contexts)
            return HTML(
                f'<box>╭─</box> <path>{dir_display}</path> <box>[</box>{context_str}<box>]</box>\n'
                f'<box>╰─❯</box> '
            )
        return HTML(
            f'<box>╭─</box> <path>{dir_display}</path>\n'
            f'<box>╰─❯</box> '
        )

    def print_welcome(self) -> None:
        """Print welcome message and help information."""
        from __version__ import __version__

        self.console.print()
        self.console.print(
            Panel(
                f"[bold cyan]FlexFlow Interactive Shell[/bold cyan] [dim]v{__version__}[/dim]\n\n"
                "Fast and efficient simulation analysis tool\n\n"
                "[yellow]Quick Start:[/yellow]\n"
                "  • Type [cyan]help[/cyan] or [cyan]?[/cyan] for available commands\n"
                "  • Use [cyan]ls[/cyan], [cyan]cd[/cyan], [cyan]find[/cyan] to browse\n"
                "  • Use [cyan]Tab[/cyan] for autocompletion\n"
                "  • Use [cyan]↑/↓[/cyan] for command history\n"
                "  • Type [cyan]exit[/cyan] or [cyan]quit[/cyan] to exit\n\n"
                "[dim]Tip: Navigate directories without leaving the shell![/dim]",
                border_style="cyan",
                box=box.ROUNDED
            )
        )
        self.console.print()

    def print_goodbye(self) -> None:
        """Print goodbye message."""
        self.console.print()
        self.console.print("[cyan]Thanks for using FlexFlow! Goodbye![/cyan]")
        self.console.print()

    def handle_shell_command(self, command: str) -> bool:
        """
        Handle built-in shell commands.

        Args:
            command: Shell command to execute

        Returns:
            True if command was handled, False otherwise
        """
        parts = command.strip().split()
        if not parts:
            return True

        cmd = parts[0].lower()

        # Exit commands
        if cmd in ['exit', 'quit', 'q']:
            self.running = False
            return True

        # Help command
        if cmd in ['help', '?']:
            self.show_help()
            return True

        # Clear screen
        if cmd == 'clear':
            os.system('clear' if os.name != 'nt' else 'cls')
            return True

        # Show history
        if cmd == 'history':
            self.show_history()
            return True

        # Set context with subcommands
        if cmd == 'use':
            if len(parts) < 2:
                self.show_use_help()
                return True

            subcommand = parts[1]

            # Check for help flag
            if subcommand in ['--help', '-h', 'help']:
                self.show_use_help()
                return True

            if subcommand == 'case':
                if len(parts) > 2:
                    self.use_case(parts[2])
                else:
                    self.console.print("[yellow]Usage:[/yellow] use case <case_name_or_path>")
            elif subcommand == 'problem':
                if len(parts) > 2:
                    self.use_problem(parts[2])
                else:
                    self.console.print("[yellow]Usage:[/yellow] use problem <problem_name>")
            elif subcommand == 'rundir':
                if len(parts) > 2:
                    self.use_rundir(parts[2])
                else:
                    self.console.print("[yellow]Usage:[/yellow] use rundir <directory_path>")
            elif subcommand == 'dir':
                if len(parts) > 2:
                    self.use_dir(parts[2])
                else:
                    self.console.print("[yellow]Usage:[/yellow] use dir <directory_path>")
            else:
                # Backwards compatibility: use <case> without subcommand
                self.use_case(parts[1])
            return True

        # Clear context with subcommands
        if cmd == 'unuse':
            if len(parts) < 2:
                # Clear all contexts
                self.unuse_all()
            else:
                subcommand = parts[1]

                # Check for help flag
                if subcommand in ['--help', '-h', 'help']:
                    self.show_unuse_help()
                    return True

                if subcommand == 'case':
                    self.unuse_case()
                elif subcommand == 'problem':
                    self.unuse_problem()
                elif subcommand == 'rundir':
                    self.unuse_rundir()
                elif subcommand == 'dir':
                    self.unuse_dir()
                elif subcommand == 'all':
                    self.unuse_all()
                else:
                    self.console.print(f"[yellow]Unknown subcommand:[/yellow] {subcommand}")
                    self.console.print("[dim]Use: unuse [case|problem|rundir|dir|all][/dim]")
            return True

        # Show current directory and all contexts
        if cmd == 'pwd':
            self.console.print(f"Working directory: [cyan]{self._current_dir}[/cyan]")
            if self._current_case:
                self.console.print(f"Case context: [cyan]{self._current_case}[/cyan]")
            if self._current_problem:
                self.console.print(f"Problem context: [cyan]{self._current_problem}[/cyan]")
            if self._current_rundir:
                self.console.print(f"Run directory: [cyan]{self._current_rundir}[/cyan]")
            if self._current_output_dir:
                self.console.print(f"Output directory: [cyan]{self._current_output_dir}[/cyan]")
            if not any([self._current_case, self._current_problem, self._current_rundir, self._current_output_dir]):
                self.console.print("[dim]No context set[/dim]")
            return True

        # Change directory
        if cmd == 'cd':
            self.change_directory(parts[1] if len(parts) > 1 else str(Path.home()))
            return True

        # List files and directories
        if cmd in ['ls', 'll', 'la']:
            # Aliases: ll = ls -l, la = ls -a
            if cmd == 'll':
                args = ['-l'] + (parts[1:] if len(parts) > 1 else ['.'])
            elif cmd == 'la':
                args = ['-a'] + (parts[1:] if len(parts) > 1 else ['.'])
            else:
                args = parts[1:] if len(parts) > 1 else ['.']
            self.list_directory(args)
            return True

        # Find cases
        if cmd == 'find':
            pattern = parts[1] if len(parts) > 1 else '*'
            self.find_cases(pattern)
            return True

        # Show tree structure
        if cmd == 'tree':
            depth = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 2
            self.show_tree(depth)
            return True

        # View file contents
        if cmd == 'cat':
            if len(parts) > 1:
                self.cat_file(parts[1:])
            else:
                self.console.print("[yellow]Usage:[/yellow] cat <file> [files...]")
            return True

        return False

    def show_help(self) -> None:
        """Show help information."""
        table = Table(title="FlexFlow Commands", box=box.ROUNDED, show_header=True)
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")

        # Add FlexFlow commands from registry
        for cmd in registry.all():
            table.add_row(cmd.name, cmd.description)

        self.console.print()
        self.console.print(table)
        self.console.print()

        # Shell commands
        shell_table = Table(title="Shell Commands", box=box.ROUNDED, show_header=True)
        shell_table.add_column("Command", style="yellow", no_wrap=True)
        shell_table.add_column("Description", style="white")

        shell_commands = [
            ("help, ?", "Show this help message"),
            ("exit, quit", "Exit FlexFlow"),
            ("clear", "Clear the screen"),
            ("history", "Show command history"),
            ("pwd", "Show current directory and contexts"),
        ]

        for cmd, desc in shell_commands:
            shell_table.add_row(cmd, desc)

        self.console.print(shell_table)
        self.console.print()

        # Browsing commands
        browse_table = Table(title="Browsing Commands", box=box.ROUNDED, show_header=True)
        browse_table.add_column("Command", style="cyan", no_wrap=True)
        browse_table.add_column("Description", style="white")

        browse_commands = [
            ("ls [path]", "List files and directories"),
            ("ls -l", "List in long format with details"),
            ("ls -a", "Show hidden files"),
            ("cd <path>", "Change directory"),
            ("cd ~", "Go to home directory"),
            ("cd ..", "Go to parent directory"),
            ("cat <file>", "View file contents"),
            ("find [pattern]", "Find case directories"),
            ("tree [depth]", "Show directory tree (default depth: 2)"),
        ]

        for cmd, desc in browse_commands:
            browse_table.add_row(cmd, desc)

        self.console.print(browse_table)
        self.console.print()

        # Context commands
        context_table = Table(title="Context Commands", box=box.ROUNDED, show_header=True)
        context_table.add_column("Command", style="green", no_wrap=True)
        context_table.add_column("Description", style="white")

        context_commands = [
            ("use case <path>", "Set current case"),
            ("use problem <name>", "Set current problem"),
            ("use rundir <path>", "Set run directory"),
            ("use dir <path>", "Set output directory"),
            ("use <case>", "Shortcut for 'use case <case>'"),
            ("use --help", "Show detailed help for use command"),
            ("unuse case", "Clear case context"),
            ("unuse problem", "Clear problem context"),
            ("unuse rundir", "Clear rundir context"),
            ("unuse dir", "Clear output dir context"),
            ("unuse", "Clear all contexts"),
            ("unuse --help", "Show detailed help for unuse command"),
        ]

        for cmd, desc in context_commands:
            context_table.add_row(cmd, desc)

        self.console.print(context_table)
        self.console.print()

    def show_history(self) -> None:
        """Show command history."""
        if not self.history_file.exists():
            self.console.print("[dim]No command history yet.[/dim]")
            return

        try:
            with open(self.history_file, 'r') as f:
                lines = f.readlines()

            self.console.print()
            self.console.print("[bold]Command History:[/bold]")
            for i, line in enumerate(lines[-20:], 1):  # Show last 20
                self.console.print(f"  [dim]{i:2d}[/dim]  {line.strip()}")
            self.console.print()

            if len(lines) > 20:
                self.console.print(f"[dim]... showing last 20 of {len(lines)} commands[/dim]")
                self.console.print()

        except Exception as e:
            self.console.print(f"[red]Error reading history: {e}[/red]")

    def change_directory(self, path: str) -> None:
        """
        Change current working directory.

        Args:
            path: Directory path to change to
        """
        try:
            # Handle special paths
            if path == '~':
                new_dir = Path.home()
            elif path == '-':
                # Go back to previous directory (not implemented yet)
                self.console.print("[yellow]Previous directory tracking not yet implemented[/yellow]")
                return
            elif path == '..':
                new_dir = self._current_dir.parent
            else:
                new_dir = Path(path)

            # Resolve to absolute path
            if not new_dir.is_absolute():
                new_dir = self._current_dir / new_dir

            new_dir = new_dir.resolve()

            # Check if directory exists
            if not new_dir.exists():
                self.console.print(f"[red]Error: Directory not found: {new_dir}[/red]")
                return

            if not new_dir.is_dir():
                self.console.print(f"[red]Error: Not a directory: {new_dir}[/red]")
                return

            # Change directory
            self._current_dir = new_dir
            os.chdir(self._current_dir)
            self.console.print(f"[green]→[/green] {self._current_dir}")

        except Exception as e:
            self.console.print(f"[red]Error changing directory: {e}[/red]")

    def list_directory(self, args: List[str]) -> None:
        """
        List files and directories.

        Args:
            args: List of paths or options
        """
        try:
            # Parse options
            show_all = '-a' in args or '--all' in args
            long_format = '-l' in args or '--long' in args
            paths = [arg for arg in args if not arg.startswith('-')]

            if not paths:
                paths = ['.']

            for path_str in paths:
                target = Path(path_str)
                if not target.is_absolute():
                    target = self._current_dir / target

                if not target.exists():
                    self.console.print(f"[red]Error: Path not found: {target}[/red]")
                    continue

                # List directory contents
                if target.is_dir():
                    self._list_dir_contents(target, show_all, long_format)
                else:
                    # Show file info
                    self._show_file_info(target)

        except Exception as e:
            self.console.print(f"[red]Error listing directory: {e}[/red]")

    def _list_dir_contents(self, directory: Path, show_all: bool, long_format: bool) -> None:
        """
        List directory contents with formatting.

        Args:
            directory: Directory to list
            show_all: Show hidden files
            long_format: Show detailed information
        """
        try:
            items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))

            # Filter hidden files
            if not show_all:
                items = [item for item in items if not item.name.startswith('.')]

            if not items:
                self.console.print(f"[dim]Empty directory[/dim]")
                return

            if long_format:
                # Create table for long format
                table = Table(box=box.SIMPLE, show_header=True, padding=(0, 2))
                table.add_column("Type", style="cyan", width=4)
                table.add_column("Size", justify="right", style="yellow", width=10)
                table.add_column("Modified", style="blue", width=16)
                table.add_column("Name", style="white")

                for item in items:
                    item_type = "DIR" if item.is_dir() else "FILE"

                    # Get size
                    if item.is_file():
                        size = item.stat().st_size
                        size_str = self._format_size(size)
                    else:
                        size_str = "-"

                    # Get modification time
                    import datetime
                    mtime = datetime.datetime.fromtimestamp(item.stat().st_mtime)
                    mtime_str = mtime.strftime("%Y-%m-%d %H:%M")

                    # Color name based on type
                    name = item.name
                    if item.is_dir():
                        name = f"[bold cyan]{name}/[/bold cyan]"
                    elif self._is_case_directory(item):
                        name = f"[bold green]{name}/[/bold green]"
                    elif item.suffix in ['.othd', '.oisd', '.plt']:
                        name = f"[magenta]{name}[/magenta]"

                    table.add_row(item_type, size_str, mtime_str, name)

                self.console.print(table)
            else:
                # Simple format - columns
                from rich.columns import Columns

                items_formatted = []
                for item in items:
                    if item.is_dir():
                        if self._is_case_directory(item):
                            items_formatted.append(f"[bold green]{item.name}/[/bold green]")
                        else:
                            items_formatted.append(f"[cyan]{item.name}/[/cyan]")
                    elif item.suffix in ['.othd', '.oisd', '.plt']:
                        items_formatted.append(f"[magenta]{item.name}[/magenta]")
                    else:
                        items_formatted.append(item.name)

                self.console.print(Columns(items_formatted, equal=True, expand=False))

        except Exception as e:
            self.console.print(f"[red]Error listing directory: {e}[/red]")

    def _is_case_directory(self, path: Path) -> bool:
        """
        Check if directory is a FlexFlow case.

        Args:
            path: Directory path

        Returns:
            True if directory appears to be a case
        """
        if not path.is_dir():
            return False

        # Check for common case indicators
        indicators = [
            'input', 'output', 'binary',
            'simflow.config', 'case.config',
            '*.othd', '*.oisd'
        ]

        for indicator in indicators:
            if '*' in indicator:
                # Glob pattern
                if list(path.glob(indicator)):
                    return True
            else:
                # Direct file/directory
                if (path / indicator).exists():
                    return True

        return False

    def _format_size(self, size: int) -> str:
        """
        Format file size in human-readable format.

        Args:
            size: Size in bytes

        Returns:
            Formatted size string
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}PB"

    def _show_file_info(self, file_path: Path) -> None:
        """
        Show information about a single file.

        Args:
            file_path: File path
        """
        stat = file_path.stat()
        import datetime

        table = Table(box=box.ROUNDED, show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Path", str(file_path))
        table.add_row("Type", "File")
        table.add_row("Size", self._format_size(stat.st_size))

        mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
        table.add_row("Modified", mtime.strftime("%Y-%m-%d %H:%M:%S"))

        self.console.print(table)

    def find_cases(self, pattern: str) -> None:
        """
        Find case directories matching pattern.

        Args:
            pattern: Search pattern (glob or name)
        """
        try:
            self.console.print(f"[dim]Searching for cases matching '{pattern}'...[/dim]\n")

            cases_found = []

            # Search current directory and subdirectories
            for item in self._current_dir.rglob('*'):
                if item.is_dir() and self._is_case_directory(item):
                    if pattern == '*' or pattern.lower() in item.name.lower():
                        cases_found.append(item)

            if not cases_found:
                self.console.print(f"[yellow]No cases found matching '{pattern}'[/yellow]")
                return

            # Display results
            table = Table(title=f"Cases Found ({len(cases_found)})", box=box.ROUNDED)
            table.add_column("#", style="dim", width=4)
            table.add_column("Case Name", style="green")
            table.add_column("Path", style="cyan")

            for i, case in enumerate(cases_found, 1):
                rel_path = case.relative_to(self._current_dir) if case.is_relative_to(self._current_dir) else case
                table.add_row(str(i), case.name, str(rel_path))

            self.console.print(table)

        except Exception as e:
            self.console.print(f"[red]Error finding cases: {e}[/red]")

    def show_use_help(self) -> None:
        """Show help for use command."""
        self.console.print()
        self.console.print("[bold cyan]Use Command - Set Context[/bold cyan]")
        self.console.print()
        self.console.print("[bold]USAGE:[/bold]")
        self.console.print("  use case <path>         Set current case")
        self.console.print("  use problem <name>      Set current problem")
        self.console.print("  use rundir <path>       Set current run directory")
        self.console.print("  use dir <name>          Set output directory (relative to case)")
        self.console.print("  use <case>              Shortcut for 'use case <case>'")
        self.console.print("  use --help              Show this help message")
        self.console.print()
        self.console.print("[bold]EXAMPLES:[/bold]")
        self.console.print("  use case CS4SG1U1")
        self.console.print("  use case ./cases/CS4SG1U1")
        self.console.print("  use problem RISER_ANALYSIS")
        self.console.print("  use rundir /path/to/run")
        self.console.print("  use dir RUN_1              [dim]# Sets CS4SG1U1/RUN_1 if case is CS4SG1U1[/dim]")
        self.console.print("  use dir ./RUN_2            [dim]# Also works with ./ prefix[/dim]")
        self.console.print("  use CS4SG1U1               [dim]# Same as 'use case CS4SG1U1'[/dim]")
        self.console.print()

    def show_unuse_help(self) -> None:
        """Show help for unuse command."""
        self.console.print()
        self.console.print("[bold cyan]Unuse Command - Clear Context[/bold cyan]")
        self.console.print()
        self.console.print("[bold]USAGE:[/bold]")
        self.console.print("  unuse case              Clear case context")
        self.console.print("  unuse problem           Clear problem context")
        self.console.print("  unuse rundir            Clear run directory context")
        self.console.print("  unuse dir               Clear output directory context")
        self.console.print("  unuse all               Clear all contexts")
        self.console.print("  unuse                   Clear all contexts (same as 'unuse all')")
        self.console.print("  unuse --help            Show this help message")
        self.console.print()
        self.console.print("[bold]EXAMPLES:[/bold]")
        self.console.print("  unuse case              [dim]# Clear only case context[/dim]")
        self.console.print("  unuse problem           [dim]# Clear only problem context[/dim]")
        self.console.print("  unuse dir               [dim]# Clear only output directory[/dim]")
        self.console.print("  unuse                   [dim]# Clear everything[/dim]")
        self.console.print()

    def use_case(self, case_input: str) -> None:
        """
        Set current case context.

        Args:
            case_input: Case name or path
        """
        try:
            # Try to resolve the case path
            case_path = Path(case_input)

            # If not absolute, try relative to current directory
            if not case_path.is_absolute():
                case_path = self._current_dir / case_path

            # Resolve to absolute path
            case_path = case_path.resolve()

            # Check if it exists
            if not case_path.exists():
                self.console.print(f"[yellow]Warning:[/yellow] Case directory does not exist: {case_path}")
                self.console.print("[dim]Setting context anyway - you can still use it with commands[/dim]")

            self._current_case = str(case_path)
            self._current_case_name = case_path.name  # Show just the name in prompt
            self.console.print(f"[green]✓[/green] Case set to: [cyan]{self._current_case_name}[/cyan]")
            self.console.print(f"[dim]Path: {case_path}[/dim]")

        except Exception as e:
            self.console.print(f"[red]Error resolving path: {e}[/red]")

    def use_problem(self, problem_name: str) -> None:
        """
        Set current problem context.

        Args:
            problem_name: Problem name or identifier
        """
        self._current_problem = problem_name
        self.console.print(f"[green]✓[/green] Problem set to: [cyan]{problem_name}[/cyan]")

    def use_dir(self, dir_input: str) -> None:
        """
        Set current output directory context (from simflow.config dir field).

        This is for convenience when multiple output directories exist within a case.
        The directory is relative to the case directory, not the current working directory.

        Args:
            dir_input: Output directory name/path (e.g., 'RUN_1', './RUN_2')
        """
        # Check if case context is set
        if not self._current_case:
            self.console.print("[yellow]Warning:[/yellow] No case context set. Use 'use case <case>' first.")
            self.console.print("[dim]Setting output directory anyway - will be relative to case when case is set[/dim]")
            self._current_output_dir = dir_input
            self.console.print(f"[green]✓[/green] Output directory set to: [cyan]{dir_input}[/cyan]")
            return

        try:
            # Output directory is relative to case directory
            case_path = Path(self._current_case)
            dir_path = Path(dir_input)

            # Remove leading ./ if present
            if str(dir_path).startswith('./'):
                dir_path = Path(str(dir_path)[2:])

            # If not absolute, make it relative to case directory
            if not dir_path.is_absolute():
                dir_path = case_path / dir_path

            dir_path = dir_path.resolve()

            # No existence check - this is just for convenience/context
            self._current_output_dir = str(dir_path)
            self.console.print(f"[green]✓[/green] Output directory set to: [cyan]{dir_path.name}[/cyan]")
            self.console.print(f"[dim]Path: {dir_path}[/dim]")

        except Exception as e:
            self.console.print(f"[red]Error resolving path: {e}[/red]")

    def use_rundir(self, rundir_input: str) -> None:
        """
        Set current run directory context.

        Args:
            rundir_input: Run directory path
        """
        try:
            # Resolve the run directory path
            rundir_path = Path(rundir_input)

            if not rundir_path.is_absolute():
                rundir_path = self._current_dir / rundir_path

            rundir_path = rundir_path.resolve()

            # Check if it exists
            if not rundir_path.exists():
                self.console.print(f"[yellow]Warning:[/yellow] Directory does not exist: {rundir_path}")
                self.console.print("[dim]Setting context anyway[/dim]")

            if not rundir_path.is_dir():
                self.console.print(f"[yellow]Warning:[/yellow] Not a directory: {rundir_path}")

            self._current_rundir = str(rundir_path)
            self.console.print(f"[green]✓[/green] Run directory set to: [cyan]{rundir_path.name}[/cyan]")
            self.console.print(f"[dim]Path: {rundir_path}[/dim]")

        except Exception as e:
            self.console.print(f"[red]Error resolving path: {e}[/red]")

    def unuse_case(self) -> None:
        """Clear case context."""
        if self._current_case:
            old_case = self._current_case_name
            self._current_case = None
            self._current_case_name = None
            self.console.print(f"[green]✓[/green] Case context cleared: [dim]{old_case}[/dim]")
        else:
            self.console.print("[dim]No case context is set[/dim]")

    def unuse_problem(self) -> None:
        """Clear problem context."""
        if self._current_problem:
            old_problem = self._current_problem
            self._current_problem = None
            self.console.print(f"[green]✓[/green] Problem context cleared: [dim]{old_problem}[/dim]")
        else:
            self.console.print("[dim]No problem context is set[/dim]")

    def unuse_dir(self) -> None:
        """Clear output directory context."""
        if self._current_output_dir:
            old_dir = Path(self._current_output_dir).name
            self._current_output_dir = None
            self.console.print(f"[green]✓[/green] Output directory context cleared: [dim]{old_dir}[/dim]")
        else:
            self.console.print("[dim]No output directory context is set[/dim]")

    def unuse_rundir(self) -> None:
        """Clear run directory context."""
        if self._current_rundir:
            old_rundir = Path(self._current_rundir).name
            self._current_rundir = None
            self.console.print(f"[green]✓[/green] Run directory context cleared: [dim]{old_rundir}[/dim]")
        else:
            self.console.print("[dim]No run directory context is set[/dim]")

    def unuse_all(self) -> None:
        """Clear all contexts."""
        cleared = []
        if self._current_case:
            cleared.append(f"case: {self._current_case_name}")
            self._current_case = None
            self._current_case_name = None
        if self._current_problem:
            cleared.append(f"problem: {self._current_problem}")
            self._current_problem = None
        if self._current_rundir:
            cleared.append(f"rundir: {Path(self._current_rundir).name}")
            self._current_rundir = None
        if self._current_output_dir:
            cleared.append(f"output dir: {Path(self._current_output_dir).name}")
            self._current_output_dir = None

        if cleared:
            self.console.print(f"[green]✓[/green] All contexts cleared:")
            for item in cleared:
                self.console.print(f"  [dim]{item}[/dim]")
        else:
            self.console.print("[dim]No contexts are currently set[/dim]")

    def cat_file(self, file_paths: List[str]) -> None:
        """
        Display file contents (like Unix cat command).

        Args:
            file_paths: List of file paths to display
        """
        for file_path_str in file_paths:
            try:
                # Resolve path
                file_path = Path(file_path_str)
                if not file_path.is_absolute():
                    file_path = self._current_dir / file_path
                file_path = file_path.resolve()

                # Check if file exists
                if not file_path.exists():
                    self.console.print(f"[red]Error: File not found: {file_path}[/red]")
                    continue

                if not file_path.is_file():
                    self.console.print(f"[red]Error: Not a file: {file_path}[/red]")
                    continue

                # Check file size
                file_size = file_path.stat().st_size
                if file_size > 1024 * 1024:  # 1 MB
                    self.console.print(f"[yellow]Warning: Large file ({self._format_size(file_size)})[/yellow]")
                    self.console.print("[dim]Showing first 1000 lines...[/dim]")
                    show_all = False
                else:
                    show_all = True

                # Show file header if multiple files
                if len(file_paths) > 1:
                    self.console.print()
                    self.console.print(f"[bold cyan]==> {file_path.name} <==[/bold cyan]")

                # Read and display file
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    if show_all:
                        content = f.read()
                        self.console.print(content)
                    else:
                        # Show first 1000 lines
                        for i, line in enumerate(f):
                            if i >= 1000:
                                self.console.print(f"\n[dim]... {file_size - f.tell()} bytes remaining ...[/dim]")
                                break
                            print(line, end='')

            except UnicodeDecodeError:
                self.console.print(f"[red]Error: Cannot display binary file: {file_path}[/red]")
            except PermissionError:
                self.console.print(f"[red]Error: Permission denied: {file_path}[/red]")
            except Exception as e:
                self.console.print(f"[red]Error reading file: {e}[/red]")

    def show_tree(self, depth: int = 2) -> None:
        """
        Show directory tree structure.

        Args:
            depth: Maximum depth to display
        """
        try:
            from rich.tree import Tree

            tree = Tree(
                f"[bold cyan]{self._current_dir.name or '/'}[/bold cyan]",
                guide_style="dim"
            )

            def add_items(parent_tree, parent_path: Path, current_depth: int):
                if current_depth >= depth:
                    return

                try:
                    items = sorted(parent_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                    # Limit items to avoid huge trees
                    items = items[:50]

                    for item in items:
                        if item.name.startswith('.'):
                            continue

                        if item.is_dir():
                            if self._is_case_directory(item):
                                branch = parent_tree.add(f"[bold green]{item.name}/[/bold green] [dim](case)[/dim]")
                            else:
                                branch = parent_tree.add(f"[cyan]{item.name}/[/cyan]")
                            add_items(branch, item, current_depth + 1)
                        else:
                            if item.suffix in ['.othd', '.oisd', '.plt']:
                                parent_tree.add(f"[magenta]{item.name}[/magenta]")
                            else:
                                parent_tree.add(f"{item.name}")

                except PermissionError:
                    parent_tree.add("[red]Permission denied[/red]")

            add_items(tree, self._current_dir, 0)
            self.console.print(tree)

        except Exception as e:
            self.console.print(f"[red]Error showing tree: {e}[/red]")

    def execute_command(self, command_line: str) -> None:
        """
        Execute a FlexFlow command.

        Args:
            command_line: Command line to execute
        """
        try:
            # Parse command line
            args = shlex.split(command_line)
            if not args:
                return

            # Inject current case if context is set and command needs a case
            args = self._inject_case_context(args)

            # Check if it's a registered command
            cmd_name = args[0]
            command = registry.get(cmd_name)

            if command:
                # Parse arguments using the app's parser
                try:
                    # Temporarily set sys.argv so error handler can detect the command
                    import sys
                    old_argv = sys.argv
                    sys.argv = ['flexflow'] + args

                    try:
                        parsed_args = self.app.parser.parse_args(args)
                        command.execute(parsed_args)
                    finally:
                        sys.argv = old_argv

                except SystemExit as e:
                    # Catch sys.exit from argparse/command execution
                    # Don't let it exit the shell
                    if e.code != 0 and e.code is not None:
                        # Suppress the "Command exited" message as errors are already shown
                        pass
                except Exception as e:
                    self.console.print(f"[red]Error: {e}[/red]")
                    # Show traceback for debugging
                    import traceback
                    self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

            else:
                self.console.print(
                    f"[red]Unknown command: {cmd_name}[/red]\n"
                    f"Type [cyan]help[/cyan] to see available commands."
                )

        except Exception as e:
            self.console.print(f"[red]Error executing command: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

    def _inject_case_context(self, args: List[str]) -> List[str]:
        """
        Inject current case context into command arguments if appropriate.

        Args:
            args: Command arguments

        Returns:
            Modified arguments with case injected if needed
        """
        if not self._current_case or len(args) < 2:
            return args

        # Commands that take a case as their second or third argument
        case_commands = {
            'case': {'show': 2, 'run': 2, 'organise': 2},  # case show <case>
            'data': {'show': 2, 'stats': 2},  # data show <case>
            'field': {'info': 2, 'extract': 2},  # field info <case>
            'check': None,  # check <file> - doesn't use case
            'plot': 1,  # plot <case> ...
        }

        cmd = args[0]

        # Check if this command uses cases
        if cmd in case_commands:
            if cmd in ['case', 'data', 'field']:
                # These have subcommands
                if len(args) >= 2:
                    subcmd = args[1]
                    if subcmd in case_commands[cmd]:
                        pos = case_commands[cmd][subcmd]
                        # Check if case position is empty or is a flag
                        if len(args) <= pos or args[pos].startswith('-'):
                            # Insert current case at the right position
                            args.insert(pos, self._current_case)
                            self.console.print(f"[dim]Using case: {self._current_case}[/dim]")
            elif cmd == 'plot':
                # plot command takes case as first argument
                if len(args) == 1 or args[1].startswith('-'):
                    args.insert(1, self._current_case)
                    self.console.print(f"[dim]Using case: {self._current_case}[/dim]")

        return args

    def run(self) -> int:
        """
        Run the interactive shell.

        Returns:
            Exit code (0 for success)
        """
        self.print_welcome()

        while self.running:
            try:
                # Get user input
                user_input = self.session.prompt(
                    self._get_prompt_message(),
                    refresh_interval=0.5
                ).strip()

                # Skip empty input
                if not user_input:
                    continue

                # Handle shell commands
                if self.handle_shell_command(user_input):
                    continue

                # Execute FlexFlow command
                self.execute_command(user_input)

            except KeyboardInterrupt:
                # Ctrl+C pressed - don't exit, just show new prompt
                self.console.print()
                continue

            except EOFError:
                # Ctrl+D pressed - exit gracefully
                self.running = False
                break

            except Exception as e:
                self.console.print(f"[red]Unexpected error: {e}[/red]")
                import traceback
                traceback.print_exc()

        self.print_goodbye()
        return 0
