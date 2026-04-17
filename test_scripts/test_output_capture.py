#!/usr/bin/env python3
"""
Unit tests for output capture functionality in interactive shell.
Tests the _execute_command_with_capture() and _execute_shell_command_with_capture() methods.
"""

import sys
import os
import io

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cli.interactive import InteractiveShell


class TestOutputCapture:
    """Test suite for output capture"""
    
    def setup_method(self):
        """Initialize shell instance for testing"""
        # Create a shell instance without app (tests will just use the parsing method)
        self.shell = InteractiveShell.__new__(InteractiveShell)
        # Initialize required attributes
        self.shell.console = None
        self.shell._current_case = None
        self.shell._current_case_name = None
        self.shell._current_problem = None
        self.shell._current_rundir = None
        self.shell._current_output_dir = None
        self.shell._current_node = None
        self.shell._current_t1 = None
        self.shell._current_t2 = None
        self.shell._current_dir = None
        self.shell._pipe_mode = False
        self.shell._captured_output = None
    
    def test_shell_command_capture_simple(self):
        """Test capturing simple shell command output"""
        output = self.shell._execute_shell_command_with_capture("echo 'Hello World'")
        assert "Hello World" in output, f"Expected 'Hello World' in output, got: {output}"
    
    def test_shell_command_capture_grep(self):
        """Test capturing shell command with grep"""
        output = self.shell._execute_shell_command_with_capture("echo -e 'apple\\nbanana\\ncherry' | grep 'banana'")
        assert "banana" in output, f"Expected 'banana' in output, got: {output}"
    
    def test_shell_command_capture_multiline(self):
        """Test capturing multi-line shell command output"""
        output = self.shell._execute_shell_command_with_capture("echo -e 'line1\\nline2\\nline3'")
        lines = output.strip().split('\n')
        assert len(lines) >= 3, f"Expected 3+ lines, got {len(lines)}"
        assert "line1" in output
        assert "line2" in output
        assert "line3" in output
    
    def test_shell_command_capture_ls(self):
        """Test capturing ls command output"""
        output = self.shell._execute_shell_command_with_capture("ls /tmp")
        # Should have some output
        assert len(output) > 0, "Expected non-empty output from ls"
    
    def test_shell_command_error_handling(self):
        """Test error handling for non-existent command"""
        output = self.shell._execute_shell_command_with_capture("this_command_does_not_exist")
        # Should contain error message
        assert "Error" in output or "not found" in output, f"Expected error, got: {output}"
    
    def test_shell_command_capture_wc(self):
        """Test capturing word count output"""
        output = self.shell._execute_shell_command_with_capture("echo -e 'a\\nb\\nc' | wc -l")
        # wc output includes the count
        assert "3" in output or output.strip() == "3", f"Expected '3' in output, got: {output}"
    
    def test_shell_command_capture_sort(self):
        """Test capturing sort command output"""
        output = self.shell._execute_shell_command_with_capture("echo -e 'zebra\\napple\\nbanana' | sort")
        lines = output.strip().split('\n')
        # Should be sorted
        assert "apple" in output
        assert "banana" in output
        assert "zebra" in output
        # First line should be 'apple'
        assert lines[0].strip() == "apple", f"Expected sorted output, got: {lines}"
    
    def test_shell_command_capture_head(self):
        """Test capturing head command output"""
        output = self.shell._execute_shell_command_with_capture("echo -e 'a\\nb\\nc\\nd\\ne' | head -2")
        lines = output.strip().split('\n')
        assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}"
    
    def test_shell_command_no_timeout_on_quick(self):
        """Test that quick commands don't timeout"""
        output = self.shell._execute_shell_command_with_capture("echo 'quick'")
        assert "quick" in output
        assert "timed out" not in output.lower()
    
    def test_shell_command_capture_cat_file(self):
        """Test capturing cat command on a file"""
        # Create a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test line 1\ntest line 2\n")
            temp_file = f.name
        
        try:
            output = self.shell._execute_shell_command_with_capture(f"cat {temp_file}")
            assert "test line 1" in output
            assert "test line 2" in output
        finally:
            os.unlink(temp_file)
    
    def test_shell_command_capture_find(self):
        """Test capturing find command output"""
        # Find Python files in src directory
        output = self.shell._execute_shell_command_with_capture("find src -name '*.py' -type f 2>/dev/null | head -5")
        # Should find some Python files
        assert ".py" in output or len(output) > 0, f"Expected Python files in output, got: {output}"


def run_tests():
    """Run all tests and report results"""
    test_suite = TestOutputCapture()
    test_methods = [method for method in dir(test_suite) if method.startswith('test_')]
    
    passed = 0
    failed = 0
    
    print("=" * 70)
    print("OUTPUT CAPTURE UNIT TESTS")
    print("=" * 70)
    
    for test_name in test_methods:
        test_suite.setup_method()
        try:
            getattr(test_suite, test_name)()
            print(f"✓ {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {test_name}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test_name}: EXCEPTION: {e}")
            failed += 1
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed} tests")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
