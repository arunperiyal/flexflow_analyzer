"""auto init: write .auto.conf in this folder, for the user to edit."""

from pathlib import Path

from rich.console import Console
from rich.markup import escape


def _context_remote():
    try:
        from shellkit.runtime import current_runtime
        rt = current_runtime()
        return rt.get('remote') if rt else None
    except Exception:
        return None


def execute_init(args) -> int:
    from src.cli.context import current_dir
    from src.core.auto.conf import AutoConfError, PLACEHOLDER, write_template
    from src.utils.remote_config import RemoteConfig

    console = Console()
    folder = Path(current_dir())
    try:
        known = [r['name'] for r in RemoteConfig().get_all_remotes()]
    except Exception:
        known = []
    remote = _context_remote()
    try:
        path = write_template(folder, remote=remote, known=known,
                              force=getattr(args, 'force', False))
    except AutoConfError as e:
        console.print(f"[red]Error:[/red] {escape(str(e))}")
        return 2
    console.print(f"[green]✓[/green] wrote {escape(str(path))}")
    todo = ['path'] + ([] if remote else ['remote'])
    console.print(f"  Edit it: set {' and '.join(f'`{k}`' for k in todo)} (now {PLACEHOLDER}); "
                  f"keep_rst and disk_alert are optional.")
    if not (folder / '.cases').exists():
        console.print("  [yellow]No .cases here yet:[/yellow] `case add` registers the cases.")
    console.print("  Then: [cyan]auto show[/cyan]")
    return 0
