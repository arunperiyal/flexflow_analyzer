"""Manage remote machines for file transfers"""

import sys

from rich.console import Console
from rich.table import Table
from rich import box
from src.utils.remote_config import get_remote_config
from . import help_messages


# The help to print for each subcommand, so a bare `remote add` says what add
# needs rather than only that something is missing.
_SUBCOMMAND_HELP = {
    'add':      help_messages.print_add_help,
    'modify':   help_messages.print_modify_help,
    'delete':   help_messages.print_delete_help,
    'list':     help_messages.print_list_help,
    'set-path': help_messages.print_set_path_help,
}


def _show_help(subcommand=None):
    """Print the help for a subcommand, or for the group when it has none."""
    _SUBCOMMAND_HELP.get(subcommand, help_messages.print_remote_help)()


def execute_remote(args):
    """Execute remote command."""

    subcommand = getattr(args, 'remote_subcommand', None)

    if hasattr(args, 'help') and args.help:
        _show_help(subcommand)
        return

    if not subcommand:
        _show_help()
        return

    if subcommand == 'add':
        execute_add(args)
    elif subcommand == 'modify':
        execute_modify(args)
    elif subcommand == 'delete':
        execute_delete(args)
    elif subcommand == 'list':
        execute_list(args)
    elif subcommand == 'set-path':
        execute_set_path(args)
    else:
        print(f"Unknown subcommand: {subcommand}")


def execute_add(args):
    """Add a new remote machine."""
    console = Console()

    name = getattr(args, 'name', None)
    user = getattr(args, 'user', None)
    ip = getattr(args, 'ip', None)
    password = getattr(args, 'password', None)
    port = getattr(args, 'port', 22)
    path = getattr(args, 'path', '')

    # A bare `remote add` is a request for help, not a mistake to report.
    if not any([name, user, ip, password, path]):
        help_messages.print_add_help()
        sys.exit(1)

    if not name:
        console.print("[red]Error: remote name is required[/red]")
        print()
        help_messages.print_add_help()
        sys.exit(1)

    # Validate all required fields
    missing = [flag for flag, value in
               (('--user', user), ('--ip', ip), ('--password', password))
               if not value]
    if missing:
        console.print(f"[red]Error: {', '.join(missing)} "
                      f"{'is' if len(missing) == 1 else 'are'} required[/red]")
        print()
        help_messages.print_add_help()
        sys.exit(1)

    # Validate IP format (basic check)
    if not _validate_ip(ip):
        console.print(f"[red]Error: Invalid IP address: {ip}[/red]")
        return

    # Validate port
    try:
        port = int(port)
        if not (1 <= port <= 65535):
            console.print("[red]Error: Port must be between 1 and 65535[/red]")
            return
    except ValueError:
        console.print("[red]Error: Port must be a number[/red]")
        return

    config = get_remote_config()
    
    if not config.add_remote(name, user, ip, password, port, path):
        console.print(f"[red]Error: Remote '{name}' already exists[/red]")
        return

    console.print(f"[green]✓ Remote '{name}' added successfully[/green]")
    _display_remote(name, user, ip, port, path)


def execute_modify(args):
    """Modify an existing remote machine."""
    console = Console()
    
    name = getattr(args, 'name', None)

    if not name:
        if not any(getattr(args, field, None)
                   for field in ('user', 'ip', 'password', 'port')):
            help_messages.print_modify_help()
            sys.exit(1)
        console.print("[red]Error: remote name is required[/red]")
        print()
        help_messages.print_modify_help()
        sys.exit(1)

    config = get_remote_config()

    # Check if remote exists
    remote = config.get_remote(name)
    if not remote:
        console.print(f"[red]Error: Remote '{name}' not found[/red]")
        return

    # Collect updates
    updates = {}
    
    if hasattr(args, 'user') and args.user:
        updates['user'] = args.user
    if hasattr(args, 'ip') and args.ip:
        if not _validate_ip(args.ip):
            console.print(f"[red]Error: Invalid IP address: {args.ip}[/red]")
            return
        updates['ip'] = args.ip
    if hasattr(args, 'password') and args.password:
        updates['password'] = args.password
    if hasattr(args, 'port') and args.port:
        try:
            port = int(args.port)
            if not (1 <= port <= 65535):
                console.print("[red]Error: Port must be between 1 and 65535[/red]")
                return
            updates['port'] = port
        except ValueError:
            console.print("[red]Error: Port must be a number[/red]")
            return

    if not updates:
        console.print("[red]Error: give at least one field to update[/red]")
        print()
        help_messages.print_modify_help()
        sys.exit(1)

    # Apply updates
    if config.update_remote(name, **updates):
        console.print(f"[green]✓ Remote '{name}' updated successfully[/green]")
        # Get updated remote and display
        remote = config.get_remote(name)
        _display_remote(name, remote['user'], remote['ip'], remote['port'], remote['path'])
    else:
        console.print(f"[red]Error: Failed to update remote '{name}'[/red]")


