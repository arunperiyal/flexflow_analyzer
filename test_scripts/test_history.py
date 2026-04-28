"""Tests for interactive shell history handling."""

from pathlib import Path

from src.cli.interactive import InteractiveShell


class _MockConsole:
    def __init__(self):
        self.messages = []

    def print(self, *args, **kwargs):
        self.messages.append(" ".join(str(arg) for arg in args))


def _make_shell(history_file: Path) -> InteractiveShell:
    shell = InteractiveShell.__new__(InteractiveShell)
    shell.console = _MockConsole()
    shell.history_file = history_file
    shell.running = True
    return shell


def test_dedupe_history_keeps_latest_occurrence_order():
    shell = _make_shell(Path("/tmp/flexflow-history-test"))
    # Newest first input.
    entries = ["ls", "pwd", "ls", "case show Case001", "pwd"]
    deduped = shell._dedupe_history_entries(entries)
    assert deduped == ["ls", "pwd", "case show Case001"]


def test_compact_history_file_removes_duplicates(tmp_path):
    history_file = tmp_path / "history"
    shell = _make_shell(history_file)

    # Newest first.
    shell._write_history_entries(["history", "ls", "history", "pwd"])
    removed = shell._compact_history_file()

    assert removed == 1
    assert shell._read_history_entries() == ["history", "ls", "pwd"]


def test_history_unique_flag_routes_to_unique_view(tmp_path):
    history_file = tmp_path / "history"
    shell = _make_shell(history_file)

    calls = []

    def _show_history(unique=False):
        calls.append(unique)

    shell.show_history = _show_history
    handled = shell.handle_shell_command("history --unique")

    assert handled is True
    assert calls == [True]
