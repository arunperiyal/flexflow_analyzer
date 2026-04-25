"""Manage remote machines for file transfers"""

from rich.console import Console
from rich.table import Table
from rich import box
from src.utils.remote_config import get_remote_config


def execute_remote(args):
    """Execute remote command."""

    if hasattr(args, 'help') and args.help:
        show_remote_help()
        return

    subcommand = getattr(args, 'remote_subcommand', None)

    if not subcommand:
        show_remote_help()
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
    
    # Validate required arguments
    if not hasattr(args, 'name') or not args.name:
        console.print("[red]Error: remote name is required[/red]")
        return
    
    name = args.name
    user = getattr(args, 'user', None)
    ip = getattr(args, 'ip', None)
    password = getattr(args, 'password', None)
    port = getattr(args, 'port', 22)
    path = getattr(args, 'path', '')

    # Validate all required fields
    if not all([user, ip, password]):
        console.print("[red]Error: --user, --ip, and --password are required[/red]")
        return

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
    
    if not hasattr(args, 'name') or not args.name:
        console.print("[red]Error: remote name is required[/red]")
        return

    name = args.name
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
        console.print("[yellow]Warning: No fields to update[/yellow]")
        return

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
    
    if not hasattr(args, 'name') or not args.name:
        console.print("[red]Error: remote name is required[/red]")
        return

    name = args.name
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
    
    if not hasattr(args, 'name') or not args.name:
        console.print("[red]Error: remote name is required[/red]")
        return

    if not hasattr(args, 'path') or not args.path:
        console.print("[red]Error: --path is required[/red]")
        return

    name = args.name
    path = args.path
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
    from src.utils.colors import Colors
    print(f"""
{Colors.BOLD}{Colors.CYAN}remote — Manage remote machines{Colors.RESET}

{Colors.BOLD}USAGE:{Colors.RESET}
    remote add <name> --user <user> --ip <ip> --password <pass> [--port <port>] [--path <path>]
    remote modify <name> [--user <user>] [--ip <ip>] [--password <pass>] [--port <port>]
    remote delete <name>
    remote list
    remote set-path <name> --path <path>

{Colors.BOLD}SUBCOMMANDS:{Colors.RESET}
    {Colors.YELLOW}add{Colors.RESET}           Add a new remote machine
    {Colors.YELLOW}modify{Colors.RESET}        Update remote configuration
    {Colors.YELLOW}delete{Colors.RESET}        Delete a remote machine
    {Colors.YELLOW}list{Colors.RESET}          Show all configured remotes
    {Colors.YELLOW}set-path{Colors.RESET}      Update base path for a remote

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--user <user>{Colors.RESET}       SSH username
    {Colors.YELLOW}--ip <ip>{Colors.RESET}           IP address or hostname
    {Colors.YELLOW}--password <pass>{Colors.RESET}   SSH password (stored in plain text)
    {Colors.YELLOW}--port <port>{Colors.RESET}       SSH port (default: 22)
    {Colors.YELLOW}--path <path>{Colors.RESET}       Base directory on remote for case downloads
    {Colors.YELLOW}-h, --help{Colors.RESET}         Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    remote add hpc1 --user john --ip 192.168.1.100 --password secret --path /home/john/cases
    remote modify hpc1 --port 2222
    remote list
    remote set-path hpc1 --path /scratch/john/new_location
    remote delete hpc1
""")
