from src.cli.interactive import InteractiveShell


class _MockConsole:
    def __init__(self):
        self.lines = []

    def print(self, message="", **kwargs):
        self.lines.append(str(message))


def _make_shell(tmp_path):
    shell = InteractiveShell.__new__(InteractiveShell)
    shell.console = _MockConsole()
    shell._current_dir = tmp_path
    return shell


def test_grep_after_context_with_separate_flag_value(tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_text("start\nERROR one\nnext1\nnext2\nend\n", encoding="utf-8")

    shell = _make_shell(tmp_path)
    shell.grep_files(["-A", "1", "^ERROR", "app.log"])

    output = "\n".join(shell.console.lines)
    assert "ERROR" in output and "one" in output
    assert "next1" in output
    assert "next2" not in output


def test_grep_after_context_with_inline_short_flag(tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_text("start\nERROR one\nnext1\nnext2\nend\n", encoding="utf-8")

    shell = _make_shell(tmp_path)
    shell.grep_files(["-A2", "^ERROR", "app.log"])

    output = "\n".join(shell.console.lines)
    assert "ERROR" in output and "one" in output
    assert "next1" in output
    assert "next2" in output


def test_grep_after_context_rejects_invalid_number(tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_text("ERROR one\n", encoding="utf-8")

    shell = _make_shell(tmp_path)
    shell.grep_files(["-A", "x", "ERROR", "app.log"])

    output = "\n".join(shell.console.lines)
    assert "Invalid after-context number" in output
