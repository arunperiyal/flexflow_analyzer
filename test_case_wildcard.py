"""
Test suite for wildcard case support in the 'use' command.

Tests the ability to iterate over all cases from .cases file using 'use case:*'.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock
from src.cli.interactive import InteractiveShell


class TestWildcardPatternDetection:
    """Test wildcard pattern detection."""
    
    def test_is_wildcard_pattern_with_asterisk(self):
        """Test detection of * as wildcard."""
        shell = InteractiveShell(Mock())
        assert shell._is_wildcard_pattern("*") is True
    
    def test_is_wildcard_pattern_without_asterisk(self):
        """Test non-wildcard strings."""
        shell = InteractiveShell(Mock())
        assert shell._is_wildcard_pattern("Case001") is False
        assert shell._is_wildcard_pattern("Case*") is False
        assert shell._is_wildcard_pattern("?") is False
        assert shell._is_wildcard_pattern("[1-3]") is False


class TestLoadCasesFromFile:
    """Test loading cases from .cases file."""
    
    def test_load_cases_from_file_success(self):
        """Test loading cases from valid .cases file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create a .cases file
            cases_data = [
                {'name': 'Case001', 'path': '/path/to/Case001'},
                {'name': 'Case002', 'path': '/path/to/Case002'},
                {'name': 'Case003', 'path': '/path/to/Case003'},
            ]
            cases_file = tmpdir_path / '.cases'
            with open(cases_file, 'w') as f:
                json.dump(cases_data, f)
            
            shell = InteractiveShell(Mock())
            shell._current_dir = tmpdir_path
            
            # Load cases
            loaded = shell._load_cases_from_file()
            
            assert len(loaded) == 3
            assert loaded[0]['name'] == 'Case001'
            assert loaded[1]['name'] == 'Case002'
            assert loaded[2]['name'] == 'Case003'
    
    def test_load_cases_from_file_not_found(self):
        """Test when .cases file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            shell = InteractiveShell(Mock())
            shell._current_dir = tmpdir_path
            
            # Load cases when file doesn't exist
            loaded = shell._load_cases_from_file()
            
            assert loaded == []
    
    def test_load_cases_from_file_invalid_format(self):
        """Test when .cases file has invalid format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create a .cases file with invalid format (dict instead of list)
            cases_file = tmpdir_path / '.cases'
            with open(cases_file, 'w') as f:
                json.dump({'case001': {'path': '/path'}}, f)
            
            shell = InteractiveShell(Mock())
            shell._current_dir = tmpdir_path
            
            # Load cases - should return empty list for invalid format
            loaded = shell._load_cases_from_file()
            
            assert loaded == []


class TestUseCaseWithWildcard:
    """Test use_case method with wildcard patterns."""
    
    def test_use_case_with_wildcard_shows_guidance(self):
        """Test that use_case with * shows guidance message."""
        shell = InteractiveShell(Mock())
        
        # This should show guidance but not set case
        shell.use_case("*")
        
        # Should not set a single case for wildcard
        assert shell._current_case is None
    
    def test_use_case_with_single_case_still_works(self):
        """Test that single case usage still works (backward compatibility)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "Case001").mkdir()
            
            shell = InteractiveShell(Mock())
            shell._current_dir = tmpdir_path
            
            shell.use_case("Case001")
            
            # Should set the current case
            assert shell._current_case is not None
            assert "Case001" in shell._current_case


class TestProcessCaseWildcardChain:
    """Test processing commands with case wildcard."""
    
    def test_process_case_wildcard_chain_basic(self):
        """Test basic wildcard chain processing with .cases file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create test case directories
            (tmpdir_path / "Case001").mkdir()
            (tmpdir_path / "Case002").mkdir()
            
            # Create .cases file
            cases_data = [
                {'name': 'Case001', 'path': str(tmpdir_path / 'Case001')},
                {'name': 'Case002', 'path': str(tmpdir_path / 'Case002')},
            ]
            cases_file = tmpdir_path / '.cases'
            with open(cases_file, 'w') as f:
                json.dump(cases_data, f)
            
            shell = InteractiveShell(Mock())
            shell._current_dir = tmpdir_path
            
            # Mock the handlers to track calls
            shell.handle_shell_command = Mock(return_value=False)
            shell.execute_command = Mock()
            
            # Process wildcard chain
            shell._process_case_wildcard_chain(["echo test"])
            
            # Should have executed echo test for each case
            assert shell.execute_command.call_count == 2
            # Restore case should be None
            assert shell._current_case is None
    
    def test_process_case_wildcard_chain_no_cases(self):
        """Test wildcard chain when no .cases file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            shell = InteractiveShell(Mock())
            shell._current_dir = tmpdir_path
            
            # Mock the handlers
            shell.handle_shell_command = Mock(return_value=False)
            shell.execute_command = Mock()
            
            # Process wildcard chain with no .cases file
            shell._process_case_wildcard_chain(["echo test"])
            
            # Should not execute any commands
            assert shell.execute_command.call_count == 0
    
    def test_process_case_wildcard_chain_restores_context(self):
        """Test that original case context is restored after loop."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create test case directories
            (tmpdir_path / "Case001").mkdir()
            (tmpdir_path / "Case002").mkdir()
            
            # Create .cases file
            cases_data = [
                {'name': 'Case001', 'path': str(tmpdir_path / 'Case001')},
                {'name': 'Case002', 'path': str(tmpdir_path / 'Case002')},
            ]
            cases_file = tmpdir_path / '.cases'
            with open(cases_file, 'w') as f:
                json.dump(cases_data, f)
            
            shell = InteractiveShell(Mock())
            shell._current_dir = tmpdir_path
            
            # Set original case context
            original_case = str(tmpdir_path / "OriginalCase")
            shell._current_case = original_case
            shell._current_case_name = "OriginalCase"
            
            # Mock the handlers
            shell.handle_shell_command = Mock(return_value=False)
            shell.execute_command = Mock()
            
            # Process wildcard chain
            shell._process_case_wildcard_chain(["echo test"])
            
            # Should restore original case context
            assert shell._current_case == original_case
            assert shell._current_case_name == "OriginalCase"
    
    def test_process_case_wildcard_chain_multiple_commands(self):
        """Test wildcard chain with multiple commands for each case."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create test case directories
            (tmpdir_path / "Case001").mkdir()
            (tmpdir_path / "Case002").mkdir()
            
            # Create .cases file
            cases_data = [
                {'name': 'Case001', 'path': str(tmpdir_path / 'Case001')},
                {'name': 'Case002', 'path': str(tmpdir_path / 'Case002')},
            ]
            cases_file = tmpdir_path / '.cases'
            with open(cases_file, 'w') as f:
                json.dump(cases_data, f)
            
            shell = InteractiveShell(Mock())
            shell._current_dir = tmpdir_path
            
            # Mock the handlers
            shell.handle_shell_command = Mock(return_value=False)
            shell.execute_command = Mock()
            
            # Process wildcard chain with 3 commands
            shell._process_case_wildcard_chain(["cmd1", "cmd2", "cmd3"])
            
            # Should execute 3 commands for each of 2 cases = 6 total
            assert shell.execute_command.call_count == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