def execute_delete(args):
    """Delete a remote machine."""
    console = Console()
    
    name = getattr(args, 'name', None)

    if not name:
        help_messages.print_delete_help()
        sys.exit(1)

    config = get_remote_config()

    # Confirmation prompt
    if not _confirm(f"Delete remote '{name}'? This cannot be undone."):
        console.print("[yellow]Cancelled[/yellow]")
        return

    if config.delete_remote(name):
        console.print(f"[green]✓ Remote '{name}' deleted successfully[/green]")
    else:
        console.print(f"[red]Error: Remote '{name}' not found[/red]")


def execute_list(args):
    """List all remote machines."""
    console = Console()
    
    config = get_remote_config()
    remotes = config.get_all_remotes()

    if not remotes:
        console.print()
        console.print("[dim]No remotes configured[/dim]")
        console.print("[dim]Use: ff remote add <name> --user <user> --ip <ip> --password <pass> --path <path>[/dim]")
        console.print()
        return

    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style='bold cyan',
        title='Configured Remote Machines',
        title_style='bold magenta',
    )
    
    table.add_column('Name',     style='yellow', min_width=15)
    table.add_column('User',     style='green',  min_width=12)
    table.add_column('IP',       style='cyan',   min_width=15)
    table.add_column('Port',     style='white',  justify='right', min_width=6)
    table.add_column('Path',     style='dim',    min_width=30)

    for remote in remotes:
        table.add_row(
            remote['name'],
            remote['user'],
            remote['ip'],
            str(remote['port']),
            remote.get('path', '—'),
        )

    console.print()
    console.print(table)
    console.print()
    console.print(f"[dim]Total: {len(remotes)} remote(s)[/dim]")
    console.print()


def execute_set_path(args):
    """Set base path for a remote machine."""
    console = Console()
    
    name = getattr(args, 'name', None)
    path = getattr(args, 'path', None)

    if not name and not path:
        help_messages.print_set_path_help()
        sys.exit(1)

    if not name:
        console.print("[red]Error: remote name is required[/red]")
        print()
        help_messages.print_set_path_help()
        sys.exit(1)

    if not path:
        console.print("[red]Error: --path is required[/red]")
        print()
        help_messages.print_set_path_help()
        sys.exit(1)

    config = get_remote_config()

    # Check if remote exists
    if not config.remote_exists(name):
        console.print(f"[red]Error: Remote '{name}' not found[/red]")
        return

    if config.update_remote(name, path=path):
        console.print(f"[green]✓ Path updated for remote '{name}': {path}[/green]")
    else:
        console.print(f"[red]Error: Failed to update remote '{name}'[/red]")


def _validate_ip(ip: str) -> bool:
    """Validate IP address format."""
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    try:
        for part in parts:
            num = int(part)
            if not (0 <= num <= 255):
                return False
        return True
    except ValueError:
        return False


def _confirm(prompt: str) -> bool:
    """Ask user for confirmation."""
    response = input(f"{prompt} (y/N): ").lower().strip()
    return response == 'y'


def _display_remote(name: str, user: str, ip: str, port: int, path: str):
    """Display remote details."""
    console = Console()
    console.print()
    console.print(f"[bold]Remote Details:[/bold]")
    console.print(f"  [yellow]Name:[/yellow]     {name}")
    console.print(f"  [yellow]User:[/yellow]     {user}")
    console.print(f"  [yellow]IP:[/yellow]       {ip}")
    console.print(f"  [yellow]Port:[/yellow]     {port}")
    console.print(f"  [yellow]Path:[/yellow]     {path or '(not set)'}")
    console.print()


def show_remote_help():
    """Display help for remote command."""
    help_messages.print_remote_help()
