"""Tests for case upload command."""

import os
import pytest
import tempfile
from unittest.mock import Mock, patch, MagicMock
from src.commands.case.download_impl.command import CaseDownloadCommand
from src.utils.remote_config import RemoteConfig


class TestCaseDownloadCommand:
    """Test suite for case upload command."""

    @pytest.fixture
    def download_cmd(self):
        """Create CaseDownloadCommand instance."""
        return CaseDownloadCommand()

    @pytest.fixture
    def mock_remote_config(self):
        """Create mock remote config."""
        with patch.object(RemoteConfig, 'remote_exists', return_value=True):
            with patch.object(RemoteConfig, 'get_remote', return_value={
                'user': 'testuser',
                'ip': '192.168.1.100',
                'port': 22,
                'password': 'testpass',
                'path': '/home/testuser/cases'
            }):
                yield RemoteConfig()

    def test_init(self, download_cmd):
        """Test initialization."""
        assert download_cmd.console is not None
        assert download_cmd.remote_config is not None

    def test_validate_remote_success(self, download_cmd):
        """Test successful remote validation."""
        with patch.object(
            download_cmd.remote_config,
            'remote_exists',
            return_value=True
        ):
            with patch.object(
                download_cmd.remote_config,
                'get_remote',
                return_value={'user': 'test', 'ip': '192.168.1.1', 'port': 22}
            ):
                result = download_cmd.validate_remote('test-remote')
                assert result is not None
                assert result['user'] == 'test'

    def test_validate_remote_not_found(self, download_cmd, capsys):
        """Test remote not found."""
        with patch.object(
            download_cmd.remote_config,
            'remote_exists',
            return_value=False
        ):
            result = download_cmd.validate_remote('nonexistent')
            assert result is None

    def test_validate_case_path_empty(self, download_cmd, capsys):
        """Test empty case path."""
        result = download_cmd.validate_case_path('')
        assert result is None or result == ''

    def test_validate_case_path_with_tilde(self, download_cmd):
        """Test case path with tilde expansion."""
        result = download_cmd.validate_case_path('~/mycase')
        assert result is not None
        assert '~' not in result
        assert result.startswith(os.path.expanduser('~'))

    def test_parse_directories_default(self, download_cmd):
        """Test default directories."""
        result = download_cmd.parse_directories(None)
        assert result == ["othd_files", "oisd_files", "binary"]

    def test_parse_directories_custom(self, download_cmd):
        """Test custom directories."""
        result = download_cmd.parse_directories("othd_files,oisd_files")
        assert result == ["othd_files", "oisd_files"]

    def test_parse_directories_with_whitespace(self, download_cmd):
        """Test directories with whitespace."""
        result = download_cmd.parse_directories(" othd_files , oisd_files ")
        assert result == ["othd_files", "oisd_files"]

    def test_parse_directories_empty_string(self, download_cmd):
        """Test empty directory string."""
        result = download_cmd.parse_directories("")
        assert result == ["othd_files", "oisd_files", "binary"]

    def test_get_remote_base_path_override(self, download_cmd):
        """Test remote base path with override."""
        remote = {'path': '/default/path'}
        result = download_cmd.get_remote_base_path(remote, '/override/path')
        assert result == '/override/path'

    def test_get_remote_base_path_from_config(self, download_cmd):
        """Test remote base path from config."""
        remote = {'path': '/home/user/cases'}
        result = download_cmd.get_remote_base_path(remote, None)
        assert result == '/home/user/cases'

    def test_get_remote_base_path_default(self, download_cmd):
        """Test remote base path default."""
        remote = {}
        result = download_cmd.get_remote_base_path(remote, None)
        assert result == '~'

    def test_construct_remote_case_path(self, download_cmd):
        """Test constructing remote case path."""
        result = download_cmd.construct_remote_case_path(
            '/home/user/cases',
            '/local/path/myCase'
        )
        assert result == '/home/user/cases/myCase'

    def test_construct_remote_case_path_with_trailing_slash(self, download_cmd):
        """Test constructing remote case path with trailing slash."""
        result = download_cmd.construct_remote_case_path(
            '/home/user/cases',
            '/local/path/myCase/'
        )
        assert result == '/home/user/cases/myCase'

    def test_upload_directory_success(self, download_cmd):
        """Test successful directory upload."""
        mock_ssh = Mock()
        mock_ssh.remote_path_exists.return_value = True
        mock_ssh.remote_is_dir.return_value = True
        mock_ssh.download_directory.return_value = 5

        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, 'othd_files'), exist_ok=True)
            result = download_cmd.download_directory(
                mock_ssh,
                '/remote/case',
                tmpdir,
                'othd_files'
            )
            assert result is True
            mock_ssh.remote_path_exists.assert_called_once_with('/remote/case/othd_files')
            mock_ssh.remote_is_dir.assert_called_once_with('/remote/case/othd_files')

    def test_upload_directory_remote_not_exists(self, download_cmd, capsys):
        """Test upload when remote directory doesn't exist and force is false."""
        mock_ssh = Mock()
        mock_ssh.remote_path_exists.return_value = False

        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, 'othd_files'), exist_ok=True)
            result = download_cmd.download_directory(
                mock_ssh,
                '/remote/case',
                tmpdir,
                'othd_files'
            )
            assert result is False

    def test_upload_directory_local_not_exists(self, download_cmd, capsys):
        """Test upload when local directory doesn't exist."""
        mock_ssh = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_cmd.download_directory(
                mock_ssh,
                '/remote/case',
                tmpdir,
                'othd_files'
            )
            assert result is False

    def test_upload_directory_remote_not_a_dir(self, download_cmd, capsys):
        """Test upload when remote path is not a directory."""
        mock_ssh = Mock()
        mock_ssh.remote_path_exists.return_value = True
        mock_ssh.remote_is_dir.return_value = False

        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, 'othd_files'), exist_ok=True)
            result = download_cmd.download_directory(
                mock_ssh,
                '/remote/case',
                tmpdir,
                'othd_files'
            )
            assert result is False

    def test_upload_directory_transfer_error(self, download_cmd, capsys):
        """Test upload with transfer error."""
        mock_ssh = Mock()
        mock_ssh.remote_path_exists.return_value = True
        mock_ssh.remote_is_dir.return_value = True
        mock_ssh.upload_directory.side_effect = IOError("Transfer failed")

        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, 'othd_files'), exist_ok=True)
            result = download_cmd.download_directory(
                mock_ssh,
                '/remote/case',
                tmpdir,
                'othd_files'
            )
            assert result is False

    def test_upload_directory_remote_not_exists_with_force(self, download_cmd):
        """Test upload when remote directory doesn't exist but force is true."""
        mock_ssh = Mock()
        mock_ssh.remote_path_exists.return_value = False
        mock_ssh.make_remote_dir.return_value = True
        mock_ssh.remote_is_dir.return_value = True
        mock_ssh.upload_directory.return_value = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, 'othd_files'), exist_ok=True)
            result = download_cmd.download_directory(
                mock_ssh,
                '/remote/case',
                tmpdir,
                'othd_files',
                force=True
            )
            assert result is True
            mock_ssh.make_remote_dir.assert_called_once_with('/remote/case/othd_files')

    def test_execute_download_no_case(self, download_cmd, capsys):
        """Test execute with no case argument."""
        args = Mock()
        args.case = None
        args.to = 'remote'
        args.force = False

        result = download_cmd.execute_download(args)
        assert result == 1

    def test_execute_download_invalid_remote(self, download_cmd):
        """Test execute with invalid remote."""
        with tempfile.TemporaryDirectory() as tmpdir:
            case_path = os.path.join(tmpdir, 'mycase')
            os.makedirs(case_path, exist_ok=True)

            args = Mock()
            args.case = case_path
            args.to = 'nonexistent'
            args.dir = None
            args.remote_path = None
            args.force = False

            with patch.object(
                download_cmd.remote_config,
                'remote_exists',
                return_value=False
            ):
                result = download_cmd.execute_download(args)
                assert result == 1

    def test_execute_download_wildcard_no_cases(self, download_cmd):
        """Test wildcard upload when .cases is empty."""
        args = Mock()
        args.case = '*'
        args.to = 'test-remote'
        args.dir = 'othd_files'
        args.remote_path = None
        args.force = False

        with patch.object(
            download_cmd.remote_config,
            'remote_exists',
            return_value=True
        ):
            with patch.object(
                download_cmd.remote_config,
                'get_remote',
                return_value={
                    'user': 'testuser',
                    'ip': '192.168.1.100',
                    'port': 22,
                    'password': 'testpass',
                    'path': '/home/testuser'
                }
            ):
                with patch('src.commands.case.download_impl.command.load_cases_from_directory', return_value=[]):
                    result = download_cmd.execute_download(args)
                    assert result == 1

    @patch('src.commands.case.download_impl.command.SSHClientWrapper')
    def test_execute_download_wildcard_success(self, mock_ssh_class, download_cmd):
        """Test wildcard upload iterates over all cases."""
        mock_ssh = Mock()
        mock_ssh.remote_path_exists.return_value = True
        mock_ssh.remote_is_dir.return_value = True
        mock_ssh.download_directory.return_value = 3
        mock_ssh_class.return_value = mock_ssh

        args = Mock()
        args.case = '*'
        args.to = 'test-remote'
        args.dir = 'othd_files'
        args.remote_path = None
        args.force = False

        with tempfile.TemporaryDirectory() as tmpdir:
            case1 = os.path.join(tmpdir, 'Case001')
            case2 = os.path.join(tmpdir, 'Case002')
            os.makedirs(os.path.join(case1, 'othd_files'), exist_ok=True)
            os.makedirs(os.path.join(case2, 'othd_files'), exist_ok=True)
            cases = [
                {'name': 'Case001', 'path': case1},
                {'name': 'Case002', 'path': case2},
            ]

            with patch.object(
                download_cmd.remote_config,
                'remote_exists',
                return_value=True
            ):
                with patch.object(
                    download_cmd.remote_config,
                    'get_remote',
                    return_value={
                        'user': 'testuser',
                        'ip': '192.168.1.100',
                        'port': 22,
                        'password': 'testpass',
                        'path': '/home/testuser'
                    }
                ):
                    with patch('src.commands.case.download_impl.command.load_cases_from_directory', return_value=cases):
                        result = download_cmd.execute_download(args)
                        assert result == 0
                        assert mock_ssh.download_directory.call_count == 2

    @patch('src.commands.case.download_impl.command.SSHClientWrapper')
    def test_execute_download_success(self, mock_ssh_class, download_cmd):
        """Test successful download execution."""
        mock_ssh = Mock()
        mock_ssh.remote_path_exists.return_value = True
        mock_ssh.remote_is_dir.return_value = True
        mock_ssh.download_directory.return_value = 5
        mock_ssh_class.return_value = mock_ssh

        args = Mock()
        args.case = './mycase'
        args.to = 'test-remote'
        args.dir = 'othd_files'
        args.remote_path = None
        args.force = False

        with tempfile.TemporaryDirectory() as tmpdir:
            args.case = os.path.join(tmpdir, 'mycase')
            os.makedirs(os.path.join(args.case, 'othd_files'), exist_ok=True)

            with patch.object(
                download_cmd.remote_config,
                'remote_exists',
                return_value=True
            ):
                with patch.object(
                    download_cmd.remote_config,
                    'get_remote',
                    return_value={
                        'user': 'testuser',
                        'ip': '192.168.1.100',
                        'port': 22,
                        'password': 'testpass',
                        'path': '/home/testuser'
                    }
                ):
                    result = download_cmd.execute_download(args)
                    assert result == 0

    @patch('src.commands.case.download_impl.command.SSHClientWrapper')
    def test_execute_download_connection_error(self, mock_ssh_class, download_cmd):
        """Test download with connection error."""
        mock_ssh = Mock()
        mock_ssh.connect.side_effect = Exception("Connection failed")
        mock_ssh_class.return_value = mock_ssh

        args = Mock()
        args.case = './mycase'
        args.to = 'test-remote'
        args.dir = None
        args.remote_path = None
        args.force = False

        with tempfile.TemporaryDirectory() as tmpdir:
            args.case = os.path.join(tmpdir, 'mycase')
            os.makedirs(args.case, exist_ok=True)

            with patch.object(
                download_cmd.remote_config,
                'remote_exists',
                return_value=True
            ):
                with patch.object(
                    download_cmd.remote_config,
                    'get_remote',
                    return_value={
                        'user': 'testuser',
                        'ip': '192.168.1.100',
                        'port': 22,
                        'password': 'testpass',
                        'path': '/home/testuser'
                    }
                ):
                    result = download_cmd.execute_download(args)
                    assert result == 1


    def test_transfer_state_round_trip(self, download_cmd, tmp_path):
        state_file = tmp_path / 'transfer_state.json'
        download_cmd._get_transfer_state_file = lambda: state_file

        state = {
            'direction': 'download',
            'status': 'interrupted',
            'remote_name': 'test-remote',
            'remote_base_path': '/home/testuser/cases',
            'case_selection': './mycase',
            'case_mode': 'single',
            'directories': ['othd_files', 'binary'],
            'force': False,
            'cases': [{'name': 'mycase', 'path': '/tmp/mycase'}],
            'completed_targets': ['/tmp/mycase::othd_files'],
        }

        download_cmd._save_transfer_state(state)
        loaded = download_cmd._load_transfer_state()

        assert loaded == state

    @patch('src.commands.case.download_impl.command.SSHClientWrapper')
    def test_execute_download_resume_skips_completed_targets(self, mock_ssh_class, download_cmd, tmp_path):
        state_file = tmp_path / 'transfer_state.json'
        download_cmd._get_transfer_state_file = lambda: state_file

        mock_ssh = Mock()
        mock_ssh.connect.return_value = True
        mock_ssh.disconnect.return_value = None
        mock_ssh_class.return_value = mock_ssh

        case_path = tmp_path / 'mycase'
        case_path.mkdir()
        (case_path / 'othd_files').mkdir()
        (case_path / 'binary').mkdir()

        state = {
            'direction': 'download',
            'status': 'interrupted',
            'remote_name': 'test-remote',
            'remote_base_path': '/home/testuser/cases',
            'case_selection': str(case_path),
            'case_mode': 'single',
            'directories': ['othd_files', 'binary'],
            'force': False,
            'cases': [{'name': 'mycase', 'path': str(case_path)}],
            'completed_targets': [f'{case_path}::othd_files'],
        }
        download_cmd._save_transfer_state(state)

        args = Mock()
        args.case = None
        args.from_remote = None
        args.dir = None
        args.remote_path = None
        args.force = False
        args.resume = True
        args.help = False
        args.examples = False

        with patch.object(download_cmd, 'validate_remote', return_value={
            'user': 'testuser',
            'ip': '192.168.1.100',
            'port': 22,
            'password': 'testpass',
            'path': '/home/testuser/cases'
        }):
            with patch.object(download_cmd, 'download_case_directory', return_value=True) as mock_download:
                result = download_cmd.execute_download(args)

        assert result == 0
        assert mock_download.call_count == 1
        assert mock_download.call_args.args[3] == 'binary'
        assert not state_file.exists()

    @patch('src.commands.case.download_impl.command.SSHClientWrapper')
    def test_execute_upload_resume_skips_completed_targets(self, mock_ssh_class, download_cmd, tmp_path):
        state_file = tmp_path / 'transfer_state.json'
        download_cmd._get_transfer_state_file = lambda: state_file

        mock_ssh = Mock()
        mock_ssh.connect.return_value = True
        mock_ssh.disconnect.return_value = None
        mock_ssh_class.return_value = mock_ssh

        case_path = tmp_path / 'mycase'
        case_path.mkdir()
        (case_path / 'othd_files').mkdir()
        (case_path / 'binary').mkdir()

        state = {
            'direction': 'upload',
            'status': 'interrupted',
            'remote_name': 'test-remote',
            'remote_base_path': '/home/testuser/cases',
            'case_selection': str(case_path),
            'case_mode': 'single',
            'directories': ['othd_files', 'binary'],
            'force': False,
            'cases': [{'name': 'mycase', 'path': str(case_path)}],
            'completed_targets': [f'{case_path}::othd_files'],
        }
        download_cmd._save_transfer_state(state)

        args = Mock()
        args.case = None
        args.to = None
        args.dir = None
        args.remote_path = None
        args.force = False
        args.resume = True
        args.help = False
        args.examples = False

        with patch.object(download_cmd, 'validate_remote', return_value={
            'user': 'testuser',
            'ip': '192.168.1.100',
            'port': 22,
            'password': 'testpass',
            'path': '/home/testuser/cases'
        }):
            with patch.object(download_cmd, 'upload_directory', return_value=True) as mock_upload:
                result = download_cmd.execute_upload(args)

        assert result == 0
        assert mock_upload.call_count == 1
        assert mock_upload.call_args.args[3] == 'binary'
        assert not state_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
