#!/usr/bin/env python3
"""
Unit tests for pipe execution functionality.
Tests the _execute_pipe() method with various pipe scenarios.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cli.interactive import InteractiveShell, PipeSegment


class TestPipeExecution:
    """Test suite for pipe execution"""
    
    def setup_method(self):
        """Initialize shell instance for testing"""
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
    
    def test_single_segment_shell(self):
        """Test executing single shell command (no actual piping)"""
        segments = [PipeSegment("echo 'hello world'")]
        output = self.shell._execute_pipe(segments)
        assert "hello world" in output, f"Expected 'hello world' in output, got: {output}"
    
    def test_two_segment_shell_pipe(self):
        """Test simple Shell → Shell pipe"""
        segments = [
            PipeSegment("echo -e 'apple\\nbanana\\ncherry'"),
            PipeSegment("grep banana")
        ]
        output = self.shell._execute_pipe(segments)
        assert "banana" in output, f"Expected 'banana' in output, got: {output}"
        assert "apple" not in output, f"Should not have 'apple', got: {output}"
    
    def test_three_segment_pipe(self):
        """Test three-segment Shell → Shell → Shell pipe"""
        segments = [
            PipeSegment("echo -e 'zebra\\napple\\nbanana'"),
            PipeSegment("sort"),
            PipeSegment("head -1")
        ]
        output = self.shell._execute_pipe(segments)
        assert "apple" in output, f"Expected sorted output starting with 'apple', got: {output}"
    
    def test_pipe_with_wc(self):
        """Test piping to word count"""
        segments = [
            PipeSegment("echo -e 'line1\\nline2\\nline3'"),
            PipeSegment("wc -l")
        ]
        output = self.shell._execute_pipe(segments)
        # wc returns the count (may have whitespace)
        assert "3" in output, f"Expected '3' in output, got: {output}"
    
    def test_pipe_with_grep_options(self):
        """Test pipe with grep options"""
        segments = [
            PipeSegment("echo -e 'HELLO\\nhello\\nHELLO WORLD'"),
            PipeSegment("grep -i hello")
        ]
        output = self.shell._execute_pipe(segments)
        # All three lines contain 'hello' (case insensitive)
        lines = [l for l in output.strip().split('\n') if l]
        assert len(lines) >= 2, f"Expected multiple lines, got: {output}"
    
    def test_pipe_with_cut(self):
        """Test pipe with cut command"""
        segments = [
            PipeSegment("echo -e 'a:b:c\\nx:y:z'"),
            PipeSegment("cut -d: -f2")
        ]
        output = self.shell._execute_pipe(segments)
        assert "b" in output and "y" in output, f"Expected 'b' and 'y', got: {output}"
    
    def test_empty_segments_list(self):
        """Test handling of empty segments"""
        segments = []
        output = self.shell._execute_pipe(segments)
        assert output == "", f"Expected empty output, got: {output}"
    
    def test_pipe_with_empty_output(self):
        """Test pipe where grep finds nothing"""
        segments = [
            PipeSegment("echo 'apple'"),
            PipeSegment("grep banana")
        ]
        output = self.shell._execute_pipe(segments)
        # grep returns empty when no match found
        assert output.strip() == "", f"Expected empty output, got: {output}"
    
    def test_pipe_with_sort_reverse(self):
        """Test pipe with sort -r (reverse)"""
        segments = [
            PipeSegment("printf 'a\\nb\\nc'"),
            PipeSegment("sort -r")
        ]
        output = self.shell._execute_pipe(segments)
        lines = output.strip().split('\n')
        # Should be sorted in reverse: c, b, a
        assert lines[0].strip() == "c", f"Expected 'c' first, got: {lines}"
    
    def test_pipe_with_head(self):
        """Test pipe with head command"""
        segments = [
            PipeSegment("echo -e 'a\\nb\\nc\\nd\\ne'"),
            PipeSegment("head -2")
        ]
        output = self.shell._execute_pipe(segments)
        lines = [l for l in output.strip().split('\n') if l]
        assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}: {lines}"
    
    def test_pipe_with_tail(self):
        """Test pipe with tail command"""
        segments = [
            PipeSegment("echo -e 'a\\nb\\nc\\nd\\ne'"),
            PipeSegment("tail -2")
        ]
        output = self.shell._execute_pipe(segments)
        lines = [l for l in output.strip().split('\n') if l]
        assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}: {lines}"
        # Should contain the last two lines
        assert "d" in output and "e" in output, f"Expected 'd' and 'e', got: {output}"
    
    def test_pipe_with_sed(self):
        """Test pipe with sed command"""
        segments = [
            PipeSegment("echo 'hello world'"),
            PipeSegment("sed 's/world/universe/'")
        ]
        output = self.shell._execute_pipe(segments)
        assert "universe" in output, f"Expected 'universe', got: {output}"
        assert "world" not in output, f"Should have replaced 'world', got: {output}"
    
    def test_pipe_segment_shell_to_shell(self):
        """Test _execute_pipe_shell_segment directly"""
        segment = PipeSegment("grep -i test")
        output = self.shell._execute_pipe_shell_segment(
            segment,
            input_text="This is a TEST\nno match\nTest again",
            next_segment=None,
            is_last=True
        )
        assert "TEST" in output and "Test again" in output, f"Got: {output}"
    
    def test_multiple_pipes_complex(self):
        """Test complex multi-segment pipe"""
        segments = [
            PipeSegment("echo -e 'file1.txt\\nfile2.py\\nscript.sh\\nfile3.txt'"),
            PipeSegment("grep txt"),
            PipeSegment("sort"),
        ]
        output = self.shell._execute_pipe(segments)
        lines = [l.strip() for l in output.strip().split('\n') if l.strip()]
        # Should have both .txt files, sorted
        assert len(lines) >= 2, f"Expected multiple lines, got: {lines}"
        assert "file1.txt" in output and "file3.txt" in output, f"Got: {output}"
    
    def test_pipe_with_awk(self):
        """Test pipe with awk command"""
        segments = [
            PipeSegment("printf 'a 1\\nb 2\\nc 3'"),
            PipeSegment("awk '{print $2}'")
        ]
        output = self.shell._execute_pipe(segments)
        assert "1" in output and "2" in output and "3" in output, f"Got: {output}"
    
    def test_shell_segment_error_handling(self):
        """Test error handling in shell segment"""
        segment = PipeSegment("command_that_does_not_exist")
        output = self.shell._execute_pipe_shell_segment(
            segment,
            input_text=None,
            next_segment=None,
            is_last=True
        )
        # Should have an error indicator
        assert "Error" in output or "not found" in output, f"Expected error message, got: {output}"
    
    def test_parse_pipe_segments_from_command_line(self):
        """Test using parsed segments in pipe execution"""
        shell = InteractiveShell.__new__(InteractiveShell)
        shell._current_case = None
        shell._current_case_name = None
        shell._current_problem = None
        shell._current_rundir = None
        shell._current_output_dir = None
        shell._current_node = None
        shell._current_t1 = None
        shell._current_t2 = None
        shell._current_dir = None
        shell._pipe_mode = False
        shell._captured_output = None
        
        # Parse from command line with printf (more portable than echo -e)
        segments = shell._parse_pipe_segments("printf 'a\\nb\\nc' | sort | tail -1")
        output = shell._execute_pipe(segments)
        # After sort and tail -1, should get 'c'
        assert "c" in output, f"Expected 'c', got: {output}"
    
    def test_pipe_preserves_spaces(self):
        """Test that piping preserves spaces in output"""
        segments = [
            PipeSegment("echo 'hello   world'"),
            PipeSegment("cat")
        ]
        output = self.shell._execute_pipe(segments)
        assert "hello   world" in output, f"Expected spaces preserved, got: {output}"
    
    def test_pipe_with_special_characters(self):
        """Test piping with special characters"""
        segments = [
            PipeSegment("echo 'test@example.com'"),
            PipeSegment("grep '@'")
        ]
        output = self.shell._execute_pipe(segments)
        assert "test@example.com" in output, f"Expected email preserved, got: {output}"


def run_tests():
    """Run all tests and report results"""
    test_suite = TestPipeExecution()
    test_methods = [method for method in dir(test_suite) if method.startswith('test_')]
    
    passed = 0
    failed = 0
    
    print("=" * 70)
    print("PIPE EXECUTION UNIT TESTS")
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
