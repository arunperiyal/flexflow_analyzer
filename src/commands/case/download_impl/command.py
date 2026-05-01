"""Case upload command implementation."""

import os
from pathlib import Path
from typing import Optional, List
from src.utils.ssh_client import SSHClientWrapper
from src.utils.remote_config import RemoteConfig
from ...case_iteration import is_wildcard_case, load_cases_from_directory
from src.utils.colors import Colors
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from rich.table import Table
from rich import box


def show_upload_help() -> None:
    """Print help for case upload command."""
    print(f"""
{Colors.BOLD}{Colors.CYAN}FlexFlow Case Upload Command{Colors.RESET}

Upload case directories from local machine to a remote server.

{Colors.BOLD}USAGE:{Colors.RESET}
    flexflow case upload [{Colors.YELLOW}case{Colors.RESET}] --to {Colors.YELLOW}REMOTE{Colors.RESET} [options]

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
    {Colors.YELLOW}case{Colors.RESET}                   Local case directory path (use * for all cases in .cases)

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}--to REMOTE{Colors.RESET}            Remote machine name (required)
    {Colors.YELLOW}--dir DIRS{Colors.RESET}             Comma-separated directories to upload
                           (default: othd_files,oisd_files,binary)
    {Colors.YELLOW}--remote-path PATH{Colors.RESET}     Override remote base path (default: remote config path)
    {Colors.YELLOW}--force{Colors.RESET}                Create remote directories if they do not exist
    {Colors.YELLOW}--examples{Colors.RESET}             Show usage examples
    {Colors.YELLOW}-h, --help{Colors.RESET}             Show this help message

{Colors.BOLD}DESCRIPTION:{Colors.RESET}
    Uploads one or more case directories to a configured remote server via
    SFTP. The remote server must be registered with 'remote add'.

    Use 'use remote:<name>' in the interactive shell to set a default remote
    so --to can be omitted.

    Wildcard mode ('case upload *') uploads all cases listed in the .cases
    file in the current directory.

{Colors.BOLD}CONTEXT:{Colors.RESET}
    Set remote context:    use remote:myserver
    Then run:              case upload CS4SG1U1
""")


