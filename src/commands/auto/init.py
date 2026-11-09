"""auto init: write .auto.conf in this folder, for the user to check and edit."""

from pathlib import Path, PurePosixPath

from rich.console import Console
from rich.markup import escape


def execute_init(args) -> int:
    from src.cli.context import current_dir
    from src.core.auto.conf import AutoConfError, PLACEHOLDER, write_template
    from src.utils.remote_config import RemoteConfig

    console = Console()
    folder = Path(current_dir())
    try:
        remotes = {r['name']: r for r in RemoteConfig().get_all_remotes()}
    except Exception:
        remotes = {}
    remote = getattr(args, 'remote', None)
    if remote and remote != 'local' and remote not in remotes:
        console.print(f"[red]Error:[/red] remote '{escape(remote)}' not found "
                      f"(`remote list` shows them)")
        return 2

    # the folder on the remote: --path, else what `remote set-path` holds
    path, path_from = getattr(args, 'path', None), None
    if not path and remote in remotes and remotes[remote].get('path'):
        path, path_from = remotes[remote]['path'], remote
    try:
        written = write_template(folder, remote=remote, path=path,
                                 keep_rst=getattr(args, 'keep_rst', None),
                                 disk_alert=getattr(args, 'disk_alert', None),
                                 known=list(remotes), path_from=path_from,
                                 force=getattr(args, 'force', False))
    except AutoConfError as e:
        console.print(f"[red]Error:[/red] {escape(str(e))}")
        return 2

    console.print(f"[green]✓[/green] wrote {escape(str(written))}")
    if remote:
        console.print(f"  remote  {escape(remote)}")
    if path:
        how = f"  [dim](from `remote set-path {escape(path_from)}`)[/dim]" if path_from else ''
        console.print(f"  path    {escape(path)}{how}")
        # case X goes to <path>/X: a path named after another folder is likely wrong
        if PurePosixPath(path.rstrip('/')).name != folder.name:
            console.print(f"  [yellow]Check the path:[/yellow] it ends in "
                          f"'{escape(PurePosixPath(path.rstrip('/')).name)}', this folder is "
                          f"'{escape(folder.name)}'. Cases go to <path>/<case>.")
    todo = [k for k, v in (('remote', remote), ('path', path)) if not v]
    if todo:
        console.print(f"  Edit it: set {' and '.join(f'`{k}`' for k in todo)} (now {PLACEHOLDER}).")
    if not (folder / '.cases').exists():
        console.print("  [yellow]No .cases here yet:[/yellow] `case add` registers the cases.")
    console.print("  Then: [cyan]auto show[/cyan]")
    return 0
