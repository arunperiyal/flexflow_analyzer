"""Tests for SSH/SFTP client wrapper."""

import os
import stat
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from src.utils.ssh_client import SSHClientWrapper
import paramiko


class TestSSHClientWrapper:
    """Test suite for SSHClientWrapper."""

    @pytest.fixture
    def ssh_wrapper(self):
        """Create SSHClientWrapper instance for testing."""
        return SSHClientWrapper(
            host="192.168.1.100",
            username="testuser",
            password="testpass",
            port=22,
        )

    def test_init(self, ssh_wrapper):
        """Test initialization."""
        assert ssh_wrapper.host == "192.168.1.100"
        assert ssh_wrapper.username == "testuser"
        assert ssh_wrapper.password == "testpass"
        assert ssh_wrapper.port == 22
        assert not ssh_wrapper.connected

    def test_init_custom_port(self):
        """Test initialization with custom port."""
        wrapper = SSHClientWrapper(
            host="remote.example.com",
            username="user",
            password="pass",
            port=2222,
        )
        assert wrapper.port == 2222

    @patch("src.utils.ssh_client.SSHClient")
    def test_connect_success(self, mock_ssh_class, ssh_wrapper):
        """Test successful SSH connection."""
        mock_ssh = Mock()
        mock_sftp = Mock()
        mock_ssh.open_sftp.return_value = mock_sftp
        mock_ssh_class.return_value = mock_ssh

        result = ssh_wrapper.connect()

        assert result is True
        assert ssh_wrapper.connected is True
        mock_ssh.set_missing_host_key_policy.assert_called_once()
        mock_ssh.connect.assert_called_once_with(
            "192.168.1.100",
            port=22,
            username="testuser",
            password="testpass",
            timeout=10,
        )
        mock_ssh.open_sftp.assert_called_once()

    @patch("src.utils.ssh_client.SSHClient")
    def test_connect_authentication_failure(self, mock_ssh_class, ssh_wrapper):
        """Test SSH authentication failure."""
        mock_ssh = Mock()
        mock_ssh.connect.side_effect = paramiko.AuthenticationException("Auth failed")
        mock_ssh_class.return_value = mock_ssh

        with pytest.raises(paramiko.AuthenticationException):
            ssh_wrapper.connect()

        assert not ssh_wrapper.connected

    @patch("src.utils.ssh_client.SSHClient")
    def test_connect_ssh_failure(self, mock_ssh_class, ssh_wrapper):
        """Test SSH connection failure."""
        mock_ssh = Mock()
        mock_ssh.connect.side_effect = paramiko.SSHException("Connection refused")
        mock_ssh_class.return_value = mock_ssh

        with pytest.raises(paramiko.SSHException):
            ssh_wrapper.connect()

    @patch("src.utils.ssh_client.SSHClient")
    def test_disconnect(self, mock_ssh_class, ssh_wrapper):
        """Test disconnection."""
        mock_ssh = Mock()
        mock_sftp = Mock()
        ssh_wrapper.ssh_client = mock_ssh
        ssh_wrapper.sftp_client = mock_sftp
        ssh_wrapper.connected = True

        ssh_wrapper.disconnect()

        mock_sftp.close.assert_called_once()
        mock_ssh.close.assert_called_once()
        assert not ssh_wrapper.connected

    @patch("src.utils.ssh_client.SSHClient")
    def test_disconnect_no_clients(self, mock_ssh_class, ssh_wrapper):
        """Test disconnection when clients are None."""
        ssh_wrapper.connected = False
        ssh_wrapper.disconnect()  # Should not raise error
        assert not ssh_wrapper.connected

    @patch("src.utils.ssh_client.SSHClient")
    def test_remote_path_exists_true(self, mock_ssh_class, ssh_wrapper):
        """Test checking if remote path exists (exists)."""
        mock_ssh = Mock()
        mock_sftp = Mock()
        mock_sftp.stat.return_value = Mock()
        ssh_wrapper.ssh_client = mock_ssh
        ssh_wrapper.sftp_client = mock_sftp
        ssh_wrapper.connected = True

        assert ssh_wrapper.remote_path_exists("/remote/path")
        mock_sftp.stat.assert_called_once_with("/remote/path")

    @patch("src.utils.ssh_client.SSHClient")
    def test_remote_path_exists_false(self, mock_ssh_class, ssh_wrapper):
        """Test checking if remote path exists (doesn't exist)."""
        mock_ssh = Mock()
        mock_sftp = Mock()
        mock_sftp.stat.side_effect = FileNotFoundError()
        ssh_wrapper.ssh_client = mock_ssh
        ssh_wrapper.sftp_client = mock_sftp
        ssh_wrapper.connected = True

        assert not ssh_wrapper.remote_path_exists("/remote/path")

    @patch("src.utils.ssh_client.SSHClient")
    def test_remote_path_exists_not_connected(self, mock_ssh_class, ssh_wrapper):
        """Test checking remote path when not connected."""
        assert not ssh_wrapper.remote_path_exists("/remote/path")

    @patch("src.utils.ssh_client.SSHClient")
    def test_remote_is_dir_true(self, mock_ssh_class, ssh_wrapper):
        """Test checking if remote path is directory (is dir)."""
        mock_ssh = Mock()
        mock_sftp = Mock()
        mock_stat_result = Mock()
        mock_stat_result.st_mode = 0o40755  # Directory mode
        mock_sftp.stat.return_value = mock_stat_result
        ssh_wrapper.ssh_client = mock_ssh
        ssh_wrapper.sftp_client = mock_sftp
        ssh_wrapper.connected = True

        with patch("stat.S_ISDIR", return_value=True):
            assert ssh_wrapper.remote_is_dir("/remote/dir")

    @patch("src.utils.ssh_client.SSHClient")
    def test_remote_is_dir_false(self, mock_ssh_class, ssh_wrapper):
        """Test checking if remote path is directory (is file)."""
        mock_ssh = Mock()
        mock_sftp = Mock()
        mock_stat_result = Mock()
        mock_stat_result.st_mode = 0o100644  # File mode
        mock_sftp.stat.return_value = mock_stat_result
        ssh_wrapper.ssh_client = mock_ssh
        ssh_wrapper.sftp_client = mock_sftp
        ssh_wrapper.connected = True

        with patch("stat.S_ISDIR", return_value=False):
            assert not ssh_wrapper.remote_is_dir("/remote/file")

    @patch("src.utils.ssh_client.SSHClient")
    def test_upload_file_success(self, mock_ssh_class, ssh_wrapper):
        """Test successful file upload."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        try:
            mock_ssh = Mock()
            mock_sftp = Mock()
            ssh_wrapper.ssh_client = mock_ssh
            ssh_wrapper.sftp_client = mock_sftp
            ssh_wrapper.connected = True

            ssh_wrapper.upload_file(tmp_path, "/remote/file.txt")

            mock_sftp.put.assert_called_once_with(tmp_path, "/remote/file.txt", callback=None)
        finally:
            os.unlink(tmp_path)

    @patch("src.utils.ssh_client.SSHClient")
    def test_upload_file_not_connected(self, mock_ssh_class, ssh_wrapper):
        """Test upload file when not connected."""
        ssh_wrapper.connected = False

        with pytest.raises(IOError, match="Not connected"):
            ssh_wrapper.upload_file("/local/file", "/remote/file")

    def test_upload_file_local_not_found(self, ssh_wrapper):
        """Test upload file when local file doesn't exist."""
        ssh_wrapper.connected = True
        ssh_wrapper.sftp_client = Mock()

        with pytest.raises(FileNotFoundError):
            ssh_wrapper.upload_file("/nonexistent/file", "/remote/file")

    @patch("src.utils.ssh_client.SSHClient")
    def test_download_file_success(self, mock_ssh_class, ssh_wrapper):
        """Test successful file download."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_ssh = Mock()
            mock_sftp = Mock()
            ssh_wrapper.ssh_client = mock_ssh
            ssh_wrapper.sftp_client = mock_sftp
            ssh_wrapper.connected = True

            local_path = os.path.join(tmpdir, "downloaded_file.txt")
            ssh_wrapper.download_file("/remote/file.txt", local_path)

            mock_sftp.get.assert_called_once_with("/remote/file.txt", local_path, callback=None)

    @patch("src.utils.ssh_client.SSHClient")
    def test_download_file_not_connected(self, mock_ssh_class, ssh_wrapper):
        """Test download file when not connected."""
        ssh_wrapper.connected = False

        with pytest.raises(IOError, match="Not connected"):
            ssh_wrapper.download_file("/remote/file", "/local/file")

    @patch("src.utils.ssh_client.SSHClient")
    def test_download_file_remote_not_found(self, mock_ssh_class, ssh_wrapper):
        """Test download file when remote file doesn't exist."""
        mock_ssh = Mock()
        mock_sftp = Mock()
        mock_sftp.stat.side_effect = FileNotFoundError()
        ssh_wrapper.ssh_client = mock_ssh
        ssh_wrapper.sftp_client = mock_sftp
        ssh_wrapper.connected = True

        with pytest.raises(FileNotFoundError):
            ssh_wrapper.download_file("/nonexistent/file", "/local/file")

    @patch("src.utils.ssh_client.SSHClient")
    def test_list_remote_dir_success(self, mock_ssh_class, ssh_wrapper):
        """Test listing remote directory."""
        mock_ssh = Mock()
        mock_sftp = Mock()
        mock_sftp.listdir.return_value = ["file1.txt", "file2.txt", "subdir"]
        ssh_wrapper.ssh_client = mock_ssh
        ssh_wrapper.sftp_client = mock_sftp
        ssh_wrapper.connected = True

        files = ssh_wrapper.list_remote_dir("/remote/dir")

        assert files == ["file1.txt", "file2.txt", "subdir"]
        mock_sftp.listdir.assert_called_once_with("/remote/dir")

    @patch("src.utils.ssh_client.SSHClient")
    def test_list_remote_dir_not_connected(self, mock_ssh_class, ssh_wrapper):
        """Test listing remote directory when not connected."""
        ssh_wrapper.connected = False

        with pytest.raises(IOError, match="Not connected"):
            ssh_wrapper.list_remote_dir("/remote/dir")

    @patch("src.utils.ssh_client.SSHClient")
    def test_context_manager(self, mock_ssh_class, ssh_wrapper):
        """Test context manager functionality."""
        mock_ssh = Mock()
        mock_sftp = Mock()
        mock_ssh.open_sftp.return_value = mock_sftp
        mock_ssh_class.return_value = mock_ssh

        with SSHClientWrapper(
            host="test.com", username="user", password="pass"
        ) as client:
            assert client.connected is True

        assert client.connected is False
        mock_sftp.close.assert_called_once()
        mock_ssh.close.assert_called_once()

    @patch("src.utils.ssh_client.SSHClient")
    def test_download_directory_success(self, mock_ssh_class, ssh_wrapper):
        """Test successful directory download."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_ssh = Mock()
            mock_sftp = Mock()

            # Mock directory structure
            mock_attr_dir = Mock()
            mock_attr_dir.filename = "subdir"
            mock_attr_dir.st_mode = 0o40755  # Directory

            mock_attr_file = Mock()
            mock_attr_file.filename = "file.txt"
            mock_attr_file.st_mode = 0o100644  # File

            mock_sftp.listdir_attr.return_value = [mock_attr_file]
            mock_sftp.stat.side_effect = lambda x: mock_attr_file

            ssh_wrapper.ssh_client = mock_ssh
            ssh_wrapper.sftp_client = mock_sftp
            ssh_wrapper.connected = True

            with patch.object(ssh_wrapper, "remote_path_exists", return_value=True):
                with patch.object(ssh_wrapper, "remote_is_dir", return_value=True):
                    with patch.object(
                        ssh_wrapper, "download_file"
                    ) as mock_download:
                        count = ssh_wrapper.download_directory(
                            "/remote/dir", tmpdir
                        )

                        assert count >= 0

    @patch("src.utils.ssh_client.SSHClient")
    def test_download_directory_not_connected(self, mock_ssh_class, ssh_wrapper):
        """Test download directory when not connected."""
        ssh_wrapper.connected = False

        with pytest.raises(IOError, match="Not connected"):
            ssh_wrapper.download_directory("/remote/dir", "/local/dir")

    @patch("src.utils.ssh_client.SSHClient")
    def test_download_directory_not_found(self, mock_ssh_class, ssh_wrapper):
        """Test download directory when remote path not found."""
        mock_ssh = Mock()
        mock_sftp = Mock()
        mock_sftp.stat.side_effect = FileNotFoundError()
        ssh_wrapper.ssh_client = mock_ssh
        ssh_wrapper.sftp_client = mock_sftp
        ssh_wrapper.connected = True

        with pytest.raises(FileNotFoundError):
            ssh_wrapper.download_directory("/nonexistent/dir", "/local/dir")

    @patch("src.utils.ssh_client.SSHClient")
    def test_download_directory_not_a_directory(self, mock_ssh_class, ssh_wrapper):
        """Test download directory when remote path is not a directory."""
        mock_ssh = Mock()
        mock_sftp = Mock()
        mock_sftp.stat.return_value = Mock(st_mode=0o100644)  # File mode
        ssh_wrapper.ssh_client = mock_ssh
        ssh_wrapper.sftp_client = mock_sftp
        ssh_wrapper.connected = True

        with patch.object(ssh_wrapper, "remote_path_exists", return_value=True):
            with patch.object(ssh_wrapper, "remote_is_dir", return_value=False):
                with pytest.raises(IOError, match="not a directory"):
                    ssh_wrapper.download_directory("/remote/file", "/local/dir")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
