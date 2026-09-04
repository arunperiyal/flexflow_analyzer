"""Tests for src/web/services/logbuf.py: the command window's ring buffer."""

from src.web.services.logbuf import LogBuffer


def test_write_splits_lines_and_assigns_increasing_seq():
    lb = LogBuffer()
    lb.write("first\nsecond\n")
    lines = lb.since(0)
    assert [e['line'] for e in lines] == ['first', 'second']
    assert [e['seq'] for e in lines] == [1, 2]
    assert lb.seq == 2


def test_since_only_returns_newer_entries():
    lb = LogBuffer()
    lb.write("a\nb\nc\n")
    assert [e['line'] for e in lb.since(1)] == ['b', 'c']
    assert lb.since(3) == []


def test_blank_lines_are_dropped():
    lb = LogBuffer()
    lb.write("first\n\n   \nsecond\n")
    assert [e['line'] for e in lb.since(0)] == ['first', 'second']


def test_ansi_color_codes_are_stripped():
    lb = LogBuffer()
    lb.write("\x1b[36m[INFO]\x1b[0m Reading riser.def\n\x1b[33m[WARNING]\x1b[0m watch out\n")
    lines = [e['line'] for e in lb.since(0)]
    assert lines == ['[INFO] Reading riser.def', '[WARNING] watch out']
    assert '\x1b' not in ''.join(lines)


def test_capture_tees_stdout_and_stderr():
    lb = LogBuffer()
    with lb.capture():
        print("stdout line")
        import sys
        print("stderr line", file=sys.stderr)
    lines = [e['line'] for e in lb.since(0)]
    assert lines == ['stdout line', 'stderr line']


def test_ring_buffer_is_bounded():
    lb = LogBuffer(maxlen=3)
    for i in range(5):
        lb.write(f"line{i}\n")
    lines = [e['line'] for e in lb.since(0)]
    assert lines == ['line2', 'line3', 'line4']
