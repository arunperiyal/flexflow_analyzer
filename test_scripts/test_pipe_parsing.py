#!/usr/bin/env python3
"""
Unit tests for pipe parsing functionality in interactive shell.
Tests the _split_by_pipe() method and PipeSegment class with various scenarios.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cli.interactive import InteractiveShell, PipeSegment


class TestPipeParsing:
    """Test suite for pipe parsing"""
    
    def setup_method(self):
        """Initialize shell instance for testing"""
        # Create a shell instance without app (tests will just use the parsing method)
        self.shell = InteractiveShell.__new__(InteractiveShell)
    
    
    
    def test_simple_pipe(self):
        """Test basic pipe splitting"""
        result = self.shell._split_by_pipe("cmd1 | cmd2")
        assert result == ["cmd1", "cmd2"], f"Expected ['cmd1', 'cmd2'], got {result}"
    
    def test_multiple_pipes(self):
        """Test multiple pipes in sequence"""
        result = self.shell._split_by_pipe("cmd1 | cmd2 | cmd3")
        assert result == ["cmd1", "cmd2", "cmd3"], f"Expected ['cmd1', 'cmd2', 'cmd3'], got {result}"
    
    def test_pipes_with_spaces(self):
        """Test pipes with varying whitespace"""
        result = self.shell._split_by_pipe("cmd1|cmd2|cmd3")
        assert result == ["cmd1", "cmd2", "cmd3"], f"Expected ['cmd1', 'cmd2', 'cmd3'], got {result}"
        
        result = self.shell._split_by_pipe("cmd1  |  cmd2  |  cmd3")
        assert result == ["cmd1", "cmd2", "cmd3"], f"Expected ['cmd1', 'cmd2', 'cmd3'], got {result}"
    
    def test_pipe_in_double_quotes(self):
        """Test pipe character inside double quotes is not split"""
        result = self.shell._split_by_pipe('case show "A|B" | grep x')
        assert result == ['case show "A|B"', "grep x"], f"Got {result}"
    
    def test_pipe_in_single_quotes(self):
        """Test pipe character inside single quotes is not split"""
        result = self.shell._split_by_pipe("cmd1 'text|with|pipes' | grep y")
        assert result == ["cmd1 'text|with|pipes'", "grep y"], f"Got {result}"
    
    def test_escaped_pipe(self):
        """Test escaped pipe character is not split"""
        result = self.shell._split_by_pipe(r"cmd1 text\|escaped | cmd2")
        assert result == [r"cmd1 text\|escaped", "cmd2"], f"Got {result}"
    
    def test_mixed_quotes_and_pipes(self):
        """Test complex case with mixed quotes"""
        result = self.shell._split_by_pipe('''cmd1 "quoted|text" 'more|text' | cmd2 "another|quoted"''')
        expected = ['cmd1 "quoted|text" \'more|text\'', 'cmd2 "another|quoted"']
        assert result == expected, f"Expected {expected}, got {result}"
    
    def test_empty_segments(self):
        """Test handling of empty segments"""
        result = self.shell._split_by_pipe("cmd1 || cmd2")
        # Empty segment between pipes
        assert len(result) == 3, f"Expected 3 segments, got {len(result)}: {result}"
        assert result[0] == "cmd1"
        assert result[1] == ""
        assert result[2] == "cmd2"
    
    def test_leading_trailing_pipes(self):
        """Test leading/trailing pipe handling"""
        result = self.shell._split_by_pipe("| cmd1 | cmd2 |")
        # Leading pipe creates empty first segment, trailing pipe is stripped away
        assert result[0] == "", f"Expected leading empty segment, got {result[0]}"
        assert len(result) == 3, f"Expected 3 segments, got {len(result)}: {result}"
        assert result[1] == "cmd1"
        assert result[2] == "cmd2"
    
    def test_whitespace_trimming(self):
        """Test that segments are properly trimmed"""
        result = self.shell._split_by_pipe("  cmd1  |  cmd2  |  cmd3  ")
        assert result == ["cmd1", "cmd2", "cmd3"], f"Got {result}"
    
    def test_no_pipes(self):
        """Test input with no pipes"""
        result = self.shell._split_by_pipe("just a simple command")
        assert result == ["just a simple command"], f"Got {result}"
    
    def test_complex_flexflow_command(self):
        """Test complex FlexFlow command with pipes"""
        result = self.shell._split_by_pipe("case show Case001 --verbose | grep -i status")
        assert result == ["case show Case001 --verbose", "grep -i status"], f"Got {result}"
    
    def test_data_piped_to_head(self):
        """Test data command piped to head"""
        result = self.shell._split_by_pipe("data show Case001 --format json | head -20")
        assert result == ["data show Case001 --format json", "head -20"], f"Got {result}"
    
    def test_quoted_command_with_args(self):
        """Test quoted arguments don't interfere with pipe detection"""
        result = self.shell._split_by_pipe('find . --name "pattern|file" | grep result')
        assert result == ['find . --name "pattern|file"', "grep result"], f"Got {result}"
    
    def test_nested_quotes(self):
        """Test nested quotes (single inside double)"""
        result = self.shell._split_by_pipe('cmd1 "text with \'single|quote\'" | cmd2')
        # Nested single quotes inside double quotes should be preserved
        assert len(result) == 2, f"Expected 2 segments, got {len(result)}: {result}"
        assert result[0] == 'cmd1 "text with \'single|quote\'"', f"Got {result[0]}"
        assert result[1] == "cmd2", f"Got {result[1]}"
    
    def test_real_world_examples(self):
        """Test real-world pipe scenarios"""
        
        # Example 1: Filter output
        result = self.shell._split_by_pipe("case show Case001 | grep status")
        assert result == ["case show Case001", "grep status"], f"Got {result}"
        
        # Example 2: Pipe to head for truncation
        result = self.shell._split_by_pipe("data show | head -50")
        assert result == ["data show", "head -50"], f"Got {result}"
        
        # Example 3: Chain multiple filters
        result = self.shell._split_by_pipe("find . | grep -v .git | sort")
        assert result == ["find .", "grep -v .git", "sort"], f"Got {result}"
        
        # Example 4: Output redirection style piping
        result = self.shell._split_by_pipe("ls -l | wc -l")
        assert result == ["ls -l", "wc -l"], f"Got {result}"
    
    def test_no_regression_semicolon_parsing(self):
        """Ensure pipe parsing doesn't break semicolon parsing"""
        # This is just to verify the semicolon parser still exists and works
        result = self.shell._split_by_semicolon("cmd1; cmd2; cmd3")
        # Semicolon parser returns segments without trimming, so there may be spaces
        assert len(result) == 3, f"Expected 3 segments, got {len(result)}: {result}"
        assert result[0].strip() == "cmd1"
        assert result[1].strip() == "cmd2"
        assert result[2].strip() == "cmd3"


