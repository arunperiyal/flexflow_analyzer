"""Case download command implementation."""

import os
import sys
from pathlib import Path
from typing import Optional, List
from src.utils.ssh_client import SSHClientWrapper
from src.utils.remote_config import RemoteConfig
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
from rich import box


class CaseDownloadCommand:
    """Download case directories from remote server to local machine."""

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

    def download_directory(
        self,
        ssh: SSHClientWrapper,
        remote_case_path: str,
        local_case_path: str,
        directory_name: str
    ) -> bool:
        """
        Download single directory from remote case.

        Args:
            ssh: SSH client wrapper
            remote_case_path: Path to case on remote
            local_case_path: Local case path
            directory_name: Name of directory to download (e.g., "othd_files")

        Returns:
            True if successful, False otherwise
        """
        remote_dir = f"{remote_case_path}/{directory_name}"
        local_dir = os.path.join(local_case_path, directory_name)

        # Check if remote directory exists
        if not ssh.remote_path_exists(remote_dir):
            self.console.print(
                f"[yellow]Warning:[/yellow] Remote directory not found: {remote_dir}"
            )
            return False

        if not ssh.remote_is_dir(remote_dir):
            self.console.print(
                f"[yellow]Warning:[/yellow] Remote path is not a directory: {remote_dir}"
            )
            return False

        # Create local directory
        os.makedirs(local_dir, exist_ok=True)

        self.console.print(f"[cyan]Downloading:[/cyan] {directory_name}")

        try:
            with Progress() as progress:
                task = progress.add_task(
                    f"Transferring {directory_name}...",
                    total=None
                )

                def update_progress(transferred, total):
                    progress.update(task, completed=transferred, total=total)

                files_count = ssh.download_directory(
                    remote_dir,
                    local_dir,
                    callback=update_progress
                )

            self.console.print(
                f"[green]✓[/green] Downloaded {files_count} files to {local_dir}"
            )
            return True

        except Exception as e:
            self.console.print(f"[red]Error:[/red] Failed to download {directory_name}: {e}")
            return False

    def execute_download(self, args) -> int:
        """
        Execute case download command.

        Args:
            args: Parsed arguments

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        # Validate case path
        case_path = self.validate_case_path(args.case)
        if not case_path:
            return 1

        # Validate remote
        remote = self.validate_remote(args.to)
        if not remote:
            return 1

        # Parse directories to download
        directories = self.parse_directories(args.dir)

        # Get remote base path
        remote_base = self.get_remote_base_path(remote, args.remote_path)

        # Construct remote case path
        remote_case_path = self.construct_remote_case_path(remote_base, case_path)

        # Show summary
        self.console.print()
        self.console.print("[bold cyan]Case Download Summary[/bold cyan]")
        self.console.print()

        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Local Case Path", case_path)
        table.add_row("Remote Machine", args.to)
        table.add_row("Remote Host", f"{remote['user']}@{remote['ip']}:{remote['port']}")
        table.add_row("Remote Case Path", remote_case_path)
        table.add_row("Directories", ", ".join(directories))

        self.console.print(table)
        self.console.print()

        # Create local case directory if it doesn't exist
        os.makedirs(case_path, exist_ok=True)

        # Connect to remote and download
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

            # Download each directory
            success_count = 0
            for directory in directories:
                if self.download_directory(
                    ssh,
                    remote_case_path,
                    case_path,
                    directory
                ):
                    success_count += 1

            ssh.disconnect()
            self.console.print()
            self.console.print(
                f"[green]✓[/green] Download complete: {success_count}/{len(directories)} directories"
            )
            return 0 if success_count > 0 else 1

        except Exception as e:
            self.console.print(f"[red]Error:[/red] {e}")
            return 1


# Create command instance
command = CaseDownloadCommand()


def execute_download(args) -> int:
    """Execute download command."""
    return command.execute_download(args)
