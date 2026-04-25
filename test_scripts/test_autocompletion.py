"""Tests for autocompletion of new commands."""

import pytest
from src.cli.interactive import FlexFlowCompleter
from src.cli.registry import registry
from unittest.mock import Mock, patch


class TestAutocompletion:
    """Test autocompletion for new commands."""

    @pytest.fixture
    def completer(self):
        """Create FlexFlowCompleter instance."""
        completer = FlexFlowCompleter()
        # Manually add commands to the completer if not registered
        if not hasattr(completer, 'commands') or 'case' not in completer.commands:
            completer.commands = {
                'case': 'Case operations',
                'remote': 'Remote machine management',
                'run': 'Run and monitor jobs',
                'data': 'Work with time-series data',
                'field': 'Work with Tecplot PLT files',
                'template': 'Generate configuration templates',
                'plot': 'Create plots',
                'compare': 'Compare multiple cases',
                'check': 'Inspect OTHD/OISD data files',
                'docs': 'View documentation',
            }
        return completer

    def test_remote_subcommands_exist(self, completer):
        """Test that remote subcommands are defined."""
        assert 'remote' in completer._SUBCOMMANDS
        assert 'add' in completer._SUBCOMMANDS['remote']
        assert 'modify' in completer._SUBCOMMANDS['remote']
        assert 'delete' in completer._SUBCOMMANDS['remote']
        assert 'list' in completer._SUBCOMMANDS['remote']
        assert 'set-path' in completer._SUBCOMMANDS['remote']

    def test_case_download_exists(self, completer):
        """Test that case download is available."""
        assert 'download' in completer._SUBCOMMANDS['case']

    def test_case_download_flags_defined(self, completer):
        """Test flags for case download are defined."""
        flags = completer._flags_for('case', 'download')
        assert '--to' in flags
        assert '--dir' in flags
        assert '--remote-path' in flags
        assert '--help' in flags

    def test_remote_add_flags_defined(self, completer):
        """Test flags for remote add are defined."""
        flags = completer._flags_for('remote', 'add')
        assert '--user' in flags
        assert '--ip' in flags
        assert '--password' in flags
        assert '--port' in flags

    def test_remote_modify_flags_defined(self, completer):
        """Test flags for remote modify are defined."""
        flags = completer._flags_for('remote', 'modify')
        assert '--user' in flags
        assert '--ip' in flags
        assert '--password' in flags
        assert '--port' in flags

    def test_remote_delete_flags_defined(self, completer):
        """Test flags for remote delete are defined."""
        flags = completer._flags_for('remote', 'delete')
        assert '--help' in flags

    def test_remote_list_flags_defined(self, completer):
        """Test flags for remote list are defined."""
        flags = completer._flags_for('remote', 'list')
        assert '--help' in flags

    def test_run_sq_by_dir_flag_defined(self, completer):
        """Test --by-dir flag in run sq is defined."""
        flags = completer._flags_for('run', 'sq')
        assert '--by-dir' in flags
        assert '--all' in flags
        assert '--watch' in flags

    def test_subcommands_in_completer(self, completer):
        """Test that subcommands dict is properly updated."""
        # Verify that both 'remote' and 'download' are in the subcommands dict
        assert 'remote' in completer._SUBCOMMANDS
        assert 'download' in completer._SUBCOMMANDS['case']
        assert 'add' in completer._SUBCOMMANDS['remote']
        assert 'list' in completer._SUBCOMMANDS['remote']

    def test_flags_for_remote_commands(self, completer):
        """Test that flags are defined for remote commands."""
        # Get flags for remote add
        add_flags = completer._flags_for('remote', 'add')
        assert '--user' in add_flags
        assert '--ip' in add_flags
        assert '--password' in add_flags
        assert add_flags['--user'] == 'SSH username (required)'
        
        # Get flags for remote list
        list_flags = completer._flags_for('remote', 'list')
        assert '--help' in list_flags

    def test_flags_for_case_download(self, completer):
        """Test that flags are defined for case download."""
        download_flags = completer._flags_for('case', 'download')
        assert '--to' in download_flags
        assert '--dir' in download_flags
        assert '--remote-path' in download_flags
        assert download_flags['--to'] == 'Remote machine name (required)'

    def test_flag_descriptions(self, completer):
        """Test that flag descriptions are meaningful."""
        # Remote add flags
        add_flags = completer._flags_for('remote', 'add')
        assert len(add_flags['--user']) > 0
        assert len(add_flags['--ip']) > 0
        assert 'required' in add_flags['--ip'].lower()
        
        # Case download flags
        download_flags = completer._flags_for('case', 'download')
        assert len(download_flags['--to']) > 0
        assert 'required' in download_flags['--to'].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

