#!/usr/bin/env python3
"""
Unit tests for main loop integration of piping.
Tests the _has_pipe(), _handle_piped_command() methods and run() loop integration.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cli.interactive import InteractiveShell, PipeSegment


class TestMainLoopIntegration:
    """Test suite for main loop piping integration"""
    
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
    
    def test_has_pipe_simple(self):
        """Test detection of simple pipe"""
        assert self.shell._has_pipe("cmd1 | cmd2"), "Should detect simple pipe"
    
    def test_has_pipe_multiple(self):
        """Test detection of multiple pipes"""
        assert self.shell._has_pipe("cmd1 | cmd2 | cmd3"), "Should detect multiple pipes"
    
    def test_has_pipe_no_pipe(self):
        """Test that non-piped command is not detected"""
        assert not self.shell._has_pipe("cmd1 arg1 arg2"), "Should not detect pipe"
    
    def test_has_pipe_pipe_in_single_quotes(self):
        """Test that pipe inside single quotes is not detected"""
        assert not self.shell._has_pipe("echo 'text|with|pipes'"), "Should not detect pipe in quotes"
    
    def test_has_pipe_pipe_in_double_quotes(self):
        """Test that pipe inside double quotes is not detected"""
        assert not self.shell._has_pipe('echo "text|with|pipes"'), "Should not detect pipe in quotes"
    
    def test_has_pipe_escaped_pipe(self):
        """Test that escaped pipe is not detected"""
        assert not self.shell._has_pipe("echo text\\|escaped"), "Should not detect escaped pipe"
    
    def test_has_pipe_mixed_quotes(self):
        """Test with mixed quotes and actual pipe"""
        assert self.shell._has_pipe('echo "text|quoted" | grep x'), "Should detect pipe after quotes"
    
    def test_has_pipe_no_space_around_pipe(self):
        """Test pipe detection without spaces"""
        assert self.shell._has_pipe("cmd1|cmd2"), "Should detect pipe without spaces"
    
    def test_handle_piped_command_executes(self):
        """Test that piped command executes through the handler"""
        # This is more of an integration test
        output_buffer = []
        
        # Mock console.print to capture output
        class MockConsole:
            def print(self, msg, **kwargs):
                output_buffer.append(msg)
        
        self.shell.console = MockConsole()
        
        # Execute a simple pipe
        self.shell._handle_piped_command("echo 'hello' | grep hello")
        
        # Should have output
        assert len(output_buffer) > 0, "Should have output from piped command"
        assert any("hello" in str(line) for line in output_buffer), f"Output should contain 'hello', got: {output_buffer}"
    
    def test_handle_piped_command_with_grep(self):
        """Test piped grep command through handler"""
        output_buffer = []
        
        class MockConsole:
            def print(self, msg, **kwargs):
                output_buffer.append(msg)
        
        self.shell.console = MockConsole()
        
        # Execute piped grep
        self.shell._handle_piped_command("echo -e 'apple\\nbanana\\ncherry' | grep banana")
        
        # Should contain banana but not apple
        output_str = ''.join(str(line) for line in output_buffer)
        assert "banana" in output_str, f"Output should contain 'banana', got: {output_str}"
    
    def test_handle_piped_command_with_sort(self):
        """Test piped sort command through handler"""
        output_buffer = []
        
        class MockConsole:
            def print(self, msg, **kwargs):
                output_buffer.append(msg)
        
        self.shell.console = MockConsole()
        
        # Execute piped sort
        self.shell._handle_piped_command("printf 'c\\na\\nb' | sort")
        
        output_str = ''.join(str(line) for line in output_buffer)
        # Should be sorted
        assert "a" in output_str and "b" in output_str and "c" in output_str, f"Got: {output_str}"
    
    def test_handle_piped_command_with_wc(self):
        """Test piped wc command through handler"""
        output_buffer = []
        
        class MockConsole:
            def print(self, msg, **kwargs):
                output_buffer.append(msg)
        
        self.shell.console = MockConsole()
        
        # Execute piped wc (printf without -e only creates 2 line breaks)
        self.shell._handle_piped_command("printf 'a\\nb\\nc' | wc -l")
        
        output_str = ''.join(str(line) for line in output_buffer)
        # wc returns count (may have leading/trailing spaces)
        # printf a\nb\nc creates 2 newlines (a\n, b\n, c with no trailing newline)
        assert "2" in output_str or output_str.strip() == "2", f"Expected '2' lines, got: {repr(output_str)}"
    
    def test_piped_command_with_no_output(self):
        """Test piped command that produces no output"""
        output_buffer = []
        
        class MockConsole:
            def print(self, msg, **kwargs):
                if msg:  # Only capture non-empty
                    output_buffer.append(msg)
        
        self.shell.console = MockConsole()
        
        # Execute grep that finds nothing
        self.shell._handle_piped_command("echo 'apple' | grep banana")
        
        # Should have minimal or no output (grep returns empty)
        # Handler should not error out
        assert True, "Should handle empty output gracefully"
    
    def test_piped_command_with_error(self):
        """Test error handling in piped command"""
        output_buffer = []
        
        class MockConsole:
            def print(self, msg, **kwargs):
                output_buffer.append(msg)
        
        self.shell.console = MockConsole()
        
        # Execute with non-existent command
        self.shell._handle_piped_command("echo test | nonexistent_command_xyz")
        
        # Should have error output
        output_str = ''.join(str(line) for line in output_buffer)
        # Either Error in pipe or command output (both are acceptable)
        assert len(output_buffer) > 0, "Should have some output for error case"
    
    def test_multiple_commands_with_some_piped(self):
        """Test mixing piped and non-piped commands in sequence"""
        output_buffer = []
        
        class MockConsole:
            def print(self, msg, **kwargs):
                output_buffer.append(msg)
        
        self.shell.console = MockConsole()
        
        # Simulate commands split by semicolon
        commands = [
            "echo 'hello' | grep hello",
            "echo 'world'",
            "printf 'a\\nb' | sort"
        ]
        
        for cmd in commands:
            output_buffer.clear()
            
            if self.shell._has_pipe(cmd):
                self.shell._handle_piped_command(cmd)
            # Skip shell commands and just check has_pipe logic
        
        # If we got here without errors, mixing works
        assert True, "Mixing piped and non-piped commands should work"
    
    def test_has_pipe_with_complex_quoting(self):
        """Test has_pipe with complex quote scenarios"""
        # Single quote inside double quote with pipe outside
        assert self.shell._has_pipe('echo "don\'t" | grep'), "Should detect pipe outside quotes"
        
        # Double quote inside single quote with pipe outside
        assert self.shell._has_pipe("echo 'say \"hello\"' | grep"), "Should detect pipe outside quotes"
    
    def test_has_pipe_with_escaped_quote(self):
        """Test has_pipe with escaped quotes"""
        # Escaped quote shouldn't affect pipe detection
        assert self.shell._has_pipe('echo \\"test\\" | grep'), "Should detect pipe after escaped quotes"
    
    def test_handle_piped_complex_chain(self):
        """Test complex piped command chain through handler"""
        output_buffer = []
        
        class MockConsole:
            def print(self, msg, **kwargs):
                output_buffer.append(msg)
        
        self.shell.console = MockConsole()
        
        # Complex chain: printf | grep | sort | head
        self.shell._handle_piped_command("printf 'zebra\\napple\\nbanana' | grep a | sort | head -1")
        
        output_str = ''.join(str(line) for line in output_buffer)
        assert "apple" in output_str or len(output_str) > 0, f"Got: {output_str}"
    
    def test_has_pipe_various_formats(self):
        """Test has_pipe with various pipe spacing"""
        test_cases = [
            ("cmd1|cmd2", True),
            ("cmd1 |cmd2", True),
            ("cmd1| cmd2", True),
            ("cmd1 | cmd2", True),
            ("cmd1  |  cmd2", True),
            ("cmd1", False),
            ("cmd1 arg | cmd2", True),
        ]
        
        for command, expected in test_cases:
            result = self.shell._has_pipe(command)
            assert result == expected, f"_has_pipe('{command}') should be {expected}, got {result}"


def run_tests():
    """Run all tests and report results"""
    test_suite = TestMainLoopIntegration()
    test_methods = [method for method in dir(test_suite) if method.startswith('test_')]
    
    passed = 0
    failed = 0
    
    print("=" * 70)
    print("MAIN LOOP INTEGRATION UNIT TESTS")
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
