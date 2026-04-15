"""
Test suite for wildcard case support in the 'use' command.

Tests the ability to iterate over multiple case directories using glob patterns.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock
from src.cli.interactive import InteractiveShell


class TestWildcardPatternDetection:
    """Test wildcard pattern detection."""
    
    def test_is_wildcard_pattern_with_asterisk(self):
        """Test detection of * wildcard."""
        shell = InteractiveShell(Mock())
        assert shell._is_wildcard_pattern("Case*") is True
        assert shell._is_wildcard_pattern("*") is True
    
    def test_is_wildcard_pattern_with_question_mark(self):
        """Test detection of ? wildcard."""
        shell = InteractiveShell(Mock())
        assert shell._is_wildcard_pattern("Case?") is True
        assert shell._is_wildcard_pattern("Case00?") is True
    
    def test_is_wildcard_pattern_with_brackets(self):
        """Test detection of [...] wildcard."""
        shell = InteractiveShell(Mock())
        assert shell._is_wildcard_pattern("Case[1-3]") is True
        assert shell._is_wildcard_pattern("Case[0-9]*") is True
    
    def test_is_wildcard_pattern_without_wildcards(self):
        """Test non-wildcard strings."""
        shell = InteractiveShell(Mock())
        assert shell._is_wildcard_pattern("Case001") is False
        assert shell._is_wildcard_pattern("Case_A") is False
        assert shell._is_wildcard_pattern("Case") is False


class TestFindMatchingCases:
    """Test finding cases matching glob patterns."""
    
    def test_find_matching_cases_with_asterisk(self):
        """Test finding cases with * pattern."""
        shell = InteractiveShell(Mock())
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            shell._current_dir = tmpdir_path
            
            # Create test case directories
            (tmpdir_path / "Case001").mkdir()
            (tmpdir_path / "Case002").mkdir()
            (tmpdir_path / "Case003").mkdir()
            (tmpdir_path / "other_dir").mkdir()
            
            # Test matching
            matches = shell._find_matching_cases("Case*")
            assert len(matches) == 3
            assert matches[0].name == "Case001"
            assert matches[1].name == "Case002"
            assert matches[2].name == "Case003"
    
    def test_find_matching_cases_with_question_mark(self):
        """Test finding cases with ? pattern."""
        shell = InteractiveShell(Mock())
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            shell._current_dir = tmpdir_path
            
            # Create test case directories
            (tmpdir_path / "Case001").mkdir()
            (tmpdir_path / "Case002").mkdir()
            (tmpdir_path / "Case010").mkdir()
            (tmpdir_path / "Case100").mkdir()
            
            # Test matching only Case00X (not Case010 or Case100)
            matches = shell._find_matching_cases("Case00?")
            assert len(matches) == 2
            assert matches[0].name == "Case001"
            assert matches[1].name == "Case002"
    
    def test_find_matching_cases_with_brackets(self):
        """Test finding cases with [...] pattern."""
        shell = InteractiveShell(Mock())
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            shell._current_dir = tmpdir_path
            
            # Create test case directories
            (tmpdir_path / "Case001").mkdir()
            (tmpdir_path / "Case002").mkdir()
            (tmpdir_path / "Case003").mkdir()
            (tmpdir_path / "Case004").mkdir()
            (tmpdir_path / "Case005").mkdir()
            
            # Test matching only Case001, Case002, Case003
            matches = shell._find_matching_cases("Case00[1-3]")
            assert len(matches) == 3
            assert matches[0].name == "Case001"
            assert matches[1].name == "Case002"
            assert matches[2].name == "Case003"
    
    def test_find_matching_cases_sorted_order(self):
        """Test that matches are sorted in consistent order."""
        shell = InteractiveShell(Mock())
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            shell._current_dir = tmpdir_path
            
            # Create test case directories in non-alphabetical order
            (tmpdir_path / "Case003").mkdir()
            (tmpdir_path / "Case001").mkdir()
            (tmpdir_path / "Case002").mkdir()
            
            # Test that results are sorted
            matches = shell._find_matching_cases("Case*")
            assert len(matches) == 3
            assert matches[0].name == "Case001"
            assert matches[1].name == "Case002"
            assert matches[2].name == "Case003"
    
    def test_find_matching_cases_no_matches(self):
        """Test when no cases match the pattern."""
        shell = InteractiveShell(Mock())
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            shell._current_dir = tmpdir_path
            
            # Create test case directories
            (tmpdir_path / "Case001").mkdir()
            (tmpdir_path / "Case002").mkdir()
            
            # Test non-matching pattern
            matches = shell._find_matching_cases("NoCase*")
            assert len(matches) == 0
    
    def test_find_matching_cases_excludes_files(self):
        """Test that only directories are matched, not files."""
        shell = InteractiveShell(Mock())
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            shell._current_dir = tmpdir_path
            
            # Create test case directories and files
            (tmpdir_path / "Case001").mkdir()
            (tmpdir_path / "Case002").mkdir()
            (tmpdir_path / "Case003.txt").touch()  # File, not directory
            
            # Test that only directories are matched
            matches = shell._find_matching_cases("Case*")
            assert len(matches) == 2
            assert all(m.is_dir() for m in matches)


class TestUseCaseWithWildcard:
    """Test use_case method with wildcard patterns."""
    
    def test_use_case_with_wildcard_shows_guidance(self):
        """Test that use_case with wildcard shows guidance message."""
        shell = InteractiveShell(Mock())
        
        # This should show guidance but not set case
        shell.use_case("Case*")
        
        # Should not set a single case for wildcard
        assert shell._current_case is None
    
    def test_use_case_with_single_case_still_works(self):
        """Test that single case usage still works (backward compatibility)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "Case001").mkdir()
            
            console_mock = Mock()
            shell = InteractiveShell(console_mock)
            shell._current_dir = tmpdir_path
            
            shell.use_case("Case001")
            
            # Should set the current case
            assert shell._current_case is not None
            assert "Case001" in shell._current_case


class TestProcessCaseWildcardChain:
    """Test processing commands with case wildcard."""
    
    def test_process_case_wildcard_chain_no_matches(self):
        """Test wildcard chain with no matching cases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            shell = InteractiveShell(Mock())
            shell._current_dir = tmpdir_path
            
            # Process wildcard chain with no matches
            shell._process_case_wildcard_chain("NoCase*", ["echo test"])
            
            # No exception should be raised, just handled gracefully
    
    def test_process_case_wildcard_chain_restores_context(self):
        """Test that original case context is restored after loop."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create test case directories
            (tmpdir_path / "Case001").mkdir()
            (tmpdir_path / "Case002").mkdir()
            
            console_mock = Mock()
            shell = InteractiveShell(console_mock)
            shell._current_dir = tmpdir_path
            
            # Set original case context
            original_case = str(tmpdir_path / "OriginalCase")
            shell._current_case = original_case
            shell._current_case_name = "OriginalCase"
            
            # Mock the handler
            shell.handle_shell_command = Mock(return_value=False)
            shell.execute_command = Mock()
            
            # Process wildcard chain
            shell._process_case_wildcard_chain("Case*", ["echo test"])
            
            # Should restore original case context
            assert shell._current_case == original_case
            assert shell._current_case_name == "OriginalCase"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
