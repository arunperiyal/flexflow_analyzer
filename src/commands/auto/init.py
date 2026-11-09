"""auto init: set auto's entries in this folder's .cases.yml -- a remote's
folder for these cases, and auto's settings -- for the user to check."""

from pathlib import Path, PurePosixPath

from rich.console import Console
from rich.markup import escape


def execute_init(args) -> int:
    from src.cli.context import current_dir
    from src.core import cases_file
    from src.core.auto.conf import AutoConfError, PLACEHOLDER, set_up
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

    # the remote's folder for these cases: --path, else its `remote set-path`
    path, path_from = getattr(args, 'path', None), None
    if remote and not path and remote in remotes and remotes[remote].get('path'):
        path, path_from = remotes[remote]['path'], remote
    try:
        cf, changed, kept = set_up(folder, remote=remote, path=path,
                                   keep_rst=getattr(args, 'keep_rst', None),
                                   disk_alert=getattr(args, 'disk_alert', None),
                                   replace=getattr(args, 'force', False))
    except AutoConfError as e:
        console.print(f"[red]Error:[/red] {escape(str(e))}")
        return 2

    console.print(f"[green]✓[/green] {escape(str(cf.path))}")
    for line in changed:
        console.print(f"  set   {escape(line)}")
    for line in kept:
        console.print(f"  [yellow]kept[/yellow]  {escape(line)}")
    if not changed and not kept:
        console.print("  nothing to change")
    if remote and path_from and any(c.startswith(f"remotes.{remote}:") for c in changed):
        console.print(f"  [dim]the folder is `remote set-path {escape(path_from)}`[/dim]")
    new_path = cf.remotes.get(remote) if remote else None
    if new_path and new_path != PLACEHOLDER:
        # case X goes to <path>/X: a folder named after another one is likely wrong
        last = PurePosixPath(new_path.rstrip('/')).name
        if last != folder.name:
            console.print(f"  [yellow]Check the path:[/yellow] it ends in '{escape(last)}', this "
                          f"folder is '{escape(folder.name)}'. Cases go to <path>/<case>.")
    if new_path == PLACEHOLDER:
        console.print(f"  Edit {cases_file.FILENAME}: set `remotes.{escape(remote)}` "
                      f"(now {PLACEHOLDER}), or `auto init --remote {escape(remote)} --path DIR`.")
    if not remote and not cf.remotes:
        console.print("  No remote yet: `auto init --remote NAME [--path DIR]`.")
    if not cf.cases:
        console.print("  [yellow]No cases listed yet:[/yellow] `case add` finds them.")
    console.print("  Then: [cyan]auto show --remote NAME[/cyan] (or `use remote:NAME`)")
    return 0