def run_tests():
    """Run all tests and report results"""
    test_suite = TestPipeParsing()
    test_segment_suite = TestPipeSegment()
    
    all_test_suites = [
        ("Pipe Parsing", test_suite),
        ("Pipe Segments", test_segment_suite)
    ]
    
    total_passed = 0
    total_failed = 0
    
    print("=" * 70)
    print("PIPE PARSING AND SEGMENT UNIT TESTS")
    print("=" * 70)
    
    for suite_name, suite in all_test_suites:
        test_methods = [method for method in dir(suite) if method.startswith('test_')]
        
        passed = 0
        failed = 0
        
        print(f"\n{suite_name}:")
        print("-" * 70)
        
        for test_name in test_methods:
            suite.setup_method()
            try:
                getattr(suite, test_name)()
                print(f"  ✓ {test_name}")
                passed += 1
            except AssertionError as e:
                print(f"  ✗ {test_name}: {e}")
                failed += 1
            except Exception as e:
                print(f"  ✗ {test_name}: EXCEPTION: {e}")
                failed += 1
        
        print(f"  Results: {passed} passed, {failed} failed")
        total_passed += passed
        total_failed += failed
    
    print("=" * 70)
    print(f"Total Results: {total_passed} passed, {total_failed} failed out of {total_passed + total_failed} tests")
    print("=" * 70)
    
    return total_failed == 0


class TestPipeSegment:
    """Test suite for PipeSegment class"""
    
    def setup_method(self):
        """Initialize for each test"""
        pass
    
    def test_shell_command_detection(self):
        """Test detection of shell commands"""
        segment = PipeSegment("grep status")
        assert not segment.is_flexflow, "grep should be detected as shell command"
        assert segment.command_name == "grep", f"Expected 'grep', got '{segment.command_name}'"
        assert segment.args == ["status"], f"Expected ['status'], got {segment.args}"
    
    def test_flexflow_command_detection(self):
        """Test detection of FlexFlow commands (if registry is loaded)"""
        segment = PipeSegment("case show Case001")
        # Only check command name - registry might not be loaded in tests
        assert segment.command_name == "case", f"Expected 'case', got '{segment.command_name}'"
        assert "show" in segment.args, f"Expected 'show' in args, got {segment.args}"
        assert "Case001" in segment.args, f"Expected 'Case001' in args, got {segment.args}"
    
    def test_command_with_options(self):
        """Test command parsing with options"""
        segment = PipeSegment("grep -i status")
        assert segment.command_name == "grep"
        assert segment.args == ["-i", "status"]
    
    def test_quoted_arguments(self):
        """Test command with quoted arguments"""
        segment = PipeSegment('grep "multi word"')
        assert segment.command_name == "grep"
        assert segment.args == ["multi word"], f"Expected ['multi word'], got {segment.args}"
    
    def test_empty_segment(self):
        """Test handling of empty segment"""
        segment = PipeSegment("")
        assert segment.command_name is None, f"Expected None, got '{segment.command_name}'"
        assert segment.args == [], f"Expected [], got {segment.args}"
    
    def test_segment_repr(self):
        """Test string representation"""
        segment = PipeSegment("case show Case001")
        repr_str = repr(segment)
        assert "case show Case001" in repr_str, f"Got {repr_str}"
        # Either flexflow or shell is acceptable in test environment
        assert ("flexflow" in repr_str or "shell" in repr_str), f"Got {repr_str}"
    
    def test_multiple_options(self):
        """Test command with multiple options"""
        segment = PipeSegment("grep -n -i status")
        assert segment.command_name == "grep"
        assert segment.args == ["-n", "-i", "status"]
    
    def test_complex_flexflow_command(self):
        """Test complex FlexFlow command"""
        segment = PipeSegment("case show Case001 --verbose")
        # Command name and args are what matter
        assert segment.command_name == "case"
        assert "show" in segment.args
        assert "Case001" in segment.args
        assert "--verbose" in segment.args



if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
