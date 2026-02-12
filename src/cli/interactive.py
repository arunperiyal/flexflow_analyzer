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

    # ---------------------------------------------------------------------------
    # Static completion tables
    # ---------------------------------------------------------------------------

    _SUBCOMMANDS: Dict[str, List[str]] = {
        'case':     ['show', 'create', 'run', 'organise', 'check', 'status'],
        'data':     ['show', 'stats'],
        'field':    ['info', 'extract'],
        'run':      ['check', 'pre', 'main', 'post', 'sq', 'sb', 'sc'],
        'template': ['plot', 'case', 'script'],
        'check':    [],
        'plot':     [],
        'compare':  [],
        'docs':     [],
    }

    _COMMON_FLAGS: Dict[str, str] = {
        '--help':     'Show help message',
        '-h':         'Show help message',
        '--verbose':  'Enable verbose output',
        '-v':         'Enable verbose output',
        '--examples': 'Show usage examples',
    }

    # Flags per (command, subcommand).  Use (command, None) for the top-level
    # command (before a subcommand is typed) and (command, subcmd) for the
    # flags that appear after a specific subcommand.
    _SUBCMD_FLAGS: Dict[tuple, Dict[str, str]] = {
        # ── case ────────────────────────────────────────────────────────────
        ('case', None):      {**_COMMON_FLAGS},
        ('case', 'show'):    {**_COMMON_FLAGS},
        ('case', 'create'):  {
            **_COMMON_FLAGS,
            '--ref-case':     'Path to reference case directory',
            '--problem-name': 'Problem name to set in simflow.config',
            '--np':           'Number of processors (default: 36)',
            '--freq':         'Output frequency (default: 50)',
            '--from-config':  'Create from YAML config file',
            '--force':        'Force overwrite if case already exists',
            '--list-vars':    'List available variables in reference case',
            '--dry-run':      'Show what would be created',
        },
        ('case', 'run'):     {
            **_COMMON_FLAGS,
            '--no-monitor': 'Submit jobs without monitoring',
            '--clean':      'Clean start (remove existing OTHD files)',
            '--from-step':  'Restart from specific timestep',
            '--dry-run':    'Show what would be done',
        },
        ('case', 'organise'): {
            **_COMMON_FLAGS,
            '--archive':      'Move .othd/.oisd/.rcv from run dir to archive dirs',
            '--clean-plt':    'Delete PLT files from run dir where binary/ has a newer copy',
            '--organise':     'Deduplicate and clean redundant OTHD/OISD files',
            '--clean-output': 'Remove intermediate .out/.rst/.plt files',
            '--keep-every':   'Keep every Nth output (default: 10)',
            '--log':          'Create log file of all deletions',
            '--no-confirm':   'Skip confirmation prompts',
        },
        ('case', 'check'):   {
            **_COMMON_FLAGS,
            '--run':     'Check .othd/.oisd in the active run directory',
            '--archive': 'Check all archived files in othd_files/oisd_files',
            '--config':  'Validate simflow.config consistency',
            '--plt':     'Check PLT files against expected set (outFreq/maxTimeSteps)',
            '--all':     'Run all checks (--run + --archive + --config + --plt)',
        },
        ('case', 'status'):  {**_COMMON_FLAGS},

        # ── data ────────────────────────────────────────────────────────────
        ('data', None):      {**_COMMON_FLAGS},
        ('data', 'show'):    {
            **_COMMON_FLAGS,
            '--node':       'Node ID',
            '--start-time': 'Start time filter',
            '--end-time':   'End time filter',
            '--variable':   'Variable(s) to show',
        },
        ('data', 'stats'):   {
            **_COMMON_FLAGS,
            '--node': 'Node ID',
        },

        # ── field ───────────────────────────────────────────────────────────
        ('field', None):     {**_COMMON_FLAGS},
        ('field', 'info'):   {
            **_COMMON_FLAGS,
            '--basic':       'Show basic info only',
            '--variables':   'List variables',
            '--zones':       'List zones',
            '--checks':      'Run consistency checks',
            '--stats':       'Show statistics',
            '--detailed':    'Detailed output',
            '--sample-file': 'Sample a specific timestep',
        },
        ('field', 'extract'): {
            **_COMMON_FLAGS,
            '--variables':   'Variables to extract',
            '--zone':        'Zone name filter',
            '--timestep':    'Specific timestep',
            '--output-file': 'Output file path',
            '--xmin': 'X minimum bound',
            '--xmax': 'X maximum bound',
            '--ymin': 'Y minimum bound',
            '--ymax': 'Y maximum bound',
            '--zmin': 'Z minimum bound',
            '--zmax': 'Z maximum bound',
        },

        # ── run ─────────────────────────────────────────────────────────────
        ('run', None):       {**_COMMON_FLAGS},
        ('run', 'check'):    {**_COMMON_FLAGS},
        ('run', 'pre'):      {
            **_COMMON_FLAGS,
            '--gmsh':    'Override gmsh executable path (sbatch --export, script unchanged)',
            '--dry-run': 'Preview without submitting',
            '--show':    'Display script contents',
        },
        ('run', 'main'):     {
            **_COMMON_FLAGS,
            '--dry-run':    'Preview without submitting',
            '--show':       'Display script contents',
            '--restart':    'Restart from specific timestep',
            '--dependency': 'Job dependency (job ID)',
            '--partition':  'Override partition (sbatch CLI, does not edit script)',
        },
        ('run', 'post'):     {
            **_COMMON_FLAGS,
            '--dry-run':      'Preview without submitting',
            '--show':         'Display script contents',
            '--upto':         'Process up to timestep',
            '--last':         'Process last N timesteps',
            '--freq':         'Output frequency',
            '--cleanup':      'Clean files before processing',
            '--no-cleanup':   'Skip cleanup',
            '--cleanup-only': 'Only run cleanup',
            '--dependency':   'Job dependency (job ID)',
        },
        ('run', 'sq'):       {
            '--all':   'Show all users jobs',
            '--watch': 'Live queue monitoring (refresh every 10s)',
            '--help':  'Show help message',
            '-h':      'Show help message',
        },
        ('run', 'sb'):       {
            '--help':  'Show help message',
            '-h':      'Show help message',
        },
        ('run', 'sc'):       {
            '--help':  'Show help message',
            '-h':      'Show help message',
        },

        # ── template ────────────────────────────────────────────────────────
        ('template', None):    {**_COMMON_FLAGS},
        ('template', 'plot'):  {
            **_COMMON_FLAGS,
            '--force': 'Overwrite existing file',
        },
        ('template', 'case'):  {
            **_COMMON_FLAGS,
            '--force': 'Overwrite existing file',
        },
        ('template', 'script'): {
            **_COMMON_FLAGS,
            '--force':        'Overwrite existing files',
            '--simflow-home': 'Set SIMFLOW_HOME in generated simflow_env.sh',
            '--gmsh-path':    'Set GMSH executable path in generated simflow_env.sh',
            '--partition':    'Override partition in generated mainFlex.sh',
        },

        # ── top-level commands with no subcommands ─────────────────────────
        ('plot', None):    {
            **_COMMON_FLAGS,
            '--node':      'Node ID to plot',
            '--component': 'Component (x, y, z)',
            '--output':    'Output file path',
        },
        ('compare', None): {**_COMMON_FLAGS},
        ('check', None):   {**_COMMON_FLAGS},
        ('docs', None):    {**_COMMON_FLAGS},
    }

    # Fixed argument values for specific positions
    # key: (command, subcommand, position_after_subcommand)
    # position 0 = first token after the subcommand
    _POSITIONAL_CHOICES: Dict[tuple, List[tuple]] = {
        ('template', 'plot',   0): [('simple', 'Simple time-series'), ('multi', 'Multi-node plot')],
        ('template', 'case',   0): [('basic', 'Basic case config'), ('full', 'Full case config')],
        ('template', 'script', 0): [
            ('pre',  'Pre-processing script'),
            ('main', 'Main simulation script'),
            ('post', 'Post-processing script'),
            ('env',  'Environment config (simflow_env.sh)'),
            ('all',  'All scripts'),
        ],
    }

    # Shell built-in commands and their descriptions
    _SHELL_COMMANDS = [
        ('exit',    'Exit FlexFlow'),
        ('quit',    'Exit FlexFlow'),
        ('help',    'Show help message'),
        ('?',       'Show help message'),
        ('clear',   'Clear screen'),
        ('history', 'Show command history'),
        ('pwd',     'Show current directory and contexts'),
        ('ls',      'List files'),
        ('ll',      'List files (long format)'),
        ('la',      'List all files (including hidden)'),
        ('cd',      'Change directory'),
        ('cat',     'View file contents'),
        ('head',    'Show first lines of file'),
        ('tail',    'Show last lines of file'),
        ('grep',    'Search file contents'),
        ('find',    'Find case directories'),
        ('tree',    'Show directory tree'),
        ('rm',      'Remove files or directories'),
        ('use',     'Set context (case/problem/rundir)'),
        ('unuse',   'Clear context'),
    ]

    # ---------------------------------------------------------------------------

    def __init__(self, shell=None):
        self.shell = shell
        self.commands: Dict[str, str] = {}   # name -> description
        self._build_command_tree()

    def _build_command_tree(self) -> None:
        """Build command description map from registry."""
        for cmd in registry.all():
            self.commands[cmd.name] = cmd.description

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    def _flags_for(self, cmd: str, subcmd: Optional[str]) -> Dict[str, str]:
        """Return the flag dict for (cmd, subcmd), falling back to (cmd, None)."""
        key = (cmd, subcmd)
        if key in self._SUBCMD_FLAGS:
            return self._SUBCMD_FLAGS[key]
        return self._SUBCMD_FLAGS.get((cmd, None), self._COMMON_FLAGS)

    def _yield_flags(self, flags: Dict[str, str], word: str):
        for flag, desc in flags.items():
            if flag.startswith(word):
                yield Completion(flag, start_position=-len(word), display_meta=desc)

    def _yield_choices(self, choices: List[tuple], word: str):
        for value, desc in choices:
            if value.startswith(word):
                yield Completion(value, start_position=-len(word), display_meta=desc)

    def _get_file_completions(self, word: str, directory: Path) -> List[tuple]:
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

    # ---------------------------------------------------------------------------
    # Main entry point
    # ---------------------------------------------------------------------------

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        words = text.split()
        ends_with_space = text.endswith(' ')

        # ── First word: complete command names ──────────────────────────────
        if len(words) == 0 or (len(words) == 1 and not ends_with_space):
            word = words[0] if words else ''
            for cmd_name, desc in self.commands.items():
                if cmd_name.startswith(word):
                    yield Completion(cmd_name, start_position=-len(word), display_meta=desc)
            for shell_cmd, desc in self._SHELL_COMMANDS:
                if shell_cmd.startswith(word):
                    yield Completion(shell_cmd, start_position=-len(word), display_meta=desc)
            return

        cmd_name = words[0]

        # ── use / unuse ──────────────────────────────────────────────────────
        if cmd_name == 'use':
            yield from self._complete_use_command(words, ends_with_space)
            return
        if cmd_name == 'unuse':
            yield from self._complete_unuse_command(words, ends_with_space)
            return

        # ── file-browsing commands ───────────────────────────────────────────
        if cmd_name in ('cd', 'cat', 'ls', 'll', 'la', 'grep', 'head', 'tail'):
            yield from self._complete_path(words, ends_with_space)
            return

        # ── FlexFlow commands ────────────────────────────────────────────────
        if cmd_name not in self.commands:
            return

        subcommands = self._SUBCOMMANDS.get(cmd_name, [])

        # Position within the command line
        # words[0] = cmd, words[1] = subcmd (maybe), words[2..] = args/flags
        has_subcmds = bool(subcommands)

        # Word currently being typed (empty string when cursor follows a space)
        current_word = '' if ends_with_space else words[-1]

        if has_subcmds:
            if len(words) == 1 or (len(words) == 2 and not ends_with_space):
                # Completing the subcommand name
                word = current_word
                for subcmd in subcommands:
                    if subcmd.startswith(word):
                        yield Completion(subcmd, start_position=-len(word), display_meta='Subcommand')
                # Also show top-level flags if user started typing '-'
                if word.startswith('-'):
                    yield from self._yield_flags(self._flags_for(cmd_name, None), word)
                return

            # Subcommand is known
            subcmd_name = words[1]

            # Position of the token after the subcommand (0-based)
            # words: [cmd, subcmd, arg0, arg1, ...]
            # when ends_with_space, the next token position = len(words) - 2
            # when not ends_with_space, current token is words[-1] at position len(words) - 3
            if ends_with_space:
                pos_after_subcmd = len(words) - 2   # how many args already typed
            else:
                pos_after_subcmd = len(words) - 3   # current word is being typed

            # Check if there are fixed positional choices for this position
            positional_key = (cmd_name, subcmd_name, max(pos_after_subcmd, 0))
            if not current_word.startswith('-') and positional_key in self._POSITIONAL_CHOICES:
                yield from self._yield_choices(self._POSITIONAL_CHOICES[positional_key], current_word)
                return

            # Otherwise complete flags
            if current_word.startswith('-') or ends_with_space:
                yield from self._yield_flags(self._flags_for(cmd_name, subcmd_name), current_word)

        else:
            # No subcommands — complete flags directly
            if current_word.startswith('-') or ends_with_space:
                yield from self._yield_flags(self._flags_for(cmd_name, None), current_word)

    # ---------------------------------------------------------------------------
    # Specialised completers
    # ---------------------------------------------------------------------------

    def _complete_use_command(self, words: List[str], ends_with_space: bool):
        """
        use case <path>
        use problem <name>
        use rundir <path>
        use <shortcut>
        """
        subcommands = [
            ('case',    'Set current case'),
            ('problem', 'Override problem name'),
            ('rundir',  'Override run directory'),
            ('--help',  'Show help'),
            ('-h',      'Show help'),
        ]

        if len(words) == 1 or (len(words) == 2 and not ends_with_space):
            word = '' if ends_with_space else (words[1] if len(words) > 1 else '')
            for val, desc in subcommands:
                if val.startswith(word):
                    yield Completion(val, start_position=-len(word), display_meta=desc)
        elif len(words) >= 2 and words[1] in ('case', 'rundir'):
            # Complete path argument
            yield from self._complete_path(words[2:], ends_with_space)

    def _complete_unuse_command(self, words: List[str], ends_with_space: bool):
        """Complete unuse subcommand names."""
        if len(words) == 1 or (len(words) == 2 and not ends_with_space):
            word = '' if ends_with_space else (words[1] if len(words) > 1 else '')
            subcommands = [
                ('case',    'Clear case context'),
                ('problem', 'Clear problem context'),
                ('rundir',  'Clear rundir context'),
                ('--help',  'Show help'),
                ('-h',      'Show help'),
            ]
            for val, desc in subcommands:
                if val.startswith(word):
                    yield Completion(val, start_position=-len(word), display_meta=desc)

    def _complete_path(self, words: List[str], ends_with_space: bool):
        """Complete file/directory paths."""
        if self.shell is None:
            return

        if not words or ends_with_space:
            word = ''
            base_dir = self.shell._current_dir
        else:
            word = words[-1]
            if '/' in word:
                parts = word.rsplit('/', 1)
                base_dir = self.shell._current_dir / parts[0]
                word = parts[1]
            else:
                base_dir = self.shell._current_dir

        for name, is_dir in self._get_file_completions(word, base_dir):
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

    _instance: Optional['InteractiveShell'] = None  # Singleton instance for context access

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
        self._current_node: Optional[int] = None  # Node ID for data/field commands
        self._current_t1: Optional[float] = None  # Start time for data/field/plot commands
        self._current_t2: Optional[float] = None  # End time for data/field/plot commands
        self._current_dir: Path = Path.cwd()  # Track current working directory

        # Store app instance for command execution
        if app is None:
            from src.cli.app import FlexFlowApp
            self.app = FlexFlowApp()
        else:
            self.app = app

        # Set singleton instance for context access by commands
        InteractiveShell._instance = self

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
        if self._current_node is not None:
            contexts.append(f'<node>n:{self._current_node}</node>')
        if self._current_t1 is not None:
            contexts.append(f'<t1>t1:{self._current_t1}</t1>')
        if self._current_t2 is not None:
            contexts.append(f'<t2>t2:{self._current_t2}</t2>')

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
                "  • Use [cyan]↑/↓[/cyan] for command history\n\n"
                "[yellow]Set Context:[/yellow]\n"
                "  [cyan]use case:Case015 node:24 t1:50.0 t2:100.0[/cyan]\n"
                "  Set multiple contexts at once with [bold]context:value[/bold] syntax\n\n"
                "[dim]Type [cyan]exit[/cyan] or [cyan]quit[/cyan] to exit[/dim]",
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

            # Check for help flag
            if parts[1] in ['--help', '-h', 'help']:
                self.show_use_help()
                return True

            # Use colon syntax: use case:Case015 OR use case:Case015 node:24
            for part in parts[1:]:
                if ':' not in part:
                    self.console.print(f"[yellow]Invalid format:[/yellow] {part}")
                    self.console.print("[dim]Use: context:value (e.g., case:Case015)[/dim]")
                    continue

                context, value = part.split(':', 1)
                context = context.strip().lower()
                value = value.strip()

                if context == 'case':
                    self.use_case(value)
                elif context == 'problem':
                    self.use_problem(value)
                elif context == 'rundir':
                    self.use_rundir(value)
                elif context == 'dir':
                    self.use_dir(value)
                elif context == 'node':
                    self.use_node(value)
                elif context == 't1':
                    self.use_t1(value)
                elif context == 't2':
                    self.use_t2(value)
                else:
                    self.console.print(f"[yellow]Unknown context:[/yellow] {context}")
                    self.console.print("[dim]Valid contexts: case, problem, rundir, dir, node, t1, t2[/dim]")
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
                elif subcommand == 'node':
                    self.unuse_node()
                elif subcommand == 't1':
                    self.unuse_t1()
                elif subcommand == 't2':
                    self.unuse_t2()
                elif subcommand == 'all':
                    self.unuse_all()
                else:
                    self.console.print(f"[yellow]Unknown subcommand:[/yellow] {subcommand}")
                    self.console.print("[dim]Use: unuse [case|problem|rundir|dir|node|t1|t2|all][/dim]")
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
            if self._current_node is not None:
                self.console.print(f"Node context: [cyan]{self._current_node}[/cyan]")
            if self._current_t1 is not None:
                self.console.print(f"Start time (t1): [cyan]{self._current_t1}[/cyan]")
            if self._current_t2 is not None:
                self.console.print(f"End time (t2): [cyan]{self._current_t2}[/cyan]")
            if not any([self._current_case, self._current_problem, self._current_rundir, self._current_output_dir,
                       self._current_node is not None, self._current_t1 is not None, self._current_t2 is not None]):
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

        # Search file contents
        if cmd == 'grep':
            if len(parts) > 1:
                self.grep_files(parts[1:])
            else:
                self.console.print("[yellow]Usage:[/yellow] grep <pattern> [files...] [options]")
                self.console.print("[dim]Options:[/dim]")
                self.console.print("  -i, --ignore-case    Case-insensitive search")
                self.console.print("  -n, --line-number    Show line numbers")
                self.console.print("  -r, --recursive      Search recursively in directories")
                self.console.print("  -l, --files-only     Show only filenames with matches")
                self.console.print("[dim]Examples:[/dim]")
                self.console.print("  grep 'error' log.txt")
                self.console.print("  grep -i 'warning' *.log")
                self.console.print("  grep -rn 'TODO' src/")
            return True

        # Show first N lines of file
        if cmd == 'head':
            if len(parts) > 1:
                self.head_file(parts[1:])
            else:
                self.console.print("[yellow]Usage:[/yellow] head [options] <file>")
                self.console.print("[dim]Options:[/dim]")
                self.console.print("  -n <num>    Number of lines to show (default: 10)")
                self.console.print("[dim]Examples:[/dim]")
                self.console.print("  head file.txt")
                self.console.print("  head -n 20 file.log")
            return True

        # Show last N lines of file
        if cmd == 'tail':
            if len(parts) > 1:
                self.tail_file(parts[1:])
            else:
                self.console.print("[yellow]Usage:[/yellow] tail [options] <file>")
                self.console.print("[dim]Options:[/dim]")
                self.console.print("  -n <num>    Number of lines to show (default: 10)")
                self.console.print("[dim]Examples:[/dim]")
                self.console.print("  tail file.txt")
                self.console.print("  tail -n 50 file.log")
            return True

        # Remove files or directories
        if cmd == 'rm':
            if len(parts) > 1:
                self.remove_files(parts[1:])
            else:
                self.console.print("[yellow]Usage:[/yellow] rm [-r] [-f] <path> [paths...]")
                self.console.print("[dim]Options:[/dim]")
                self.console.print("  -r, --recursive    Remove directories recursively")
                self.console.print("  -f, --force        Skip confirmation prompts")
                self.console.print("[dim]Examples:[/dim]")
                self.console.print("  rm old_output.othd")
                self.console.print("  rm -r SIMFLOW_DATA/")
                self.console.print("  rm -rf tmp_dir/")
                self.console.print("  rm file1.plt file2.plt file3.plt")
            return True

        return False

    def show_help(self) -> None:
        """Show help information."""
        table = Table(title="Main Commands", box=box.ROUNDED, show_header=True)
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")

        # Add FlexFlow commands from registry
        for cmd in registry.all():
            table.add_row(cmd.name, cmd.description)

        # Add use and unuse commands with prominent syntax hint
        table.add_row("use", "Set context with [bold]context:value[/bold] syntax")
        table.add_row("unuse", "Clear context")

        self.console.print()
        self.console.print(table)
        self.console.print()

        # Add prominent context syntax example
        self.console.print("[yellow]Context Syntax Example:[/yellow]")
        self.console.print("  [cyan]use case:Case015 node:24 t1:50.0 t2:100.0[/cyan]")
        self.console.print("  [dim]Set multiple contexts at once[/dim]")
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
            ("head [-n num] <file>", "Show first lines of file (default: 10)"),
            ("tail [-n num] <file>", "Show last lines of file (default: 10)"),
            ("grep <pattern> [files]", "Search file contents"),
            ("find [pattern]", "Find case directories"),
            ("tree [depth]", "Show directory tree (default depth: 2)"),
            ("rm [-r] [-f] <path>", "Remove files or directories"),
        ]

        for cmd, desc in browse_commands:
            browse_table.add_row(cmd, desc)

        self.console.print(browse_table)
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
        import glob as glob_module

        try:
            # Parse options
            show_all = '-a' in args or '--all' in args
            long_format = '-l' in args or '--long' in args
            paths = [arg for arg in args if not arg.startswith('-')]

            if not paths:
                paths = ['.']

            # Expand glob patterns (e.g. *.sh, *.geo)
            expanded_paths = []
            for path_str in paths:
                if any(c in path_str for c in ('*', '?', '[')):
                    # Resolve glob relative to current directory
                    base = self._current_dir / path_str
                    matches = glob_module.glob(str(base))
                    if matches:
                        expanded_paths.extend(sorted(matches))
                    else:
                        self.console.print(f"[yellow]No matches: {path_str}[/yellow]")
                else:
                    expanded_paths.append(path_str)

            # Collect all file matches to display together
            matched_files = []

            for path_str in expanded_paths:
                target = Path(path_str)
                if not target.is_absolute():
                    target = self._current_dir / target

                if not target.exists():
                    self.console.print(f"[red]Error: Path not found: {target}[/red]")
                    continue

                if target.is_dir():
                    # Flush any pending file matches first
                    if matched_files:
                        self._list_matched_files(matched_files, long_format)
                        matched_files = []
                    self._list_dir_contents(target, show_all, long_format)
                else:
                    matched_files.append(target)

            # Display any remaining file matches
            if matched_files:
                self._list_matched_files(matched_files, long_format)

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

    def _list_matched_files(self, files: List[Path], long_format: bool) -> None:
        """
        Display a list of matched files (from glob expansion) using compact formatting.

        Args:
            files: List of file paths to display
            long_format: Show detailed information
        """
        import datetime
        from rich.columns import Columns

        if long_format:
            table = Table(box=box.SIMPLE, show_header=True, padding=(0, 2))
            table.add_column("Size", justify="right", style="yellow", width=10)
            table.add_column("Modified", style="blue", width=16)
            table.add_column("Name", style="white")

            for f in files:
                stat = f.stat()
                size_str = self._format_size(stat.st_size)
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
                mtime_str = mtime.strftime("%Y-%m-%d %H:%M")
                name = f.name
                if f.suffix in ['.othd', '.oisd', '.plt']:
                    name = f"[magenta]{name}[/magenta]"
                table.add_row(size_str, mtime_str, name)

            self.console.print(table)
        else:
            items_formatted = []
            for f in files:
                if f.suffix in ['.othd', '.oisd', '.plt']:
                    items_formatted.append(f"[magenta]{f.name}[/magenta]")
                else:
                    items_formatted.append(f.name)
            self.console.print(Columns(items_formatted, equal=True, expand=False))

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
        self.console.print("  use context:value [context:value ...]")
        self.console.print()
        self.console.print("[bold]CONTEXTS:[/bold]")
        self.console.print("  case       Case directory path")
        self.console.print("  problem    Problem name")
        self.console.print("  rundir     Run directory path")
        self.console.print("  dir        Output directory (relative to case)")
        self.console.print("  node       Node ID for data/field commands")
        self.console.print("  t1         Start time for data/field/plot commands")
        self.console.print("  t2         End time for data/field/plot commands")
        self.console.print()
        self.console.print("[bold]EXAMPLES:[/bold]")
        self.console.print("  [dim]# Single context[/dim]")
        self.console.print("  use case:Case015")
        self.console.print("  use node:24")
        self.console.print("  use t1:50.0")
        self.console.print()
        self.console.print("  [dim]# Multiple contexts[/dim]")
        self.console.print("  use case:Case015 problem:rigid node:0")
        self.console.print("  use case:Case015 node:24 t1:50.0 t2:100.0")
        self.console.print("  use node:0 t1:150.0 t2:200.0")
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
        self.console.print("  unuse node              Clear node context")
        self.console.print("  unuse t1                Clear start time context")
        self.console.print("  unuse t2                Clear end time context")
        self.console.print("  unuse all               Clear all contexts")
        self.console.print("  unuse                   Clear all contexts (same as 'unuse all')")
        self.console.print("  unuse --help            Show this help message")
        self.console.print()
        self.console.print("[bold]EXAMPLES:[/bold]")
        self.console.print("  unuse case              [dim]# Clear only case context[/dim]")
        self.console.print("  unuse node              [dim]# Clear only node context[/dim]")
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
        Set current run directory context (output directory within case).

        This is relative to the case directory, not the current working directory.

        Args:
            rundir_input: Run directory path (relative to case directory)
        """
        # Check if case context is set
        if not self._current_case:
            self.console.print("[yellow]Warning:[/yellow] No case context set. Use 'use case <case>' first.")
            self.console.print("[dim]Setting run directory anyway - will be relative to case when case is set[/dim]")
            self._current_rundir = rundir_input
            self.console.print(f"[green]✓[/green] Run directory set to: [cyan]{rundir_input}[/cyan]")
            return

        try:
            # Run directory is relative to case directory
            case_path = Path(self._current_case)
            rundir_path = Path(rundir_input)

            # Remove leading ./ if present
            if str(rundir_path).startswith('./'):
                rundir_path = Path(str(rundir_path)[2:])

            # If not absolute, make it relative to case directory
            if not rundir_path.is_absolute():
                rundir_path = case_path / rundir_path

            rundir_path = rundir_path.resolve()

            # No existence check - this is just for convenience/context
            self._current_rundir = str(rundir_path)
            self.console.print(f"[green]✓[/green] Run directory set to: [cyan]{rundir_path.name}[/cyan]")
            self.console.print(f"[dim]Path: {rundir_path}[/dim]")

        except Exception as e:
            self.console.print(f"[red]Error resolving path: {e}[/red]")

    def use_node(self, node_input: str) -> None:
        """
        Set current node context for data/field commands.

        Args:
            node_input: Node ID (integer)
        """
        try:
            node_id = int(node_input)
            if node_id < 0:
                self.console.print("[red]Error:[/red] Node ID must be non-negative")
                return
            self._current_node = node_id
            self.console.print(f"[green]✓[/green] Node set to: [cyan]{node_id}[/cyan]")
        except ValueError:
            self.console.print(f"[red]Error:[/red] Invalid node ID: {node_input}")
            self.console.print("[dim]Node ID must be an integer[/dim]")

    def use_t1(self, time_input: str) -> None:
        """
        Set start time context for data/field/plot commands.

        Args:
            time_input: Start time (float)
        """
        try:
            start_time = float(time_input)
            self._current_t1 = start_time
            self.console.print(f"[green]✓[/green] Start time (t1) set to: [cyan]{start_time}[/cyan]")
        except ValueError:
            self.console.print(f"[red]Error:[/red] Invalid time value: {time_input}")
            self.console.print("[dim]Time must be a number[/dim]")

    def use_t2(self, time_input: str) -> None:
        """
        Set end time context for data/field/plot commands.

        Args:
            time_input: End time (float)
        """
        try:
            end_time = float(time_input)
            self._current_t2 = end_time
            self.console.print(f"[green]✓[/green] End time (t2) set to: [cyan]{end_time}[/cyan]")
        except ValueError:
            self.console.print(f"[red]Error:[/red] Invalid time value: {time_input}")
            self.console.print("[dim]Time must be a number[/dim]")

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

    def unuse_node(self) -> None:
        """Clear node context."""
        if self._current_node is not None:
            old_node = self._current_node
            self._current_node = None
            self.console.print(f"[green]✓[/green] Node context cleared: [dim]{old_node}[/dim]")
        else:
            self.console.print("[dim]No node context is set[/dim]")

    def unuse_t1(self) -> None:
        """Clear start time context."""
        if self._current_t1 is not None:
            old_t1 = self._current_t1
            self._current_t1 = None
            self.console.print(f"[green]✓[/green] Start time (t1) context cleared: [dim]{old_t1}[/dim]")
        else:
            self.console.print("[dim]No start time (t1) context is set[/dim]")

    def unuse_t2(self) -> None:
        """Clear end time context."""
        if self._current_t2 is not None:
            old_t2 = self._current_t2
            self._current_t2 = None
            self.console.print(f"[green]✓[/green] End time (t2) context cleared: [dim]{old_t2}[/dim]")
        else:
            self.console.print("[dim]No end time (t2) context is set[/dim]")

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
        if self._current_node is not None:
            cleared.append(f"node: {self._current_node}")
            self._current_node = None
        if self._current_t1 is not None:
            cleared.append(f"t1: {self._current_t1}")
            self._current_t1 = None
        if self._current_t2 is not None:
            cleared.append(f"t2: {self._current_t2}")
            self._current_t2 = None

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

    def head_file(self, args: List[str]) -> None:
        """
        Display first N lines of a file (like Unix head command).

        Args:
            args: List containing optional -n flag and file path
        """
        # Parse arguments
        num_lines = 10  # default
        file_path_str = None

        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                try:
                    num_lines = int(args[i + 1])
                    i += 2
                except ValueError:
                    self.console.print(f"[red]Error: Invalid number: {args[i + 1]}[/red]")
                    return
            else:
                file_path_str = args[i]
                i += 1

        if not file_path_str:
            self.console.print("[yellow]Error: No file specified[/yellow]")
            return

        try:
            # Resolve path
            file_path = Path(file_path_str)
            if not file_path.is_absolute():
                file_path = self._current_dir / file_path
            file_path = file_path.resolve()

            # Check if file exists
            if not file_path.exists():
                self.console.print(f"[red]Error: File not found: {file_path}[/red]")
                return

            if not file_path.is_file():
                self.console.print(f"[red]Error: Not a file: {file_path}[/red]")
                return

            # Read and display first N lines
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                for i, line in enumerate(f):
                    if i >= num_lines:
                        break
                    print(line, end='')

        except UnicodeDecodeError:
            self.console.print(f"[red]Error: Cannot display binary file: {file_path}[/red]")
        except PermissionError:
            self.console.print(f"[red]Error: Permission denied: {file_path}[/red]")
        except Exception as e:
            self.console.print(f"[red]Error reading file: {e}[/red]")

    def tail_file(self, args: List[str]) -> None:
        """
        Display last N lines of a file (like Unix tail command).

        Args:
            args: List containing optional -n flag and file path
        """
        # Parse arguments
        num_lines = 10  # default
        file_path_str = None

        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                try:
                    num_lines = int(args[i + 1])
                    i += 2
                except ValueError:
                    self.console.print(f"[red]Error: Invalid number: {args[i + 1]}[/red]")
                    return
            else:
                file_path_str = args[i]
                i += 1

        if not file_path_str:
            self.console.print("[yellow]Error: No file specified[/yellow]")
            return

        try:
            # Resolve path
            file_path = Path(file_path_str)
            if not file_path.is_absolute():
                file_path = self._current_dir / file_path
            file_path = file_path.resolve()

            # Check if file exists
            if not file_path.exists():
                self.console.print(f"[red]Error: File not found: {file_path}[/red]")
                return

            if not file_path.is_file():
                self.console.print(f"[red]Error: Not a file: {file_path}[/red]")
                return

            # Read all lines and display last N
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                for line in lines[-num_lines:]:
                    print(line, end='')

        except UnicodeDecodeError:
            self.console.print(f"[red]Error: Cannot display binary file: {file_path}[/red]")
        except PermissionError:
            self.console.print(f"[red]Error: Permission denied: {file_path}[/red]")
        except Exception as e:
            self.console.print(f"[red]Error reading file: {e}[/red]")

    def remove_files(self, args: List[str]) -> None:
        """
        Remove files or directories (like Unix rm command).

        Args:
            args: List containing optional flags and one or more paths.
                  Flags: -r/--recursive, -f/--force, or combined -rf/-fr.
        """
        import shutil

        recursive = False
        force = False
        raw_paths: List[str] = []

        for arg in args:
            # Combined short flags like -rf or -fr
            if arg.startswith('-') and not arg.startswith('--') and len(arg) > 2:
                flags = arg[1:]
                if all(c in 'rf' for c in flags):
                    recursive = 'r' in flags
                    force = 'f' in flags
                    continue
            if arg in ('-r', '--recursive'):
                recursive = True
            elif arg in ('-f', '--force'):
                force = True
            else:
                raw_paths.append(arg)

        if not raw_paths:
            self.console.print("[yellow]Error: no paths specified[/yellow]")
            return

        removed: List[str] = []
        errors:  List[str] = []

        for raw in raw_paths:
            target = Path(raw)
            if not target.is_absolute():
                target = self._current_dir / target
            target = target.resolve()

            if not target.exists():
                errors.append(f"not found: {raw}")
                continue

            is_dir = target.is_dir()

            if is_dir and not recursive:
                errors.append(f"is a directory (use -r to remove): {raw}")
                continue

            # Confirm unless -f
            if not force:
                kind = "directory and all its contents" if is_dir else "file"
                self.console.print(
                    f"  Remove {kind} [cyan]{target.name}[/cyan]? [dim](y/N)[/dim] ",
                    end='',
                )
                try:
                    answer = input().strip().lower()
                except (EOFError, KeyboardInterrupt):
                    answer = ''
                if answer != 'y':
                    self.console.print("  [dim]skipped[/dim]")
                    continue

            try:
                if is_dir:
                    shutil.rmtree(target)
                else:
                    target.unlink()
                removed.append(str(raw))
            except PermissionError:
                errors.append(f"permission denied: {raw}")
            except Exception as e:
                errors.append(f"{raw}: {e}")

        for r in removed:
            self.console.print(f"  [green]removed[/green]  {r}")
        for e in errors:
            self.console.print(f"  [red]error[/red]    {e}")

    def grep_files(self, args: List[str]) -> None:
        """
        Search file contents (like Unix grep command).

        Args:
            args: List containing pattern and file paths, with optional flags
        """
        import re
        import glob

        # Parse arguments
        pattern = None
        file_paths = []
        ignore_case = False
        show_line_numbers = True  # Default to showing line numbers
        recursive = False
        files_only = False

        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith('-') and not arg.startswith('--') and len(arg) > 2:
                # Handle combined short flags like -irn
                for char in arg[1:]:
                    if char == 'i':
                        ignore_case = True
                    elif char == 'n':
                        show_line_numbers = True
                    elif char == 'r':
                        recursive = True
                    elif char == 'l':
                        files_only = True
            elif arg in ['-i', '--ignore-case']:
                ignore_case = True
            elif arg in ['-n', '--line-number']:
                show_line_numbers = True
            elif arg in ['-r', '--recursive']:
                recursive = True
            elif arg in ['-l', '--files-only']:
                files_only = True
            elif pattern is None:
                pattern = arg
            else:
                file_paths.append(arg)
            i += 1

        if pattern is None:
            self.console.print("[yellow]Error: No pattern specified[/yellow]")
            return

        # If no files specified, search in current directory
        if not file_paths:
            file_paths = ['*']

        # Compile regex pattern
        try:
            flags = re.IGNORECASE if ignore_case else 0
            regex = re.compile(pattern, flags)
        except re.error as e:
            self.console.print(f"[red]Error: Invalid regex pattern: {e}[/red]")
            return

        # Expand file patterns and collect files
        files_to_search = []
        for pattern_str in file_paths:
            # Handle trailing slashes
            pattern_str = pattern_str.rstrip('/')

            # Check if pattern contains glob characters
            has_glob = '*' in pattern_str or '?' in pattern_str or '[' in pattern_str

            if has_glob:
                # Use glob to expand pattern
                if not Path(pattern_str).is_absolute():
                    base_path = self._current_dir
                else:
                    # Find the first directory component that doesn't have glob chars
                    parts = Path(pattern_str).parts
                    base_idx = 0
                    for i, part in enumerate(parts):
                        if '*' in part or '?' in part or '[' in part:
                            break
                        base_idx = i + 1
                    base_path = Path(*parts[:base_idx]) if base_idx > 0 else Path('/')
                    pattern_str = str(Path(*parts[base_idx:])) if base_idx < len(parts) else '*'

                # Perform glob search
                if recursive:
                    matched = [f for f in base_path.rglob(pattern_str) if f.is_file()]
                else:
                    matched = [f for f in base_path.glob(pattern_str) if f.is_file()]
                files_to_search.extend(matched)
            else:
                # No glob characters - treat as literal path
                if not Path(pattern_str).is_absolute():
                    pattern_path = self._current_dir / pattern_str
                else:
                    pattern_path = Path(pattern_str)

                if pattern_path.exists():
                    if pattern_path.is_file():
                        files_to_search.append(pattern_path)
                    elif pattern_path.is_dir():
                        # Search in directory
                        if recursive:
                            files_to_search.extend([f for f in pattern_path.rglob('*') if f.is_file()])
                        else:
                            files_to_search.extend([f for f in pattern_path.glob('*') if f.is_file()])
                else:
                    # File/directory doesn't exist - show error
                    self.console.print(f"[yellow]Warning: Path not found: {pattern_path}[/yellow]")

        # Filter to only files
        files_to_search = [f for f in files_to_search if f.is_file()]

        if not files_to_search:
            self.console.print("[yellow]No files found to search[/yellow]")
            return

        # Search files
        total_matches = 0
        files_with_matches = 0

        for file_path in files_to_search:
            try:
                # Skip binary files (simple check)
                if file_path.suffix in ['.pyc', '.so', '.o', '.bin', '.exe']:
                    continue

                matches = []
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            matches.append((line_num, line.rstrip()))

                if matches:
                    files_with_matches += 1
                    total_matches += len(matches)

                    if files_only:
                        # Just show filename
                        self.console.print(f"[cyan]{file_path}[/cyan]")
                    else:
                        # Show file header if multiple files
                        if len(files_to_search) > 1:
                            self.console.print()
                            self.console.print(f"[bold cyan]{file_path}[/bold cyan]")

                        # Show matching lines
                        for line_num, line in matches:
                            if show_line_numbers:
                                # Highlight the pattern in the line
                                highlighted = regex.sub(lambda m: f"[yellow]{m.group()}[/yellow]", line)
                                self.console.print(f"[green]{line_num}[/green]:{highlighted}")
                            else:
                                highlighted = regex.sub(lambda m: f"[yellow]{m.group()}[/yellow]", line)
                                self.console.print(highlighted)

            except UnicodeDecodeError:
                # Skip binary files
                continue
            except PermissionError:
                self.console.print(f"[dim]Permission denied: {file_path}[/dim]")
            except Exception as e:
                self.console.print(f"[dim]Error reading {file_path}: {e}[/dim]")

        # Show summary
        if total_matches > 0:
            self.console.print()
            self.console.print(f"[dim]Found {total_matches} matches in {files_with_matches} files[/dim]")
        else:
            self.console.print("[yellow]No matches found[/yellow]")

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
            try:
                args = shlex.split(command_line)
            except ValueError as e:
                print(f"Error: {e}")
                return
            if not args:
                return

            # Inject current contexts if set and command needs them
            args = self._inject_case_context(args)
            args = self._inject_data_context(args)

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
            'case': {'show': 2, 'run': 2, 'organise': 2, 'check': 2, 'status': 2},  # case show <case>
            'data': {'show': 2, 'stats': 2},  # data show <case>
            'field': {'info': 2, 'extract': 2},  # field info <case>
            'run': {'check': 2, 'pre': 2, 'main': 2, 'post': 2},  # run check <case>
            'template': {'script': 3},  # template script <type> <case>
            'check': None,  # check <file> - doesn't use case
            'plot': 1,  # plot <case> ...
        }

        cmd = args[0]

        # Check if this command uses cases
        if cmd in case_commands:
            if cmd in ['case', 'data', 'field', 'run', 'template']:
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

    def _inject_data_context(self, args: List[str]) -> List[str]:
        """
        Inject current node/time contexts into command arguments if appropriate.

        Args:
            args: Command arguments

        Returns:
            Modified arguments with node/time contexts injected if needed
        """
        if len(args) < 1:
            return args

        cmd = args[0]

        # Commands that use node, t1, t2 contexts
        data_commands = {
            'data': {'show', 'stats'},
            'field': {'info', 'extract'},
            'plot': True,  # plot uses these directly
        }

        # Check if this command uses data contexts
        if cmd not in data_commands:
            return args

        context_added = []

        # For commands with subcommands
        if cmd in ['data', 'field']:
            if len(args) < 2:
                return args
            subcmd = args[1]
            if subcmd not in data_commands[cmd]:
                return args

        # Inject --node if set and not already present
        if self._current_node is not None and '--node' not in args:
            args.append('--node')
            args.append(str(self._current_node))
            context_added.append(f"node: {self._current_node}")

        # Inject --start-time if t1 is set and not already present
        if self._current_t1 is not None and '--start-time' not in args:
            args.append('--start-time')
            args.append(str(self._current_t1))
            context_added.append(f"t1: {self._current_t1}")

        # Inject --end-time if t2 is set and not already present
        if self._current_t2 is not None and '--end-time' not in args:
            args.append('--end-time')
            args.append(str(self._current_t2))
            context_added.append(f"t2: {self._current_t2}")

        # Show what was injected
        if context_added:
            self.console.print(f"[dim]Using: {', '.join(context_added)}[/dim]")

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