class CaseUploadCommand:
    """Upload case directories from local machine to remote server."""

    def __init__(self):
        self.console = Console()
        self.remote_config = RemoteConfig()

    def validate_remote(self, remote_name: str) -> Optional[dict]:
        """
        Validate and retrieve remote configuration.

        Args:
            remote_name: Name of the remote machine

        Returns:
            Remote configuration dict or None if invalid
        """
        if not self.remote_config.remote_exists(remote_name):
            self.console.print(f"[red]Error:[/red] Remote '{remote_name}' not found.")
            return None

        return self.remote_config.get_remote(remote_name)

    def _get_cases_base_dir(self) -> Path:
        """Return directory used to resolve .cases for wildcard mode."""
        from src.cli.interactive import InteractiveShell

        if hasattr(InteractiveShell, "_instance") and InteractiveShell._instance:
            return InteractiveShell._instance._current_dir
        return Path.cwd()

    def validate_case_path(self, case_path: str) -> Optional[str]:
        """
        Validate and resolve case path.

        Args:
            case_path: Case path (relative or absolute)

        Returns:
            Absolute case path or None if invalid
        """
        if not case_path:
            self.console.print("[red]Error:[/red] Case path not provided.")
            return None

        case_path = os.path.expanduser(case_path)
        return case_path

    def parse_directories(self, dirs_arg: Optional[str]) -> List[str]:
        """
        Parse comma-separated directory list.

        Args:
            dirs_arg: Comma-separated string of directories

        Returns:
            List of directory names
        """
        if not dirs_arg:
            return ["othd_files", "oisd_files", "binary"]

        dirs = [d.strip() for d in dirs_arg.split(",") if d.strip()]
        return dirs if dirs else ["othd_files", "oisd_files", "binary"]

    def get_remote_base_path(self, remote: dict, override_path: Optional[str]) -> str:
        """
        Determine remote base path.

        Args:
            remote: Remote configuration dict
            override_path: Optional override path

        Returns:
            Remote base path
        """
        if override_path:
            return os.path.expanduser(override_path)

        # Use remote's configured path
        remote_path = remote.get("path")
        if remote_path:
            return remote_path

        # Default to home directory
        return "~"

    def construct_remote_case_path(
        self,
        remote_base: str,
        case_path: str
    ) -> str:
        """
        Construct remote case path.

        Args:
            remote_base: Remote base path
            case_path: Local case path (to extract case name)

        Returns:
            Remote case path
        """
        case_name = os.path.basename(case_path.rstrip("/"))
        return f"{remote_base}/{case_name}"

    def upload_directory(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        local_case_path: str,
        directory_name: str,
        force: bool = False
    ) -> bool:
        """
        Upload a single directory from local case to remote case.

        Args:
            ssh: SSH client wrapper
            remote_case_path: Destination case path on remote
            local_case_path: Source local case path
            directory_name: Name of directory to upload (e.g., "othd_files")
            force: Create remote directory if it doesn't exist

        Returns:
            True if successful, False otherwise
        """
        local_dir = os.path.join(local_case_path, directory_name)
        remote_dir = f"{remote_case_path}/{directory_name}"

        # Check if local source directory exists
        if not os.path.exists(local_dir):
            self.console.print(
                f"[yellow]Warning:[/yellow] Local directory not found: {local_dir}"
            )
            return False

        if not os.path.isdir(local_dir):
            self.console.print(
                f"[yellow]Warning:[/yellow] Local path is not a directory: {local_dir}"
            )
            return False

        # Check/create remote destination directory
        if not ssh.remote_path_exists(remote_dir):
            if force:
                # Try to create the remote directory
                self.console.print(
                    f"[cyan]Creating:[/cyan] Remote directory {remote_dir}"
                )
                if not ssh.make_remote_dir(remote_dir):
                    self.console.print(
                        f"[red]Error:[/red] Failed to create remote directory: {remote_dir}"
                    )
                    return False
                self.console.print(
                    f"[green]✓[/green] Created remote directory: {remote_dir}"
                )
            else:
                self.console.print(
                    f"[yellow]Warning:[/yellow] Remote directory not found: {remote_dir}"
                )
                self.console.print(
                    f"[dim]Use --force to create remote directories[/dim]"
                )
                return False

        if not ssh.remote_is_dir(remote_dir):
            self.console.print(
                f"[yellow]Warning:[/yellow] Remote path is not a directory: {remote_dir}"
            )
            return False

        self.console.print(f"[cyan]Uploading:[/cyan] {directory_name}")

        try:
            total_bytes = sum(
                os.path.getsize(os.path.join(root, f))
                for root, _, files in os.walk(local_dir)
                for f in files
            )

            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task(
                    f"Transferring {directory_name}...",
                    total=total_bytes or None,
                )

                state = {"done": 0, "last": 0}

                def update_progress(transferred, _file_total):
                    if transferred < state["last"]:
                        state["done"] += state["last"]
                    state["last"] = transferred
                    progress.update(task, completed=state["done"] + transferred)

                files_count = ssh.upload_directory(
                    local_dir,
                    remote_dir,
                    callback=update_progress,
                )

                progress.update(task, completed=total_bytes)

            self.console.print(
                f"[green]✓[/green] Uploaded {files_count} files to {remote_dir}"
            )
            return True

        except Exception as e:
            self.console.print(f"[red]Error:[/red] Failed to upload {directory_name}: {e}")
            return False

    def download_directory(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        local_case_path: str,
        directory_name: str,
        force: bool = False
    ) -> bool:
        """Backward-compatible alias; uses upload behavior."""
        return self.upload_directory(
            ssh=ssh,
            remote_case_path=remote_case_path,
            local_case_path=local_case_path,
            directory_name=directory_name,
            force=force
        )

    def execute_upload(self, args) -> int:
        """
        Execute case upload command.

        Args:
            args: Parsed arguments

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        if hasattr(args, "help") and args.help:
            show_upload_help()
            return 0

        if hasattr(args, "examples") and args.examples:
            show_upload_help()
            return 0

        # Validate case path
        case_path = self.validate_case_path(args.case)
        if not case_path:
            return 1

        if not args.to:
            self.console.print(
                "[red]Error:[/red] Remote machine not provided. Use --to or 'use remote:<name>' in interactive shell."
            )
            return 1

        force_enabled = bool(getattr(args, "force", False))

        # Validate remote
        remote = self.validate_remote(args.to)
        if not remote:
            return 1

        # Parse directories to upload
        directories = self.parse_directories(args.dir)

        # Get remote base path
        remote_base = self.get_remote_base_path(remote, args.remote_path)

        # Wildcard mode: iterate all cases from .cases
        if is_wildcard_case(case_path):
            base_dir = self._get_cases_base_dir()
            cases = load_cases_from_directory(base_dir)
            if not cases:
                self.console.print(
                    f"[red]Error:[/red] No cases found in .cases at {base_dir}"
                )
                return 1

            self.console.print()
            self.console.print(
                f"[bold cyan]Case Upload Summary[/bold cyan] [dim](wildcard mode: {len(cases)} cases)[/dim]"
            )
            self.console.print()

            table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
            table.add_column("Parameter", style="cyan")
            table.add_column("Value", style="white")
            table.add_row("Case Selection", "* (all cases from .cases)")
            table.add_row("Cases Base Dir", str(base_dir))
            table.add_row("Remote Machine", args.to)
            table.add_row("Remote Host", f"{remote['user']}@{remote['ip']}:{remote['port']}")
            table.add_row("Remote Base Path", remote_base)
            table.add_row("Directories", ", ".join(directories))
            table.add_row("Force Create Missing Dir", "Yes" if force_enabled else "No")
            self.console.print(table)
            self.console.print()

            try:
                ssh = SSHClientWrapper(
                    host=remote["ip"],
                    username=remote["user"],
                    password=remote["password"],
                    port=remote.get("port", 22)
                )

                self.console.print("[cyan]Connecting to remote server...[/cyan]")
                ssh.connect()
                self.console.print("[green]✓[/green] Connected successfully")
                self.console.print()

                success_count = 0
                total_targets = len(cases) * len(directories)

                for idx, case_entry in enumerate(cases, 1):
                    entry_path = case_entry.get("path")
                    entry_name = case_entry.get("name", f"case-{idx}")

                    self.console.print(
                        f"[bold]Case {idx}/{len(cases)}:[/bold] [cyan]{entry_name}[/cyan]"
                    )

                    if not entry_path:
                        self.console.print("[yellow]Warning:[/yellow] Missing case path in .cases entry")
                        self.console.print()
                        continue

                    if not os.path.exists(entry_path) or not os.path.isdir(entry_path):
                        self.console.print(
                            f"[yellow]Warning:[/yellow] Local case directory not found: {entry_path}"
                        )
                        self.console.print()
                        continue

                    remote_case_path = self.construct_remote_case_path(remote_base, entry_path)
                    self.console.print(f"[dim]Remote case path: {remote_case_path}[/dim]")

                    for directory in directories:
                        if self.upload_directory(
                            ssh,
                            remote_case_path,
                            entry_path,
                            directory,
                            force=force_enabled
                        ):
                            success_count += 1
                    self.console.print()

                ssh.disconnect()
                self.console.print(
                    f"[green]✓[/green] Upload complete: {success_count}/{total_targets} directories"
                )
                return 0 if success_count > 0 else 1

            except Exception as e:
                self.console.print(f"[red]Error:[/red] {e}")
                return 1

        if not os.path.exists(case_path):
            self.console.print(f"[red]Error:[/red] Local case path not found: {case_path}")
            return 1
        if not os.path.isdir(case_path):
            self.console.print(f"[red]Error:[/red] Local case path is not a directory: {case_path}")
            return 1

        # Construct remote case path
        remote_case_path = self.construct_remote_case_path(remote_base, case_path)

        # Show summary
        self.console.print()
        self.console.print("[bold cyan]Case Upload Summary[/bold cyan]")
        self.console.print()

        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Local Case Path", case_path)
        table.add_row("Remote Machine", args.to)
        table.add_row("Remote Host", f"{remote['user']}@{remote['ip']}:{remote['port']}")
        table.add_row("Remote Case Path", remote_case_path)
        table.add_row("Directories", ", ".join(directories))
        table.add_row("Force Create Missing Dir", "Yes" if force_enabled else "No")

        self.console.print(table)
        self.console.print()

        # Connect to remote and upload
        try:
            ssh = SSHClientWrapper(
                host=remote["ip"],
                username=remote["user"],
                password=remote["password"],
                port=remote.get("port", 22)
            )

            self.console.print("[cyan]Connecting to remote server...[/cyan]")
            ssh.connect()
            self.console.print("[green]✓[/green] Connected successfully")
            self.console.print()

            # Upload each directory
            success_count = 0
            for directory in directories:
                if self.upload_directory(
                    ssh,
                    remote_case_path,
                    case_path,
                    directory,
                    force=force_enabled
                ):
                    success_count += 1

            ssh.disconnect()
            self.console.print()
            self.console.print(
                f"[green]✓[/green] Upload complete: {success_count}/{len(directories)} directories"
            )
            return 0 if success_count > 0 else 1

        except Exception as e:
            self.console.print(f"[red]Error:[/red] {e}")
            return 1

    def execute_download(self, args) -> int:
        """Backward-compatible alias; uses upload behavior."""
        return self.execute_upload(args)


# Backward-compatible alias for older imports/tests.
CaseDownloadCommand = CaseUploadCommand


# Create command instance
command = CaseUploadCommand()


def execute_upload(args) -> int:
    """Execute upload command."""
    return command.execute_upload(args)


def execute_download(args) -> int:
    """Backward-compatible alias for older imports."""
    return execute_upload(args)
