"""Tests for autocompletion of new commands."""

import pytest
from src.cli.interactive import FlexFlowCompleter
from src.cli.registry import registry
from unittest.mock import Mock, patch
from prompt_toolkit.document import Document


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

    def test_case_upload_exists(self, completer):
        """Test that case upload is available."""
        assert 'upload' in completer._SUBCOMMANDS['case']

    def test_case_upload_flags_defined(self, completer):
        """Test flags for case upload are defined."""
        flags = completer._flags_for('case', 'upload')
        assert '--to' in flags
        assert '--dir' in flags
        assert '--remote-path' in flags
        assert '--force' in flags
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
        assert '--sort' in flags
        assert '--out' in flags
        assert '--lines' in flags
        assert '-n' in flags

    def test_run_main_np_flags_defined(self, completer):
        """Test -n/--np flags in run main are defined."""
        flags = completer._flags_for('run', 'main')
        assert '--np' in flags
        assert '-n' in flags

    def test_subcommands_in_completer(self, completer):
        """Test that subcommands dict is properly updated."""
        # Verify that both 'remote' and 'upload' are in the subcommands dict
        assert 'remote' in completer._SUBCOMMANDS
        assert 'upload' in completer._SUBCOMMANDS['case']
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

    def test_flags_for_case_upload(self, completer):
        """Test that flags are defined for case upload."""
        upload_flags = completer._flags_for('case', 'upload')
        assert '--to' in upload_flags
        assert '--dir' in upload_flags
        assert '--remote-path' in upload_flags
        assert '--force' in upload_flags
        assert 'remote:<name>' in upload_flags['--to']

    def test_flag_descriptions(self, completer):
        """Test that flag descriptions are meaningful."""
        # Remote add flags
        add_flags = completer._flags_for('remote', 'add')
        assert len(add_flags['--user']) > 0
        assert len(add_flags['--ip']) > 0
        assert 'required' in add_flags['--ip'].lower()
        
        # Case upload flags
        upload_flags = completer._flags_for('case', 'upload')
        assert len(upload_flags['--to']) > 0
        assert 'remote' in upload_flags['--to'].lower()

    def test_history_flag_completion(self, completer):
        """Test history command flag completions."""
        completions = list(completer.get_completions(Document("history --u"), None))
        texts = {c.text for c in completions}
        assert '--unique' in texts

        completions = list(completer.get_completions(Document("history "), None))
        texts = {c.text for c in completions}
        assert '--unique' in texts
        assert '--help' in texts

    def test_set_setting_name_completion_includes_timeout(self, completer):
        """Test set command suggests timeout setting."""
        completions = list(completer.get_completions(Document("set t"), None))
        texts = {c.text for c in completions}
        assert 'timeout' in texts

    def test_set_timeout_value_completion(self, completer):
        """Test set timeout suggests common minute values."""
        completions = list(completer.get_completions(Document("set timeout "), None))
        texts = {c.text for c in completions}
        assert '15' in texts
        assert '20' in texts

    def test_use_last_completion(self, completer):
        """Test use command suggests 'last' shortcut."""
        completions = list(completer.get_completions(Document("use la"), None))
        texts = {c.text for c in completions}
        assert 'last' in texts

    def test_grep_after_context_flag_completion(self, completer):
        """Test grep --after-context and -A flag completion."""
        completions = list(completer.get_completions(Document("grep --a"), None))
        texts = {c.text for c in completions}
        assert '--after-context' in texts

        completions = list(completer.get_completions(Document("grep -A"), None))
        texts = {c.text for c in completions}
        assert '-A' in texts

    def test_vi_path_completion(self, completer, tmp_path):
        """Test vi command path completions."""
        (tmp_path / "notes.txt").write_text("hello")
        completer.shell = Mock()
        completer.shell._current_dir = tmp_path
        completer.shell._aliases = {}

        completions = list(completer.get_completions(Document("vi no"), None))
        texts = {c.text for c in completions}
        assert 'notes.txt' in texts

    def test_case_create_ref_case_path_completion_after_space(self, completer, tmp_path):
        """Test case create --ref-case path completion when argument is empty."""
        (tmp_path / "refCase").mkdir()
        completer.shell = Mock()
        completer.shell._current_dir = tmp_path
        completer.shell._aliases = {}

        completions = list(completer.get_completions(Document("case create --ref-case "), None))
        texts = {c.text for c in completions}
        assert 'refCase/' in texts

    def test_case_create_from_config_path_completion_after_space(self, completer, tmp_path):
        """Test case create --from-config path completion when argument is empty."""
        (tmp_path / "case_config.yaml").write_text("case_name: demo")
        completer.shell = Mock()
        completer.shell._current_dir = tmp_path
        completer.shell._aliases = {}

        completions = list(completer.get_completions(Document("case create --from-config "), None))
        texts = {c.text for c in completions}
        assert 'case_config.yaml' in texts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
