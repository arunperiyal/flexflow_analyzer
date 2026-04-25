"""SSH/SFTP client wrapper for remote file transfers."""

import os
import stat
import paramiko
from paramiko import SSHClient, AutoAddPolicy, SFTPClient
from typing import Optional, List, Callable
import tempfile
from pathlib import Path


class SSHClientWrapper:
    """Manages SSH connections and SFTP file transfers."""

    def __init__(self, host: str, username: str, password: str, port: int = 22):
        """
        Initialize SSH client.

        Args:
            host: Remote host IP or hostname
            username: SSH username
            password: SSH password
            port: SSH port (default: 22)
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.ssh_client: Optional[SSHClient] = None
        self.sftp_client: Optional[SFTPClient] = None
        self.connected = False

    def connect(self) -> bool:
        """
        Connect to remote SSH server.

        Returns:
            True if connection successful, False otherwise

        Raises:
            paramiko.AuthenticationException: If authentication fails
            paramiko.SSHException: If SSH connection fails
            OSError: If network error occurs
        """
        try:
            self.ssh_client = SSHClient()
            self.ssh_client.set_missing_host_key_policy(AutoAddPolicy())
            self.ssh_client.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10,
            )
            self.sftp_client = self.ssh_client.open_sftp()
            self.connected = True
            return True
        except paramiko.AuthenticationException as e:
            raise paramiko.AuthenticationException(
                f"SSH authentication failed for {self.username}@{self.host}:{self.port}: {e}"
            )
        except paramiko.SSHException as e:
            raise paramiko.SSHException(
                f"SSH connection failed to {self.host}:{self.port}: {e}"
            )
        except OSError as e:
            raise OSError(f"Network error connecting to {self.host}:{self.port}: {e}")

    def disconnect(self) -> None:
        """Close SSH and SFTP connections."""
        if self.sftp_client:
            try:
                self.sftp_client.close()
            except Exception:
                pass
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception:
                pass
        self.connected = False

    def remote_path_exists(self, remote_path: str) -> bool:
        """
        Check if remote path exists.

        Args:
            remote_path: Path on remote server

        Returns:
            True if path exists, False otherwise
        """
        if not self.connected or not self.sftp_client:
            return False
        try:
            self.sftp_client.stat(remote_path)
            return True
        except FileNotFoundError:
            return False

    def remote_is_dir(self, remote_path: str) -> bool:
        """
        Check if remote path is a directory.

        Args:
            remote_path: Path on remote server

        Returns:
            True if path is directory, False otherwise
        """
        if not self.connected or not self.sftp_client:
            return False
        try:
            stat_result = self.sftp_client.stat(remote_path)
            return stat.S_ISDIR(stat_result.st_mode)
        except FileNotFoundError:
            return False

    def upload_file(self, local_path: str, remote_path: str, callback: Optional[Callable] = None) -> None:
        """
        Upload single file to remote server.

        Args:
            local_path: Local file path
            remote_path: Remote file path
            callback: Optional callback(bytes_transferred, total_bytes) for progress

        Raises:
            IOError: If upload fails
            FileNotFoundError: If local file not found
        """
        if not self.connected or not self.sftp_client:
            raise IOError("Not connected to SSH server")

        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")

        try:
            self.sftp_client.put(local_path, remote_path, callback=callback)
        except Exception as e:
            raise IOError(f"Failed to upload {local_path} to {remote_path}: {e}")

    def download_file(self, remote_path: str, local_path: str, callback: Optional[Callable] = None) -> None:
        """
        Download single file from remote server.

        Args:
            remote_path: Remote file path
            local_path: Local file path
            callback: Optional callback(bytes_transferred, total_bytes) for progress

        Raises:
            IOError: If download fails
            FileNotFoundError: If remote file not found
        """
        if not self.connected or not self.sftp_client:
            raise IOError("Not connected to SSH server")

        if not self.remote_path_exists(remote_path):
            raise FileNotFoundError(f"Remote file not found: {remote_path}")

        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.sftp_client.get(remote_path, local_path, callback=callback)
        except Exception as e:
            raise IOError(f"Failed to download {remote_path} to {local_path}: {e}")

    def list_remote_dir(self, remote_path: str) -> List[str]:
        """
        List contents of remote directory.

        Args:
            remote_path: Remote directory path

        Returns:
            List of filenames in directory

        Raises:
            IOError: If directory listing fails
        """
        if not self.connected or not self.sftp_client:
            raise IOError("Not connected to SSH server")

        try:
            return self.sftp_client.listdir(remote_path)
        except Exception as e:
            raise IOError(f"Failed to list directory {remote_path}: {e}")

    def download_directory(
        self,
        remote_dir: str,
        local_dir: str,
        patterns: Optional[List[str]] = None,
        callback: Optional[Callable] = None,
    ) -> int:
        """
        Recursively download directory from remote server.

        Args:
            remote_dir: Remote directory path
            local_dir: Local directory path
            patterns: Optional list of filename patterns to include (e.g., ['*.csv', '*.txt']).
                     If None, downloads all files.
            callback: Optional callback(bytes_transferred, total_bytes) for progress

        Returns:
            Number of files downloaded

        Raises:
            IOError: If download fails
            FileNotFoundError: If remote directory not found
        """
        if not self.connected or not self.sftp_client:
            raise IOError("Not connected to SSH server")

        if not self.remote_path_exists(remote_dir):
            raise FileNotFoundError(f"Remote directory not found: {remote_dir}")

        if not self.remote_is_dir(remote_dir):
            raise IOError(f"Remote path is not a directory: {remote_dir}")

        os.makedirs(local_dir, exist_ok=True)
        files_downloaded = 0

        def _matches_pattern(filename: str, patterns: Optional[List[str]]) -> bool:
            """Check if filename matches any pattern."""
            if patterns is None:
                return True
            import fnmatch
            return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)

        def _recursive_download(remote_subdir: str, local_subdir: str) -> None:
            nonlocal files_downloaded
            try:
                for item in self.sftp_client.listdir_attr(remote_subdir):
                    remote_path = f"{remote_subdir}/{item.filename}"
                    local_path = os.path.join(local_subdir, item.filename)

                    if stat.S_ISDIR(item.st_mode):
                        os.makedirs(local_path, exist_ok=True)
                        _recursive_download(remote_path, local_path)
                    else:
                        if _matches_pattern(item.filename, patterns):
                            try:
                                self.download_file(remote_path, local_path, callback)
                                files_downloaded += 1
                            except IOError as e:
                                raise IOError(f"Failed to download file {remote_path}: {e}")
            except Exception as e:
                raise IOError(f"Error downloading directory {remote_subdir}: {e}")

        _recursive_download(remote_dir, local_dir)
        return files_downloaded

    def upload_directory(
        self,
        local_dir: str,
        remote_dir: str,
        patterns: Optional[List[str]] = None,
        callback: Optional[Callable] = None,
    ) -> int:
        """
        Recursively upload directory to remote server.

        Args:
            local_dir: Local directory path
            remote_dir: Remote directory path
            patterns: Optional list of filename patterns to include (e.g., ['*.csv', '*.txt']).
                     If None, uploads all files.
            callback: Optional callback(bytes_transferred, total_bytes) for progress

        Returns:
            Number of files uploaded

        Raises:
            IOError: If upload fails
            FileNotFoundError: If local directory not found
        """
        if not self.connected or not self.sftp_client:
            raise IOError("Not connected to SSH server")

        if not os.path.isdir(local_dir):
            raise FileNotFoundError(f"Local directory not found: {local_dir}")

        self._ensure_remote_dir_exists(remote_dir)
        files_uploaded = 0

        def _matches_pattern(filename: str, patterns: Optional[List[str]]) -> bool:
            """Check if filename matches any pattern."""
            if patterns is None:
                return True
            import fnmatch
            return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)

        def _recursive_upload(local_subdir: str, remote_subdir: str) -> None:
            nonlocal files_uploaded
            try:
                for item in os.listdir(local_subdir):
                    local_path = os.path.join(local_subdir, item)
                    remote_path = f"{remote_subdir}/{item}"

                    if os.path.isdir(local_path):
                        self._ensure_remote_dir_exists(remote_path)
                        _recursive_upload(local_path, remote_path)
                    else:
                        if _matches_pattern(item, patterns):
                            try:
                                self.upload_file(local_path, remote_path, callback)
                                files_uploaded += 1
                            except IOError as e:
                                raise IOError(f"Failed to upload file {local_path}: {e}")
            except Exception as e:
                raise IOError(f"Error uploading directory {local_subdir}: {e}")

        _recursive_upload(local_dir, remote_dir)
        return files_uploaded

    def _ensure_remote_dir_exists(self, remote_path: str) -> None:
        """Create remote directory if it doesn't exist."""
        if not self.sftp_client:
            return
        try:
            self.sftp_client.stat(remote_path)
        except FileNotFoundError:
            try:
                self.sftp_client.mkdir(remote_path)
            except Exception:
                pass

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
