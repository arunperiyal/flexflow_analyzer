"""
FlexFlow application, built on shellkit.

This module declares what FlexFlow is -- its commands, contexts, builtins and
banner. The shell itself (prompt, history, completion, `use`, pipes, ...)
is shellkit's.
"""

from rich import box
from rich.panel import Panel

from shellkit import App

from src.cli import builtins as ff_builtins
from src.cli.context import CONTEXTS


def _banner(rt):
    from __version__ import __version__
    rt.console.print()
    rt.console.print(Panel(
        f"[bold cyan]FlexFlow Interactive Shell[/bold cyan] [dim]v{__version__}[/dim]\n\n"
        "Fast and efficient simulation analysis tool\n\n"
        "[yellow]Quick Start:[/yellow]\n"
        "  • Type [cyan]help[/cyan] or [cyan]?[/cyan] for available commands\n"
        "  • Use [cyan]ls[/cyan], [cyan]cd[/cyan], [cyan]find[/cyan] to browse\n"
        "  • Use [cyan]Tab[/cyan] for autocompletion\n"
        "  • Use [cyan]↑/↓[/cyan] for command history\n"
        "  • Chain commands with [cyan];[/cyan] (e.g., [cyan]use case:C1; data show[/cyan])\n"
        "  • Pipe commands with [cyan]|[/cyan] (e.g., [cyan]case show | grep status[/cyan])\n\n"
        "[yellow]Set Context:[/yellow]\n"
        "  [cyan]use case:Case015 node:24 t1:50.0 t2:100.0[/cyan]\n"
        "  Set multiple contexts at once with [bold]context:value[/bold] syntax\n\n"
        "[dim]Type [cyan]exit[/cyan] or [cyan]quit[/cyan] to exit[/dim]",
        border_style="cyan", box=box.ROUNDED))
    rt.console.print()


HELP_HEADER = (
    "[yellow]Context:[/yellow]   [cyan]use case:Case015 node:24 t1:50.0 t2:100.0[/cyan]  "
    "[dim](`use list` shows them all)[/dim]\n"
    "[yellow]Chaining:[/yellow]  [cyan]use case:Case005; data show; plot --data-type pendulum[/cyan]\n"
    "[yellow]Piping:[/yellow]    [cyan]case show | head -10[/cyan]   "
    "[cyan]data show | grep -i status[/cyan]"
)


def _register_commands(app):
    from src.commands.case import CaseCommand
    from src.commands.data import DataCommand
    from src.commands.field import FieldCommand
    from src.commands.def_cmd import DefCommand
    from src.commands.check import CheckCommand
    from src.commands.visualization import PlotCommand, CompareCommand
    from src.commands.template import TemplateCommand
    from src.commands.utils import DocsCommand
    from src.commands.run import RunCommand
    from src.commands.remote import RemoteCommand

    app.register(
        # Domain commands
        CaseCommand, DataCommand, FieldCommand, DefCommand,
        # Execution commands
        RunCommand,
        # File inspection
        CheckCommand,
        # Visualization commands
        PlotCommand, CompareCommand,
        # Configuration commands
        RemoteCommand,
        # Utility commands
        TemplateCommand, DocsCommand,
    )


def create_app() -> App:
    """The FlexFlow shellkit App, with every command registered."""
    from __version__ import __version__

    app = App(
        'flexflow',
        version=__version__,
        description='FlexFlow - Analyze and visualize FlexFlow simulation data',
        storage='~/.flexflow',
        contexts=CONTEXTS,
        builtins=('core', 'files'),
        banner=_banner,
        goodbye="\n[cyan]Thanks for using FlexFlow! Goodbye![/cyan]\n",
        help_header=HELP_HEADER,
        session_timeout=15,
        file_style=ff_builtins.file_style,
    )
    for builtin in ff_builtins.builtins():
        app.add_builtin(builtin)
    _register_commands(app)
    return app
